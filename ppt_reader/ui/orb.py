"""원 버튼 묶음 창: 원 버튼(코랄 C 음파 링)과 위성 버튼 다섯 개.

창 하나에 함께 그리고, 버튼 자리에만 마스크를 건다. 마스크 밖(투명한 곳)의 클릭은 아래 쇼로 간다.
"""
from __future__ import annotations

import math
import random
from typing import Callable

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF,
                           QRadialGradient, QRegion)
from PySide6.QtWidgets import QToolTip

from . import theme
from .overlay import OverlayWindow

R = 28  # 원 버튼 반지름
MARGIN = 28  # 작업 영역 오른쪽·아래에서 원 가장자리까지
BARS = 36
BAR_GAP = 5  # 원 가장자리에서 막대가 시작하는 거리
SAT_D = 46
SAT_R = 132  # 원 버튼 중심에서 위성 버튼 중심까지
SAT_ANGLES = [180 + 22.5 * i for i in range(5)]  # 왼쪽(180도)에서 위(270도)까지
OPEN_TIME = 0.3
STAGGER = 0.03
COLLAPSE_AFTER = 4.0
# 창 안에서 원 버튼 중심의 자리. 왼쪽과 위로 위성 버튼(뒤에 질문창, 알림 줄)이 들어갈 자리를 둔다.
CENTER = QPointF(470, 200)
WIN_W = int(CENTER.x()) + R + MARGIN
WIN_H = int(CENTER.y()) + R + MARGIN

SATELLITES = ["ask", "read", "speed", "settings", "quit"]
TIPS = {"ask": "질문하기", "speed": "배속 (누를 때마다 바뀜)", "settings": "설정", "quit": "끝내기"}


def cubic_bezier(x1: float, y1: float, x2: float, y2: float) -> Callable[[float], float]:
    """CSS cubic-bezier와 같은 이징 함수."""
    def ease(x: float) -> float:
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(28):
            t = (lo + hi) / 2
            if 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t * t * x2 + t ** 3 < x:
                lo = t
            else:
                hi = t
        t = (lo + hi) / 2
        return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t * t * y2 + t ** 3
    return ease


POP = cubic_bezier(.2, .9, .3, 1.3)


def speed_label(speed: float) -> str:
    return f"x{speed:g}"


def corner_center(available: QRect) -> QPoint:
    """모니터 작업 영역(작업 표시줄·Dock 제외)에서 원 버튼 중심의 화면 좌표."""
    return QPoint(available.x() + available.width() - MARGIN - R,
                  available.y() + available.height() - MARGIN - R)


class OrbWindow(OverlayWindow):
    def __init__(self, on_action: Callable[[str], None]):
        super().__init__(click_through=False)
        self.resize(WIN_W, WIN_H)
        self.on_action = on_action
        self.state = "idle"  # idle / reading / thinking / speaking
        self.level = 0.0  # 목소리 크기 0~1 (부드럽게 한 값)
        self.tone = 0.5  # 목소리 높낮이 느낌 0~1
        self.speed = 1.0
        self.question_open = False
        self.is_open = False
        self._t = 0.0
        self._anim_from: float | None = None  # 펼치거나 접기 시작한 시각
        self._idle_left = COLLAPSE_AFTER
        self._hover = -1  # 마우스가 올라간 위성 버튼 차례, 없으면 -1
        rnd = random.Random(7)
        self._noise = [rnd.random() for _ in range(BARS)]
        self._update_mask()

    # ------------------------------------------------------------ 바깥에서 부르기

    def place(self, available: QRect) -> None:
        c = corner_center(available)
        self.move(c.x() - int(CENTER.x()), c.y() - int(CENTER.y()))

    def orb_center_global(self) -> QPoint:
        return self.mapToGlobal(CENTER.toPoint())

    def set_state(self, state: str) -> None:
        self.state = state

    def set_speed(self, speed: float) -> None:
        self.speed = speed

    def expand(self) -> None:
        if not self.is_open:
            self.is_open = True
            self._idle_left = COLLAPSE_AFTER
            self._start_anim()

    def collapse(self) -> None:
        if self.is_open:
            self.is_open = False
            self._hover = -1
            QToolTip.hideText()
            self._start_anim()

    def tick(self, dt: float, cursor: QPoint) -> None:
        self._t += dt
        if self._anim_from is not None and self._t - self._anim_from > OPEN_TIME + STAGGER * len(SATELLITES):
            self._anim_from = None
            self._update_mask()
        local = QPointF(self.mapFromGlobal(cursor))
        on_orb = _dist(local, CENTER) <= R + BAR_GAP
        hover = self._satellite_at(local)
        if hover != self._hover:
            self._hover = hover
            self._show_tip()
        if self.is_open and self._anim_from is None:
            if on_orb or hover >= 0:
                self._idle_left = COLLAPSE_AFTER  # 올려 둔 동안은 세지 않고, 벗어나면 처음부터 센다
            elif not self.question_open:
                self._idle_left -= dt
                if self._idle_left <= 0:
                    self.collapse()
        self.update()

    # ------------------------------------------------------------ 위성 버튼 자리

    def _target(self, i: int) -> QPointF:
        a = math.radians(SAT_ANGLES[i])
        return QPointF(CENTER.x() + SAT_R * math.cos(a), CENTER.y() + SAT_R * math.sin(a))

    def _progress(self, i: int) -> float:
        """0이면 원 버튼 안에 숨음, 1이면 제자리. 펼칠 때는 튀어 나간다."""
        if self._anim_from is None:
            return 1.0 if self.is_open else 0.0
        e = self._t - self._anim_from
        if self.is_open:
            return POP(min(1.0, max(0.0, (e - i * STAGGER) / OPEN_TIME)))
        k = min(1.0, max(0.0, (e - (len(SATELLITES) - 1 - i) * STAGGER) / (OPEN_TIME * 0.7)))
        return 1.0 - k * k

    def _satellite_at(self, local: QPointF) -> int:
        if not self.is_open or self._anim_from is not None:
            return -1
        for i in range(len(SATELLITES)):
            if _dist(local, self._target(i)) <= SAT_D / 2:
                return i
        return -1

    def _start_anim(self) -> None:
        self._anim_from = self._t
        self._update_mask()

    def _update_mask(self) -> None:
        c = CENTER.toPoint()
        region = QRegion(QRect(c.x() - 90, c.y() - 90, 180, 180), QRegion.RegionType.Ellipse)  # 원 버튼과 빛
        if self._anim_from is not None:
            # 움직이는 동안에는 위성 버튼이 지나가는 4분원 전체를 연다
            r = SAT_R + SAT_D // 2 + 14
            disk = QRegion(QRect(c.x() - r, c.y() - r, 2 * r, 2 * r), QRegion.RegionType.Ellipse)
            region = region.united(disk.intersected(QRegion(QRect(c.x() - r, c.y() - r, r + 8, r + 8))))
        elif self.is_open:
            for i in range(len(SATELLITES)):
                t = self._target(i).toPoint()
                h = SAT_D // 2 + 10  # 그림자까지
                region = region.united(QRegion(QRect(t.x() - h, t.y() - h, 2 * h, 2 * h + 4),
                                               QRegion.RegionType.Ellipse))
        self.setMask(region)

    def _show_tip(self) -> None:
        if self._hover < 0:
            QToolTip.hideText()
            return
        key = SATELLITES[self._hover]
        if key == "read":
            text = "정지" if self.state in ("reading", "speaking") else "읽기"
        else:
            text = TIPS[key]
        t = self._target(self._hover)
        QToolTip.showText(self.mapToGlobal(QPoint(int(t.x()) - 20, int(t.y() + SAT_D / 2 + 4))), text, self)

    # ------------------------------------------------------------ 누르기

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        local = event.position()
        if _dist(local, CENTER) <= R + BAR_GAP:
            if self.is_open:
                self.collapse()
            else:
                self.expand()
            return
        hit = self._satellite_at(local)
        if hit < 0:
            event.ignore()
            return
        self._idle_left = COLLAPSE_AFTER
        key = SATELLITES[hit]
        if key in ("ask", "settings"):
            self.collapse()
        self.on_action(key)
        self._show_tip()  # 읽기 ↔ 정지 글자가 바뀌었을 수 있다

    # ------------------------------------------------------------ 그리기

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i in range(len(SATELLITES)):  # 위성 버튼은 원 버튼 뒤에서 튀어 나온다
            k = self._progress(i)
            if k > 0.001:
                self._paint_satellite(p, i, k)
        self._paint_orb(p)
        p.end()

    def _paint_satellite(self, p: QPainter, i: int, k: float) -> None:
        target = self._target(i)
        pos = QPointF(CENTER.x() + (target.x() - CENTER.x()) * k, CENTER.y() + (target.y() - CENTER.y()) * k)
        r = SAT_D / 2
        p.save()
        p.setOpacity(min(1.0, k * 3))
        shadow = QRadialGradient(pos + QPointF(0, 4), r + 12)
        shadow.setColorAt(0.0, QColor(0, 0, 0, 46))
        shadow.setColorAt(r / (r + 12), QColor(0, 0, 0, 38))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shadow)
        p.drawEllipse(pos + QPointF(0, 4), r + 12, r + 12)
        p.setBrush(QColor("white"))
        p.setPen(QPen(QColor(255, 111, 97, 102), 1))
        p.drawEllipse(pos, r, r)
        key = SATELLITES[i]
        if key == "settings":
            # ⚙ 글자는 운영체제가 컬러 이모지로 그려 코랄 색이 먹지 않는다. 그래서 도형으로 그린다
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.SATELLITE_GLYPH))
            p.drawPath(_gear(pos, 9.0))
            p.restore()
            return
        glyph = {"ask": "?", "quit": "✕",
                 "read": "■" if self.state in ("reading", "speaking") else "▶",
                 "speed": speed_label(self.speed)}[key]
        font = QFont(theme.FONT_FAMILY)
        font.setPixelSize(14 if key == "speed" else 18)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(theme.SATELLITE_GLYPH))
        p.drawText(QRectF(pos.x() - r, pos.y() - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, glyph)
        p.restore()

    def _paint_orb(self, p: QPainter) -> None:
        t, lv, c = self._t, self.level, CENTER
        theta = math.pi / 4 + 0.5 * t  # 그라데이션 방향(135도)이 초당 0.5라디안으로 돈다
        d = QPointF(math.cos(theta), math.sin(theta))

        # 코랄 빛 그림자
        blur = 10 + lv * 18
        glow = QColor(theme.CORAL)
        glow.setAlphaF(min(1.0, 0.35 + lv * 0.4))
        clear = QColor(theme.CORAL)
        clear.setAlphaF(0.0)
        rg = QRadialGradient(c, R + blur)
        rg.setColorAt(0.0, glow)
        rg.setColorAt(R / (R + blur), glow)
        rg.setColorAt(1.0, clear)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(rg)
        p.drawEllipse(c, R + blur, R + blur)

        # 막대 36개
        tone_k = 2 + round(self.tone * 3)
        for i in range(BARS):
            a = 2 * math.pi * i / BARS
            if self.state == "idle":
                length = 2 + 7 * max(0.0, math.cos(a - 1.2 * t)) ** 6
            elif self.state in ("reading", "speaking"):
                spec = 0.5 + 0.5 * math.sin(a * tone_k + 3 * t + self._noise[i] * 6)
                length = 2 + lv * (11 if self.state == "reading" else 18) * (0.35 + 0.65 * spec)
            else:
                length = 2
            pen = QPen(theme.coral_at(0.5 + 0.5 * math.cos(a - theta)), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            r0 = R + BAR_GAP
            p.drawLine(QPointF(c.x() + r0 * math.cos(a), c.y() + r0 * math.sin(a)),
                       QPointF(c.x() + (r0 + length) * math.cos(a), c.y() + (r0 + length) * math.sin(a)))

        # 원과 흰 테두리
        lg = QLinearGradient(c - d * R, c + d * R)
        for stop, color in theme.CORAL_STOPS:
            lg.setColorAt(stop, QColor(color))
        p.setBrush(lg)
        p.setPen(QPen(QColor(255, 255, 255, 204), 2))
        p.drawEllipse(c, R, R)

        if self.state == "thinking":  # 원 안쪽에서 흰 호가 돈다
            pen = QPen(QColor("white"), 4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            rr = R - 6
            start = -math.degrees(4 * t)
            p.drawArc(QRectF(c.x() - rr, c.y() - rr, 2 * rr, 2 * rr), int(start * 16), int(-108 * 16))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("white"))
        dot = 4 + lv * 5
        p.drawEllipse(c, dot, dot)


def _gear(c: QPointF, r: float) -> QPainterPath:
    """톱니 8개 톱니바퀴. 가운데 구멍은 OddEven 채우기로 뚫는다."""
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    teeth, inner = 8, r * 0.74
    points = []
    for k in range(teeth * 4):
        a = 2 * math.pi * (k - 0.5) / (teeth * 4)
        rr = r if k % 4 in (1, 2) else inner
        points.append(QPointF(c.x() + rr * math.cos(a), c.y() + rr * math.sin(a)))
    path.addPolygon(QPolygonF(points + points[:1]))
    path.addEllipse(c, r * 0.3, r * 0.3)
    return path


def _dist(a: QPointF, b: QPointF) -> float:
    return math.hypot(a.x() - b.x(), a.y() - b.y())
