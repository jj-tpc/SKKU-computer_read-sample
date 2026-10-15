"""실행 중인 PowerPoint가 지금 몇 번 슬라이드를 띄우고 있는지 알아내고, 슬라이드를 넘긴다.

- Windows: COM 자동화 (pywin32)
- macOS:   AppleScript (osascript)
"""
from __future__ import annotations

import glob
import os
import queue
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse


class LinkError(RuntimeError):
    pass


@dataclass(frozen=True)
class PptState:
    mode: str  # "none"(실행 안 됨/열린 문서 없음) | "edit"(편집 화면) | "show"(슬라이드 쇼)
    index: int | None  # 지금 보이는 슬라이드 번호(1부터). 모르면 None
    path: str  # 프레젠테이션 경로. 저장 안 된 문서면 이름만, OneDrive면 URL일 수 있음


# ---------------------------------------------------------------- Windows

class _WinPowerPoint:
    _PP_SLIDESHOW_DONE = 5  # 쇼가 끝나고 검은 화면이 보이는 상태

    def init_thread(self):
        import pythoncom

        pythoncom.CoInitialize()

    def close_thread(self):
        import pythoncom

        pythoncom.CoUninitialize()

    @staticmethod
    def _app():
        import pywintypes
        import win32com.client

        try:
            return win32com.client.GetActiveObject("PowerPoint.Application")
        except pywintypes.com_error:
            return None

    def poll(self) -> PptState | None:
        import pywintypes

        # PowerPoint 객체를 계속 붙잡고 있으면 사용자가 창을 닫아도 프로세스가 남으므로 매번 새로 얻는다.
        app = self._app()
        if app is None:
            return PptState("none", None, "")
        try:
            if app.SlideShowWindows.Count > 0:
                win = app.SlideShowWindows(1)
                path = win.Presentation.FullName
                idx = None
                if win.View.State != self._PP_SLIDESHOW_DONE:
                    idx = win.View.Slide.SlideIndex
                return PptState("show", idx, path)
            if app.Presentations.Count == 0 or app.Windows.Count == 0:
                return PptState("none", None, "")
            win = app.ActiveWindow
            path = win.Presentation.FullName
            try:
                idx = win.View.Slide.SlideIndex
            except (pywintypes.com_error, AttributeError):  # 여러 장을 골랐거나 슬라이드 밖에 커서가 있을 때
                idx = None
            return PptState("edit", idx, path)
        except (pywintypes.com_error, AttributeError):
            # PowerPoint가 바쁘면(쇼 시작 중, 대화상자 열림 등) 호출이 거절된다.
            # pywin32는 이를 AttributeError로 알리기도 한다. 다음에 다시 확인한다.
            return None

    def goto_slide(self, number: int):
        import pywintypes

        app = self._app()
        if app is None:
            return
        try:
            if app.SlideShowWindows.Count > 0:
                app.SlideShowWindows(1).View.GotoSlide(number)
        except (pywintypes.com_error, AttributeError):
            pass


# ---------------------------------------------------------------- macOS

_MAC_POLL = r'''
if application "Microsoft PowerPoint" is not running then return "none"
set m to "edit"
set idx to 0
set p to ""
tell application "Microsoft PowerPoint"
    try
        if (count of presentations) is 0 then set m to "none"
    end try
    try
        if (count of slide show windows) > 0 then set m to "show"
    end try
    if m is "show" then
        try
            set idx to slide index of slide of slide show view of slide show window 1
        end try
        try
            set p to full name of presentation of slide show window 1
        end try
    else if m is "edit" then
        try
            set idx to slide index of slide of view of document window 1
        end try
    end if
    if m is not "none" and p is "" then
        try
            set p to full name of active presentation
        end try
    end if
end tell
if p is not "" and p does not start with "/" then
    try
        set p to POSIX path of (p as alias)
    end try
end if
return m & (ASCII character 9) & (idx as text) & (ASCII character 9) & p
'''

_MAC_GOTO = r'''
on run argv
    set n to (item 1 of argv) as integer
    tell application "Microsoft PowerPoint"
        if (count of slide show windows) is 0 then return
        set v to slide show view of slide show window 1
        try
            go to slide v number n
        on error
            go to next slide v
        end try
    end tell
end run
'''


class _MacPowerPoint:
    def init_thread(self):
        if not _mac_powerpoint_installed():
            raise LinkError("Microsoft PowerPoint가 설치되어 있지 않습니다.")

    def close_thread(self):
        pass

    @staticmethod
    def _osascript(script: str, *args: str) -> str:
        r = subprocess.run(["osascript", "-", *args], input=script, capture_output=True,
                           text=True, encoding="utf-8", timeout=10)
        if r.returncode != 0:
            err = r.stderr.strip()
            if "-1743" in err or "not allowed" in err.lower() or "권한" in err:
                raise LinkError("PowerPoint 제어 권한이 없습니다. 시스템 설정 > 개인정보 보호 및 보안 > "
                                "자동화에서 이 프로그램(또는 터미널)의 'Microsoft PowerPoint'를 켜 주세요.")
            raise LinkError("PowerPoint 상태를 읽지 못했습니다: " + err)
        return r.stdout.strip()

    def poll(self) -> PptState | None:
        try:
            out = self._osascript(_MAC_POLL)
        except subprocess.TimeoutExpired:
            return None
        parts = out.split("\t")
        mode = parts[0] if parts and parts[0] in ("none", "edit", "show") else "none"
        if mode == "none":
            return PptState("none", None, "")
        try:
            idx = int(parts[1]) or None
        except (IndexError, ValueError):
            idx = None
        path = parts[2] if len(parts) > 2 else ""
        return PptState(mode, idx, path)

    def goto_slide(self, number: int):
        try:
            self._osascript(_MAC_GOTO, str(number))
        except (LinkError, subprocess.TimeoutExpired):
            pass


def _mac_powerpoint_installed() -> bool:
    for p in ("/Applications/Microsoft PowerPoint.app",
              os.path.expanduser("~/Applications/Microsoft PowerPoint.app")):
        if os.path.isdir(p):
            return True
    try:
        out = subprocess.run(["mdfind", "kMDItemCFBundleIdentifier == 'com.microsoft.Powerpoint'"],
                             capture_output=True, text=True, timeout=5).stdout
        return bool(out.strip())
    except (OSError, subprocess.SubprocessError):
        return False


# ---------------------------------------------------------------- 공통

def _make_backend():
    if sys.platform == "win32":
        try:
            import win32com.client  # noqa: F401
        except ImportError as e:
            raise LinkError("pywin32가 설치되어 있지 않습니다. "
                            "'pip install -r requirements.txt'를 실행하세요.") from e
        return _WinPowerPoint()
    if sys.platform == "darwin":
        return _MacPowerPoint()
    raise LinkError("PowerPoint 연동은 Windows와 macOS에서만 됩니다.")


class PowerPointLink:
    """백그라운드 스레드에서 PowerPoint를 주기적으로 확인한다.

    상태가 바뀔 때마다 on_change(PptState), 문제가 생기면 on_error(메시지)를 그 스레드에서 호출한다.
    """

    def __init__(self, on_change: Callable[[PptState], None], on_error: Callable[[str], None],
                 interval: float | None = None):
        self._backend = _make_backend()
        self._on_change = on_change
        self._on_error = on_error
        self._interval = interval or (0.4 if sys.platform == "win32" else 0.7)
        self._cmds: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="ppt-link", daemon=True)
        self._thread.start()

    def goto_slide(self, number: int):
        """슬라이드 쇼가 진행 중이면 그 번호의 슬라이드로 넘긴다."""
        self._cmds.put(("goto", number))

    def close(self):
        self._cmds.put(("quit",))

    def _run(self):
        try:
            self._backend.init_thread()
        except LinkError as e:
            self._on_error(str(e))
            return
        last: PptState | None = None
        last_error = ""
        try:
            while True:
                try:
                    cmd = self._cmds.get(timeout=self._interval)
                except queue.Empty:
                    cmd = None
                if cmd is not None:
                    if cmd[0] == "quit":
                        return
                    if cmd[0] == "goto":
                        try:
                            self._backend.goto_slide(cmd[1])
                        except Exception:
                            pass
                try:
                    state = self._backend.poll()
                except LinkError as e:
                    if str(e) != last_error:
                        last_error = str(e)
                        self._on_error(last_error)
                    continue
                except Exception:
                    continue  # 예상 못 한 일시적 오류로 연동이 멈추지 않게 다음 확인으로 넘어간다
                last_error = ""
                if state is not None and state != last:
                    last = state
                    self._on_change(state)
        finally:
            self._backend.close_thread()


def resolve_local_path(path: str) -> Path | None:
    """PowerPoint가 알려 준 경로를 이 컴퓨터의 실제 파일 경로로 바꾼다. 못 찾으면 None."""
    if not path:
        return None
    if not path.lower().startswith(("http://", "https://")):
        p = Path(path)
        return p if p.is_file() else None
    # OneDrive/SharePoint에 저장된 파일은 URL로 보인다. 동기화 폴더에서 같은 파일을 찾아본다.
    segments = [s for s in unquote(urlparse(path).path).split("/") if s]
    for root in _onedrive_roots():
        for i in range(len(segments)):
            candidate = Path(root, *segments[i:])
            if candidate.is_file():
                return candidate
    return None


def _onedrive_roots() -> list[str]:
    roots = []
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if os.environ.get(var):
            roots.append(os.environ[var])
    home = os.path.expanduser("~")
    roots += glob.glob(os.path.join(home, "Library", "CloudStorage", "OneDrive*"))
    roots += glob.glob(os.path.join(home, "OneDrive*"))
    seen, out = set(), []
    for r in roots:
        key = os.path.normcase(os.path.abspath(r))
        if key not in seen and os.path.isdir(r):
            seen.add(key)
            out.append(r)
    return out
