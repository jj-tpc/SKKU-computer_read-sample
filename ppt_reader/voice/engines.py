"""문장 하나를 소리 데이터로 만드는 경계와 운영체제 음성(Windows SAPI, macOS say).

클라우드 음성(cloud.py)도 같은 Engine을 따르므로 밖에서는 voices()와 synth()만 쓴다.
synth()는 음성 스레드에서만 부른다. SAPI COM 객체는 만든 스레드에서만 쓸 수 있다.
"""
from __future__ import annotations

import array
import locale
import math
import os
import re
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass, field

from .signal import word_spans

RATE = 22050  # 운영체제 음성과 ElevenLabs의 표본 빈도(Hz). 16bit mono
BYTES_PER_SEC = RATE * 2
X5 = 5.0
# x5에서 음성이 실제로 낸 배속을 잴 때 쓰는 짧은 문장
X5_PROBE = "오늘은 태양계의 여러 행성에 대해 함께 알아보겠습니다."


class EngineUnavailable(RuntimeError):
    pass


@dataclass
class Voice:
    id: str
    name: str
    lang: str  # 예: "ko_KR", "en_US"

    @property
    def is_korean(self) -> bool:
        return self.lang.lower().startswith("ko")


@dataclass
class Synth:
    pcm: bytes  # 16bit, mono
    words: list[tuple[int, int, float]] = field(default_factory=list)  # (글자 시작 위치, 글자 수, 시작 초)
    engine_speed: float = 1.0  # 엔진이 실제로 낸 배속(늘이기 전)
    rate: int = RATE  # 표본 빈도(Hz). Gemini는 24000

    @property
    def seconds(self) -> float:
        return len(self.pcm) / (self.rate * 2)


class Engine:
    def voices(self) -> list[Voice]:
        raise NotImplementedError

    def synth(self, text: str, voice_id: str | None, speed: float,
              prev_text: str = "", next_text: str = "") -> Synth:
        """prev_text, next_text는 앞뒤 문장이다. 쓰는 엔진(ElevenLabs)만 쓴다."""
        raise NotImplementedError

    def close(self) -> None:
        pass


def estimate_words(text: str, seconds: float) -> list[tuple[int, int, float]]:
    """낱말 시각을 주지 않는 엔진용. 소리 길이를 낱말 글자 수(공백 빼고)에 비례해 나눈다."""
    spans = word_spans(text)
    total = sum(n for _, n in spans)
    out, done = [], 0
    for start, n in spans:
        out.append((start, n, seconds * done / total if total else 0.0))
        done += n
    return out


def voiced_seconds(pcm: bytes, threshold: int = 300) -> float:
    """앞뒤 무음을 뺀 소리 길이. 엔진이 붙이는 무음은 배속을 따라 줄지 않아 배속을 잴 때 뺀다."""
    samples = array.array("h", pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    idx = [i for i in range(0, len(samples), 32) if abs(samples[i]) > threshold]
    if not idx:
        return 0.0
    return (idx[-1] - idx[0]) / RATE


# ---------------------------------------------------------------- Windows (SAPI)

_SAPI_CATEGORIES = (
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices",
    # '설정 > 음성'에서 추가한 음성은 여기에만 등록되는 경우가 있다. SAPI로도 쓸 수 있다.
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices",
)
_SVSF_ASYNC, _SVSF_IS_XML, _SVSF_NOT_XML, _SVSF_PERSIST_XML = 1, 8, 16, 32
_SAFT_22K_16BIT_MONO = 22
_SVE_WORD = 32


class _WordEvents:
    def __init__(self):
        self.words = []

    def OnWord(self, StreamNumber, StreamPosition, CharacterPosition, Length):
        self.words.append((int(CharacterPosition), int(Length), int(StreamPosition) / BYTES_PER_SEC))


def sapi_rate(speed: float) -> int:
    """SAPI Rate r은 3^(r/10)배다. x1.5는 4, x2는 6."""
    return max(-10, min(10, round(10 * math.log(speed) / math.log(3))))


class SapiEngine(Engine):
    def __init__(self, x5_factors: dict[str, float] | None = None):
        try:
            import pythoncom  # noqa: F401
            import win32com.client  # noqa: F401
        except ImportError as e:
            raise EngineUnavailable("pywin32가 설치되어 있지 않습니다. "
                                    "'pip install -r requirements.txt'를 실행하세요.") from e
        self.x5_factors = x5_factors if x5_factors is not None else {}
        self._sp = None

    def voices(self) -> list[Voice]:
        import win32com.client

        found: list[Voice] = []
        seen: set[str] = set()
        for cat_id in _SAPI_CATEGORIES:
            try:
                cat = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
                cat.SetId(cat_id, False)
                tokens = cat.EnumerateTokens()
            except Exception:
                continue
            for i in range(tokens.Count):
                tok = tokens.Item(i)
                name = tok.GetDescription()
                key = re.sub(r"\s+Desktop\b", "", name.split(" - ")[0]).strip()
                if key in seen:  # 같은 목소리가 두 곳에 등록된 경우 하나만
                    continue
                seen.add(key)
                found.append(Voice(tok.Id, name, _lcid_to_locale(tok.GetAttribute("Language"))))
        return found

    def _voice(self):
        if self._sp is None:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            self._sp = win32com.client.DispatchWithEvents("SAPI.SpVoice", _WordEvents)
            self._sp.EventInterests = _SVE_WORD
            self._default_voice = self._sp.Voice
        return self._sp

    def _render(self, text: str, voice_id: str | None, rate: int, absspeed: int):
        import pythoncom
        import win32com.client

        sp = self._voice()
        sp.Voice = self._default_voice
        if voice_id:
            try:
                tok = win32com.client.Dispatch("SAPI.SpObjectToken")
                tok.SetId(voice_id, "", False)
                sp.Voice = tok
            except Exception:
                pass  # 음성을 못 찾으면 기본 음성으로
        ms = win32com.client.Dispatch("SAPI.SpMemoryStream")
        ms.Format.Type = _SAFT_22K_16BIT_MONO
        sp.AudioOutputStream = ms
        sp.Rate = rate
        # 지속 XML은 다음 읽기에도 남는다. 그래서 x5가 아닐 때도 매번 0으로 되돌린다.
        sp.Speak(f'<rate absspeed="{absspeed}"/>', _SVSF_IS_XML | _SVSF_PERSIST_XML)
        sp.words = []
        sp.Speak(text, _SVSF_ASYNC | _SVSF_NOT_XML)
        while not sp.WaitUntilDone(10):
            pythoncom.PumpWaitingMessages()  # 단어 이벤트는 이 스레드의 메시지로 온다
        pythoncom.PumpWaitingMessages()
        return bytes(ms.GetData()), list(sp.words)

    def x5_factor(self, voice_id: str | None) -> float:
        """이 음성이 x5 설정에서 실제로 내는 배속. 처음 한 번만 재고 기억한다."""
        key = voice_id or ""
        if key not in self.x5_factors:
            slow, _ = self._render(X5_PROBE, voice_id, 0, 0)
            fast, _ = self._render(X5_PROBE, voice_id, 10, 5)
            a, b = voiced_seconds(slow), voiced_seconds(fast)
            self.x5_factors[key] = round(a / b, 3) if a > 0 and b > 0 else 1.0
        return self.x5_factors[key]

    def synth(self, text: str, voice_id: str | None, speed: float,
              prev_text: str = "", next_text: str = "") -> Synth:
        if speed >= X5:
            factor = self.x5_factor(voice_id)
            pcm, words = self._render(text, voice_id, 10, 5)
            return Synth(pcm, words, factor)
        pcm, words = self._render(text, voice_id, sapi_rate(speed), 0)
        return Synth(pcm, words, speed)

    def close(self) -> None:
        if self._sp is not None:
            import pythoncom

            self._sp = None
            pythoncom.CoUninitialize()


def _lcid_to_locale(attr: str) -> str:
    try:
        lcid = int(attr.split(";")[0], 16)
    except (ValueError, AttributeError):
        return ""
    return locale.windows_locale.get(lcid, "")


# ---------------------------------------------------------------- macOS (say)

class SayEngine(Engine):
    BASE_WPM = 190  # x1일 때 분당 단어 수
    MAX_WPM = 500  # say가 받는 최고 속도. x5도 여기서 멈추고(약 2.63배) 나머지는 재생할 때 늘인다

    def voices(self) -> list[Voice]:
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True,
                                 encoding="utf-8", timeout=15).stdout
        except (OSError, subprocess.SubprocessError):
            return []
        found = []
        for line in out.splitlines():
            # 예: "Yuna                ko_KR    # 안녕하세요. 제 이름은 유나입니다."
            m = re.match(r"^(.+?)\s+([a-z]{2,3}[_-][A-Za-z0-9]+)\s+#", line)
            if m:
                name = m.group(1).strip()
                found.append(Voice(name, name, m.group(2)))
        return found

    def synth(self, text: str, voice_id: str | None, speed: float,
              prev_text: str = "", next_text: str = "") -> Synth:
        wpm = min(self.MAX_WPM, round(self.BASE_WPM * speed))
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            cmd = ["say", "-o", path, "--file-format=WAVE", f"--data-format=LEI16@{RATE}", "-r", str(wpm)]
            if voice_id:
                cmd += ["-v", voice_id]
            cmd.append(" " + text if text.startswith("-") else text)  # '-'로 시작하면 옵션으로 오해한다
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            with wave.open(path, "rb") as w:
                if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, RATE):
                    raise EngineUnavailable("say가 예상과 다른 형식으로 저장했습니다.")
                pcm = w.readframes(w.getnframes())
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        engine_speed = wpm / self.BASE_WPM if speed >= X5 else speed
        return Synth(pcm, estimate_words(text, len(pcm) / BYTES_PER_SEC), engine_speed)


def make_engine(x5_factors: dict[str, float] | None = None) -> Engine:
    if sys.platform == "win32":
        return SapiEngine(x5_factors)
    if sys.platform == "darwin":
        return SayEngine()
    raise EngineUnavailable("이 프로그램은 Windows와 macOS에서 동작합니다.")
