"""오션·코랄 디자인 값과 Qt 스타일시트. 색은 이 파일 한 곳에만 둔다."""
from __future__ import annotations

import sys

from PySide6.QtGui import QColor

OCEAN_900 = "#06283D"
OCEAN_800 = "#0B3A53"
OCEAN_700 = "#0E5E84"
OCEAN_600 = "#0E6BA8"
AQUA = "#2BB3C0"
FOAM = "#E6F7F8"
FOAM_2 = "#F3FBFC"
SAND = "#FFF7F1"
LINE = "#D6E6EC"
MUTED = "#5B7A8C"
CORAL_L, CORAL, CORAL_D = "#FF9E6D", "#FF6F61", "#E8466E"
OK, BAD, WARN = "#1E9E74", "#E8466E", "#C2601F"
SATELLITE_GLYPH = "#F0565E"

FONT_FAMILY = "Malgun Gothic" if sys.platform == "win32" else "Apple SD Gothic Neo"

# 코랄 그라데이션: 135도, 가운데 색이 55% 자리에 온다
CORAL_STOPS = ((0.0, CORAL_L), (0.55, CORAL), (1.0, CORAL_D))


def coral_at(t: float) -> QColor:
    """코랄 그라데이션의 t(0~1) 자리 색."""
    t = min(1.0, max(0.0, t))
    for (t0, c0), (t1, c1) in zip(CORAL_STOPS, CORAL_STOPS[1:]):
        if t <= t1:
            k = (t - t0) / (t1 - t0)
            a, b = QColor(c0), QColor(c1)
            return QColor(round(a.red() + (b.red() - a.red()) * k),
                          round(a.green() + (b.green() - a.green()) * k),
                          round(a.blue() + (b.blue() - a.blue()) * k))
    return QColor(CORAL_D)


STYLESHEET = f"""
QToolTip {{
    background-color: rgba(11, 58, 83, 240);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 5px 9px;
    font-family: "{FONT_FAMILY}";
    font-size: 13px;
}}
"""
