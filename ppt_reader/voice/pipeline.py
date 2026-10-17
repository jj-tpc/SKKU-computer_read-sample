"""문장 줄: 앞 문장을 재생하는 동안 다음 문장을 합성해서 틈 없이 잇는다. session의 VoicePort를 따른다.

합성은 음성 스레드(VoiceThread) 하나에서 넣은 차례대로 하고, 결과는 화면 스레드로 넘어와 재생된다.
클라우드 음성이 실패하면 그 문장부터 운영체제 음성으로 이어 읽는다.
- network, timeout, other: 이번 장(또는 답)이 끝날 때까지 운영체제 음성. 다음 장에서 다시 시도한다.
- key, quota: on_cloud_failed로 알리면 session이 키 확인 표시를 지운다. 그 뒤로는 키를 다시 확인할 때까지 운영체제 음성.
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from .cache import VoiceCache, cache_key, sentence_plan
from .cloud import VoiceError
from .engines import Engine, Synth
from .signal import (CLOSED, MouthHold, curves, mouth_shape, syllable_at, syllable_events, value_at,
                     words_started)


def _noop(*_args):
    pass


class VoiceThread:
    """음성 합성 전용 스레드. 일은 넣은 차례대로 하고, 결과는 post(콜백, 인자)로 화면 스레드에 넘긴다."""

    def __init__(self, post: Callable[[Callable, tuple], None]):
        self._post = post
        self._jobs: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="voice", daemon=True)
        self._thread.start()

    def submit(self, fn: Callable[[], object], on_result: Callable[[object], None]) -> None:
        self._jobs.put((fn, on_result))

    def close(self, last: Callable[[], None] | None = None, timeout: float = 3.0) -> None:
        """last는 이 스레드에서 마지막으로 돈다(SAPI 정리처럼 만든 스레드에서 해야 하는 일)."""
        self._jobs.put((last, None))
        self._jobs.put(None)
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while True:
            item = self._jobs.get()
            if item is None:
                return
            fn, on_result = item
            if fn is None:
                continue
            try:
                result = fn()
            except Exception as e:  # 예상 못 한 오류도 화면 쪽에 알린다
                result = e
            if on_result is not None:
                self._post(on_result, (result,))


class InlineThread:
    """시험용: 넣자마자 그 자리에서 돈다."""

    def submit(self, fn, on_result) -> None:
        try:
            result = fn()
        except Exception as e:
            result = e
        on_result(result)

    def close(self, last=None, timeout: float = 0) -> None:
        if last is not None:
            last()


@dataclass
class _Result:
    index: int
    synth: Synth | None
    failure: VoiceError | None = None  # 클라우드가 실패해서 운영체제 음성으로 만든 경우
    error: str = ""  # 운영체제 음성도 실패
    chosen: object = None  # ElevenLabs가 고른 첫 목소리


@dataclass
class _Job:
    tag: object
    token: int
    items: list[tuple[str, str, str]]
    kind: str  # "script" | "answer"
    voice_id: str | None
    speed: float
    output_id: str | None
    cloud: tuple[str, Engine] | None
    closed: bool = True  # 답은 문장이 다 올 때까지 열려 있다
    cloud_off: threading.Event = field(default_factory=threading.Event)
    cloud_failed: bool = False
    requested: int = 0
    play_index: int = -1
    results: dict[int, Synth] = field(default_factory=dict)


@dataclass
class Frame:
    """화면이 30~60fps로 읽는 값. 원 버튼, 강아지, 말풍선이 이것만 본다."""
    speaking: bool = False
    level: float = 0.0
    tone: float = 0.5
    mouth: int = CLOSED
    words: int = 0  # 지금 문장에서 읽기 시작한 낱말 수
    sentence: int = -1
    text: str = ""
    before: str = ""  # 이 답(장)에서 앞서 말한 문장들. 말풍선은 문장이 바뀌어도 글을 이어 보인다


@dataclass
class _Playing:
    synth: Synth
    text: str
    levels: list[float]
    tones: list[float]
    events: list


class Pipeline:
    def __init__(self, os_engine: Engine, player, thread, cloud_for: Callable[[], tuple[str, Engine] | None],
                 cache: VoiceCache | None = None, now: Callable[[], float] = time.monotonic):
        self.os_engine = os_engine
        self.player = player
        self.thread = thread
        self.cloud_for = cloud_for  # 지금 설정으로 쓸 클라우드 엔진. 운영체제 음성이면 None
        self.cache = cache
        self.now = now
        self.token = 0
        self.job: _Job | None = None
        self.playing: _Playing | None = None
        self.hold = MouthHold()
        self.on_done: Callable[[object, bool], None] = _noop  # (tag, 끝까지 읽었나)
        self.on_error: Callable[[object, str], None] = _noop  # (tag, 문구) 운영체제 음성도 실패
        self.on_cloud_failed: Callable[[str, str], None] = _noop  # (제공자, 오류 종류)
        self.on_voice_chosen: Callable[[str, object], None] = _noop  # (제공자, 목소리)
        self.on_started: Callable[[object, int], None] = _noop  # (tag, 문장 번호) 그 문장의 재생을 시작함
        player.on_finished = self._played
        player.on_failed = self._play_failed

    # ------------------------------------------------------------ session의 VoicePort

    def voices(self) -> list:
        return self.os_engine.voices()

    def speak(self, text: str, voice_id: str | None = None, speed: float = 1.0, tag=None,
              output_id: str | None = None) -> None:
        """대본 한 장을 문장으로 잘라 차례로 읽는다. 끝나면 on_done(tag, True)."""
        self._start(_Job(tag, 0, sentence_plan(text), "script", voice_id, speed, output_id, self.cloud_for()))

    def begin_answer(self, tag, voice_id: str | None, speed: float, output_id: str | None) -> None:
        """질의응답 답: 문장이 오는 대로 add_sentence로 넣고, 다 오면 end_answer."""
        self._start(_Job(tag, 0, [], "answer", voice_id, speed, output_id, self.cloud_for(), closed=False))

    def add_sentence(self, text: str) -> None:
        job = self.job
        if job is None or job.kind != "answer" or job.closed:
            return
        prev = job.items[-1][1] if job.items else ""
        job.items.append((prev, text, ""))  # 뒤 문장은 아직 오지 않았다
        self._request_more()
        self._try_play()

    def end_answer(self) -> None:
        if self.job is not None and self.job.kind == "answer":
            self.job.closed = True
            self._try_play()

    def stop(self) -> None:
        job = self.job
        self.token += 1
        self.job = None
        self.playing = None
        self.player.stop()
        if job is not None:
            self.on_done(job.tag, False)

    def frame(self) -> Frame:
        p, job = self.playing, self.job
        if p is None or job is None:
            self.hold.update(CLOSED, self.now())
            return Frame(mouth=self.hold.shape)
        t = self.player.position()
        level = value_at(p.levels, t)
        mouth = self.hold.update(mouth_shape(level, syllable_at(p.events, t)), self.now())
        before = " ".join(item[1] for item in job.items[:job.play_index])
        return Frame(True, level, value_at(p.tones, t), mouth, words_started(p.synth.words, t),
                     job.play_index, p.text, before)

    def close(self) -> None:
        self.stop()
        self.thread.close(self.os_engine.close)

    # ------------------------------------------------------------ 안쪽

    def _start(self, job: _Job) -> None:
        self.stop()
        job.token = self.token
        self.job = job
        if job.closed and not job.items:
            self._finish(job, True)
            return
        self._request_more()

    def _request_more(self) -> None:
        """재생 중인 문장 다음 것까지 미리 합성을 부탁해 둔다."""
        job = self.job
        while job is not None and job.requested < min(len(job.items), job.play_index + 2):
            index = job.requested
            job.requested += 1
            self.thread.submit(lambda j=job, i=index: self._synth(j, i),
                               lambda res, j=job: self._synthesized(j, res))

    def _synth(self, job: _Job, index: int) -> _Result:
        """음성 스레드에서 돈다."""
        prev, text, nxt = job.items[index]
        failure = None
        if job.cloud is not None and not job.cloud_off.is_set():
            provider, engine = job.cloud
            key = ""
            try:
                if hasattr(engine, "ensure_voice"):
                    engine.ensure_voice()
                if job.kind == "script" and self.cache is not None:
                    key = cache_key(provider, engine, prev, text, nxt)
                    hit = self.cache.get(key)
                    if hit is not None:
                        return _Result(index, hit)
                    self.cache.claim(key)
                synth = engine.synth(text, None, 1.0, prev, nxt)
                if key:
                    self.cache.put(key, synth)
                return _Result(index, synth, chosen=getattr(engine, "chosen_voice", None))
            except VoiceError as e:
                job.cloud_off.set()  # 이 장의 남은 문장은 운영체제 음성으로
                failure = e
            finally:
                if key:
                    self.cache.release(key)
        try:
            return _Result(index, self.os_engine.synth(text, job.voice_id, job.speed), failure)
        except Exception as e:
            return _Result(index, None, failure, error=str(e)[:200] or type(e).__name__)

    def _synthesized(self, job: _Job, res) -> None:
        if job is not self.job or job.token != self.token:
            return  # 멈춘 뒤 늦게 온 결과
        if isinstance(res, Exception):
            res = _Result(-1, None, error=str(res)[:200] or type(res).__name__)
        if res.failure is not None and not job.cloud_failed:
            job.cloud_failed = True  # 알림은 한 장(답)에 한 번
            self.on_cloud_failed(job.cloud[0], res.failure.kind)
        if res.chosen is not None and job.cloud is not None:
            self.on_voice_chosen(job.cloud[0], res.chosen)
        if res.synth is None:
            self._fail_job(job, res.error)
            return
        job.results[res.index] = res.synth
        self._try_play()

    def _fail_job(self, job: _Job, message: str) -> None:
        self.token += 1
        self.job = None
        self.playing = None
        self.player.stop()
        self.on_error(job.tag, message)

    def _try_play(self) -> None:
        job = self.job
        if job is None or self.player.busy:
            return
        nxt = job.play_index + 1
        if nxt in job.results:
            job.play_index = nxt
            synth = job.results.pop(nxt)
            text = job.items[nxt][1]
            levels, tones = curves(synth.pcm, synth.rate)
            self.playing = _Playing(synth, text, levels, tones, syllable_events(text, synth.words, synth.seconds))
            self.player.play(synth, job.speed, job.output_id)
            self.on_started(job.tag, nxt)
            self._request_more()
        elif job.closed and nxt >= len(job.items):
            self._finish(job, True)

    def _played(self) -> None:
        self.playing = None
        self._try_play()

    def _play_failed(self, message: str) -> None:
        if self.job is not None:
            self._fail_job(self.job, message)

    def _finish(self, job: _Job, completed: bool) -> None:
        if job is self.job:
            self.job = None
            self.playing = None
            self.on_done(job.tag, completed)
