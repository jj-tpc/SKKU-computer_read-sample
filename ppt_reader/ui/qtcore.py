"""화면 없이도 쓰는 Qt 도구(QtCore만): 다른 스레드의 일을 주 스레드로 옮기기, session이 쓰는 시계.

화면 없는 명령줄 옵션(--say)도 쓰므로 Qt 화면(QtWidgets)을 불러오지 않는다.
"""
from __future__ import annotations

import time
from typing import Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot


class MainThreadInvoker(QObject):
    """다른 스레드에서 부른 함수를 Qt 주 스레드에서 돌린다."""
    _call = Signal(object, object)

    def __init__(self):
        super().__init__()
        self._call.connect(self._run, Qt.ConnectionType.QueuedConnection)

    @Slot(object, object)
    def _run(self, fn, args):
        fn(*args)

    def wrap(self, fn: Callable) -> Callable:
        return lambda *args: self._call.emit(fn, args)

    def post(self, fn: Callable, args: tuple) -> None:
        self._call.emit(fn, args)


class _TimerHandle:
    def __init__(self, timer: QTimer, alive: set):
        self._timer, self._alive = timer, alive

    def cancel(self) -> None:
        self._timer.stop()
        self._alive.discard(self._timer)


class QtClock:
    """session이 쓰는 시계. 시험에서는 가짜 시계로 바뀐다."""

    def __init__(self):
        self._alive: set[QTimer] = set()  # 파이썬 쪽에서 붙잡아 두어야 타이머가 사라지지 않는다

    def now(self) -> float:
        return time.monotonic()

    def call_later(self, seconds: float, fn: Callable[[], None]) -> _TimerHandle:
        timer = QTimer()
        timer.setSingleShot(True)

        def fire():
            self._alive.discard(timer)
            fn()

        timer.timeout.connect(fire)
        self._alive.add(timer)
        timer.start(max(0, int(seconds * 1000)))
        return _TimerHandle(timer, self._alive)
