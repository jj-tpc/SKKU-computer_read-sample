"""macOS 창 보조(pyobjc). 다른 앱의 전체 화면 위에 강아지와 원 버튼을 띄운다.

Qt의 StaysOnTop만으로는 PowerPoint 전체 화면 아래로 깔린다. Apple DTS 답변대로 세 가지를 함께 한다.
- 앱 활성화 정책 accessory(Dock 아이콘 없음)
- 앱을 활성화하지 않는 NSPanel(Qt의 Tool 창이 NSPanel이 되므로 그 창의 styleMask에 더한다)
- 레벨 NSScreenSaverWindowLevel, collectionBehavior CanJoinAllSpaces | CanJoinAllApplications | FullScreenAuxiliary
pyobjc가 없거나 실패하면 Qt 기본 동작으로 두고 False를 돌려준다. --self-check가 그 결과를 보인다.
"""
from __future__ import annotations

import os
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


def make_key(widget) -> bool:
    """질문창을 열 때: 전체 화면 쇼 위에 띄우고 키 입력을 받게 한다.

    빌드 서버 시험에서 이때 이 앱이 활성 앱이 되지만, 쇼의 전체 화면은 그대로 남았다. 닫을 때 restore_front로
    쇼를 다시 활성화한다. 띄울 때 활성화를 막으면(WA_ShowWithoutActivating) 글자가 들어가지 않았다.
    """
    if not _cocoa():
        return False
    try:
        float_over_fullscreen(widget)
        _ns_window(widget).makeKeyAndOrderFront_(None)
        return True
    except Exception:
        return False


def _trace(*parts) -> None:
    """질문창 포커스 진단. 환경 변수 PPT_READER_TRACE가 있을 때만 표준 오류에 쓴다(빌드 서버 화면 시험이 켬)."""
    if os.environ.get("PPT_READER_TRACE"):
        print("[mac-focus]", *parts, file=sys.stderr, flush=True)


_last_other = None  # 마지막으로 본, 이 앱이 아닌 맨 앞 앱(보통 쇼)
_last_front_pid = None


def note_front() -> None:
    """1초마다 부른다. 이 앱이 아닌 맨 앞 앱을 기억해 둔다.

    질문창을 여는 순간에 이미 이 앱이 활성일 수 있다(빌드 서버 시험에서 그랬다). 그때 돌려줄 곳이 이 값이다.
    """
    global _last_other, _last_front_pid
    if not _cocoa():
        return
    try:
        from AppKit import NSRunningApplication, NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        pid = app.processIdentifier() if app is not None else None
        if pid != _last_front_pid:
            _last_front_pid = pid
            _trace("front changed", app.localizedName() if app else None)
        if app is not None and pid != NSRunningApplication.currentApplication().processIdentifier():
            _last_other = app
    except Exception:
        pass


def front_app():
    """질문창을 열기 전에 맨 앞에 있던 앱(보통 PowerPoint). 닫을 때 다시 앞으로 돌린다.

    이 앱이 이미 맨 앞이면 note_front가 마지막으로 본 다른 앱을 돌려준다.
    """
    if not _cocoa():
        return None
    try:
        from AppKit import NSRunningApplication, NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        me = NSRunningApplication.currentApplication()
        mine = app is not None and app.processIdentifier() == me.processIdentifier()
        target = _last_other if mine or app is None else app
        if target is not None and target.isTerminated():
            target = None
        _trace("front_app", app.localizedName() if app else None, "me_active", me.isActive(),
               "target", target.localizedName() if target else None)
        return target
    except Exception as e:
        _trace("front_app error", repr(e))
        return None


def trace_state(label: str) -> None:
    """진단: 이 앱이 활성인지, 키 창이 무엇인지. PPT_READER_TRACE가 있을 때만."""
    if not os.environ.get("PPT_READER_TRACE") or not _cocoa():
        return
    try:
        from AppKit import NSApplication, NSRunningApplication, NSWorkspace

        key = NSApplication.sharedApplication().keyWindow()
        front = NSWorkspace.sharedWorkspace().frontmostApplication()
        _trace(label, "me_active", NSRunningApplication.currentApplication().isActive(),
               "key", type(key).__name__ if key is not None else None, key.title() if key is not None else "",
               "front", front.localizedName() if front else None)
    except Exception as e:
        _trace(label, "error", repr(e))


def restore_front(app) -> None:
    """질문창을 열며 이 앱이 활성화됐으면, 앞서 맨 앞에 있던 앱(쇼)을 다시 활성화해 쇼가 키 입력을 받게 한다.

    macOS 14부터 활성화는 협력 방식이라, 이 앱이 먼저 활성을 넘겨줘야 다른 앱이 앞으로 온다.
    그래도 0.3초 뒤 이 앱이 활성이면 스스로 비활성화해 바로 앞의 앱에 넘긴다.
    """
    if not _cocoa():
        return
    try:
        from AppKit import NSApplication, NSRunningApplication
        from PySide6.QtCore import QTimer

        me = NSRunningApplication.currentApplication()
        nsapp = NSApplication.sharedApplication()
        _trace("restore", app.localizedName() if app else None, "me_active", me.isActive(),
               "yield", hasattr(nsapp, "yieldActivationToApplication_"),
               "activateFrom", hasattr(app, "activateFromApplication_options_") if app else None)
        if not me.isActive():
            return
        if app is None:  # 기억한 앱이 없으면 비활성화해서 바로 앞의 앱에 넘긴다
            nsapp.deactivate()
            _trace("deactivated (no app)")
            return
        if hasattr(nsapp, "yieldActivationToApplication_"):
            nsapp.yieldActivationToApplication_(app)
        if hasattr(app, "activateFromApplication_options_"):
            ok = app.activateFromApplication_options_(me, 0)
        else:
            ok = app.activateWithOptions_(1 << 1)  # NSApplicationActivateIgnoringOtherApps
        _trace("activate returned", ok)

        def later():
            _trace("after 0.3s me_active", me.isActive(), "target_active", app.isActive())
            if me.isActive():
                nsapp.deactivate()
                _trace("deactivated")

        QTimer.singleShot(300, later)
    except Exception as e:
        _trace("restore error", repr(e))


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
