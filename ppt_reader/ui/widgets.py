"""설정 창과 대본 창이 함께 쓰는 작은 부품: 스위치, 칩, 단추 묶음, 접히는 카드, 앉은 강아지, 코랄 막대."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QStackedWidget, QVBoxLayout, QWidget)

from . import theme
from .dog import CELL, FRAMES, POSES, load_sheet


def coral_gradient(rect: QRectF) -> QLinearGradient:
    g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    for stop, color in theme.CORAL_STOPS:
        g.setColorAt(stop, QColor(color))
    return g


class Toggle(QAbstractButton):
    """켜지면 코랄 그라데이션, 꺼지면 #CFDCE2인 42×24 둥근 스위치."""

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(42, 24)

    def sizeHint(self) -> QSize:
        return QSize(42, 24)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, 42, 24)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(coral_gradient(r) if self.isChecked() else QColor("#CFDCE2"))
        p.drawRoundedRect(r, 12, 12)
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(21 if self.isChecked() else 3, 3, 18, 18))
        p.end()


class Chip(QLabel):
    """상태 칩. tone: ok / bad / warn / off / (기본)."""

    def __init__(self, text: str = "", tone: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("chip")
        self.set(text, tone)

    def set(self, text: str, tone: str = "") -> None:
        self.setText(text)
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)


def label(text: str, name: str = "", parent=None) -> QLabel:
    lab = QLabel(text, parent)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(name in ("hint", "cardSum"))
    return lab


def button(text: str, on_click: Callable[[], None] | None = None, primary: bool = False, small: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        b.setProperty("primary", True)
    if small:
        b.setProperty("small", True)
    if on_click is not None:
        b.clicked.connect(lambda _checked=False: on_click())
    return b


class Segmented(QFrame):
    """단추 묶음(하나만 고름). changed(key)."""
    changed = Signal(str)

    def __init__(self, items: list[tuple[str, str]], current: str, parent=None):
        super().__init__(parent)
        self.setObjectName("seg")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.group = QButtonGroup(self)
        self.buttons: dict[str, QPushButton] = {}
        for key, text in items:
            b = QPushButton(text)
            b.setProperty("seg", True)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setChecked(key == current)
            self.group.addButton(b)
            self.buttons[key] = b
            b.clicked.connect(lambda _c=False, k=key: self.changed.emit(k))
            lay.addWidget(b)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def set_current(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)


class SittingDog(QWidget):
    """앉기 자세 애니메이션(초당 4프레임). 설정 창 머리와 강아지 고르기 카드에 쓴다."""

    def __init__(self, dog: str, size: int = 96, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.frames = load_sheet(dog)[POSES["sit"][0]]
        self.frame = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next)
        self._timer.start(1000 // POSES["sit"][1])

    def set_dog(self, dog: str) -> None:
        self.frames = load_sheet(dog)[POSES["sit"][0]]
        self.update()

    def _next(self) -> None:
        self.frame = (self.frame + 1) % FRAMES
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.drawPixmap(self.rect(), self.frames[self.frame], self.frames[self.frame].rect())
        p.end()


class CoralBar(QWidget):
    """머리의 준비 진행 막대(폭 320, 높이 8, 코랄 그라데이션)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(320, 8)
        self.value = 0.0

    def set_value(self, value: float) -> None:
        self.value = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#DCEBF0"))
        p.drawRoundedRect(QRectF(0, 0, 320, 8), 4, 4)
        if self.value > 0:
            r = QRectF(0, 0, 320 * self.value, 8)
            p.setBrush(coral_gradient(r))
            p.drawRoundedRect(r, 4, 4)
        p.end()


class Card(QFrame):
    """접히는 카드: 머리(번호 또는 ✓, 이름, 다음 할 일, 요약)를 누르면 펼치고 접는다."""
    toggled = Signal(bool)

    def __init__(self, number: int, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.number = number
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.head = QWidget()
        self.head.setCursor(Qt.CursorShape.PointingHandCursor)
        hl = QHBoxLayout(self.head)
        hl.setContentsMargins(18, 14, 18, 14)
        hl.setSpacing(12)
        self.num = QLabel(str(number))
        self.num.setObjectName("num")
        self.num.setFixedSize(28, 28)
        self.num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = label(title, "cardTitle")
        self.next_tag = label("다음 할 일", "nextTag")
        self.next_tag.hide()
        self.sum = label("", "cardSum")
        self.sum.setWordWrap(False)
        self.arrow = QLabel("▾")
        hl.addWidget(self.num)
        hl.addWidget(self.title)
        hl.addWidget(self.next_tag)
        hl.addStretch(1)
        hl.addWidget(self.sum)
        hl.addWidget(self.arrow)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(58, 0, 18, 14)
        self.body_layout.setSpacing(12)
        outer.addWidget(self.head)
        outer.addWidget(self.body)
        self.head.mousePressEvent = lambda _e: self.set_open(not self.is_open, user=True)
        self.is_open = True
        self.set_open(False)

    def set_open(self, open_: bool, user: bool = False) -> None:
        self.is_open = open_
        self.body.setVisible(open_)
        self.arrow.setText("▴" if open_ else "▾")
        if user:
            self.toggled.emit(open_)

    def set_state(self, done: bool, is_next: bool, summary: str) -> None:
        self.num.setText("✓" if done else str(self.number))
        self.num.setProperty("done", done)
        self.num.setProperty("next", is_next and not done)
        self.num.style().unpolish(self.num)
        self.num.style().polish(self.num)
        self.next_tag.setVisible(is_next and not done)
        self.sum.setText(summary)


def row(*widgets, stretch_after: int = -1, grow: int = -1) -> QWidget:
    """가로 한 줄. stretch_after 번째 부품 뒤에 빈 곳을 두거나, grow 번째 부품을 늘인다."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    for i, item in enumerate(widgets):
        lay.addWidget(item, 1 if i == grow else 0)
        if i == stretch_after:
            lay.addStretch(1)
    if stretch_after == -1 and grow == -1:
        lay.insertStretch(len(widgets) - 1, 1)
    return w


class FitStack(QStackedWidget):
    """보이는 페이지의 높이만 차지하는 겹침 위젯(기본은 가장 큰 페이지 높이를 차지한다)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(self._fit)

    def addWidget(self, w):
        i = super().addWidget(w)
        self._fit(self.currentIndex())
        return i

    def _fit(self, index: int) -> None:
        for i in range(self.count()):
            policy = QSizePolicy.Policy.Preferred if i == index else QSizePolicy.Policy.Ignored
            self.widget(i).setSizePolicy(QSizePolicy.Policy.Preferred, policy)
        self.adjustSize()


def field(title: str, *widgets, hint: str = "") -> QWidget:
    """위에 굵은 이름, 아래에 입력 부품."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)
    head = QWidget()
    hl = QHBoxLayout(head)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(8)
    hl.addWidget(label(title, "fieldLabel"))
    if hint:
        h = label(hint, "hint")
        h.setWordWrap(False)
        hl.addWidget(h)
    hl.addStretch(1)
    lay.addWidget(head)
    for item in widgets:
        lay.addWidget(item)
    return w
