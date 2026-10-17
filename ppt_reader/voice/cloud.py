"""클라우드 음성 엔진: ElevenLabs(HTTP), Gemini(google-genai).

늘 x1로 합성하고 engine_speed = 1.0을 돌려준다. x1.5·x2·x5는 재생할 때 늘인다. 그래야 저장한 소리 하나로
네 배속을 모두 내고, 배속을 바꿔도 다시 합성(요금)하지 않는다.
한 요청은 TIMEOUT 안에 끝나야 한다. 오류는 다섯 종류(VoiceError.kind)로 바꾸고, 문구에서 키를 지운다.
"""
from __future__ import annotations

import base64
import io
import json
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
import wave
from typing import Callable

from .engines import Engine, Synth, Voice, estimate_words
from .signal import word_spans

TIMEOUT = 8.0
PROVIDER_NAMES = {"elevenlabs": "ElevenLabs", "gemini": "Gemini"}
GEMINI_VOICES = (
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede", "Callirrhoe", "Autonoe",
    "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia",
    "Achernar", "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi", "Vindemiatrix",
    "Sadachbia", "Sadaltager", "Sulafat",
)
def _tls_context() -> ssl.SSLContext:
    """빌드한 macOS 앱의 파이썬은 시스템 인증서를 쓰지 않아 HTTPS 확인이 실패할 수 있다. certifi 묶음을 쓴다."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError, OSError):
        return ssl.create_default_context()


_KEYISH = re.compile(r"(sk[-_][A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{20,}|[A-Fa-f0-9]{32,})")


class VoiceError(Exception):
    """kind: "key" | "quota" | "network" | "timeout" | "other". detail은 제공자 오류의 첫 줄(키를 지움)."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


def scrub(text: str, *secrets: str) -> str:
    """오류 문구의 첫 줄만 남기고, 넘겨준 키와 키 모양 문자열을 지운다.

    제공자가 키 앞뒤 몇 글자를 보여 주는 경우("Incorrect API key provided: sk-pr****1234")도 있어서
    키의 앞 6글자로 시작하는 낱말과 "API key provided:" 뒤의 낱말도 지운다.
    """
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    for secret in secrets:
        if secret:
            line = line.replace(secret, "***")
            if len(secret) >= 8:
                line = re.sub(re.escape(secret[:6]) + r"\S*", "***", line)
    line = re.sub(r"(?i)(api key provided:?\s*)\S+", r"\1***", line)
    return _KEYISH.sub("***", line)[:200]


def words_from_alignment(text: str, alignment) -> list[tuple[int, int, float]] | None:
    """ElevenLabs 글자 시각을 낱말 시각으로 바꾼다. 글자를 이어 붙인 것이 보낸 글과 다르면 None."""
    if not isinstance(alignment, dict):
        return None
    chars = alignment.get("characters")
    starts = alignment.get("character_start_times_seconds")
    if not isinstance(chars, list) or not isinstance(starts, list) or len(chars) != len(starts):
        return None
    if "".join(str(c) for c in chars) != text:
        return None
    at: list[float] = []  # 글 안의 글자 위치마다 시작 초
    for piece, t in zip(chars, starts):
        at.extend([float(t)] * len(str(piece)))
    return [(start, n, at[start]) for start, n in word_spans(text)]


# ---------------------------------------------------------------- ElevenLabs

def _elevenlabs_error(status: int, body: bytes, key: str) -> VoiceError:
    code, message = "", ""
    try:
        detail = json.loads(body.decode("utf-8", "replace")).get("detail")
        if isinstance(detail, dict):
            code = str(detail.get("code") or detail.get("status") or "")
            message = str(detail.get("message") or "")
        elif isinstance(detail, str):
            message = detail
    except (ValueError, AttributeError):
        message = body.decode("utf-8", "replace")
    text = scrub(f"{status} {code} {message}".strip(), key)
    if code in ("quota_exceeded", "insufficient_credits") or status == 402:
        return VoiceError("quota", text)
    if status in (401, 403):
        return VoiceError("key", text)
    if status == 429:  # 동시 요청·빈도 제한, 서버 바쁨: 잠깐 막힌 것이라 다음에 다시 시도한다
        return VoiceError("network", text)
    return VoiceError("other", text)


class ElevenLabsEngine(Engine):
    BASE = "https://api.elevenlabs.io"

    def __init__(self, key: str, model: str, voice_id: str = "",
                 opener: Callable | None = None):
        self.key = key
        self.model = model
        self.voice_id = voice_id
        self.chosen_voice: Voice | None = None
        self._open = opener or urllib.request.urlopen  # 시험에서는 가짜로 바꾼다
        self._tls = _tls_context()

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(
            self.BASE + path, method=method,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={"xi-api-key": self.key, "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with self._open(req, timeout=TIMEOUT, context=self._tls) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise _elevenlabs_error(e.code, e.read() or b"", self.key) from None
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)):
                raise VoiceError("timeout", "응답이 늦음") from None
            raise VoiceError("network", scrub(str(e.reason), self.key)) from None
        except (socket.timeout, TimeoutError):
            raise VoiceError("timeout", "응답이 늦음") from None
        except (ConnectionError, OSError) as e:
            raise VoiceError("network", scrub(str(e), self.key)) from None
        except ValueError as e:
            raise VoiceError("other", scrub(f"응답을 읽을 수 없음: {e}", self.key)) from None

    def voices(self) -> list[Voice]:
        found: list[Voice] = []
        token = ""
        for _ in range(20):  # 100개씩 최대 2,000개
            query = {"page_size": 100}
            if token:
                query["next_page_token"] = token
            data = self._request("GET", "/v2/voices?" + urllib.parse.urlencode(query))
            for v in data.get("voices") or []:
                if isinstance(v, dict) and v.get("voice_id"):
                    found.append(Voice(str(v["voice_id"]), str(v.get("name") or v["voice_id"]), ""))
            token = data.get("next_page_token") or ""
            if not data.get("has_more") or not token:
                break
        return found

    def check_key(self) -> None:
        """돈이 들지 않는 목록 조회. 목소리 읽기 권한까지 확인된다."""
        self._request("GET", "/v2/voices?page_size=1")

    def ensure_voice(self) -> None:
        """고른 목소리가 없으면 목록의 첫 목소리를 쓰고 chosen_voice에 남긴다. 화면 쪽이 설정에 저장한다."""
        if not self.voice_id:
            listed = self.voices()
            if not listed:
                raise VoiceError("other", "ElevenLabs 계정에 쓸 수 있는 목소리가 없음")
            self.voice_id, self.chosen_voice = listed[0].id, listed[0]

    def synth(self, text: str, voice_id: str | None, speed: float,
              prev_text: str = "", next_text: str = "") -> Synth:
        # voice_id 인자는 운영체제 음성의 것이라 쓰지 않는다
        self.ensure_voice()
        vid = self.voice_id
        body = {"text": text, "model_id": self.model}
        if prev_text:
            body["previous_text"] = prev_text
        if next_text:
            body["next_text"] = next_text
        path = f"/v1/text-to-speech/{urllib.parse.quote(vid, safe='')}/with-timestamps?output_format=pcm_22050"
        data = self._request("POST", path, body)
        try:
            pcm = base64.b64decode(data["audio_base64"])
        except (KeyError, TypeError, ValueError):
            raise VoiceError("other", "소리가 없는 응답") from None
        seconds = len(pcm) / (22050 * 2)
        words = words_from_alignment(text, data.get("alignment")) or estimate_words(text, seconds)
        return Synth(pcm, words, 1.0, 22050)


# ---------------------------------------------------------------- Gemini

def read_wav(data: bytes, default_rate: int = 24000) -> tuple[bytes, int]:
    """RIFF WAV면 머리를 읽어 PCM과 표본 빈도를 꺼낸다. 머리가 없으면 24kHz 날 PCM으로 본다."""
    if data[:4] == b"RIFF":
        with wave.open(io.BytesIO(data), "rb") as w:
            if w.getnchannels() != 1 or w.getsampwidth() != 2:
                raise VoiceError("other", "예상과 다른 소리 형식")
            return w.readframes(w.getnframes()), w.getframerate()
    return data, default_rate


def _gemini_error(e: Exception, key: str) -> VoiceError:
    name = type(e).__name__.lower()
    status = getattr(e, "status_code", None) or getattr(e, "code", None)
    text = scrub(f"{status or ''} {getattr(e, 'message', None) or e}".strip(), key)
    if "timeout" in name:
        return VoiceError("timeout", text)
    if isinstance(status, int):
        lowered = text.lower()
        if status in (401, 403) or (status == 400 and "api key" in lowered):
            return VoiceError("key", text)
        if status == 429:
            # 분당 한도는 잠깐 막힌 것이고, 그 밖(하루 한도, 요금)은 키를 다시 확인할 때까지 쓰지 않는다
            return VoiceError("network" if "per minute" in lowered or "perminute" in lowered else "quota", text)
        return VoiceError("other", text)
    if "noresponse" in name or "connect" in name or "network" in name or isinstance(e, (ConnectionError, OSError)):
        return VoiceError("network", text)
    return VoiceError("other", text)


class GeminiVoiceEngine(Engine):
    def __init__(self, key: str, model: str, voice: str = "Kore", client=None):
        self.key = key
        self.model = model
        self.voice = voice
        self._client = client  # 시험에서는 가짜 클라이언트

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.key)
        return self._client

    def voices(self) -> list[Voice]:
        return [Voice(v, v, "") for v in GEMINI_VOICES]

    def synth(self, text: str, voice_id: str | None, speed: float,
              prev_text: str = "", next_text: str = "") -> Synth:
        # Gemini 3.8 TTS는 입력 글을 그대로 읽는 대본으로 다룬다. 지시문을 넣으면 그것까지 읽으므로 글만 보낸다.
        try:
            interaction = self._get_client().interactions.create(
                model=self.model,
                input=[{"type": "user_input", "content": [{"type": "text", "text": text}]}],
                response_format={"type": "audio"},
                generation_config={"speech_config": [{"voice": self.voice}]},
                timeout=TIMEOUT,
            )
        except VoiceError:
            raise
        except Exception as e:
            raise _gemini_error(e, self.key) from None
        audio = getattr(interaction, "output_audio", None)
        data = getattr(audio, "data", None) if audio is not None else None
        if data is None and isinstance(audio, dict):
            data = audio.get("data")
        if not data:
            raise VoiceError("other", "소리가 없는 응답")
        raw = base64.b64decode(data) if isinstance(data, str) else bytes(data)
        pcm, rate = read_wav(raw)
        return Synth(pcm, estimate_words(text, len(pcm) / (rate * 2)), 1.0, rate)


# ---------------------------------------------------------------- 설정에서 엔진 고르기

def cloud_engine(settings_data: dict) -> tuple[str, Engine] | None:
    """설정의 목소리 엔진이 클라우드이고 그 키 확인이 맞았으면 (제공자, 엔진). 아니면 None(운영체제 음성)."""
    name = settings_data.get("voice_engine")
    keys, ok = settings_data.get("keys", {}), settings_data.get("key_ok", {})
    conf = settings_data.get("cloud_voice", {}).get(name, {})
    if name not in PROVIDER_NAMES or not ok.get(name) or not keys.get(name):
        return None
    if name == "elevenlabs":
        return name, ElevenLabsEngine(keys[name], conf.get("model", ""), conf.get("voice_id", ""))
    return name, GeminiVoiceEngine(keys[name], conf.get("model", ""), conf.get("voice") or "Kore")
