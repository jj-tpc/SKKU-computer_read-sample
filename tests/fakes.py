"""시험용 가짜 음성, 연동, 시계."""
from __future__ import annotations

from ppt_reader.voice.engines import Voice


class FakeVoice:
    def __init__(self):
        self.spoken = []  # (text, tag, voice_id)
        self.outputs_used = []
        self.speeds = []
        self.stops = 0

    def voices(self):
        return [Voice("en", "English", "en_US"), Voice("ko", "Korean", "ko_KR")]

    def speak(self, text, voice_id=None, speed=1.0, tag=None, output_id=None):
        self.spoken.append((text, tag, voice_id))
        self.outputs_used.append(output_id)
        self.speeds.append(speed)

    def stop(self):
        self.stops += 1


class FakeLink:
    def __init__(self, on_change=None, on_error=None):
        self.gotos = []
        self.closed = False

    def goto_slide(self, n):
        self.gotos.append(n)

    def close(self):
        self.closed = True


class _Timer:
    def __init__(self, at, fn):
        self.at, self.fn, self.cancelled = at, fn, False

    def cancel(self):
        self.cancelled = True


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.timers: list[_Timer] = []

    def now(self):
        return self.t

    def call_later(self, seconds, fn):
        timer = _Timer(self.t + seconds, fn)
        self.timers.append(timer)
        return timer

    def advance(self, seconds):
        end = self.t + seconds
        while True:
            due = [x for x in self.timers if not x.cancelled and x.at <= end]
            if not due:
                break
            first = min(due, key=lambda x: x.at)
            self.timers.remove(first)
            self.t = first.at
            first.fn()
        self.t = end


class FakeAnswerVoice(FakeVoice):
    """답 문장도 받는 가짜 음성(Pipeline의 begin_answer/add_sentence/end_answer)."""

    def __init__(self):
        super().__init__()
        self.answers = []  # {"tag", "sentences", "ended"}

    def begin_answer(self, tag, voice_id, speed, output_id):
        self.answers.append({"tag": tag, "sentences": [], "ended": False})

    def add_sentence(self, text):
        self.answers[-1]["sentences"].append(text)

    def end_answer(self):
        self.answers[-1]["ended"] = True


class FakeLLM:
    """session.llm_start 자리. 받은 요청과 콜백을 남겨 두고, 시험이 글 조각을 직접 흘려 보낸다."""

    def __init__(self):
        self.calls = []  # (provider, key, request, cancel)

    def __call__(self, provider, key, req, on_chunk, on_done, on_error):
        import threading

        cancel = threading.Event()
        self.calls.append({"provider": provider, "key": key, "req": req, "cancel": cancel,
                           "chunk": on_chunk, "done": on_done, "error": on_error})
        return cancel

    @property
    def last(self):
        return self.calls[-1]
