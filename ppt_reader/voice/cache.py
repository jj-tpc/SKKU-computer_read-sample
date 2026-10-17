"""대본 소리 저장(앱 폴더 voice_cache/)과 미리 만들기.

클라우드 음성으로 만든 대본 문장만 저장한다. 미리 만들어 두면 발표 중에 인터넷이 끊겨도 대본을 읽고,
리허설과 본 발표에서 같은 글을 다시 합성(요금)하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from ..qa import split_sentences
from .cloud import VoiceError
from .engines import Engine, Synth

LIMIT = 500 * 1024 * 1024
RETRY_AFTER = 30.0  # 인터넷 문제로 실패하면 이만큼 쉬었다가 다시 한다
JOIN_TIMEOUT = 3.0


def sentence_plan(text: str) -> list[tuple[str, str, str]]:
    """읽을 글 한 덩어리를 (앞 문장, 문장, 뒤 문장) 목록으로. 대본 읽기와 미리 만들기가 같은 것을 써야 키가 맞는다."""
    sents = split_sentences(text)
    return [(sents[i - 1] if i else "", s, sents[i + 1] if i + 1 < len(sents) else "")
            for i, s in enumerate(sents)]


def voice_name(engine: Engine) -> str:
    return getattr(engine, "voice_id", "") or getattr(engine, "voice", "")


def cache_key(provider: str, engine: Engine, prev: str, text: str, nxt: str) -> str:
    # 앞뒤 문장을 넣는 것은 ElevenLabs가 그것으로 문장 사이 억양을 잇기 때문이다
    parts = (provider, getattr(engine, "model", ""), voice_name(engine), prev, text, nxt)
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


class VoiceCache:
    def __init__(self, folder: Path | str, limit: int = LIMIT):
        self.dir = Path(folder) / "voice_cache"
        self.limit = limit
        self._lock = threading.Lock()
        self._busy: set[str] = set()  # 지금 누가 합성하고 있는 키

    def has(self, key: str) -> bool:
        return (self.dir / f"{key}.json").exists()

    def get(self, key: str) -> Synth | None:
        meta_path, pcm_path = self.dir / f"{key}.json", self.dir / f"{key}.pcm"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            pcm = pcm_path.read_bytes()
            now = time.time()
            for p in (meta_path, pcm_path):
                os.utime(p, (now, now))  # 최근에 씀: 정리할 때 늦게 지운다
            return Synth(pcm, [tuple(w) for w in meta["words"]], float(meta["engine_speed"]), int(meta["rate"]))
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def put(self, key: str, synth: Synth) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            _write(self.dir / f"{key}.pcm", synth.pcm)
            meta = {"rate": synth.rate, "words": synth.words, "engine_speed": synth.engine_speed,
                    "made_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            _write(self.dir / f"{key}.json", json.dumps(meta).encode("utf-8"))  # json이 마지막: 이것이 있어야 저장된 것
        except OSError:
            return
        self.prune()

    def claim(self, key: str) -> bool:
        with self._lock:
            if key in self._busy:
                return False
            self._busy.add(key)
            return True

    def release(self, key: str) -> None:
        with self._lock:
            self._busy.discard(key)

    def prune(self) -> None:
        """모두 합해 한도를 넘으면 오래 쓰지 않은 것부터 지운다."""
        with self._lock:
            entries = []
            total = 0
            for meta in self.dir.glob("*.json"):
                pcm = meta.with_suffix(".pcm")
                try:
                    size = meta.stat().st_size + (pcm.stat().st_size if pcm.exists() else 0)
                    entries.append((meta.stat().st_mtime, meta, pcm, size))
                except OSError:
                    continue
                total += size
            for _, meta, pcm, size in sorted(entries, key=lambda e: e[0]):
                if total <= self.limit:
                    break
                for p in (meta, pcm):
                    try:
                        p.unlink()
                    except OSError:
                        pass
                total -= size


class Presynth:
    """대본 소리 미리 만들기. 스레드 하나가 지금 장부터 끝까지, 그다음 앞 장들을 차례로 합성해 저장한다.

    on_progress(done, total)와 on_failed(kind, detail)는 이 스레드에서 불린다. 화면 쪽이 화면 스레드로 옮긴다.
    """

    def __init__(self, cache: VoiceCache, on_progress: Callable[[int, int], None],
                 on_failed: Callable[[str, str], None], retry_after: float = RETRY_AFTER):
        self.cache = cache
        self.on_progress = on_progress
        self.on_failed = on_failed
        self.retry_after = retry_after
        self._cmds: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self, provider: str, engine: Engine, slides: list[list[tuple[str, str, str]]], first: int = 0) -> None:
        """slides: 장마다 sentence_plan 결과. first: 지금 장(0부터)."""
        self._ensure_thread()
        self._cmds.put(("start", provider, engine, [list(s) for s in slides], max(0, first)))

    def redo(self, slide: int, plan: list[tuple[str, str, str]]) -> None:
        """대본을 고친 장만 다시 만든다."""
        self._cmds.put(("redo", slide, list(plan)))

    def stop(self) -> None:
        self._cmds.put(("stop",))

    def close(self) -> None:
        if self._thread is not None:
            self._cmds.put(("quit",))
            self._thread.join(timeout=JOIN_TIMEOUT)

    def _ensure_thread(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="voice-presynth", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        provider = engine = None
        slides: list[list[tuple[str, str, str]]] = []
        order: list[tuple[int, int]] = []  # 남은 (장, 문장) 차례
        while True:
            try:
                cmd = self._cmds.get(block=not order)
            except queue.Empty:
                cmd = None
            if cmd is not None:
                if cmd[0] == "quit":
                    return
                if cmd[0] == "stop":
                    order = []
                    continue
                if cmd[0] == "start":
                    _, provider, engine, slides, first = cmd
                    try:
                        if hasattr(engine, "ensure_voice"):
                            engine.ensure_voice()  # 저장 키에 목소리가 들어가므로 먼저 정한다
                    except VoiceError as e:
                        self.on_failed(e.kind, e.detail)
                        order, engine = [], None
                        continue
                    n = len(slides)
                    order = [(s, i) for s in list(range(first, n)) + list(range(0, min(first, n)))
                             for i in range(len(slides[s]))]
                    self._report(provider, engine, slides)
                    continue
                if cmd[0] == "redo" and engine is not None and 0 <= cmd[1] < len(slides):
                    slides[cmd[1]] = cmd[2]
                    order = [(cmd[1], i) for i in range(len(cmd[2]))] + [o for o in order if o[0] != cmd[1]]
                    self._report(provider, engine, slides)
                    continue
                continue
            s, i = order[0]
            prev, text, nxt = slides[s][i]
            key = cache_key(provider, engine, prev, text, nxt)
            if self.cache.has(key) or not self.cache.claim(key):
                order.pop(0)  # 이미 있거나, 읽는 쪽이 지금 합성하고 있다
                continue
            try:
                self.cache.put(key, engine.synth(text, None, 1.0, prev, nxt))
                order.pop(0)
                self._report(provider, engine, slides)
            except VoiceError as e:
                self.on_failed(e.kind, e.detail)
                if e.kind in ("key", "quota"):
                    order = []  # 키를 다시 확인할 때까지 하지 않는다
                else:
                    self._wait(self.retry_after)
            except Exception as e:  # 예상 못 한 오류로 스레드가 죽지 않게
                self.on_failed("other", str(e)[:200])
                order.pop(0)
            finally:
                self.cache.release(key)

    def _wait(self, seconds: float) -> None:
        """쉬는 동안 온 명령은 다시 큐 앞으로 돌려놓는다."""
        try:
            cmd = self._cmds.get(timeout=seconds)
        except queue.Empty:
            return
        pending = [cmd]
        while True:
            try:
                pending.append(self._cmds.get_nowait())
            except queue.Empty:
                break
        for c in pending:
            self._cmds.put(c)

    def _report(self, provider, engine, slides) -> None:
        keys = [cache_key(provider, engine, *item) for plan in slides for item in plan]
        self.on_progress(sum(1 for k in keys if self.cache.has(k)), len(keys))

