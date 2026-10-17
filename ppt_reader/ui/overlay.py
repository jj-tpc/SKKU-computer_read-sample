"""강아지, 원 버튼 묶음, 말풍선, 알림 줄이 함께 쓰는 창 성격.

테두리 없음, 배경 투명, 항상 위, 작업 표시줄에 안 보임, 포커스를 빼앗지 않음.
포커스를 빼앗지 않아야 원 버튼을 눌러도 PowerPoint 쇼가 키 입력을 계속 받는다.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from . import platform_mac

# 그림자는 창마다 직접 그린다. 시스템 그림자(NoDropShadowWindowHint로 끔)는 macOS에서 투명 창의 옛 모양으로 남는다
OVERLAY_FLAGS = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus
                 | Qt.WindowType.NoDropShadowWindowHint)


class OverlayWindow(QWidget):
    def __init__(self, click_through: bool):
        flags = OVERLAY_FLAGS
        if click_through:
            flags |= Qt.WindowType.WindowTransparentForInput
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # macOS에서 Tool 창은 앱이 비활성이면 숨는다. 이 앱은 늘 비활성(쇼가 활성)이다.
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.mac_floating = False

    def showEvent(self, event):
        super().showEvent(event)
        self.mac_floating = platform_mac.float_over_fullscreen(self)
