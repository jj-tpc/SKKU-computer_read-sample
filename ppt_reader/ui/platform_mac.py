"""macOS 창 보조(pyobjc). 다른 앱의 전체 화면 위에 강아지와 원 버튼을 띄운다.

Qt의 StaysOnTop만으로는 PowerPoint 전체 화면 아래로 깔린다. Apple DTS 답변대로 세 가지를 함께 한다.
- 앱 활성화 정책 accessory(Dock 아이콘 없음)
- 앱을 활성화하지 않는 NSPanel(Qt의 Tool 창이 NSPanel이 되므로 그 창의 styleMask에 더한다)
- 레벨 NSScreenSaverWindowLevel, collectionBehavior CanJoinAllSpaces | CanJoinAllApplications | FullScreenAuxiliary
pyobjc가 없거나 실패하면 Qt 기본 동작으로 두고 False를 돌려준다. --self-check가 그 결과를 보인다.
"""
from __future__ import annotations

import sys

# AppKit 값. pyobjc 판에 따라 이름이 없을 수 있어 숫자로 둔다.
_NONACTIVATING_PANEL = 1 << 7
_SCREEN_SAVER_LEVEL = 1000
_CAN_JOIN_ALL_SPACES = 1 << 0
_FULL_SCREEN_AUXILIARY = 1 << 8
_CAN_JOIN_ALL_APPLICATIONS = 1 << 18
_BEHAVIOR = _CAN_JOIN_ALL_SPACES | _FULL_SCREEN_AUXILIARY | _CAN_JOIN_ALL_APPLICATIONS
_ACTIVATION_POLICY_ACCESSORY = 1


def become_accessory() -> bool:
    if not _cocoa():
        return False
    try:
        from AppKit import NSApplication

        return bool(NSApplication.sharedApplication().setActivationPolicy_(_ACTIVATION_POLICY_ACCESSORY))
    except Exception:
        return False


def _cocoa() -> bool:
    """offscreen 플랫폼(시험)에서는 winId()가 NSView가 아니라서 pyobjc 포인터로 쓰면 프로세스가 죽는다."""
    if sys.platform != "darwin":
        return False
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.platformName() == "cocoa"


def _ns_window(widget):
    import objc

    view = objc.objc_object(c_void_p=int(widget.winId()))  # Qt의 winId()는 NSView다
    return view.window()


def float_over_fullscreen(widget) -> bool:
    """창이 보인 뒤에 부른다. Qt가 창 플래그를 다시 정하면 레벨이 돌아가므로 보일 때마다 다시 한다."""
    if not _cocoa():
        return False
    try:
        win = _ns_window(widget)
        win.setStyleMask_(win.styleMask() | _NONACTIVATING_PANEL)
        win.setHidesOnDeactivate_(False)
        win.setCollectionBehavior_(_BEHAVIOR)
        win.setLevel_(_SCREEN_SAVER_LEVEL)
        win.orderFrontRegardless()
        return True
    except Exception:
        return False


def check(widget) -> tuple[bool, str]:
    """--self-check용: 보조가 실제 NSWindow에 적용됐는지 읽어서 확인한다."""
    if sys.platform != "darwin":
        return True, "해당 없음"
    if not _cocoa():
        return False, "cocoa 플랫폼이 아님"
    try:
        from AppKit import NSApplication

        win = _ns_window(widget)
        policy = NSApplication.sharedApplication().activationPolicy()
        level, behavior, mask = win.level(), win.collectionBehavior(), win.styleMask()
        ok = (policy == _ACTIVATION_POLICY_ACCESSORY and level == _SCREEN_SAVER_LEVEL
              and behavior & _BEHAVIOR == _BEHAVIOR and bool(mask & _NONACTIVATING_PANEL)
              and not win.hidesOnDeactivate())
        return ok, (f"policy={policy} level={level} behavior={behavior:#x} "
                    f"nonactivating={bool(mask & _NONACTIVATING_PANEL)} panel={win.isKindOfClass_(_panel_class())}")
    except Exception as e:
        return False, f"pyobjc 보조 실패: {type(e).__name__}: {e}"


def _panel_class():
    from AppKit import NSPanel

    return NSPanel
