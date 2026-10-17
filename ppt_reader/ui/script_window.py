"""대본 창: 슬라이드마다 대본을 고치고, 발표자 노트와 그림 캡션을 본다. 설정 창의 [📝 대본 열기]로 연다.

고친 대본은 칸을 벗어나거나 다른 장으로 갈 때 저장한다. PowerPoint 연동 중이면 쇼의 지금 장을 따라 고른다.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QScrollArea, QVBoxLayout,
                               QWidget)

from ..captions import OVER_LIMIT
from . import theme
from .widgets import Chip, button, label

TITLE = "대본 — {name}"
EDITED = "✎ 고친 대본 — 고친 대로 읽습니다"
AUTO = "자동으로 뽑은 대본 — 고치면 고친 대로 읽습니다"
SOURCE_CHANGED = "원본이 바뀌었어요"
CAP_MADE, CAP_EDITED, CAP_WAITING, CAP_OFF = "LLM이 만듦", "✎ 고침", "기다리는 중", "캡션 꺼짐"


class SlideCard(QAbstractButton):
    """150×92 흰 카드: 제목, 본문 첫 줄, ✎(고친 대본)과 🖼n(그림 수), 장 번호. 고르면 코랄 테두리."""

    def __init__(self, number: int, title: str, first: str):
        super().__init__()
        self.setCheckable(True)
        self.setFixedSize(150, 92)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.number, self.title, self.first = number, title, first
        self.badges = ""

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(1, 1, 148, 90)
        p.setPen(QPen(QColor(theme.CORAL), 2) if self.isChecked() else Qt.PenStyle.NoPen)
        p.setBrush(QColor("white"))
        p.drawRoundedRect(r, 10, 10)
        bold = QFont(theme.FONT_FAMILY)
        bold.setPixelSize(12)
        bold.setBold(True)
        small = QFont(theme.FONT_FAMILY)
        small.setPixelSize(11)
        p.setPen(QColor(theme.OCEAN_800))
        p.setFont(bold)
        p.drawText(QRectF(9, 7, 132, 16), Qt.AlignmentFlag.AlignLeft, p.fontMetrics().elidedText(self.title, Qt.TextElideMode.ElideRight, 132))
        p.setFont(small)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(9, 26, 132, 32), Qt.TextFlag.TextWordWrap.value, self.first)
        p.setPen(QColor(theme.CORAL_D))
        p.drawText(QRectF(9, 68, 90, 16), Qt.AlignmentFlag.AlignLeft, self.badges)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(100, 68, 41, 16), Qt.AlignmentFlag.AlignRight, str(self.number))
        p.end()


class ScriptWindow(QWidget):
    def __init__(self, controller):
        super().__init__(None, Qt.WindowType.Window)
        self.controller = controller
        self.session = controller.session
        self.setObjectName("scriptRoot")
        self.resize(1020, 640)
        self.index = -1  # 지금 고른 장(0부터)
        self._loading = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        # 위: 슬라이드 카드 띠
        film = QFrame()
        film.setObjectName("film")
        self.film_scroll = QScrollArea()
        self.film_scroll.setWidgetResizable(True)
        self.film_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.film_scroll.setFixedHeight(118)
        self.film_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.film_scroll.setStyleSheet("background: transparent;")
        self.film_inner = QWidget()
        self.film_layout = QHBoxLayout(self.film_inner)
        self.film_layout.setContentsMargins(16, 12, 16, 12)
        self.film_layout.setSpacing(10)
        self.film_scroll.setWidget(self.film_inner)
        fl = QVBoxLayout(film)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(self.film_scroll)
        outer.addWidget(film)
        self.cards: list[SlideCard] = []
        # 가운데와 오른쪽
        work = QWidget()
        work.setObjectName("work")
        wl = QHBoxLayout(work)
        wl.setContentsMargins(16, 14, 16, 14)
        wl.setSpacing(14)
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)
        self.heading = label("")
        self.heading.setStyleSheet("font-size: 17px; font-weight: 700;")
        self.editor = QPlainTextEdit()
        self.editor.setStyleSheet("font-size: 15px;")
        self.editor.installEventFilter(self)  # 칸을 벗어날 때 저장
        status = QWidget()
        sl = QHBoxLayout(status)
        sl.setContentsMargins(0, 0, 0, 0)
        self.status = label("", "hint")
        self.status.setWordWrap(False)
        self.changed_chip = Chip(SOURCE_CHANGED, "warn")
        sl.addWidget(self.status)
        sl.addWidget(self.changed_chip)
        sl.addStretch(1)
        sl.addWidget(button("원래 내용으로", self.reset_edit, small=True))
        cl.addWidget(self.heading)
        cl.addWidget(self.editor, 1)
        cl.addWidget(status)
        wl.addWidget(center, 1)
        side = QScrollArea()
        side.setWidgetResizable(True)
        side.setFrameShape(QFrame.Shape.NoFrame)
        side.setFixedWidth(320)
        side.setStyleSheet("QScrollArea { background: transparent; }")
        side.viewport().setAutoFillBackground(False)
        side_inner = QWidget()
        side_inner.setObjectName("work")
        self.side = QVBoxLayout(side_inner)
        self.side.setContentsMargins(0, 0, 4, 0)
        self.side.setSpacing(8)
        side.setWidget(side_inner)
        wl.addWidget(side)
        outer.addWidget(work, 1)
        # 오른쪽: 캡션 진행, 발표자 노트, 그림 캡션
        bar = QFrame()
        bar.setObjectName("capBox")
        bl = QVBoxLayout(bar)
        bl.setContentsMargins(10, 8, 10, 8)
        self.cap_chip = Chip()
        self.cap_text = label("", "hint")
        self.cap_stop = button("멈추기", controller.stop_captions, small=True)
        self.cap_redo = button("다시 만들기", controller.redo_captions, small=True)
        top = QWidget()
        tl = QHBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(self.cap_chip)
        tl.addWidget(self.cap_text, 1)
        tl.addWidget(self.cap_stop)
        tl.addWidget(self.cap_redo)
        self.cap_over = label(OVER_LIMIT, "hint")
        bl.addWidget(top)
        bl.addWidget(self.cap_over)
        self.side.addWidget(bar)
        self.side.addWidget(label("발표자 노트", "fieldLabel"))
        self.notes = label("")
        self.notes.setWordWrap(True)
        self.notes.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        notes_box = QFrame()
        notes_box.setObjectName("capBox")
        nl = QVBoxLayout(notes_box)
        nl.setContentsMargins(10, 8, 10, 8)
        nl.addWidget(self.notes)
        self.side.addWidget(notes_box)
        self.side.addWidget(label("그림 캡션", "fieldLabel"))
        self.pic_box = QVBoxLayout()
        self.pic_box.setSpacing(8)
        holder = QWidget()
        holder.setLayout(self.pic_box)
        self.side.addWidget(holder)
        self.side.addStretch(1)
        self.caption_edits: dict[str, QPlainTextEdit] = {}
        self.rebuild()

    # ------------------------------------------------------------ 장 목록

    def rebuild(self) -> None:
        """파일을 열거나 다시 불러오면 카드를 새로 만든다."""
        deck = self.session.deck
        self.setWindowTitle(TITLE.format(name=deck.name if deck else ""))
        for c in self.cards:
            c.deleteLater()
        self.cards = []
        if deck is None:
            return
        while self.film_layout.count():
            item = self.film_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, s in enumerate(deck.slides):
            lines = [x for x in s.body.split("\n") if x.strip()]
            title = (s.title or "").split("\n")[0] or (lines[0] if lines else "(내용 없음)")
            first = next((x for x in lines if x != title), "")
            b = SlideCard(s.number, title, first)
            b.clicked.connect(lambda _c=False, k=i: self.select(k, user=True))
            self.film_layout.addWidget(b)
            self.cards.append(b)
            self._refresh_card(i)
        self.film_layout.addStretch(1)
        self.select(max(0, min(self.session.current, len(deck.slides) - 1)))

    def select(self, i: int, user: bool = False) -> None:
        deck = self.session.deck
        if deck is None or not (0 <= i < len(deck.slides)):
            return
        if i != self.index:
            self._save_edit()
        self.index = i
        for k, c in enumerate(self.cards):
            c.setChecked(k == i)
        if 0 <= i < len(self.cards):
            self.film_scroll.ensureWidgetVisible(self.cards[i])
        if user:
            self.session.select(i, user=True)  # 연동 중이면 쇼도 같은 장으로
        self._show()

    def follow(self, i: int) -> None:
        """session의 지금 장이 바뀌면(쇼를 넘김 등) 따라 고른다."""
        if i != self.index:
            self.select(i)

    def _show(self) -> None:
        deck = self.session.deck
        s = deck.slides[self.index]
        self._loading = True
        self.heading.setText(f"{s.number}. {(s.title or '').split(chr(10))[0]}")
        self.editor.setPlainText(self.session.script_for(self.index))
        self._loading = False
        edited = s.number in self.session.edits
        self.status.setText(EDITED if edited else AUTO)
        self.changed_chip.setVisible(s.number in self.session.source_changed)
        self.notes.setText(s.notes or "(없음)")
        self.show_captions()

    # ------------------------------------------------------------ 고친 대본

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusOut:
            if obj is self.editor:
                self._save_edit()
            else:
                key = next((k for k, w in self.caption_edits.items() if w is obj), None)
                if key is not None:
                    self._save_caption(key, obj)
        return super().eventFilter(obj, event)

    def _save_edit(self) -> None:
        deck = self.session.deck
        if self._loading or deck is None or not (0 <= self.index < len(deck.slides)):
            return
        text = self.editor.toPlainText()
        if text != self.session.script_for(self.index):
            self.session.set_edit(self.index, text)
            self._refresh_card(self.index)
            self._show_status()

    def _show_status(self) -> None:
        s = self.session.deck.slides[self.index]
        self.status.setText(EDITED if s.number in self.session.edits else AUTO)
        self.changed_chip.setVisible(s.number in self.session.source_changed)

    def reset_edit(self) -> None:
        if self.session.deck is not None and self.index >= 0:
            self.session.reset_edit(self.index)
            self._refresh_card(self.index)
            self._show()

    def _refresh_card(self, i: int) -> None:
        if 0 <= i < len(self.cards):
            s = self.session.deck.slides[i]
            pics = self.controller.pictures.get(s.number, [])
            self.cards[i].badges = ("✎ " if s.number in self.session.edits else "") + (f"🖼{len(pics)}" if pics else "")
            self.cards[i].update()

    def refresh_cards(self) -> None:
        for i in range(len(self.cards)):
            self._refresh_card(i)

    # ------------------------------------------------------------ 캡션

    def show_captions(self) -> None:
        """오른쪽 캡션 진행 막대와 그림 캡션 칸을 지금 상태로 다시 그린다."""
        c = self.controller
        chip, tone, text, making, done = c.caption_view()
        self.cap_chip.set(chip, tone)
        self.cap_text.setText(text)
        self.cap_stop.setVisible(making)
        self.cap_redo.setVisible(done)
        self.cap_over.setVisible(c.caption_over_limit)
        while self.pic_box.count():
            item = self.pic_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.caption_edits = {}
        deck = self.session.deck
        if deck is None or self.index < 0:
            return
        pics = c.pictures.get(deck.slides[self.index].number, [])
        if not pics:
            self.pic_box.addWidget(label("이 장에는 그림이 없어요.", "hint"))
            return
        for p in pics:
            if p.skip:
                skipped = QLabel(f"그림 {p.index}: {p.skip}")
                skipped.setStyleSheet("font-style: italic; color: #5B7A8C; font-size: 12px;")
                skipped.setWordWrap(True)
                self.pic_box.addWidget(skipped)
                continue
            entry = c.caption_store.get(p.key) if c.caption_store else None
            state = (CAP_OFF if not self.controller.settings["captions"]
                     else CAP_EDITED if entry and entry.get("edited")
                     else CAP_MADE if entry else CAP_WAITING)
            box = QFrame()
            box.setObjectName("capBox")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(10, 8, 10, 8)
            bl.addWidget(label(f"그림 {p.index} 캡션 · {state}", "hint"))
            ed = QPlainTextEdit(entry["text"] if entry else "")
            ed.setFixedHeight(70)
            ed.installEventFilter(self)  # 칸을 벗어날 때 고친 캡션을 저장한다
            bl.addWidget(ed)
            self.caption_edits[p.key] = ed
            self.pic_box.addWidget(box)

    def _save_caption(self, key: str, editor: QPlainTextEdit) -> None:
        text = editor.toPlainText().strip()
        entry = self.controller.caption_store.get(key) if self.controller.caption_store else None
        if text and (entry is None or entry.get("text") != text):
            self.controller.edit_caption(key, text)

    def closeEvent(self, event):
        self._save_edit()
        super().closeEvent(event)
