"""운영체제에 들어 있는 음성 합성(TTS)으로 글을 읽는다. 인터넷 연결이 필요 없다.

- Windows: SAPI (pywin32로 SAPI.SpVoice COM 객체 사용)
- macOS:   `say` 명령
출력 장치(스피커, 이어폰 등)를 골라서 읽을 수 있다.
"""
from __future__ import annotations

import locale
import math
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable


class TTSUnavailable(RuntimeError):
    pass


# 블루투스 이어폰(그리고 HDMI 모니터 같은 장치)은 소리가 한동안 없으면 연결을 쉬게 했다가, 소리가 다시
# 오면 깨어나는 동안(약 0.5초) 첫마디를 버린다. 그래서 오래 조용했다가 읽기 시작할 때는 앞에 무음을 넣는다.
LEAD_SILENCE_MS = 1000
IDLE_BEFORE_LEAD = 2.0  # 이만큼(초) 넘게 조용했으면 장치가 쉬고 있다고 본다


@dataclass
class Voice:
    id: str
    name: str
    lang: str  # 예: "ko_KR", "en_US"

    @property
    def is_korean(self) -> bool:
        return self.lang.lower().startswith("ko")


@dataclass
class AudioOutput:
    id: str    # Windows: SAPI 오디오 출력 토큰 Id, macOS: 장치 이름
    name: str  # 예: "헤드폰(OpenRun Pro 2 by Shokz)", "MacBook Pro Speakers"


# ---------------------------------------------------------------- Windows (SAPI)

_SAPI_CATEGORIES = (
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices",
    # '설정 > 음성'에서 추가한 음성은 여기에만 등록되는 경우가 있다. SAPI로도 쓸 수 있다.
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices",
)
_SVSF_ASYNC, _SVSF_PURGE, _SVSF_IS_XML, _SVSF_NOT_XML = 1, 2, 8, 16


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

    @staticmethod
    def outputs() -> list[AudioOutput]:
        import win32com.client

        tokens = win32com.client.Dispatch("SAPI.SpVoice").GetAudioOutputs()
        return [AudioOutput(t.Id, t.GetDescription()) for t in (tokens.Item(i) for i in range(tokens.Count))]

    @classmethod
    def default_output(cls) -> AudioOutput | None:
        endpoint = _default_render_endpoint()
        return next((o for o in cls.outputs() if endpoint and _is_endpoint(o.id, endpoint)), None)

    def init_thread(self):
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        self._sp = win32com.client.Dispatch("SAPI.SpVoice")
        self._default_voice = self._sp.Voice

    def _set_output(self, output_id: str | None):
        # SAPI는 Windows에서 기본 출력 장치를 바꿔도 따라가지 않고 목록의 첫 장치(보통 내장 스피커)로
        # 읽는다. 그래서 고른 장치가 없거나 연결이 끊겼으면 Windows의 지금 기본 장치를 찾아 직접 지정한다.
        tokens = self._sp.GetAudioOutputs()
        tokens = [tokens.Item(i) for i in range(tokens.Count)]
        for want in (output_id, _default_render_endpoint()):
            tok = next((t for t in tokens if want and _is_endpoint(t.Id, want)), None)
            if tok is not None:
                if self._sp.AudioOutput.Id != tok.Id:
                    self._sp.AudioOutput = tok
                return

    def start(self, text: str, voice_id: str | None, speed: float, output_id: str | None = None,
              lead_ms: int = 0):
        import win32com.client

        try:
            self._set_output(output_id)
        except Exception:
            pass  # 장치를 못 바꾸면 SAPI가 쓰던 장치로 읽는다
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
        if lead_ms:  # 무음만 XML로 따로 넣고, 본문은 그대로 NotXML로 읽는다
            self._sp.Speak(f'<silence msec="{int(lead_ms)}"/>', _SVSF_ASYNC | _SVSF_IS_XML)
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


def _is_endpoint(token_id: str, endpoint: str) -> bool:
    # SAPI 출력 토큰 Id는 "...\MMAudioOut\{0.0.0.00000000}.{GUID}"처럼 장치 ID로 끝난다.
    return token_id.lower().endswith(endpoint.lower())


def _default_render_endpoint() -> str | None:
    """Windows 소리 설정의 '기본 출력 장치' ID. 예: "{0.0.0.00000000}.{ced7d08c-...}"

    pywin32에는 이 기능(IMMDeviceEnumerator)이 없어서 ctypes로 COM 함수 표를 직접 부른다.
    """
    import ctypes
    from ctypes import POINTER, byref, c_void_p, c_wchar_p

    ole32 = ctypes.OleDLL("ole32")
    ole32.CoTaskMemFree.restype = None  # 반환값이 없는 함수라 HRESULT 검사를 하지 않게 한다

    def guid(text: str):
        g = (ctypes.c_byte * 16)()
        ole32.CLSIDFromString(text, byref(g))
        return g

    def method(obj, index: int, *argtypes, restype=ctypes.HRESULT):
        vtbl = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
        return ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(vtbl[index])

    enum, dev, dev_id = c_void_p(), c_void_p(), c_wchar_p()
    try:
        ole32.CoCreateInstance(byref(guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")), None, 1,  # MMDeviceEnumerator
                               byref(guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")), byref(enum))
        # IMMDeviceEnumerator::GetDefaultAudioEndpoint(eRender=0, eConsole=0, &device)
        method(enum, 4, ctypes.c_int, ctypes.c_int, POINTER(c_void_p))(enum, 0, 0, byref(dev))
        method(dev, 5, POINTER(c_wchar_p))(dev, byref(dev_id))  # IMMDevice::GetId
        return dev_id.value
    except OSError:
        return None
    finally:
        if dev_id.value is not None:
            ole32.CoTaskMemFree(dev_id)
        for obj in (dev, enum):
            if obj.value:
                method(obj, 2, restype=ctypes.c_ulong)(obj)  # Release


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

    @staticmethod
    def outputs() -> list[AudioOutput]:
        try:
            out = subprocess.run(["say", "-a", "?"], capture_output=True, text=True,
                                 encoding="utf-8", timeout=15).stdout
        except (OSError, subprocess.SubprocessError):
            return []
        found = []
        for line in out.splitlines():
            # 예: "   91 MacBook Pro Speakers"  (앞의 숫자는 재부팅하면 바뀔 수 있어 이름으로 고른다)
            m = re.match(r"^\s*\d+\s+(.+?)\s*$", line)
            if m:
                found.append(AudioOutput(m.group(1), m.group(1)))
        return found

    @staticmethod
    def default_output() -> AudioOutput | None:
        return None  # say는 언제나 macOS의 지금 기본 출력 장치로 읽는다

    def init_thread(self):
        pass

    def start(self, text: str, voice_id: str | None, speed: float, output_id: str | None = None,
              lead_ms: int = 0):
        cmd = ["say", "-r", str(int(self.BASE_WPM * speed))]
        if voice_id:
            cmd += ["-v", voice_id]
        if output_id and any(o.id == output_id for o in self.outputs()):  # 연결이 끊긴 장치면 기본 장치로
            cmd += ["-a", output_id]
        # '-'로 시작하면 옵션으로 오해하므로 앞에 공백을 붙인다. [[slnc N]]은 say의 무음 명령이다.
        body = " " + text if text.startswith("-") else text
        cmd.append(f"[[slnc {int(lead_ms)}]] {body}" if lead_ms else body)
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

    def outputs(self) -> list[AudioOutput]:
        """소리를 낼 수 있는 장치 목록. 블루투스 이어폰처럼 연결된 장치가 바뀌면 결과도 바뀐다."""
        try:
            return self._engine.outputs()
        except Exception:
            return []

    def default_output(self) -> AudioOutput | None:
        """운영체제의 지금 기본 출력 장치. 알 수 없으면 None."""
        try:
            return self._engine.default_output()
        except Exception:
            return None

    def speak(self, text: str, voice_id: str | None = None, speed: float = 1.0, tag=None,
              output_id: str | None = None):
        """output_id가 None이거나 그 장치가 연결되어 있지 않으면 운영체제의 기본 출력 장치로 읽는다."""
        self._cmds.put(("speak", text, voice_id, speed, tag, output_id))

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
        quiet_since: float | None = None  # 마지막으로 소리가 끝난 시각. None = 아직 한 번도 안 읽음
        last_output: object = object()
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
                        quiet_since = time.monotonic()
                        self._on_event("done", current, False)
                    if cmd[0] == "quit":
                        return
                    if cmd[0] == "speak":
                        _, text, voice_id, speed, current, output_id = cmd
                        # 오래 조용했거나 장치가 바뀌었으면 장치가 깨어나도록 앞에 무음을 넣는다.
                        # 자동 발표처럼 바로 이어 읽을 때는 넣지 않아서 장 사이가 늘어지지 않는다.
                        idle = (quiet_since is None or output_id != last_output
                                or time.monotonic() - quiet_since > IDLE_BEFORE_LEAD)
                        last_output = output_id
                        try:
                            engine.start(text, voice_id, speed, output_id, LEAD_SILENCE_MS if idle else 0)
                            speaking = True
                            self._on_event("start", current, None)
                        except Exception as e:  # 음성 엔진 오류는 화면에 알린다
                            quiet_since = time.monotonic()
                            self._on_event("error", current, str(e))
                if speaking and not engine.busy():
                    speaking = False
                    quiet_since = time.monotonic()
                    self._on_event("done", current, engine.finished_ok())
        finally:
            engine.close_thread()
