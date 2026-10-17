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


CORAL_QSS = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {CORAL_L}, stop:0.55 {CORAL}, stop:1 {CORAL_D})"

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
QWidget#settingsRoot, QWidget#scriptRoot {{ font-family: "{FONT_FAMILY}"; font-size: 14px; color: {OCEAN_800}; }}
QWidget#settingsScroll {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {FOAM}, stop:0.32 #FFFFFF, stop:1 #FFFFFF); }}
QFrame#card {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 16px; }}
QLabel#cardTitle {{ font-size: 16px; font-weight: 700; }}
QLabel#cardSum, QLabel#hint {{ font-size: 12px; color: {MUTED}; }}
QLabel#heroTitle {{ font-size: 21px; font-weight: 700; }}
QLabel#nextTag {{ font-size: 11px; font-weight: 700; color: white; background: {CORAL_QSS}; border-radius: 9px; padding: 2px 8px; }}
QLabel#fieldLabel {{ font-size: 13px; font-weight: 600; }}
QLabel#num {{ border-radius: 14px; font-weight: 700; font-size: 13px; background: {FOAM}; color: {OCEAN_700}; }}
QLabel#num[done="true"] {{ background: #E3F6EF; color: {OK}; }}
QLabel#num[next="true"] {{ background: {CORAL_QSS}; color: white; }}
QLabel#chip {{ font-size: 12px; padding: 3px 10px; border-radius: 11px; background: {FOAM}; color: {OCEAN_700}; }}
QLabel#chip[tone="ok"] {{ background: #E3F6EF; color: {OK}; }}
QLabel#chip[tone="bad"] {{ background: #FDE8EE; color: {BAD}; }}
QLabel#chip[tone="warn"] {{ background: #FFF1E6; color: {WARN}; }}
QLabel#chip[tone="off"] {{ background: #EEF2F4; color: #7C93A0; }}
QLabel#toast {{ background: rgba(11, 58, 83, 235); color: white; border-radius: 10px; padding: 6px 14px; font-size: 13px; }}
QPushButton {{ border: 1px solid {LINE}; background: #FFFFFF; border-radius: 10px; padding: 6px 14px; color: {OCEAN_800}; }}
QPushButton:hover {{ background: {FOAM_2}; }}
QPushButton[primary="true"] {{ border: 0; background: {CORAL_QSS}; color: white; font-weight: 700; }}
QPushButton[small="true"] {{ padding: 4px 10px; font-size: 13px; border-radius: 8px; }}
QPushButton[seg="true"] {{ border: 0; background: transparent; padding: 6px 12px; border-radius: 8px; color: {OCEAN_700}; }}
QPushButton[seg="true"]:checked {{ background: #FFFFFF; color: {CORAL_D}; font-weight: 700; }}
QPushButton#link {{ border: 0; background: transparent; color: {OCEAN_600}; text-decoration: underline; padding: 0; }}
QFrame#seg {{ background: {FOAM}; border-radius: 10px; }}
QComboBox, QLineEdit, QPlainTextEdit {{ border: 1px solid {LINE}; border-radius: 10px; padding: 6px 10px; background: #FFFFFF; color: {OCEAN_800}; }}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {AQUA}; }}
QFrame#film {{ background: {OCEAN_800}; }}
QPushButton#slideCard {{ background: #FFFFFF; border: 2px solid transparent; border-radius: 10px; text-align: left; padding: 6px 8px; }}
QPushButton#slideCard:checked {{ border: 2px solid {CORAL}; }}
QWidget#work {{ background: {FOAM_2}; }}
QFrame#capBox {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 10px; }}
QProgressBar {{ border: 0; border-radius: 4px; background: #DCEBF0; max-height: 8px; }}
QProgressBar::chunk {{ border-radius: 4px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {AQUA}, stop:1 {OCEAN_600}); }}
"""
