"""음성 흐름 시험. 가짜 PCM, 가짜 HTTP, 가짜 재생기로 소리와 인터넷 없이 돈다."""
from __future__ import annotations

import base64
import io
import json
import math
import os
import struct
import threading
import time
import urllib.error
import wave

import pytest

from ppt_reader.voice import cloud, signal
from ppt_reader.voice.cache import Presynth, VoiceCache, cache_key, sentence_plan
from ppt_reader.voice.cloud import ElevenLabsEngine, GeminiVoiceEngine, VoiceError, cloud_engine
from ppt_reader.voice.engines import Synth, Voice, estimate_words, sapi_rate, voiced_seconds
from ppt_reader.voice.pipeline import InlineThread, Pipeline

player_mod = pytest.importorskip("ppt_reader.voice.player")


def tone_pcm(seconds: float, freq: float = 220, amp: int = 8000, rate: int = 22050) -> bytes:
    n = int(seconds * rate)
    return struct.pack(f"<{n}h", *(int(amp * math.sin(2 * math.pi * freq * i / rate)) for i in range(n)))


# ---------------------------------------------------------------- 신호

def test_curves_level_and_tone():
    pcm = b"\0\0" * 2205 + tone_pcm(0.1, 200) + tone_pcm(0.1, 2000, amp=4000)
    levels, tones = signal.curves(pcm, 22050)
    assert len(levels) == 15 and max(levels) == 1.0
    assert levels[0] == 0.0 and levels[7] == 1.0 and 0.4 < levels[12] < 0.6  # 무음, 큰 소리, 작은 소리
    assert tones[12] > tones[7] * 3  # 높은 소리일수록 영교차가 많다
    assert signal.value_at(levels, 0.15) == levels[7] and signal.value_at(levels, 9.0) == 0.0


@pytest.mark.parametrize("level, syllable, shape", [
    (0.1, "이", signal.CLOSED), (0.3, "이", signal.WIDE), (0.3, "가", signal.SMALL), (0.8, "가", signal.OPEN),
    (0.8, "에", signal.WIDE), (0.8, "애", signal.WIDE), (0.8, "얘", signal.WIDE), (0.8, "예", signal.WIDE),
    (0.8, "의", signal.WIDE), (0.8, "으", signal.OPEN), (0.8, "A", signal.OPEN), (0.3, None, signal.SMALL),
])
def test_mouth_shape(level, syllable, shape):
    assert signal.mouth_shape(level, syllable) == shape


def test_mouth_holds_60ms():
    hold = signal.MouthHold()
    assert hold.update(signal.OPEN, 0.0) == signal.OPEN
    assert hold.update(signal.CLOSED, 0.03) == signal.OPEN  # 60ms 전에는 바꾸지 않는다
    assert hold.update(signal.CLOSED, 0.061) == signal.CLOSED
    assert hold.update(signal.WIDE, 0.07) == signal.CLOSED


def test_syllable_times_and_words():
    text = "안녕 hello 세상"
    words = [(0, 2, 0.0), (3, 5, 1.0), (9, 2, 2.0)]
    events = signal.syllable_events(text, words, 3.0)
    assert events == [(0.0, "안"), (0.5, "녕"), (1.0, None), (2.0, "세"), (2.5, "상")]
    assert signal.syllable_at(events, 0.6) == "녕" and signal.syllable_at(events, 1.2) is None
    assert signal.words_started(words, 1.0) == 2 and signal.words_started(words, -1) == 0


def test_engine_helpers():
    assert estimate_words("가나 다라마", 1.0) == [(0, 2, 0.0), (3, 3, 0.4)]  # 글자 수에 비례(macOS say, Gemini)
    assert [sapi_rate(s) for s in (1.0, 1.5, 2.0)] == [0, 4, 6]
    assert abs(voiced_seconds(b"\0\0" * 22050 + tone_pcm(1.0) + b"\0\0" * 22050) - 1.0) < 0.01
    assert Synth(b"\0" * 48000, rate=24000).seconds == 1.0


# ---------------------------------------------------------------- 재생 도우미

def test_stretch_ratio():
    assert player_mod.stretch_ratio(1.5, 1.5) == 1.0
    assert player_mod.stretch_ratio(1.5, 1.55) == 1.0  # SAPI가 조금 더 빠르면 늘이지 않는다
    assert player_mod.stretch_ratio(5.0, 5.198) == 1.0  # Heami x5
    assert player_mod.stretch_ratio(5.0, 3.47) == pytest.approx(1.441, abs=0.001)  # Zira x5는 나머지만
    assert player_mod.stretch_ratio(2.0, 1.0) == 2.0  # 클라우드 음성은 늘 x1로 만들고 늘인다


def test_lead_silence_rule():
    """옛 test_tts.py의 앞 무음 규칙: 처음, 2초 넘게 조용했을 때, 장치가 바뀌었을 때만."""
    assert player_mod.need_lead(None, 10.0, "spk", None)
    assert not player_mod.need_lead(9.5, 10.0, "spk", "spk")  # 자동 발표처럼 이어 읽으면 넣지 않는다
    assert player_mod.need_lead(9.5, 10.0, "ear", "spk")
    assert player_mod.need_lead(7.0, 10.0, "spk", "spk")
    assert player_mod.lead_samples(22050, 1.0) == 22050
    assert player_mod.lead_samples(22050, 2.0) == 44100  # 늘인 뒤에도 정확히 1초


def test_wav_and_device_match():
    data = player_mod.wav_bytes(tone_pcm(0.5), 22050)
    with wave.open(io.BytesIO(data)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 22050, 11025)
    sapi = r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\AudioOutput\TokenEnums\MMAudioOut\{0.0.0.00000000}.{ABC}"
    assert player_mod.matches(sapi, "{0.0.0.00000000}.{abc}", "헤드폰")  # 옛 설정의 SAPI 토큰 id
    assert player_mod.matches("MacBook Pro Speakers", "BuiltInSpeakerDevice", "MacBook Pro Speakers")
    assert not player_mod.matches("", "{x}", "스피커")


# ---------------------------------------------------------------- 클라우드: ElevenLabs

class FakeResp:
    def __init__(self, data):
        self.data = data

    def read(self):
        return json.dumps(self.data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeOpener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, req, timeout, context=None):
        self.requests.append((req, timeout))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return FakeResp(r)


def http_error(code: int, detail) -> urllib.error.HTTPError:
    body = json.dumps({"detail": detail}).encode()
    return urllib.error.HTTPError("https://api.elevenlabs.io/x", code, "err", {}, io.BytesIO(body))


def alignment(text: str, step: float = 0.1) -> dict:
    return {"characters": list(text), "character_start_times_seconds": [i * step for i in range(len(text))],
            "character_end_times_seconds": [(i + 1) * step for i in range(len(text))]}


def test_elevenlabs_synth_with_timestamps():
    text = "안녕 세상"
    pcm = tone_pcm(0.5)
    opener = FakeOpener({"audio_base64": base64.b64encode(pcm).decode(), "alignment": alignment(text)})
    eng = ElevenLabsEngine("el-secret-key", "eleven_multilingual_v2", "voice123", opener=opener)
    synth = eng.synth(text, "SAPI-voice", 2.0, "앞 문장.", "뒤 문장.")
    req, timeout = opener.requests[0]
    assert req.full_url == ("https://api.elevenlabs.io/v1/text-to-speech/voice123/with-timestamps"
                            "?output_format=pcm_22050")
    assert req.get_header("Xi-api-key") == "el-secret-key" and timeout == cloud.TIMEOUT
    body = json.loads(req.data)
    assert body == {"text": text, "model_id": "eleven_multilingual_v2", "previous_text": "앞 문장.",
                    "next_text": "뒤 문장."}  # 배속은 보내지 않는다(늘 x1)
    assert synth.pcm == pcm and synth.rate == 22050 and synth.engine_speed == 1.0
    assert synth.words == [(0, 2, 0.0), (3, 2, pytest.approx(0.3))]


def test_elevenlabs_alignment_mismatch_falls_back_to_estimate():
    pcm = tone_pcm(1.0)
    opener = FakeOpener({"audio_base64": base64.b64encode(pcm).decode(), "alignment": alignment("다른 글")})
    synth = ElevenLabsEngine("k", "m", "v", opener=opener).synth("가나 다라마", None, 1.0)
    assert synth.words == estimate_words("가나 다라마", 1.0)


@pytest.mark.parametrize("error, kind", [
    (http_error(401, {"type": "authentication_error", "code": "invalid_api_key", "message": "bad key k-123"}), "key"),
    (http_error(403, {"code": "insufficient_permissions", "message": "no"}), "key"),
    (http_error(402, {"code": "insufficient_credits", "message": "no credits"}), "quota"),
    (http_error(401, {"status": "quota_exceeded", "message": "옛 모양"}), "quota"),
    (http_error(429, {"code": "rate_limit_exceeded", "message": "slow down"}), "network"),
    (http_error(500, {"code": "internal", "message": "boom"}), "other"),
    (urllib.error.URLError(TimeoutError("timed out")), "timeout"),
    (urllib.error.URLError(OSError("connection refused")), "network"),
    (TimeoutError(), "timeout"),
])
def test_elevenlabs_errors(error, kind):
    eng = ElevenLabsEngine("k-123", "m", "v", opener=FakeOpener(error))
    with pytest.raises(VoiceError) as info:
        eng.synth("안녕", None, 1.0)
    assert info.value.kind == kind and "k-123" not in str(info.value)


def test_elevenlabs_voices_and_first_voice():
    opener = FakeOpener(
        {"voices": [{"voice_id": "a1", "name": "Anna"}], "has_more": True, "next_page_token": "p2"},
        {"voices": [{"voice_id": "b2", "name": "Bora"}], "has_more": False},
        {"voices": [{"voice_id": "a1", "name": "Anna"}], "has_more": False},
        {"audio_base64": base64.b64encode(tone_pcm(0.2)).decode()},
    )
    eng = ElevenLabsEngine("k", "m", "", opener=opener)
    assert [v.name for v in eng.voices()] == ["Anna", "Bora"]
    assert "next_page_token=p2" in opener.requests[1][0].full_url
    eng.synth("안녕", None, 1.0)  # 목소리를 고르지 않았으면 첫 목소리
    assert eng.voice_id == "a1" and eng.chosen_voice.name == "Anna"
    assert "/text-to-speech/a1/" in opener.requests[3][0].full_url


# ---------------------------------------------------------------- 클라우드: Gemini

class FakeGeminiClient:
    def __init__(self, result):
        self.result = result
        self.calls = []
        self.interactions = self

    def create(self, **kw):
        self.calls.append(kw)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Audio:
    def __init__(self, data):
        self.output_audio = type("A", (), {"data": data})()


def test_gemini_synth_reads_wav():
    pcm = tone_pcm(0.5, rate=24000)
    data = base64.b64encode(player_mod.wav_bytes(pcm, 24000)).decode()
    client = FakeGeminiClient(Audio(data))
    synth = GeminiVoiceEngine("gm", "gemini-3.8-flash-tts", "Kore", client=client).synth("안녕 세상", None, 5.0)
    call = client.calls[0]
    assert call["model"] == "gemini-3.8-flash-tts" and call["generation_config"] == {"speech_config": [{"voice": "Kore"}]}
    assert call["input"] == [{"type": "user_input", "content": [{"type": "text", "text": "안녕 세상"}]}]  # 지시문 없이 글만
    assert synth.pcm == pcm and synth.rate == 24000 and synth.engine_speed == 1.0
    assert synth.words == estimate_words("안녕 세상", 0.5)


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status_code, self.message = status, message


class ReadTimeout(Exception):
    pass


@pytest.mark.parametrize("error, kind", [
    (ApiError(400, "API key not valid. Please pass a valid API key. AIzaSyFAKEFAKEFAKEFAKEFAKEFAKE"), "key"),
    (ApiError(403, "permission denied"), "key"),
    (ApiError(429, "Quota exceeded for metric: requests per minute"), "network"),
    (ApiError(429, "You exceeded your current quota"), "quota"),
    (ApiError(500, "internal"), "other"),
    (ReadTimeout("read timed out"), "timeout"),
    (ConnectionError("down"), "network"),
])
def test_gemini_errors(error, kind):
    eng = GeminiVoiceEngine("AIzaSyFAKEFAKEFAKEFAKEFAKEFAKE", "m", "Kore", client=FakeGeminiClient(error))
    with pytest.raises(VoiceError) as info:
        eng.synth("안녕", None, 1.0)
    assert info.value.kind == kind and "AIza" not in str(info.value)


def test_cloud_engine_from_settings():
    data = {"voice_engine": "os", "keys": {"elevenlabs": "k", "gemini": "g"},
            "key_ok": {"elevenlabs": True, "gemini": False},
            "cloud_voice": {"elevenlabs": {"model": "eleven_flash_v2_5", "voice_id": "v1"},
                            "gemini": {"model": "gemini-3.8-flash-tts", "voice": "Puck"}}}
    assert cloud_engine(data) is None
    provider, eng = cloud_engine({**data, "voice_engine": "elevenlabs"})
    assert provider == "elevenlabs" and eng.model == "eleven_flash_v2_5" and eng.voice_id == "v1"
    assert cloud_engine({**data, "voice_engine": "gemini"}) is None  # 키 확인이 맞지 않았으면 운영체제 음성
    provider, eng = cloud_engine({**data, "voice_engine": "gemini", "key_ok": {"gemini": True}})
    assert provider == "gemini" and eng.voice == "Puck"


# ---------------------------------------------------------------- 저장

class FakeCloud:
    """클라우드 엔진 흉내. fail에 오류 종류를 넣으면 그 횟수만큼 실패한다."""

    def __init__(self, model="m", voice_id="v", fail=()):
        self.model, self.voice_id = model, voice_id
        self.fail = list(fail)
        self.calls = []

    def synth(self, text, voice_id, speed, prev_text="", next_text=""):
        self.calls.append((text, prev_text, next_text, speed))
        if self.fail:
            raise VoiceError(self.fail.pop(0), "가짜 오류")
        return Synth(tone_pcm(0.2), estimate_words(text, 0.2), 1.0)


class FakeOS:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
        self.closed = False

    def voices(self):
        return [Voice("ko", "Korean", "ko_KR")]

    def synth(self, text, voice_id, speed, prev_text="", next_text=""):
        self.calls.append((text, voice_id, speed))
        if self.fail:
            raise RuntimeError("SAPI 실패")
        return Synth(tone_pcm(0.3), estimate_words(text, 0.3), speed)

    def close(self):
        self.closed = True


def test_cache_key_and_roundtrip(tmp_path):
    cache = VoiceCache(tmp_path)
    eng = FakeCloud()
    k1 = cache_key("elevenlabs", eng, "", "문장.", "다음.")
    assert k1 != cache_key("elevenlabs", eng, "", "문장.", "")  # 앞뒤 문장도 키에 들어간다
    assert k1 != cache_key("elevenlabs", FakeCloud(voice_id="w"), "", "문장.", "다음.")
    assert cache.get(k1) is None
    synth = Synth(tone_pcm(0.2), [(0, 3, 0.0)], 1.0, 24000)
    cache.put(k1, synth)
    got = cache.get(k1)
    assert got.pcm == synth.pcm and got.words == [(0, 3, 0.0)] and got.rate == 24000


def test_cache_prunes_oldest(tmp_path):
    cache = VoiceCache(tmp_path)
    for i in range(4):
        cache.put(f"k{i}", Synth(b"\0" * 8800))
        t = time.time() - 100 + i * 10
        for ext in (".json", ".pcm"):
            os.utime(cache.dir / f"k{i}{ext}", (t, t))
    cache.get("k0")  # 꺼내면 최근에 쓴 것이 된다
    cache.limit = 3 * 9000
    cache.prune()
    assert cache.has("k0") and not cache.has("k1") and cache.has("k2") and cache.has("k3")


def test_sentence_plan():
    assert sentence_plan("첫째. 둘째! 셋째") == [("", "첫째.", "둘째!"), ("첫째.", "둘째!", "셋째"), ("둘째!", "셋째", "")]


def run_presynth(tmp_path, eng, slides, first=0, retry=0.05):
    cache = VoiceCache(tmp_path)
    progress, failures, done = [], [], threading.Event()

    def on_progress(d, total):
        progress.append((d, total))
        if d == total:
            done.set()

    def on_failed(kind, detail):
        failures.append(kind)
        if kind in ("key", "quota"):
            done.set()

    ps = Presynth(cache, on_progress, on_failed, retry_after=retry)
    ps.start("elevenlabs", eng, slides, first)
    assert done.wait(5)
    ps.close()
    return cache, progress, failures


def test_presynth_order_and_skip_cached(tmp_path):
    slides = [sentence_plan("가. 나."), sentence_plan("다."), sentence_plan("라.")]
    eng = FakeCloud()
    cache = VoiceCache(tmp_path)
    cache.put(cache_key("elevenlabs", eng, "", "다.", ""), Synth(b"\0\0"))  # 이미 있음
    _, progress, failures = run_presynth(tmp_path, eng, slides, first=1)
    assert [c[0] for c in eng.calls] == ["라.", "가.", "나."]  # 지금 장부터 끝까지, 그다음 앞 장
    assert all(c[3] == 1.0 for c in eng.calls) and eng.calls[1][2] == "나."  # x1, 뒤 문장 넘김
    assert progress[0] == (1, 4) and progress[-1] == (4, 4) and failures == []


def test_presynth_key_error_stops_and_network_retries(tmp_path):
    eng = FakeCloud(fail=["key"])
    _, progress, failures = run_presynth(tmp_path / "a", eng, [sentence_plan("가. 나.")])
    assert failures == ["key"] and len(eng.calls) == 1  # 키를 다시 확인할 때까지 하지 않는다
    eng = FakeCloud(fail=["network"])
    _, progress, failures = run_presynth(tmp_path / "b", eng, [sentence_plan("가. 나.")])
    assert failures == ["network"] and progress[-1] == (2, 2)  # 쉬었다가 다시 해서 끝냈다


# ---------------------------------------------------------------- 문장 줄

class FakePlayer:
    def __init__(self):
        self.busy = False
        self.played = []
        self.pos = 0.0
        self.on_finished = self.on_failed = None

    def play(self, synth, speed, output_id):
        self.busy = True
        self.played.append((synth, speed, output_id))

    def position(self):
        return self.pos

    def stop(self):
        self.busy = False

    def finish(self):
        self.busy = False
        self.on_finished()


class DeferredThread:
    """합성 결과를 바로 주지 않고 run()을 부를 때 준다. 멈춘 뒤 늦게 온 결과를 흉내 낸다."""

    def __init__(self):
        self.jobs = []

    def submit(self, fn, on_result):
        self.jobs.append((fn, on_result))

    def run(self):
        jobs, self.jobs = self.jobs, []
        for fn, cb in jobs:
            cb(fn())

    def close(self, last=None, timeout=0):
        pass


def make_pipeline(tmp_path, cloud_plan=None, os_engine=None, thread=None):
    os_engine = os_engine or FakeOS()
    player = FakePlayer()
    p = Pipeline(os_engine, player, thread or InlineThread(), lambda: cloud_plan, VoiceCache(tmp_path))
    p.events = []
    p.on_done = lambda tag, ok: p.events.append(("done", tag, ok))
    p.on_error = lambda tag, msg: p.events.append(("error", tag, msg))
    p.on_cloud_failed = lambda provider, kind: p.events.append(("cloud", provider, kind))
    p.on_voice_chosen = lambda provider, voice: p.events.append(("chosen", provider, voice))
    return p, player, os_engine


def test_pipeline_plays_in_order_one_ahead(tmp_path):
    p, player, os_engine = make_pipeline(tmp_path)
    p.speak("첫 문장. 둘째 문장. 셋째 문장.", "ko", 1.5, tag=7, output_id="dev")
    assert [c[0] for c in os_engine.calls] == ["첫 문장.", "둘째 문장."]  # 재생 중인 문장의 다음 것까지만
    assert len(player.played) == 1 and player.played[0][1:] == (1.5, "dev")
    player.finish()
    assert len(player.played) == 2 and len(os_engine.calls) == 3
    player.finish()
    player.finish()
    assert p.events == [("done", 7, True)] and p.job is None


def test_pipeline_stop_drops_late_results(tmp_path):
    thread = DeferredThread()
    p, player, _ = make_pipeline(tmp_path, thread=thread)
    p.speak("하나. 둘.", "ko", 1.0, tag=1)
    p.stop()
    thread.run()  # 멈춘 뒤에 온 합성 결과
    assert player.played == [] and p.events == [("done", 1, False)]


def test_pipeline_cloud_failure_falls_back_then_retries_next_slide(tmp_path):
    eng = FakeCloud(fail=["network"])
    p, player, os_engine = make_pipeline(tmp_path, ("elevenlabs", eng))
    p.speak("하나. 둘. 셋.", "ko", 2.0, tag=1)
    for _ in range(3):
        player.finish()
    assert len(eng.calls) == 1 and [c[0] for c in os_engine.calls] == ["하나.", "둘.", "셋."]  # 그 문장부터 운영체제 음성
    assert os_engine.calls[0][2] == 2.0  # 운영체제 음성은 엔진이 배속을 낸다
    assert p.events == [("cloud", "elevenlabs", "network"), ("done", 1, True)]  # 알림은 한 번
    p.speak("넷.", "ko", 2.0, tag=2)  # 다음 장에서 다시 시도
    assert eng.calls[-1][0] == "넷." and player.played[-1][0].engine_speed == 1.0


def test_pipeline_uses_cache_for_scripts_only(tmp_path):
    eng = FakeCloud()
    p, player, _ = make_pipeline(tmp_path, ("elevenlabs", eng))
    p.speak("하나. 둘.", "ko", 5.0, tag=1)
    player.finish()
    player.finish()
    assert len(eng.calls) == 2 and eng.calls[0][1:3] == ("", "둘.")
    p.speak("하나. 둘.", "ko", 1.0, tag=2)  # 배속이 달라도 저장한 x1 소리를 그대로 쓴다
    player.finish()
    player.finish()
    assert len(eng.calls) == 2
    p.begin_answer(3, "ko", 1.0, None)  # 답은 저장하지 않는다
    p.add_sentence("하나.")
    p.add_sentence("둘.")
    p.end_answer()
    player.finish()
    player.finish()
    assert len(eng.calls) == 4 and eng.calls[3][1:3] == ("하나.", "")  # 앞 문장만 넘긴다
    assert p.events[-1] == ("done", 3, True)


def test_pipeline_answer_waits_for_more_sentences(tmp_path):
    p, player, _ = make_pipeline(tmp_path)
    p.begin_answer(1, "ko", 1.0, None)
    p.add_sentence("첫 문장.")
    player.finish()
    assert p.events == [] and p.job is not None  # 답이 아직 오는 중
    p.add_sentence("둘째.")
    player.finish()
    p.end_answer()
    assert p.events == [("done", 1, True)]


def test_pipeline_os_failure_reports_error(tmp_path):
    p, player, _ = make_pipeline(tmp_path, os_engine=FakeOS(fail=True))
    p.speak("하나.", "ko", 1.0, tag=4)
    assert p.events == [("error", 4, "SAPI 실패")] and player.played == []


def test_pipeline_frame(tmp_path):
    p, player, _ = make_pipeline(tmp_path)
    assert not p.frame().speaking
    p.speak("이 문장.", "ko", 1.0, tag=1)
    player.pos = 0.05
    f = p.frame()
    assert f.speaking and f.level > 0.5 and f.text == "이 문장." and f.sentence == 0
    assert f.mouth == signal.WIDE and f.words == 1  # '이'는 가로 입


@pytest.mark.live
@pytest.mark.parametrize("provider, env", [("elevenlabs", "PPT_READER_LIVE_ELEVENLABS"),
                                           ("gemini", "PPT_READER_LIVE_GEMINI")])
def test_live_cloud_voice(provider, env):
    key = os.environ.get(env)
    if not key:
        pytest.skip(f"{env}에 키가 없음")
    if provider == "elevenlabs":
        eng = ElevenLabsEngine(key, "eleven_multilingual_v2")
        eng.check_key()
    else:
        eng = GeminiVoiceEngine(key, "gemini-3.8-flash-tts", "Kore")
    synth = eng.synth("안녕하세요. 시험입니다.", None, 1.0)
    assert synth.seconds > 0.5 and synth.words and synth.engine_speed == 1.0
