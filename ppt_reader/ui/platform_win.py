"""Windows 창 보조(ctypes). Qt 플래그로 모자란 것만 한다.

- 쇼가 뜬 모니터 찾기: PowerPoint 슬라이드 쇼 창(창 클래스 screenClass)이 있는 모니터
- 질문창을 닫으면 쇼에 포커스 돌려주기
- 작업 표시줄에 python.exe 대신 이 앱의 아이콘 보이기
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

SHOW_CLASS = "screenClass"  # PowerPoint 슬라이드 쇼 창. GUI 툴킷 조사에서 확인했다
APP_ID = "local.pptreader"  # macOS 번들 식별자와 같게 둔다
_MONITOR_DEFAULTTONULL = 0


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def _user32():
    user32 = ctypes.windll.user32
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(_MonitorInfo)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    return user32


def show_monitor_rect() -> tuple[int, int, int, int] | None:
    """쇼 창이 있는 모니터의 사각형(실제 픽셀: 왼, 위, 오른, 아래). 쇼가 없으면 None."""
    if sys.platform != "win32":
        return None
    try:
        user32 = _user32()
        hwnd = user32.FindWindowW(SHOW_CLASS, None)
        if not hwnd or not user32.IsWindowVisible(hwnd):
            return None
        monitor = user32.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONULL)
        if not monitor:
            return None
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(_MonitorInfo)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        r = info.rcMonitor
        return r.left, r.top, r.right, r.bottom
    except (OSError, AttributeError):
        return None


def foreground_window() -> int:
    """질문창을 열기 전의 전경 창(보통 쇼). 닫을 때 돌려준다."""
    if sys.platform != "win32":
        return 0
    try:
        return int(_user32().GetForegroundWindow() or 0)
    except (OSError, AttributeError):
        return 0


def restore_foreground(hwnd: int) -> None:
    if sys.platform == "win32" and hwnd:
        try:
            _user32().SetForegroundWindow(hwnd)
        except (OSError, AttributeError):
            pass


def set_app_id() -> bool:
    """작업 표시줄이 이 프로세스를 python.exe와 따로 묶어, 창 아이콘(원 버튼 그림)을 보이게 한다.

    소스로 실행할 때 이것이 없으면 python.exe 아이콘이 보인다. 창을 띄우기 전에 불러야 한다.
    """
    if sys.platform != "win32":
        return False
    try:
        fn = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        fn.argtypes = [wintypes.LPCWSTR]
        fn.restype = ctypes.c_long
        return fn(APP_ID) == 0
    except (OSError, AttributeError):
        return False
