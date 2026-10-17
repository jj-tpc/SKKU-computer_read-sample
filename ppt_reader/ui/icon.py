"""앱 아이콘. 화면 오른쪽 아래 원 버튼이 쉴 때 모양을 줄여 그린다.

실행 중인 창의 아이콘(작업 표시줄)은 여기서 바로 그린다. 실행 파일의 아이콘(.ico·.icns)은
tools/make_icon.py가 같은 그림으로 만들어 ppt_reader/assets에 둔다. 그림을 바꾸면 그 도구를 다시 돌린다.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QLinearGradient, QPainter, QPen, QPixmap

from . import theme

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
SIMPLE_BELOW = 64  # 이보다 작으면(작업 표시줄 크기) 막대가 뭉개져 보여서 원과 흰 점만 그린다


def image(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _paint(p, size)
    p.end()
    return img


def app_icon() -> QIcon:
    """크기마다 따로 그려 담는다. 작은 크기를 큰 그림에서 줄이면 막대가 흐려진다."""
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(QPixmap.fromImage(image(size)))
    return icon


def _paint(p: QPainter, s: int) -> None:
    c = QPointF(s / 2, s / 2)
    simple = s < SIMPLE_BELOW
    r = s * (0.46 if simple else 0.31)
    theta = math.pi / 4  # 원 버튼 그라데이션이 처음 놓이는 방향(왼쪽 위 밝은 코랄 → 오른쪽 아래 짙은 코랄)

    if not simple:  # 원 둘레의 짧은 막대. 원 버튼처럼 36개, 64px은 사이가 막히지 않게 24개
        bars = 36 if s >= 96 else 24
        r0, length = r + s * 0.045, s * 0.035
        for i in range(bars):
            a = 2 * math.pi * i / bars
            pen = QPen(theme.coral_at(0.5 + 0.5 * math.cos(a - theta)), max(1.5, s * 3 / 128))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(c.x() + r0 * math.cos(a), c.y() + r0 * math.sin(a)),
                       QPointF(c.x() + (r0 + length) * math.cos(a), c.y() + (r0 + length) * math.sin(a)))

    d = QPointF(math.cos(theta), math.sin(theta))
    lg = QLinearGradient(c - d * r, c + d * r)
    for stop, color in theme.CORAL_STOPS:
        lg.setColorAt(stop, QColor(color))
    p.setBrush(lg)
    p.setPen(QPen(QColor(255, 255, 255, 204), max(1.0, s / 64)))
    p.drawEllipse(c, r, r)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("white"))
    p.drawEllipse(c, r * 0.22, r * 0.22)
