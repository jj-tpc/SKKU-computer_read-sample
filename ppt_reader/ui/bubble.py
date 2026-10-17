"""말풍선: 질의응답 답을 말하는 동안 강아지 머리 위에 뜬다(대본을 읽을 때는 뜨지 않는다).

스트림·이어서: 목소리가 읽기 시작한 낱말까지만 보이고, 문장이 바뀌어도 글이 이어진다. 세 줄이 넘으면 위로 밀려
올라가고 맨 윗줄은 흐려진다. 클릭은 아래로 통과한다.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath,
                           QPolygonF)

from . import theme
from .orb import POP
from .overlay import OverlayWindow

BODY_W = 300
PAD_X, PAD_Y = 16, 11
LINE_H = 24  # 16px × 줄 높이 1.5
MAX_LINES = 3
TAIL = 9
TAIL_X = 24
MARGIN = 28  # 그림자와 흔들림 자리
RX = (26, 20, 24, 14)  # 왼위, 오른위, 오른아래, 왼아래 모서리 가로 반지름
RY = (20, 26, 18, 22)
WORD_FADE = 0.28
SCROLL = 0.3
BOB_PERIOD, BOB = 3.2, 3.0
APPEAR, APPEAR_MOVE = 0.25, 0.4
STOPS = ((0.0, "#FF7A59"), (0.55, "#F2545B"), (1.0, "#D93D6A"))


def stone_path(r: QRectF) -> QPainterPath:
    """모서리마다 조금씩 다른 둥근 돌 모양."""
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p = QPainterPath()
    p.moveTo(x + RX[0], y)
    p.lineTo(x + w - RX[1], y)
    p.arcTo(QRectF(x + w - 2 * RX[1], y, 2 * RX[1], 2 * RY[1]), 90, -90)
    p.lineTo(x + w, y + h - RY[2])
    p.arcTo(QRectF(x + w - 2 * RX[2], y + h - 2 * RY[2], 2 * RX[2], 2 * RY[2]), 0, -90)
    p.lineTo(x + RX[3], y + h)
    p.arcTo(QRectF(x, y + h - 2 * RY[3], 2 * RX[3], 2 * RY[3]), 270, -90)
    p.lineTo(x, y + RY[0])
    p.arcTo(QRectF(x, y, 2 * RX[0], 2 * RY[0]), 180, -90)
    p.closeSubpath()
    return p


def layout_words(words: list[str], fm: QFontMetricsF, width: float) -> list[tuple[int, float]]:
    """낱말마다 (줄 번호, 줄 안 x). 한국어는 띄어쓰기 단위로만 줄을 바꾼다(keep-all)."""
    space = fm.horizontalAdvance(" ")
    out, line, x = [], 0, 0.0
    for w in words:
        ww = fm.horizontalAdvance(w)
        if x > 0 and x + ww > width:
            line, x = line + 1, 0.0
        out.append((line, x))
        x += ww + space
    return out


class BubbleWindow(OverlayWindow):
    def __init__(self):
        super().__init__(click_through=True)
        self.resize(BODY_W + 2 * MARGIN, PAD_Y * 2 + LINE_H * MAX_LINES + TAIL + 2 * MARGIN)
        self._font = QFont(theme.FONT_FAMILY)
        self._font.setPixelSize(16)
        self._font.setWeight(QFont.Weight.DemiBold)
        self.fm = QFontMetricsF(self._font)
        self.words: list[str] = []
        self.born: list[float] = []  # 낱말이 처음 보인 시각
        self.below = False  # 위에 자리가 없어 강아지 아래에 떴다
        self._t = 0.0
        self._shown_at = -1e9
        self._scroll = 0.0  # 지금 밀려 올라간 줄 수(움직이는 중이면 소수)
        self._scroll_from = 0.0
        self._scroll_to = 0.0
        self._scroll_at = -1e9

    # ------------------------------------------------------------ 바깥에서 부르기

    def begin(self) -> None:
        self.words, self.born = [], []
        self._scroll = self._scroll_from = self._scroll_to = 0.0
        self._shown_at = self._t
        self.show()

    def set_text(self, text: str) -> None:
        """지금까지 읽기 시작한 글. 새 낱말만 떠오르는 움직임을 한다."""
        words = text.split()
        if words[:len(self.words)] != self.words:  # 앞이 달라졌으면(새 답) 처음부터
            self.words, self.born = [], []
        for w in words[len(self.words):]:
            self.words.append(w)
            self.born.append(self._t)
        lines = self._lines()
        target = max(0, lines - MAX_LINES)
        if target != self._scroll_to:
            self._scroll_from, self._scroll_to, self._scroll_at = self._scroll, float(target), self._t

    def place(self, dog_x: float, dog_y: float, area) -> None:
        """강아지 머리 위(왼쪽 = 강아지 x + 36, 아래 = 강아지 y + 18). 위에 자리가 없으면 아래. 작업 영역 안으로."""
        body_h = self._body_height()
        left = dog_x + 36
        top = dog_y + 18 - TAIL - body_h
        self.below = top < area.y
        if self.below:
            top = dog_y + 128 + TAIL
        left = min(max(left, area.x), area.right - BODY_W)
        top = min(max(top, area.y + (TAIL if self.below else 0)), area.bottom - body_h - (0 if self.below else TAIL))
        # 창 안에서 몸통은 아래쪽에 붙어 있다(꼬리가 아래로). 아래에 뜰 때는 위쪽에 붙인다
        win_top = top - MARGIN - (TAIL if self.below else self.height() - 2 * MARGIN - TAIL - body_h)
        self.move(round(left - MARGIN), round(win_top))

    def tick(self, dt: float) -> None:
        self._t += dt
        e = self._t - self._scroll_at
        k = min(1.0, max(0.0, e / SCROLL))
        self._scroll = self._scroll_from + (self._scroll_to - self._scroll_from) * (1 - (1 - k) ** 3)
        if self.isVisible():
            self.update()

    # ------------------------------------------------------------ 그리기

    def _lines(self) -> int:
        lay = layout_words(self.words, self.fm, BODY_W - 2 * PAD_X)
        return lay[-1][0] + 1 if lay else 1

    def _body_height(self) -> float:
        return PAD_Y * 2 + LINE_H * min(MAX_LINES, max(1, self._lines()))

    def _body_rect(self) -> QRectF:
        h = self._body_height()
        top = MARGIN + TAIL if self.below else self.height() - MARGIN - TAIL - h
        return QRectF(MARGIN, top, BODY_W, h)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        e = self._t - self._shown_at
        p.setOpacity(min(1.0, max(0.0, e / APPEAR)))
        k = POP(min(1.0, max(0.0, e / APPEAR_MOVE)))
        body = self._body_rect()
        bob = BOB * math.sin(2 * math.pi * self._t / BOB_PERIOD)  # 물에 뜬 것처럼
        scale = 0.94 + 0.06 * k
        p.translate(body.left() + TAIL_X, body.bottom() + 10 * (1 - k) + bob)
        p.scale(scale, scale)
        p.translate(-(body.left() + TAIL_X), -body.bottom())
        self._paint_shadow(p, body)
        grad = QLinearGradient(body.topLeft(), body.bottomRight())  # 135도
        for stop, color in STOPS:
            grad.setColorAt(stop, QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawPath(stone_path(body))
        p.setBrush(QColor("#F2545B"))
        if self.below:  # 꼬리는 강아지 머리를 가리킨다
            tail = [QPointF(body.left() + TAIL_X - 7, body.top() + 1), QPointF(body.left() + TAIL_X + 7, body.top() + 1),
                    QPointF(body.left() + TAIL_X - 2, body.top() - TAIL)]
        else:
            tail = [QPointF(body.left() + TAIL_X - 7, body.bottom() - 1), QPointF(body.left() + TAIL_X + 7, body.bottom() - 1),
                    QPointF(body.left() + TAIL_X - 2, body.bottom() + TAIL)]
        p.drawPolygon(QPolygonF(tail))
        self._paint_text(p, body)
        p.end()

    def _paint_shadow(self, p: QPainter, body: QRectF) -> None:
        # 바다색 그림자 0 10px 24px rgba(14,107,168,.3)를 겹친 돌 모양 여러 장으로 흉내 낸다
        for i in range(6, 0, -1):
            grow = i * 4
            c = QColor(14, 107, 168)
            c.setAlphaF(0.3 / 6 * (7 - i) / 3.5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawPath(stone_path(body.adjusted(-grow / 2, 10 - grow / 2, grow / 2, 10 + grow / 2)))

    def _paint_text(self, p: QPainter, body: QRectF) -> None:
        dpr = self.devicePixelRatioF()
        img = QImage(int(body.width() * dpr), int(body.height() * dpr), QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.GlobalColor.transparent)
        q = QPainter(img)
        q.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        q.setFont(self._font)
        q.setPen(QColor("white"))
        ascent = self.fm.ascent() + (LINE_H - self.fm.height()) / 2
        lay = layout_words(self.words, self.fm, BODY_W - 2 * PAD_X)
        for (line, x), word, born in zip(lay, self.words, self.born):
            y = PAD_Y + (line - self._scroll) * LINE_H
            if y < -LINE_H or y > body.height():
                continue
            k = min(1.0, max(0.0, (self._t - born) / WORD_FADE))  # 새 낱말은 아래에서 떠오르며 선명해진다
            q.setOpacity(k)
            q.drawText(QPointF(PAD_X + x, y + ascent + 4 * (1 - k)), word)
        if self._scroll > 0.01:  # 세 줄을 넘으면 맨 윗줄을 위에서 45%까지 흐리게 가린다
            q.setOpacity(1.0)
            q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            fade = QLinearGradient(0, 0, 0, body.height() * 0.45)
            fade.setColorAt(0.0, QColor(0, 0, 0, 0))
            fade.setColorAt(1.0, QColor(0, 0, 0, 255))
            q.fillRect(QRectF(0, 0, body.width(), body.height() * 0.45), fade)
        q.end()
        p.drawImage(body.topLeft(), img)
