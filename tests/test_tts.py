"""음성 스레드 테스트. 실제 음성 엔진 대신 가짜 엔진을 쓴다."""
import queue
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ppt_reader.tts as tts  # noqa: E402


class FakeEngine:
    def __init__(self):
        self.starts = []  # (text, output_id, lead_ms)

    def init_thread(self):
        pass

    def start(self, text, voice_id, speed, output_id=None, lead_ms=0):
        self.starts.append((text, output_id, lead_ms))

    def busy(self):
        return False  # 바로 다 읽은 것으로 친다

    def finished_ok(self):
        return True

    def stop(self):
        pass

    def close_thread(self):
        pass


def test_lead_silence_only_after_quiet(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(tts, "_make_engine", lambda: engine)
    events = queue.Queue()
    sp = tts.Speaker(lambda kind, tag, info: events.put((kind, tag)))

    def say(text, output_id=None):
        sp.speak(text, tag=text, output_id=output_id)
        while events.get(timeout=3) != ("done", text):
            pass
        return engine.starts[-1][2]

    assert say("처음") == tts.LEAD_SILENCE_MS  # 처음 읽을 때는 장치가 깨어나도록 무음을 넣는다
    assert say("바로 이어서") == 0  # 자동 발표처럼 이어 읽으면 넣지 않는다
    assert say("이어폰으로", output_id="ear") == tts.LEAD_SILENCE_MS  # 장치가 바뀌면 넣는다
    monkeypatch.setattr(tts, "IDLE_BEFORE_LEAD", 0.0)  # 오래 조용했던 것으로 만든다
    assert say("한참 뒤", output_id="ear") == tts.LEAD_SILENCE_MS
    sp.close()
