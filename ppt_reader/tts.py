"""운영체제에 들어 있는 음성 합성(TTS)으로 글을 읽는다. 인터넷 연결이 필요 없다.

- Windows: SAPI (pywin32로 SAPI.SpVoice COM 객체 사용)
- macOS:   `say` 명령
"""
from __future__ import annotations

import locale
import math
import queue
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Callable


class TTSUnavailable(RuntimeError):
    pass


@dataclass
class Voice:
    id: str
    name: str
    lang: str  # 예: "ko_KR", "en_US"

    @property
    def is_korean(self) -> bool:
        return self.lang.lower().startswith("ko")


# ---------------------------------------------------------------- Windows (SAPI)

_SAPI_CATEGORIES = (
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices",
    # '설정 > 음성'에서 추가한 음성은 여기에만 등록되는 경우가 있다. SAPI로도 쓸 수 있다.
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices",
)
_SVSF_ASYNC, _SVSF_PURGE, _SVSF_NOT_XML = 1, 2, 16


class _SapiEngine:
    def __init__(self):
        import pythoncom  # noqa: F401  (pywin32 설치 여부 확인)
        import win32com.client  # noqa: F401

    @staticmethod
    def voices() -> list[Voice]:
        import win32com.client

        found: list[Voice] = []
        seen: set[str] = set()
        for cat_id in _SAPI_CATEGORIES:
            try:
                cat = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
                cat.SetId(cat_id, False)
                tokens = cat.EnumerateTokens()
            except Exception:
                continue
            for i in range(tokens.Count):
                tok = tokens.Item(i)
                name = tok.GetDescription()
                key = re.sub(r"\s+Desktop\b", "", name.split(" - ")[0]).strip()
                if key in seen:  # 같은 목소리가 두 곳에 등록된 경우 하나만
                    continue
                seen.add(key)
                found.append(Voice(tok.Id, name, _lcid_to_locale(tok.GetAttribute("Language"))))
        return found

    def init_thread(self):
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        self._sp = win32com.client.Dispatch("SAPI.SpVoice")
        self._default_voice = self._sp.Voice

    def start(self, text: str, voice_id: str | None, speed: float):
        import win32com.client

        self._sp.Voice = self._default_voice
        if voice_id:
            try:
                tok = win32com.client.Dispatch("SAPI.SpObjectToken")
                tok.SetId(voice_id, "", False)
                self._sp.Voice = tok
            except Exception:
                pass  # 음성을 못 찾으면 기본 음성으로
        # SAPI 속도는 -10(1/3배) ~ +10(3배)
        self._sp.Rate = max(-10, min(10, round(10 * math.log(speed) / math.log(3))))
        self._sp.Volume = 100
        self._sp.Speak(text, _SVSF_ASYNC | _SVSF_NOT_XML)

    def busy(self) -> bool:
        return not self._sp.WaitUntilDone(0)

    def finished_ok(self) -> bool:
        return True

    def stop(self):
        self._sp.Speak("", _SVSF_ASYNC | _SVSF_PURGE)

    def close_thread(self):
        import pythoncom

        self._sp = None
        pythoncom.CoUninitialize()


def _lcid_to_locale(attr: str) -> str:
    try:
        lcid = int(attr.split(";")[0], 16)
    except (ValueError, AttributeError):
        return ""
    return locale.windows_locale.get(lcid, "")


# ---------------------------------------------------------------- macOS (say)

class _SayEngine:
    BASE_WPM = 190  # 1.0배속일 때 분당 단어 수

    def __init__(self):
        self._proc: subprocess.Popen | None = None

    @staticmethod
    def voices() -> list[Voice]:
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True,
                                 encoding="utf-8", timeout=15).stdout
        except (OSError, subprocess.SubprocessError):
            return []
        found = []
        for line in out.splitlines():
            # 예: "Yuna                ko_KR    # 안녕하세요. 제 이름은 유나입니다."
            m = re.match(r"^(.+?)\s+([a-z]{2,3}[_-][A-Za-z0-9]+)\s+#", line)
            if m:
                name = m.group(1).strip()
                found.append(Voice(name, name, m.group(2)))
        return found

    def init_thread(self):
        pass

    def start(self, text: str, voice_id: str | None, speed: float):
        cmd = ["say", "-r", str(int(self.BASE_WPM * speed))]
        if voice_id:
            cmd += ["-v", voice_id]
        # '-'로 시작하면 옵션으로 오해하므로 앞에 공백을 붙인다.
        cmd.append(" " + text if text.startswith("-") else text)
        self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def busy(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def finished_ok(self) -> bool:
        return self._proc is not None and self._proc.returncode == 0

    def stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def close_thread(self):
        self.stop()


# ---------------------------------------------------------------- 공통

def _make_engine():
    if sys.platform == "win32":
        try:
            return _SapiEngine()
        except ImportError as e:
            raise TTSUnavailable("pywin32가 설치되어 있지 않습니다. "
                                 "'pip install -r requirements.txt'를 실행하세요.") from e
    if sys.platform == "darwin":
        return _SayEngine()
    raise TTSUnavailable("이 프로그램은 Windows와 macOS에서 동작합니다.")


class Speaker:
    """전용 스레드에서 한 번에 한 덩어리씩 읽는다.

    on_event(kind, tag, info)는 그 스레드에서 호출된다.
      kind = "start" | "done" | "error"
      "done"일 때 info는 끝까지 읽었으면 True, 중간에 멈췄으면 False
    """

    def __init__(self, on_event: Callable[[str, object, object], None]):
        self._engine = _make_engine()
        self._on_event = on_event
        self._cmds: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="tts", daemon=True)
        self._thread.start()

    def voices(self) -> list[Voice]:
        return self._engine.voices()

    def speak(self, text: str, voice_id: str | None = None, speed: float = 1.0, tag=None):
        self._cmds.put(("speak", text, voice_id, speed, tag))

    def stop(self):
        self._cmds.put(("stop",))

    def close(self):
        self._cmds.put(("quit",))
        self._thread.join(timeout=3)

    def _run(self):
        engine = self._engine
        engine.init_thread()
        current = None
        speaking = False
        try:
            while True:
                try:
                    cmd = self._cmds.get(timeout=0.05)
                except queue.Empty:
                    cmd = None
                if cmd is not None:
                    if speaking:
                        engine.stop()
                        speaking = False
                        self._on_event("done", current, False)
                    if cmd[0] == "quit":
                        return
                    if cmd[0] == "speak":
                        _, text, voice_id, speed, current = cmd
                        try:
                            engine.start(text, voice_id, speed)
                            speaking = True
                            self._on_event("start", current, None)
                        except Exception as e:  # 음성 엔진 오류는 화면에 알린다
                            self._on_event("error", current, str(e))
                if speaking and not engine.busy():
                    speaking = False
                    self._on_event("done", current, engine.finished_ok())
        finally:
            engine.close_thread()
