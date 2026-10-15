# 재구현 프롬프트: PPT 읽어주기

이 문서는 이 저장소의 프로그램을 **처음부터 똑같이 다시 만들기 위한 프롬프트**입니다.
빈 폴더에서 코딩 에이전트(Claude Code 등)를 실행하고, 아래 코드 블록 안의 내용 전체를 그대로 붙여 넣으세요.

- 대상 에이전트: 파일 쓰기와 셸 실행이 가능한 코딩 에이전트
- 기준 구현: 이 저장소 `ppt_reader/` (v1.0.0, Windows 11 + PowerPoint + Python 3.14에서 검증)
- 프롬프트 구성: 역할 → 배경 → 목표 → 제약 → 모듈별 명세 → UI 문구 → 시험 → 함정 → 작업 순서 → 완료 기준 → 보고 형식

````xml
<prompt version="1.0">

<role>
당신은 데스크톱 자동화와 접근성 소프트웨어 경험이 많은 Python 엔지니어다.
Windows COM, macOS AppleScript, tkinter, 운영체제 내장 TTS(SAPI, say)를 실무 수준으로 다룬다.
명세를 글자 그대로 구현하고, 명세에 없는 기능은 추가하지 않으며, 직접 실행해서 확인한 것과 확인하지 못한 것을 구분해 보고한다.
</role>

<context>
<scenario>
학생이 발표할 PPT를 띄워 두면 컴퓨터가 그 내용을 목소리로 읽어 주는 프로그램이 필요하다.
학교 수업의 가상 시나리오에서 "AI 발표자"처럼 쓰인다. 사용자는 한국어 사용자(학생, 교사)다.
</scenario>
<platforms>Windows 10/11과 macOS에서 같은 소스 코드로 동작해야 한다. Linux는 대상이 아니다.</platforms>
<why_these_choices>
- 인터넷 없이도 수업 중에 확실히 동작해야 하므로 운영체제 내장 음성을 쓴다(Windows SAPI, macOS say).
- 설치를 단순하게 하려고 GUI는 Python 표준 라이브러리 tkinter만 쓴다.
- "띄워 놓으면"이라는 요구에 맞추려고, 파일을 직접 여는 방식과 함께 실행 중인 PowerPoint의 현재 슬라이드를 따라가는 연동 기능을 둔다.
</why_these_choices>
</context>

<objective>
아래 명세와 똑같이 동작하는 프로그램 "PPT 읽어주기"를 만든다. 결과물은 다음 다섯 가지다.
1. `ppt_reader` 패키지(화면, 슬라이드 추출, 음성, PowerPoint 연동, 명령줄)
2. 시연용 예제 발표 자료 생성기와 그 결과물인 `sample/sample_presentation.pptx`
3. pytest 자동 테스트 10개
4. 운영체제별 실행 스크립트와 PyInstaller 빌드 설정
5. 한국어 README.md
</objective>

<hard_constraints>
- Python 3.9 이상에서 동작해야 한다. 모든 모듈 맨 위에 `from __future__ import annotations`를 두고, `X | None` 같은 표기는 주석(annotation)에서만 쓴다.
- 외부 의존성은 `python-pptx>=1.0`과 `pywin32>=306; sys_platform == "win32"` 두 개뿐이다. 그 외(pyttsx3, edge-tts, comtypes, PyQt 등)는 쓰지 않는다.
- 사용자에게 보이는 문구는 전부 한국어이며 <ui_strings>의 문구를 글자 그대로 쓴다.
- 코드 주석과 docstring도 한국어로 쓴다. 주석은 "왜"를 설명할 때만 단다.
- Tk 8.6은 BMP 밖의 문자(이모지)를 그리지 못한다. 화면 문구에는 BMP 기호(▶ ■ ◀ ● ✎ ·)만 쓴다.
- 음성 재생과 PowerPoint 확인은 각각 별도 스레드에서 돌린다. tkinter 위젯은 메인 스레드에서만 만진다. 스레드 사이 통신은 `queue.Queue`로 한다.
- COM 객체는 그 객체를 만든 스레드에서만 쓴다. 스레드 사이에는 COM 객체가 아니라 문자열(음성 토큰 ID 등)을 넘긴다.
</hard_constraints>

<project_structure>
```
main.py                     시작점. ppt_reader.__main__.main()을 호출해 sys.exit
requirements.txt
run_windows.bat             Windows 실행 스크립트 (ASCII 전용, CRLF)
run_mac.sh                  macOS 실행 스크립트 (LF)
ppt_reader.spec             PyInstaller 빌드 설정
README.md
PROMPT.md                   (이 문서. 다시 만들 필요 없음)
.gitignore                  .venv/ __pycache__/ *.pyc .pytest_cache/ build/ dist/
.gitattributes              *.sh text eol=lf / *.bat text eol=crlf
ppt_reader/
  __init__.py               docstring 한 줄 + __version__ = "1.0.0"
  __main__.py               명령줄 옵션
  app.py                    화면(tkinter)과 모든 상호작용 로직
  slides.py                 .pptx에서 대본 추출, 읽기용 문장 다듬기
  tts.py                    음성 합성 (Windows SAPI / macOS say)
  link.py                   PowerPoint 연동 (Windows COM / macOS AppleScript)
tools/make_sample.py        예제 발표 자료 생성
sample/sample_presentation.pptx
tests/test_slides.py        추출, 다듬기, 경로 해석 테스트 (4개)
tests/test_app_logic.py     화면 로직 테스트, 가짜 음성/가짜 PowerPoint 사용 (5개)
```
</project_structure>

<module_specs>

<module name="ppt_reader/slides.py">
<data_model>
```python
SOURCES = [
    ("notes_first", "노트 우선 (없으면 본문)"),
    ("body", "슬라이드 본문"),
    ("notes", "발표자 노트"),
    ("both", "본문 + 노트"),
]

@dataclass
class Slide:
    number: int          # 1부터. PowerPoint의 SlideIndex와 같다
    title: str = ""
    body: str = ""       # 제목을 포함한 슬라이드 위 글자 전체
    notes: str = ""
    hidden: bool = False
    def script(self, source: str) -> str: ...

@dataclass
class Deck:
    path: Path
    slides: list[Slide] = field(default_factory=list)
    name -> path.name    (property)
```
`Slide.script(source)`가 돌려주는 값:
- "body"는 body, "notes"는 notes
- "both"는 body와 notes 중 비어 있지 않은 것을 `"\n\n"`로 이은 것
- 그 밖의 값(notes_first)은 `notes or body`
</data_model>

<extraction_rules>
`load_deck(path)`는 `pptx.Presentation`으로 파일을 열고, 슬라이드마다 다음 순서로 처리한다.
1. title: `slide.shapes.title`가 있으면 그 글자를 `_clean`한 값, 없으면 ""
2. body: `[title]`(비어 있지 않을 때만)로 시작한다. 이어서 `_in_reading_order(slide.shapes)` 순서로 각 도형의 `_shape_texts`를 붙인다. 제목 도형은 `shape_id`를 비교해서 건너뛴다. 최종 body는 이 조각들을 `"\n"`로 이은 것이다.
3. notes: `slide.has_notes_slide`이고 `notes_slide.notes_text_frame`이 None이 아닐 때만 그 글자를 `_clean`한 값을 쓴다. `slide.notes_slide`에 함부로 접근하지 않는다(없으면 새로 만들어 버린다).
4. hidden: `slide._element.get("show") == "0"`

보조 함수:
- `_in_reading_order(shapes)`: `sorted(shapes, key=lambda s: (s.top or 0, s.left or 0))`. 위에서 아래로 읽고, 같은 높이면 왼쪽부터 읽는다.
- `_shape_texts(shape) -> list[str]`, 아래 순서로 판단한다.
  - 자리표시자 중 FOOTER, DATE, SLIDE_NUMBER는 `[]`
  - GROUP은 자식 도형을 읽기 순서로 재귀 처리한다
  - 표(`has_table`)는 행마다 셀 글자를 `_clean`하고 빈 셀을 빼서 `", "`로 잇는다. 빈 행은 버린다
  - `has_text_frame`이면 `_clean(text_frame.text)`이고, 비어 있으면 `[]`
  - 그 밖의 도형은 `[]`
- `_clean(text)`: `\v`(python-pptx가 줄바꿈 `<a:br>`을 이렇게 돌려준다)와 `\r`을 `\n`으로 바꾼다. 각 줄의 앞뒤 공백을 지우고 빈 줄은 버린 뒤 `"\n"`로 잇는다.
</extraction_rules>

<speech_normalization>
`to_speech(text)`는 TTS가 줄 사이에서 쉬도록 문장을 다듬는다. 정규식과 상수는 아래 그대로 쓴다.
```python
_BULLET = re.compile(r"^[\s•·∙◦▪▫■□◆◇○●◎▶▷►➢➤→⇒※✓✔☞*\-–—]+")
_SENTENCE_END = tuple(".?!。…:;,)]}\"'”’")
```
처리 순서: `\v`와 `\r`을 `\n`으로 바꾸고 줄 단위로 나눈다. 줄마다 `_BULLET`을 지우고, strip하고, 연속 공백을 하나로 줄인다. 빈 줄은 버린다. 줄이 `_SENTENCE_END` 중 하나로 끝나지 않으면 "."을 붙인다. 마지막으로 `"\n"`로 잇는다.
</speech_normalization>
</module>

<module name="ppt_reader/tts.py">
<public_api>
```python
class TTSUnavailable(RuntimeError): ...

@dataclass
class Voice:
    id: str
    name: str
    lang: str            # "ko_KR", "en_US" 형식
    is_korean -> lang.lower().startswith("ko")   (property)

@dataclass
class AudioOutput:
    id: str              # Windows: SAPI 오디오 출력 토큰 Id, macOS: 장치 이름
    name: str            # 예: "헤드폰(OpenRun Pro 2 by Shokz)", "MacBook Pro Speakers"

class Speaker:
    def __init__(self, on_event: Callable[[str, object, object], None]): ...
    def voices(self) -> list[Voice]: ...
    def outputs(self) -> list[AudioOutput]: ...         # 엔진 예외는 잡아서 []
    def default_output(self) -> AudioOutput | None: ... # 운영체제의 지금 기본 출력 장치. 엔진 예외는 잡아서 None
    def speak(self, text, voice_id=None, speed=1.0, tag=None, output_id=None): ...
        # 큐에 ("speak", text, voice_id, speed, tag, output_id)를 넣는다.
        # output_id가 None이거나 그 장치가 연결되어 있지 않으면 기본 출력 장치로 읽는다.
    def stop(self): ...
    def close(self): ...  # ("quit",)를 넣고 join(timeout=3)
```
on_event(kind, tag, info)는 음성 스레드에서 호출된다. kind는 "start", "done", "error" 중 하나다. "done"이면 info는 끝까지 읽었을 때 True, 중간에 멈췄을 때 False다. "error"이면 info는 오류 메시지 문자열이다.
</public_api>

<worker_loop>
`Speaker`는 이름이 "tts"인 daemon 스레드를 하나 띄우고, 엔진이 바뀌어도 같은 루프를 쓴다.
```
engine.init_thread()
current=None; speaking=False
loop:
  cmd = queue.get(timeout=0.05) (비어 있으면 None)
  if cmd 있음:
     if speaking: engine.stop(); speaking=False; emit("done", current, False)
     if quit: return
     if speak: current=tag; try engine.start(text, voice_id, speed, output_id); speaking=True; emit("start")
               except Exception as e: emit("error", current, str(e))
  if speaking and not engine.busy(): speaking=False; emit("done", current, engine.finished_ok())
finally: engine.close_thread()
```
새 명령은 어떤 것이든(speak, stop, quit) 지금 읽고 있는 것을 먼저 끊는다. 그래서 이전 tag의 done(False)가 다음 start보다 항상 먼저 나온다.
</worker_loop>

<engine platform="win32" name="_SapiEngine">
- 생성자에서 `pythoncom`과 `win32com.client`를 import한다. 실패하면 `_make_engine`이 `TTSUnavailable("pywin32가 설치되어 있지 않습니다. 'pip install -r requirements.txt'를 실행하세요.")`를 던진다.
- 음성 목록(`voices`, staticmethod, 메인 스레드에서 호출): 아래 두 카테고리를 차례로 연다. `SAPI.SpObjectTokenCategory`에 `SetId(cat, False)`를 하고 `EnumerateTokens()`로 토큰을 얻는다.
  ```
  HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices
  HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices
  ```
  OneCore 카테고리는 '설정 > 음성'에서 추가한 음성이 여기에만 등록되는 경우가 있어서 함께 본다. 이 음성도 SAPI로 쓸 수 있다.
  토큰마다 name은 `GetDescription()`이다. 중복 제거 키는 `re.sub(r"\s+Desktop\b", "", name.split(" - ")[0]).strip()`이고, 먼저 나온 것(Desktop)을 남긴다.
  lang은 `GetAttribute("Language")`의 첫 항목(`;`로 나눈 첫 값)을 16진수 LCID로 해석해 `locale.windows_locale`로 바꾼 값이다. 실패하면 "".
  Voice.id는 토큰의 `Id`(레지스트리 전체 경로)다.
- 출력 장치 목록(`outputs`, staticmethod): `SAPI.SpVoice`의 `GetAudioOutputs()` 토큰마다 `AudioOutput(token.Id, token.GetDescription())`.
- `default_output` (classmethod): `_default_render_endpoint()`로 얻은 장치 ID로 끝나는(`_is_endpoint`) 출력을 outputs에서 찾는다. 없으면 None.
- `_is_endpoint(token_id, endpoint)`: 소문자로 바꿔 `token_id.endswith(endpoint)`. SAPI 출력 토큰 Id는 `...\MMAudioOut\{0.0.0.00000000}.{GUID}`처럼 Windows 장치 ID로 끝난다.
- `_default_render_endpoint()`: Windows 소리 설정의 '기본 출력 장치' ID를 돌려준다(예: `{0.0.0.00000000}.{ced7d08c-...}`). pywin32에는 IMMDeviceEnumerator가 없으므로 ctypes로 COM 함수 표(vtable)를 직접 부른다. 외부 패키지(comtypes, pycaw)는 쓰지 않는다.
  1. `ole32 = ctypes.OleDLL("ole32")`, `ole32.CoTaskMemFree.restype = None`(반환값이 없는 함수라 HRESULT 검사를 끈다)
  2. GUID는 `CLSIDFromString`으로 16바이트 버퍼에 만든다. `CoCreateInstance(CLSID_MMDeviceEnumerator {BCDE0395-E52F-467C-8E3D-C4579291692E}, None, CLSCTX_INPROC_SERVER(1), IID_IMMDeviceEnumerator {A95664D2-9614-4F35-A746-DE8DB63617E6}, &enum)`
  3. vtable 4번 `GetDefaultAudioEndpoint(eRender=0, eConsole=0, &dev)`, dev의 vtable 5번 `GetId(&id)`. 함수 원형은 `WINFUNCTYPE(HRESULT, c_void_p, ...)`
  4. OSError면 None. finally에서 id를 `CoTaskMemFree`하고 dev와 enum을 vtable 2번 `Release`(restype c_ulong)한다.
- `init_thread`: `pythoncom.CoInitialize()`를 하고 `SAPI.SpVoice`를 만든 뒤 기본 음성을 기억해 둔다.
- `_set_output(output_id)`: SAPI는 Windows에서 기본 출력 장치를 바꿔도 따라가지 않고, `GetAudioOutputs()`의 첫 장치(보통 내장 스피커)로 읽는다. 그래서 출력 장치를 매번 직접 지정한다. 지금 SpVoice의 `GetAudioOutputs()` 토큰 중에서 `output_id`, 그다음 `_default_render_endpoint()` 순서로 `_is_endpoint`가 맞는 첫 토큰을 찾는다. 찾으면 `AudioOutput.Id`가 다를 때만 `self._sp.AudioOutput = token`을 하고 끝낸다. 둘 다 없으면 그대로 둔다.
- `start(text, voice_id, speed, output_id=None)`:
  0. `_set_output(output_id)`. 예외가 나면 무시하고 SAPI가 쓰던 장치로 읽는다.
  1. 먼저 기본 음성으로 되돌린다.
  2. voice_id가 있으면 `SAPI.SpObjectToken`에 `SetId(voice_id, "", False)`를 해서 지정한다. 실패하면 조용히 기본 음성을 쓴다.
  3. `Rate = clamp(round(10*ln(speed)/ln(3)), -10, 10)`. SAPI 속도는 -10이 1/3배, +10이 3배다.
  4. `Volume = 100`
  5. `Speak(text, SVSFlagsAsync(1) | SVSFIsNotXML(16))`. NotXML이 없으면 본문의 "<"를 SAPI가 XML로 해석한다.
- `busy()`는 `not WaitUntilDone(0)`, `finished_ok()`는 항상 True다.
- `stop()`은 `Speak("", SVSFlagsAsync(1) | SVSFPurgeBeforeSpeak(2))`다.
- `close_thread()`는 참조를 버리고 `CoUninitialize()`를 한다.
</engine>

<engine platform="darwin" name="_SayEngine">
- `BASE_WPM = 190`, 1.0배속일 때의 분당 단어 수다.
- voices: `say -v ?`를 실행한다(utf-8, timeout 15초, 실패하면 []). 줄마다 정규식 `r"^(.+?)\s+([a-z]{2,3}[_-][A-Za-z0-9]+)\s+#"`를 적용한다. id와 name은 모두 1번 그룹을 strip한 값, lang은 2번 그룹이다.
- outputs: `say -a ?`를 실행한다(utf-8, timeout 15초, 실패하면 []). 줄마다 정규식 `r"^\s*\d+\s+(.+?)\s*$"`를 적용하고 id와 name 모두 1번 그룹(장치 이름)이다. 앞의 숫자 ID는 재부팅하면 바뀔 수 있어서 쓰지 않는다.
- default_output: 항상 None이다. say는 언제나 macOS의 지금 기본 출력 장치로 읽는다.
- start(text, voice_id, speed, output_id=None): `["say", "-r", str(int(190*speed))]`로 시작하고, voice_id가 있으면 `["-v", voice_id]`를 붙인다. output_id가 있고 지금 outputs에 같은 id가 있을 때만 `["-a", output_id]`를 붙인다(연결이 끊긴 장치면 기본 장치로 읽는다). 마지막에 본문을 붙이는데, 본문이 "-"로 시작하면 옵션으로 오해하지 않도록 앞에 공백 하나를 붙인다. `Popen`으로 실행하고 stdout과 stderr는 DEVNULL로 보낸다.
- busy는 `poll() is None`, finished_ok는 `returncode == 0`이다.
- stop은 `terminate()`, 2초 동안 `wait`, 그래도 안 끝나면 `kill()`이다. close_thread는 stop을 부른다.
- 그 밖의 OS에서는 `TTSUnavailable("이 프로그램은 Windows와 macOS에서 동작합니다.")`를 던진다.
</engine>
</module>

<module name="ppt_reader/link.py">
<public_api>
```python
class LinkError(RuntimeError): ...

@dataclass(frozen=True)
class PptState:
    mode: str            # "none" | "edit" | "show"
    index: int | None    # 지금 보이는 슬라이드 번호(1부터), 모르면 None
    path: str            # FullName. 저장 안 했으면 이름만, OneDrive면 URL일 수 있음

class PowerPointLink:
    def __init__(self, on_change, on_error, interval=None): ...  # interval 기본값: win32 0.4초, 그 외 0.7초
    def goto_slide(self, number: int): ...   # 명령 큐에 ("goto", n)
    def close(self): ...                     # 명령 큐에 ("quit",)

def resolve_local_path(path: str) -> Path | None: ...
```
</public_api>

<poll_thread>
이름이 "ppt-link"인 daemon 스레드에서 돈다.
- 처음에 `backend.init_thread()`를 부르고, LinkError가 나면 `on_error(msg)`를 한 번 부르고 끝낸다.
- 루프:
  1. `cmds.get(timeout=interval)`로 명령을 기다린다.
  2. quit이면 끝낸다. goto면 `backend.goto_slide(n)`을 부르되 모든 예외를 삼킨다.
  3. `state = backend.poll()`을 부른다.
     - LinkError는 메시지가 직전과 다를 때만 on_error를 부르고 continue한다.
     - 다른 모든 Exception도 continue한다. 스레드가 절대 죽지 않게 하는 것이 목적이다.
     - 오류 없이 poll이 끝나면 기억해 둔 오류 메시지를 지운다.
  4. state가 None이 아니고 직전에 보낸 state와 다를 때만 `on_change(state)`를 부른다. 바뀔 때만 알리는 이 규칙이 아래 <app_logic>의 중복 읽기 방지의 전제다.
- finally에서 `backend.close_thread()`를 부른다.
- 백엔드 선택(`_make_backend`):
  - win32에서 pywin32가 없으면 `LinkError("pywin32가 설치되어 있지 않습니다. 'pip install -r requirements.txt'를 실행하세요.")`
  - darwin이면 `_MacPowerPoint`
  - 그 밖이면 `LinkError("PowerPoint 연동은 Windows와 macOS에서만 됩니다.")`
</poll_thread>

<backend platform="win32" name="_WinPowerPoint">
- init_thread에서 `CoInitialize()`, close_thread에서 `CoUninitialize()`를 한다.
- `_app()`: `win32com.client.GetActiveObject("PowerPoint.Application")`를 부르고, com_error가 나면 None이다. **매 poll마다 새로 얻고 저장해 두지 않는다.** 붙잡고 있으면 사용자가 PowerPoint를 닫아도 프로세스가 남는다.
- poll:
  - app이 None이면 `PptState("none", None, "")`
  - `SlideShowWindows.Count > 0`이면 `win = SlideShowWindows(1)`, `path = win.Presentation.FullName`이다. `win.View.State == 5`(ppSlideShowDone, 쇼가 끝난 검은 화면)이면 idx는 None이고, 아니면 `win.View.Slide.SlideIndex`다. 결과는 "show".
  - `Presentations.Count == 0` 또는 `Windows.Count == 0`이면 "none"
  - 그 밖에는 `win = ActiveWindow`, `path = win.Presentation.FullName`, `idx = win.View.Slide.SlideIndex`다. 이 마지막 호출이 com_error나 AttributeError로 실패하면 idx는 None이다. 결과는 "edit".
  - 위 전체에서 `pywintypes.com_error`나 **AttributeError**가 나면 None을 돌려준다(이번 회차를 건너뜀). pywin32의 동적 디스패치는 PowerPoint가 바빠서 호출을 거절할 때(예: 쇼를 시작하는 순간) com_error 대신 AttributeError를 던진다. 실제 시험에서 이것 때문에 연동 스레드가 죽은 적이 있다.
- goto_slide(n): 쇼 창이 있으면 `SlideShowWindows(1).View.GotoSlide(n)`을 부르고, com_error와 AttributeError는 무시한다. `View.Next()`는 쓰지 않는다. 애니메이션이 있는 장에서는 Next가 장을 넘기지 않고 애니메이션만 진행시킨다.
</backend>

<backend platform="darwin" name="_MacPowerPoint">
- init_thread: PowerPoint가 설치되어 있지 않으면 `LinkError("Microsoft PowerPoint가 설치되어 있지 않습니다.")`를 던진다.
  설치 여부는 `/Applications/Microsoft PowerPoint.app`, `~/Applications/Microsoft PowerPoint.app`, `mdfind "kMDItemCFBundleIdentifier == 'com.microsoft.Powerpoint'"`(timeout 5초) 순서로 확인한다.
  설치되지 않은 앱 이름이 든 AppleScript를 컴파일하면 "앱이 어디 있습니까?" 대화상자가 뜰 수 있어서 미리 확인한다.
- `_osascript(script, *args)`: `subprocess.run(["osascript", "-", *args], input=script, capture_output=True, text=True, encoding="utf-8", timeout=10)`로 실행한다. returncode가 0이 아니면 stderr를 본다.
  - stderr에 "-1743", "not allowed"(소문자 비교), "권한" 중 하나가 있으면 다음 LinkError를 던진다.
    `"PowerPoint 제어 권한이 없습니다. 시스템 설정 > 개인정보 보호 및 보안 > 자동화에서 이 프로그램(또는 터미널)의 'Microsoft PowerPoint'를 켜 주세요."`
  - 그 밖에는 `LinkError("PowerPoint 상태를 읽지 못했습니다: " + stderr)`를 던진다.
- poll: 아래 스크립트를 실행한다(TimeoutExpired면 None). 출력을 탭으로 나누어 mode, idx, path를 얻는다. mode가 세 값 중 하나가 아니면 "none"으로 본다. idx는 `int(...) or None`이고 실패하면 None이다.
```applescript
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
```
- goto_slide(n): 아래 스크립트를 인자 `str(n)`과 함께 실행한다. LinkError와 TimeoutExpired는 무시한다.
```applescript
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
```
</backend>

<resolve_local_path>
- 빈 문자열이면 None이다.
- http나 https로 시작하지 않으면 `Path(path)`가 파일일 때 그 경로, 아니면 None이다. 저장하지 않은 "Presentation1" 같은 이름은 None이 된다.
- URL이면 OneDrive나 SharePoint에 저장된 파일이다. `unquote(urlparse(url).path)`를 "/"로 나눈 조각들을 만든다. 각 OneDrive 루트에 대해 i = 0부터 차례로 `Path(root, *segments[i:])`를 만들어 보고, 처음으로 존재하는 파일을 돌려준다.
- OneDrive 루트 후보는 아래 순서로 모은다. 존재하는 폴더만 남기고, normcase(abspath)로 중복을 지운다.
  1. 환경변수 OneDrive, OneDriveConsumer, OneDriveCommercial
  2. `~/Library/CloudStorage/OneDrive*`
  3. `~/OneDrive*`
</resolve_local_path>
</module>

<module name="ppt_reader/app.py">
<constants>
```python
APP_TITLE = "PPT 읽어주기"
DEFAULT_OUTPUT_LABEL = "시스템 기본 장치"
SETTINGS_FILE = Path.home() / ".ppt_reader_settings.json"
READING_BG = "#ffe08a"            # 지금 읽는 슬라이드 표시 색
EMPTY_SLIDE_PAUSE_MS = 1500       # 읽을 글이 없는 장에서 자동 발표가 쉬는 시간
```
</constants>

<state>
| 속성 | 의미 |
|---|---|
| events: Queue | 다른 스레드에서 화면 스레드로 오는 이벤트 |
| deck: Deck 또는 None | 지금 연 발표 자료 |
| deck_mtime: float | 연 파일의 수정 시각 |
| current: int | 화면에 보이는 슬라이드 위치(0부터), 없으면 -1 |
| edits: dict[int, str] | 슬라이드 번호(number)를 키로, 사용자가 고친 대본을 값으로 |
| token: int | 읽기를 시작하거나 멈출 때마다 1 증가. 늦게 도착한 이벤트를 걸러 내는 용도 |
| reading: (token, 위치) 또는 None | 지금 읽는 중인 것 |
| speaker, link, ppt_state, voice_ids(화면 표시 이름을 음성 id로) | |
| output_choices: dict[str, AudioOutput 또는 None] | 출력 장치 목록의 표시 글자를 장치로. None은 시스템 기본 장치 |
| output: AudioOutput 또는 None | 고른 출력 장치. None이면 운영체제의 기본 출력 장치 |
| tk 변수 | voice_var, output_var, speed_var(Double), auto_next_var, read_on_change_var, follow_var, topmost_var |

설정 파일에서 읽는 기본값은 speed 1.0, auto_next False, read_on_change True, topmost False, source "notes_first"다. output은 `{"id": ..., "name": ...}` dict이고 id가 있을 때만 `AudioOutput(id, name 또는 id)`로 복원한다. 그 밖에는 None이다. follow_var(연동)는 저장하지 않고 항상 꺼진 상태로 시작한다.
초기화 순서: `_build_ui(source)` → `_init_speaker(saved_voice)` → `after(50, _pump)` → WM_DELETE_WINDOW를 quit에 연결 → topmost가 켜져 있으면 적용 → `_show_slide()` → initial_path가 있으면 `open_file`.
</state>

<layout>
pack 순서가 중요하다. 아래쪽 막대들을 `side="bottom"`으로 먼저 붙여야 창이 작아져도 가려지지 않는다.
1. 위쪽 줄(Frame, padding (10,8)), 왼쪽부터 차례로:
   - [파일 열기...] 버튼
   - [PowerPoint 연동] Checkbutton (padx (14,6), command=toggle_link)
   - link_label (회색 #555)
   - 오른쪽 끝에 [항상 위] Checkbutton
2. status 라벨(padding (10,6), 글자색 #333)을 bottom에 붙인다. `<Configure>`에서 wraplength를 width-24로 맞춘다.
3. 옵션 줄 2(padding (10,4,10,0))를 bottom에 붙인다. 들어가는 것:
   - "다 읽으면 다음 장으로 넘어가기 (자동 발표)" Checkbutton
   - "슬라이드 쇼에서 장을 넘기면 바로 읽기" Checkbutton (padx 16)
4. 옵션 줄 1(padding (10,6,10,0))을 bottom에 붙인다. 안쪽은 grid로 두 줄을 배치하고 모두 sticky "w"다.
   - 0행: "읽을 내용" 라벨(0열), 읽기 전용 Combobox(1열, width 22, SOURCES의 표시 이름들, 저장된 source로 current 지정, padx (6,16)), "목소리" 라벨(2열), 읽기 전용 Combobox(3열, width 40, textvariable=voice_var, padx 6)
   - 1행: "출력 장치" 라벨(0열, pady (6,0)), 읽기 전용 Combobox(1열부터 columnspan 3, width 48, textvariable=output_var, `postcommand=_refresh_outputs`, `<<ComboboxSelected>>` → `_on_output_change`, padx (6,0), pady (6,0)). postcommand로 목록을 펼 때마다 장치를 다시 읽어서, 나중에 연결한 블루투스 이어폰도 고를 수 있게 한다.
5. 제어 줄(padding (10,8,10,0))을 bottom에 붙인다.
   - 왼쪽부터: [◀ 이전], [▶ 읽기](width 10, padx 4), [■ 정지], [다음 ▶](padx 4)
   - 오른쪽에 둔 Frame 안에: "속도" 라벨, ttk.Scale(0.5~2.0, length 140, padx 6), 속도 값 라벨(width 5, 글자 `f"{v:.1f}배"`)
6. 가로 ttk.PanedWindow(fill both, expand, padx 10). 왼쪽 칸과 오른쪽 칸의 weight는 1:3이다.
   - 왼쪽 칸: tk.Listbox(activestyle none, exportselection False, width 34, height 16)와 세로 스크롤바
   - 오른쪽 칸(padding (10,0,0,0)), 위에서부터:
     - header 라벨(굵게)
     - 안내 라벨 "읽을 대본 (여기서 고치면 고친 대로 읽습니다)" (#666, pady (2,4))
     - 맨 아래(side bottom) 줄: edited_label(#b05000)과 오른쪽 끝의 [원래 내용으로] 버튼
     - 그 사이에 tk.Text(wrap word, undo True, width 52, height 12, padx 10, pady 8)와 세로 스크롤바
7. 크기 고정: `update_idletasks()`를 한 뒤 `w = reqwidth`, `h = reqheight + status.reqheight`로 `geometry(f"{w}x{h}")`를 지정한다. `minsize(int(w*0.75), int(h*0.75))`, `status.wraplength = w-24`도 설정한다.
   창 크기를 픽셀로 박아 두면 화면 배율이 125% 이상일 때 아래쪽이 잘린다. 그래서 위젯 크기를 글자 수로 정하고, 그 결과로 창 크기를 한 번만 고정한다. 한 번 고정해 두면 긴 안내 문구가 떠도 창이 늘어나지 않는다.
8. 키 바인딩(root):
   - `<space>` → _on_space
   - `<Escape>` → stop
   - `<F5>` → read_current
   - `<Prior>`/`<Next>` → 포커스가 tk.Text가 아닐 때만 이전/다음 장으로 가고 "break"
9. 글꼴: Windows는 "Malgun Gothic", macOS는 "Apple SD Gothic Neo", 그 밖에는 "TkDefaultFont"이다. 크기(Windows/macOS)는 다음과 같다.
   - 목록 11/13
   - 대본 13/15
   - 제목 14/17 굵게
   - `run()`에서 TkDefaultFont 10/13
</layout>

<app_logic>
<behavior name="_init_speaker">
1. Speaker를 만들고, 그 이벤트를 `events.put(("tts", kind, tag, info))`로 넘긴다. TTSUnavailable이 나면 `messagebox.showerror(APP_TITLE, msg)`를 띄우고 speaker는 None인 채로 둔다.
2. 음성 목록을 `key=lambda v: not v.is_korean`으로 안정 정렬해서 한국어 음성을 앞에 둔다.
3. 표시 이름은 lang이 있으면 `f"{name}  [{lang}]"`(공백 두 칸), 없으면 name이다.
4. 저장된 음성이 목록에 있으면 그것을, 없으면 첫 번째 음성을 고른다.
5. 한국어 음성이 하나도 없으면 상태 표시줄에 해당 안내를 띄운다(<ui_strings> 참고).
6. `_refresh_outputs()`를 부른다.
</behavior>

<behavior name="_refresh_outputs">
speaker가 없으면 아무것도 하지 않는다.
1. `default = speaker.default_output()`. 첫 항목 글자는 default가 있으면 `f"시스템 기본 장치 (지금: {default.name})"`, 없으면 `"시스템 기본 장치"`이고 값은 None이다.
2. `speaker.outputs()`를 차례로 넣는다. 글자는 name이고, 이미 있는 글자면 `f"{name} (2)"`, `(3)`처럼 번호를 붙인다.
3. 고를 항목: output이 None이면 첫 항목. output이 있으면 id가 같은 항목. 그런 항목이 없으면(이어폰 연결이 끊김) `f"{output.name} (연결 안 됨 - 기본 장치로 읽음)"` 항목을 output 값으로 추가해서 고른다. output은 바꾸지 않으므로 다시 연결되면 그 장치로 읽는다.
4. Combobox values를 갱신하고 output_var를 고른 항목으로 둔다.
</behavior>

<behavior name="_on_output_change">
`output = output_choices.get(output_var)`로 두고 `f"이제 '{장치 이름 또는 시스템 기본 장치}'(으)로 읽습니다. 다음에 읽을 때부터 적용됩니다."`를 띄운다.
</behavior>

<behavior name="speak_slide(i)">
speaker나 deck이 없으면 아무것도 하지 않는다.
1. `_commit_edit()`
2. `text = to_speech(_script_for(i))`
3. token을 1 올리고 `reading = (token, i)`로 두고 `_mark_reading(i)`를 부른다.
4. text가 비어 있으면 `speaker.stop()`을 부르고 "읽을 내용이 없습니다" 상태를 띄운다. EMPTY_SLIDE_PAUSE_MS 뒤에 `_on_read_finished(tok, True, quiet=True)`를 예약한다. 자동 발표 중이면 잠깐 쉬었다가 다음 장으로 넘어가게 하려는 것이다.
5. text가 있으면 `speaker.speak(text, voice_ids.get(voice_var), speed_var, tag=token, output_id=output.id 또는 None)`을 부르고 "읽는 중" 상태를 띄운다.
</behavior>

<behavior name="read_current">
- 이미 읽는 중이면 아무것도 하지 않는다.
- deck이 없으면 안내 문구만 띄운다.
- 그 밖에는 `speak_slide(current)`를 부른다.
</behavior>

<behavior name="stop(message='정지했습니다.')">
1. 읽는 중이었는지 기억해 둔다.
2. token을 1 올리고, reading을 None으로, `_mark_reading(None)`을 부른다.
3. `speaker.stop()`을 부른다.
4. 읽는 중이었고 message가 비어 있지 않을 때만 상태 표시줄에 message를 띄운다.
</behavior>

<behavior name="_on_read_finished(tok, completed, quiet=False)">
1. reading이 None이거나 그 token이 tok과 다르면 아무것도 하지 않는다. 이미 다른 장을 읽기 시작했거나 정지한 뒤에 늦게 온 이벤트다.
2. reading을 None으로, `_mark_reading(None)`을 부른다.
3. completed가 아니면 여기서 끝낸다.
4. 자동 발표가 꺼져 있으면, quiet가 아닐 때만 "다 읽었습니다"를 띄우고 끝낸다.
5. 자동 발표가 켜져 있으면 `nxt = _next_index(i)`를 구한다. 숨긴 장은 건너뛴다.
   - nxt가 없으면 "마지막 슬라이드까지 모두 읽었습니다."를 띄운다.
   - 있으면 `select(nxt, sync_ppt=True)`를 하고 `speak_slide(nxt)`를 부른다.
</behavior>

<behavior name="_mark_reading(i)">
1. 처음 불릴 때 Listbox의 원래 selectbackground와 selectforeground를 기억해 둔다.
2. 모든 항목의 배경을 ""로 되돌리고, i 항목만 READING_BG로 칠한다.
3. 읽는 장은 보통 선택된 장이기도 해서 파란 선택 색에 노란 표시가 가린다. 그래서 i == current일 때는 선택 색도 READING_BG(글자 black)로 바꾸고, 아니면 원래 색으로 되돌린다.
4. play 버튼 글자를 "● 읽는 중" 또는 "▶ 읽기"로 바꾼다.
</behavior>

<behavior name="_on_space">
- 이벤트가 난 위젯이 tk.Text, tk.Entry, ttk.Entry, tk.Button, ttk.Button, ttk.Checkbutton, tk.Checkbutton 중 하나면 아무것도 하지 않는다. 버튼은 자체 스페이스 바인딩이 있어서 두 번 동작하게 된다.
- 그 밖에는 읽는 중이면 stop, 아니면 read_current를 부르고 "break"를 돌려준다.
</behavior>

<behavior name="open_file(path, keep_position=False) -> bool">
1. 확장자가 .ppt, .pps, .key면 경고 대화상자를 띄우고 False를 돌려준다.
2. load_deck에서 예외가 나면 오류 대화상자를 띄우고 False를 돌려준다.
3. `_commit_edit()`을 부르고 `stop(message="")`로 조용히 멈춘다.
4. 다른 파일이면 edits를 비운다. 같은 파일을 다시 읽는 경우에는 고친 대본을 남겨 둔다.
5. 시작 위치는 keep_position이면 current, 아니면 0이다.
6. deck과 mtime을 저장하고 Listbox를 다시 채운다. 각 항목은 `f" {s.number:>2}. {label[:30]}{mark}"`이다.
   - label은 `(title or body)`의 첫 줄이고, 비어 있으면 "(내용 없음)"
   - mark는 숨긴 장이면 "  (숨김)"
7. 창 제목을 `f"{deck.name} - {APP_TITLE}"`로 바꾼다.
8. `current = -1`로 두고 시작 위치를 범위 안으로 맞춰 select한다.
9. "불러옴" 상태를 띄우고 True를 돌려준다.
</behavior>

<behavior name="select(i, user=False, sync_ppt=False)">
1. deck이 없거나 i가 범위 밖이면 `_show_slide()`만 부른다.
2. i가 current와 다르면 먼저 `_commit_edit()`을 부른다.
3. current를 i로 바꾸고 Listbox에서 selection_clear, selection_set, **activate**, see를 한다. activate를 빼면 스페이스바가 예전 active 항목을 다시 선택해 버린다.
4. `_show_slide()`를 부른다.
5. user가 True면 stop을 부른다.
6. user나 sync_ppt가 True이고, 연동 중이며 `ppt_state.mode == "show"`면 `link.goto_slide(slide.number)`를 부른다.
목록 클릭(`<<ListboxSelect>>`에서 선택이 current와 다를 때)과 이전/다음 버튼은 `user=True`로 부른다.
</behavior>

<behavior name="대본 편집">
- `_script_for(i)`: 그 장의 번호가 edits에 있으면 고친 대본을, 없으면 `slide.script(source_key)`를 돌려준다. source_key는 `SOURCES[max(source_box.current(), 0)][0]`이다.
- `_show_slide()`:
  1. Text를 비운다.
  2. 장이 없으면 header를 "PPT 파일을 열어 주세요"로 바꾸고 첫 화면 안내를 띄운다.
  3. 장이 있으면 header를 `f"슬라이드 {n} / {N}"`로 바꾸고, 제목이 있으면 `f"  ·  {제목 첫 줄}"`을 덧붙인다. 대본을 넣고, 고친 장이면 edited_label에 "✎ 고친 대본"을 띄운다.
  4. 마지막에 `edit_modified(False)`와 `edit_reset()`을 부른다.
- `_commit_edit()`: Text가 수정된 경우에만 동작한다.
  - 내용을 strip한 값이 원래 대본을 strip한 값과 같으면 edits에서 그 장을 지운다.
  - 다르면 edits에 저장한다.
  - 수정 플래그를 끄고 edited_label을 갱신한다.
- [원래 내용으로]: edits에서 현재 장을 지우고 `_show_slide()`를 부른다.
- 읽을 내용 Combobox가 바뀌면 `_commit_edit()`과 `_show_slide()`를 부른다.
</behavior>

<behavior name="toggle_link">
- 켤 때: PowerPointLink를 만든다. 상태 변화는 `events.put(("ppt", st))`, 오류는 `events.put(("ppt_error", msg))`로 넘긴다. LinkError가 나면 체크를 해제하고 오류 대화상자를 띄운다. 성공하면 ppt_state를 None으로 두고 link_label을 "PowerPoint 찾는 중..."으로 바꾼다.
- 끌 때: link를 close하고 None으로 둔다. ppt_state를 None으로, link_label을 ""로 바꾼다.
</behavior>

<behavior name="_on_ppt_state(st)" critical="true">
이 함수는 PowerPoint와 이 프로그램이 서로 장을 넘기면서도 같은 장을 두 번 읽지 않게 하는 핵심이다. 아래 순서대로 구현한다.
```
prev = ppt_state; ppt_state = st; first = (prev is None)      # 연동 직후 첫 상태는 화면만 맞춘다
if st.mode == "none": link_label = "PowerPoint에 열린 발표 자료가 없습니다"; return
link_label = f"{'슬라이드 쇼' if show else '편집 화면'} · {st.index or '-'}번 · {basename(st.path)}"
if prev and prev.mode == "show" and st.mode != "show": stop(message="슬라이드 쇼가 끝나서 읽기를 멈췄습니다.")
loaded = _follow_file(st.path)                 # True=새로 불러옴, False=이미 열림, None=실패
if loaded is None or st.index is None or deck is None: return
i = st.index - 1
entered_show = st.mode == "show" and (prev is None or prev.mode != "show")
if i == current and not loaded and not entered_show: return   # 이 프로그램이 넘긴 장이라 이미 맞춰져 있음
select(i)                                       # user=False: PowerPoint로 다시 goto하지 않음
if st.mode != "show" or first or loaded: return # 편집 화면, 연동 직후, 파일을 새로 연 직후에는 읽지 않음
if read_on_change: speak_slide(i)               # 읽던 것을 끊고 새 장을 읽음
elif reading and reading[1] != i: stop()
```
- 슬라이드 쇼를 시작하면 entered_show 덕분에 첫 장을 읽는다. 편집 화면에서 이미 같은 장이 선택되어 있어도 마찬가지다.
- 자동 발표에서는 이 프로그램이 current를 먼저 바꾸고 goto를 보낸다. 그 뒤 PowerPoint가 따라오면서 생기는 이벤트는 `i == current`이므로 무시된다.
</behavior>

<behavior name="_follow_file(ppt_path) -> True|False|None">
1. `local = resolve_local_path(ppt_path)`를 구한다.
2. local이 None일 때:
   - 이미 연 파일과 이름이 같으면(대소문자 무시) False를 돌려준다. 경로는 몰라도 같은 이름의 파일을 이미 열어 둔 경우다.
   - 아니면 "파일 위치를 알 수 없습니다" 상태를 띄우고 None을 돌려준다.
3. local이 이미 연 파일과 같은 경로일 때(normcase와 abspath로 비교):
   - mtime이 바뀌었으면 `open_file(local, keep_position=True)`로 다시 읽고, 성공하면 "다시 불러왔습니다" 상태를 띄운다.
   - 어느 쪽이든 False를 돌려준다.
4. 그 밖에는 `open_file(local)`이 성공하면 True, 실패하면 None을 돌려준다.
</behavior>

<behavior name="_pump (50ms마다)">
events를 비울 때까지 꺼내서 처리하고, 다시 `after(50)`을 예약한다.
- ("tts", "done") → `_on_read_finished(tag, bool(info))`
- ("tts", "error") → `_on_read_finished(tag, False)`를 부른 뒤 "음성 재생 오류" 상태를 띄운다
- ("tts", "start") → 아무것도 하지 않는다
- ("ppt", st) → link가 있을 때만 `_on_ppt_state(st)`
- ("ppt_error", msg) → link가 있을 때만 link_label을 "연동 문제 발생"으로 바꾸고 상태 표시줄에 msg를 띄운다
</behavior>

<behavior name="quit">
1. `_commit_edit()`
2. 설정을 SETTINGS_FILE에 저장한다. 키는 source, voice, output(`{"id", "name"}` 또는 null), speed(round 2), auto_next, read_on_change, topmost이고, `json.dumps(ensure_ascii=False, indent=2)`, utf-8로 쓰며 OSError는 무시한다.
3. link.close(), speaker.close(), root.destroy()
설정을 읽을 때 OSError나 ValueError가 나면 빈 dict를 쓴다.
</behavior>

<behavior name="run(initial_path)">
1. Windows면 `ctypes.windll.shcore.SetProcessDpiAwareness(1)`을 부르고, 실패는 무시한다.
2. `tk.Tk()`를 만들고 TkDefaultFont의 글꼴을 설정한다.
3. `App(root, initial_path)`를 만들고 mainloop를 돈다.
</behavior>
</app_logic>
</module>

<module name="ppt_reader/__main__.py">
argparse(prog "ppt_reader", description "PPT 발표 자료를 소리 내어 읽어 주는 프로그램")를 쓴다.
옵션: 위치 인자 file(선택), --list-voices, --list-outputs, --dump, --say, --slide N, --source {notes_first,body,notes,both}(기본 notes_first), --voice 이름 일부, --output 장치 이름 일부, --speed(기본 1.0), --probe-ppt.
시작할 때 stdout과 stderr를 utf-8로 reconfigure한다(실패는 무시). Windows 콘솔에서 한글이 깨지지 않게 하려는 것이다.

| 옵션 | 동작 |
|---|---|
| --list-voices | 음성마다 `f"{'*' if v.is_korean else ' '} {v.name}  [{v.lang}]"`를 출력한다 |
| --list-outputs | 장치마다 `f"{'*' if 기본 장치 else ' '} {o.name}"`를 출력하고, 기본 장치를 알면 마지막에 `(* = 지금 기본 출력 장치)`를 출력한다 |
| --dump | file이 없으면 `p.error("파일을 지정하세요.")`. 장마다 `f"===== 슬라이드 {n}{' (숨김)' if hidden else ''} : {title}"`를 출력하고, 다음 줄에 `to_speech(script)`를 출력한다. 대본이 비었으면 "(읽을 내용 없음)" |
| --say | 소리 내어 읽는다. --voice가 있으면 이름에 그 문자열이 들어간 음성(대소문자 무시)을 찾고, 없으면 `"'{voice}' 음성을 찾지 못해 기본 음성으로 읽습니다."`를 출력한다. --voice가 없으면 첫 한국어 음성을 쓴다. --output이 있으면 이름에 그 문자열이 들어간 장치(대소문자 무시)를 찾고, 없으면 `"'{output}' 출력 장치를 찾지 못해 기본 장치로 읽습니다. (--list-outputs 로 확인)"`를 출력한다. 장마다 `f"[{n}] {text}"`를 출력하고, 같은 tag의 done 이벤트가 올 때까지 기다린다. error가 오면 "오류:"를 출력하고 1을 돌려준다. Ctrl+C면 stop하고, 마지막에는 항상 close한다 |
| --slide N | --dump와 --say에서 그 번호의 장만 처리한다 |
| --probe-ppt | PowerPointLink를 만들고 첫 이벤트를 15초 동안 기다린 뒤 close한다. 결과에 따라 다음 중 하나를 출력한다: `"상태: {mode}, 슬라이드: {index}, 경로: {path!r}"`와 `"이 컴퓨터의 파일: {resolve_local_path(path)}"` / `"연동 오류: ..."` / `"연동 불가: ..."` / `"15초 안에 PowerPoint 응답이 없습니다."` |
| (옵션 없음) | `app.run(file)` |
</module>
</module_specs>

<ui_strings>
아래 문구를 글자, 띄어쓰기, 문장부호까지 그대로 쓴다. `{}`는 값이 들어가는 자리다.

| 위치 | 문구 |
|---|---|
| 창 제목 | `PPT 읽어주기` / 파일을 연 뒤 `{파일명} - PPT 읽어주기` |
| 파일 대화상자 | 제목 `발표할 PPT 파일 선택`, 형식 `("PowerPoint 프레젠테이션", "*.pptx *.pptm")`, `("모든 파일", "*.*")` |
| 첫 화면 header | `PPT 파일을 열어 주세요` |
| 첫 화면 상태 | `[파일 열기]로 발표 자료(.pptx)를 불러오거나, PowerPoint에 띄워 두고 [PowerPoint 연동]을 켜세요.` |
| 불러옴 | `'{파일명}' 불러옴: 슬라이드 {N}장 (발표자 노트 있는 장 {k}개). [▶ 읽기] 또는 스페이스바를 누르세요.` |
| 읽는 중 | `{n}번 슬라이드를 읽는 중...  (정지: Esc)` (공백 두 칸) |
| 빈 장 | `{n}번 슬라이드에는 읽을 내용이 없습니다.` |
| 다 읽음 | `{n}번 슬라이드를 다 읽었습니다.` |
| 끝 | `마지막 슬라이드까지 모두 읽었습니다.` |
| 정지 | `정지했습니다.` |
| 파일 없이 읽기 | `먼저 [파일 열기]로 PPT 파일을 불러오거나 [PowerPoint 연동]을 켜세요.` |
| 한국어 음성 없음 | `한국어 음성이 설치되어 있지 않습니다. README의 '한국어 음성 설치'를 참고하세요.` |
| 음성 오류 | `음성 재생 오류: {info}` |
| 옛 형식 경고 | `'{파일명}' 형식은 읽을 수 없습니다.\nPowerPoint에서 [다른 이름으로 저장] → .pptx 로 저장한 뒤 여세요.` |
| 열기 실패 | `파일을 열 수 없습니다.\n{경로}\n\n{예외}` |
| 출력 장치 목록 | `시스템 기본 장치` / `시스템 기본 장치 (지금: {장치 이름})` / `{장치 이름} (연결 안 됨 - 기본 장치로 읽음)` |
| 출력 장치 바꿈 | `이제 '{장치 이름 또는 시스템 기본 장치}'(으)로 읽습니다. 다음에 읽을 때부터 적용됩니다.` |
| 연동 라벨 | `PowerPoint 찾는 중...` / `PowerPoint에 열린 발표 자료가 없습니다` / `{슬라이드 쇼|편집 화면} · {번호 또는 -}번 · {파일명}` / `연동 문제 발생` |
| 쇼 종료 | `슬라이드 쇼가 끝나서 읽기를 멈췄습니다.` |
| 경로 모름 | `PowerPoint의 '{파일명}' 파일 위치를 알 수 없습니다. 파일을 저장했는지 확인하거나 [파일 열기]로 같은 파일을 직접 여세요.` |
| 다시 불러옴 | `PowerPoint에서 저장한 내용을 다시 불러왔습니다.` |
| 편집 표시 | `✎ 고친 대본` |
| 목록 항목 | `" {번호:>2}. {라벨[:30]}"`, 숨긴 장은 끝에 `"  (숨김)"`, 빈 장 라벨은 `(내용 없음)` |
| 버튼, 체크박스 | `파일 열기...`, `PowerPoint 연동`, `항상 위`, `◀ 이전`, `▶ 읽기`, `● 읽는 중`, `■ 정지`, `다음 ▶`, `원래 내용으로`, `다 읽으면 다음 장으로 넘어가기 (자동 발표)`, `슬라이드 쇼에서 장을 넘기면 바로 읽기` |
| 라벨 | `읽을 내용`, `목소리`, `출력 장치`, `속도`, `{v:.1f}배`, `읽을 대본 (여기서 고치면 고친 대로 읽습니다)` |
</ui_strings>

<sample_deck file="tools/make_sample.py">
python-pptx 기본 템플릿을 쓰고 슬라이드 크기는 13.333 x 7.5인치다. `sample/sample_presentation.pptx`에 저장하고 `만들었습니다: {경로}`를 출력한다. 등장인물 이름은 실존 인물로 오해받지 않게 "홍길동"을 쓴다.

| 장 | 레이아웃 | 내용 | 발표자 노트 |
|---|---|---|---|
| 1 | 0 (제목) | 제목 `인공지능과 우리의 학교생활`, 부제 `컴퓨터 과목 발표 · 2학년 3반 홍길동` | `안녕하세요. 오늘은 인공지능이 우리의 학교생활을 어떻게 바꾸고 있는지 발표하겠습니다.` |
| 2 | 1 (제목+내용) | 제목 `인공지능이란?`, 문단 3개: `사람처럼 배우고 판단하는 컴퓨터 프로그램` / `데이터에서 규칙을 스스로 찾아냄` / `번역, 음성 인식, 그림 그리기 등에 활용` | `인공지능은 사람처럼 배우고 판단하는 컴퓨터 프로그램입니다.\n많은 데이터를 보고 스스로 규칙을 찾아낸다는 점이 일반 프로그램과 다릅니다.` |
| 3 | 5 (제목만) | 제목 `학교에서 쓰이는 예`, 표 3x2(위치 1in,2in / 크기 11in x 2.5in): (분야, 예시), (수업, AI 튜터, 자동 채점), (생활, 급식 메뉴 추천, 번역기) | 없음 (노트 우선이면 본문을 읽는지 확인하는 용도) |
| 4 | 1, **숨김** (`show="0"`) | 제목 `(예비) 질문 대비 자료`, 본문 `인공지능이 틀릴 때는 어떻게 하나요?` | 없음 |
| 5 | 6 (빈 화면) | 글상자 (1,1,5,2)in: `좋은 점` + `• 궁금한 것을 바로 물어볼 수 있다` / 글상자 (7,1,5,2)in: `주의할 점` + `• 답이 항상 맞지는 않다`. 두 글상자 모두 첫 run 28pt | `인공지능은 편리하지만 답이 항상 맞는 것은 아닙니다. 꼭 다시 확인하는 습관이 필요합니다.` |
| 6 | 0 | 제목 `감사합니다`, 부제 `질문 있으신가요?` | `지금까지 발표를 들어 주셔서 감사합니다. 궁금한 점이 있으면 질문해 주세요.` |

`python -m ppt_reader --dump sample/sample_presentation.pptx`를 실행하면 3번 장은 다음처럼 나와야 한다.
```
===== 슬라이드 3 : 학교에서 쓰이는 예
학교에서 쓰이는 예.
분야, 예시.
수업, AI 튜터, 자동 채점.
생활, 급식 메뉴 추천, 번역기.
```
`--source body --slide 5`로 실행하면 `좋은 점.` / `궁금한 것을 바로 물어볼 수 있다.` / `주의할 점.` / `답이 항상 맞지는 않다.`가 이 순서로 나와야 한다. 글상자 하나를 다 읽은 뒤 다음 글상자로 넘어가는지 확인하는 용도다.
</sample_deck>

<tests>
<file name="tests/test_slides.py">
각 테스트 파일은 `sys.path`에 프로젝트 루트를 넣어서 import한다.
- fixture deck_path: tmp_path에 두 장짜리 pptx를 만든다.
  - 1장(레이아웃 1): 제목 "제목", 본문 "첫 줄\n둘째 줄", 노트 "노트 대본입니다."
  - 2장(레이아웃 6): 글상자를 일부러 "오른쪽"(5,1), "아래"(1,4), "왼쪽"(1,1) 순서로 만든다(단위 인치). 표 2x2를 (1,6)에 둔다: (0,0)="가", (0,1)="나", (1,0)="다". 이 장은 숨긴다.
- test_load_deck:
  - 1장 body == "제목\n첫 줄\n둘째 줄", notes == "노트 대본입니다.", 숨기지 않음
  - 2장 body == "왼쪽\n오른쪽\n아래\n가, 나\n다", notes == "", 숨김
- test_script_sources:
  - `Slide(1, title="T", body="T\n본문", notes="노트")`에서 네 가지 source의 결과를 확인한다. "both"는 `"T\n본문\n\n노트"`
  - `Slide(2, body="본문만").script("notes_first") == "본문만"`
- test_to_speech:
  - `"• 첫째\n- 둘째\n\n셋째입니다.\n질문?"`는 `"첫째.\n둘째.\n셋째입니다.\n질문?"`
  - `"  \n \v "`는 `""`
  - `"줄\v바꿈"`은 `"줄.\n바꿈."`
- test_resolve_local_path:
  - 실제 파일이면 그 경로를, "Presentation1"이면 None을 돌려준다
  - 환경변수 OneDrive를 tmp_path로 두면 `https://d.docs.live.net/abc123/Docs/%EB%B0%9C%ED%91%9C.pptx`가 `tmp_path/Docs/발표.pptx`로 풀린다
</file>
<file name="tests/test_app_logic.py">
실제 소리와 PowerPoint를 쓰지 않는다.
- FakeSpeaker: voices는 en, ko 두 개다. 클래스 속성 `connected = [SPEAKERS("dev-speakers", "스피커(Realtek)"), EARPHONES("dev-earphones", "헤드폰(Shokz)")]`를 outputs로 돌려주고, default_output은 SPEAKERS다. speak 호출을 (text, tag, voice_id)로, output_id는 따로 outputs_used에 기록하고, stop 횟수를 센다.
- FakeLink: goto_slide 호출을 기록한다.
- fixture app:
  - 예제 pptx가 없으면 skip한다.
  - `app_mod.Speaker`를 FakeSpeaker로, `SETTINGS_FILE`을 tmp_path로 monkeypatch한다. 사용자 홈의 설정 파일을 건드리지 않기 위해서다.
  - 보조 함수 `make_app()`이 `tk.Tk()`를 만들고(TclError면 skip) withdraw한 뒤 예제를 연 App을 돌려준다. fixture는 이것을 쓴다.
  - 정리할 때 `root.destroy()`의 TclError는 무시한다(테스트 안에서 quit으로 이미 닫았을 수 있다).
- 보조 함수 `finish(a)`: 마지막 speak의 tag로 `_on_read_finished(tag, True)`를 부른다.
- test_open_and_read:
  - 장 6개, current 0, 기본 음성 표시 이름이 "Korean"으로 시작, Text에 "발표하겠습니다"가 들어 있다
  - 읽으면 "안녕하세요"로 시작하는 글을 voice "ko"로 읽는다
  - finish한 뒤 reading은 None, current는 그대로 0이다
- test_auto_next_skips_hidden: 자동 발표를 켜고 읽으면서 finish를 반복한다. 방문한 위치는 `[0, 1, 2, 4, 5, 5]`이고, 끝나면 reading은 None이다.
- test_edit_is_used:
  - 2번 장에서 대본을 "에이아이는 인공지능입니다"로 바꾸고 3번 장으로 가면 `edits == {2: "에이아이는 인공지능입니다"}`
  - 2번 장을 읽으면 `"에이아이는 인공지능입니다."`를 읽는다
  - stop하고 reset_edit하면 edits가 비어 있다
- test_powerpoint_follow:
  - edit(2): current 1, 아직 읽지 않음
  - show(2): "인공지능은"을 읽는다
  - show(3): current 2, "학교에서"를 읽는다
  - 자동 발표를 켜고 finish: current 4, `gotos == [5]`
  - show(5): 다시 읽지 않는다(speak 횟수가 그대로)
  - `select(0, user=True)`: `gotos == [5, 1]`, 읽기 멈춤
  - read_current를 한 뒤 edit(1): 읽기 멈춤
- test_output_device:
  - 출력 장치 목록 첫 항목은 `"시스템 기본 장치 (지금: 스피커(Realtek))"`이고 그것이 골라져 있다. 읽으면 output_id는 None이다
  - "헤드폰(Shokz)"를 고르고 `_on_output_change()`, stop 후 읽으면 output_id는 "dev-earphones"다
  - quit한 뒤 `FakeSpeaker.connected`를 `[SPEAKERS]`로 바꾸고(monkeypatch) make_app으로 다시 띄우면 `"헤드폰(Shokz) (연결 안 됨 - 기본 장치로 읽음)"`이 골라져 있고, 읽으면 output_id는 여전히 "dev-earphones"다
- test_powerpoint_unknown_file:
  - show(1, "Presentation1"): 상태에 "위치를 알 수 없습니다"가 들어 있다
  - show(2, `https://d.docs.live.net/x/` + 예제 파일명): 이름이 같으므로 current가 1이 된다
</file>
</tests>

<launchers_and_packaging>
<file name="requirements.txt">
```
python-pptx>=1.0
pywin32>=306; sys_platform == "win32"
```
</file>
<file name="run_windows.bat">
- 문구는 영어 ASCII만 쓰고 줄바꿈은 CRLF로 저장한다. UTF-8 한글이 든 배치 파일은 cmd에서 깨지고, LF만 쓰면 goto 레이블이 오작동한다.
- `cd /d "%~dp0"`로 스크립트가 있는 폴더로 이동한다.
- `.venv\installed.ok`가 있으면 바로 실행 단계로 간다.
- 없으면 venv를 만든다. `py`가 있으면 `py -3 -m venv .venv`, 없으면 `python -m venv .venv`를 쓴다. python.exe가 생기지 않았으면 python.org 안내를 하고 "Add python.exe to PATH" 체크를 안내한 뒤 pause하고 종료한다.
- `pip install --disable-pip-version-check -r requirements.txt`가 실패하면 인터넷 안내를 하고 pause하고 종료한다.
- 성공하면 marker 파일 `installed.ok`를 만든다.
- 실행은 `start "" ".venv\Scripts\pythonw.exe" main.py %*`다(콘솔 창이 남지 않게).
</file>
<file name="run_mac.sh">
- `#!/bin/bash`로 시작하고 LF로 저장한다. 안내 문구는 한국어다.
- `cd "$(dirname "$0")"`로 스크립트가 있는 폴더로 이동한다.
- python3가 없으면 python.org 안내를 하고 종료한다.
- `python3 -c "import tkinter; tkinter.Tk().destroy()"`가 실패하면 python.org 설치나 `brew install python-tk`를 안내하고 종료한다.
- `.venv/installed.ok`가 없으면 venv를 만들고 pip install을 한다. 실패하면 안내하고 종료하고, 성공하면 touch로 marker를 만든다.
- 실행은 `exec .venv/bin/python main.py "$@"`다.
</file>
<file name="ppt_reader.spec">
- `Analysis(["main.py"], datas=collect_data_files("pptx"), hiddenimports=["win32timezone"] if win32 else [])`
- PYZ와 EXE(exclude_binaries=True, name="PPTReader", console=False), COLLECT(name="PPTReader")로 onedir 빌드를 만든다.
- darwin이면 `BUNDLE(name="PPTReader.app", bundle_identifier="local.pptreader")`도 만든다. info_plist에 다음 세 키를 넣는다.
  - `CFBundleDisplayName: "PPT 읽어주기"`
  - `NSHighResolutionCapable: True`
  - `NSAppleEventsUsageDescription: "PowerPoint에서 지금 보이는 슬라이드를 알아내고 넘기기 위해 필요합니다."`
  마지막 키가 없으면 macOS가 자동화 권한을 묻지 않고 바로 거부한다.
- 특정 기관을 사칭하는 bundle id는 쓰지 않는다.
</file>
</launchers_and_packaging>

<readme>
README.md는 한국어로 쓰고 다음 섹션을 이 순서로 둔다.
1. 한 줄 소개: Windows와 macOS에서 같은 코드로 동작하며 인터넷 없이 읽는다는 점
2. 할 수 있는 것: 표로 정리한다(파일 읽기 순서 규칙, 읽을 내용 4가지, 대본 고치기, PowerPoint 연동, 자동 발표, 목소리와 속도, 출력 장치)
3. 실행하기: Python 3.9 이상 설치와 PATH 체크, Windows bat 더블클릭, macOS `bash run_mac.sh`(python.org 권장, Homebrew면 python-tk), 직접 실행 명령
4. 사용 방법: (1) 파일만 열어서 읽기, (2) PowerPoint 연동 5단계, 저장해야 반영된다는 점, 단축키 표
5. 한국어 음성 설치: Windows는 설정 → 시간 및 언어 → 음성 → 음성 추가, macOS는 손쉬운 사용 → 읽기 및 말하기 → Yuna
6. macOS 권한: 자동화 허용 방법과 거부했을 때 다시 켜는 위치
7. 실행 파일 만들기: OS별로 따로 빌드한다는 점, dist 결과물, 서명하지 않은 Mac 앱은 오른쪽 클릭 → 열기
8. 문제 해결 표(이어폰을 꽂았는데 스피커로 나오는 경우 포함)와 명령줄 도구(--list-voices, --list-outputs, --dump, --say, --probe-ppt)
9. 구조: 파일 트리와 스레드 구성, 확인 주기(0.4초, 0.7초)
</readme>

<known_pitfalls>
기준 구현을 만들면서 실제로 겪었거나 미리 막은 문제들이다. 하나도 빼지 말고 반영한다.
1. pywin32 동적 디스패치는 PowerPoint가 바쁘면 com_error 대신 AttributeError를 던진다. poll에서 둘 다 잡고, 폴링 루프 바깥쪽에서 모든 예외를 다시 잡아서 연동 스레드가 죽지 않게 한다.
2. PowerPoint COM 객체를 저장해 두지 않는다(프로세스가 남는다). COM 객체를 스레드 사이에 넘기지 않는다.
3. 장을 넘길 때는 GotoSlide를 쓴다. Next는 애니메이션만 진행시킬 수 있다.
4. 폴러는 상태가 바뀔 때만 알리고, 화면은 이미 current인 장의 이벤트를 무시한다. 둘 중 하나라도 빠지면 자동 발표에서 같은 장을 두 번 읽거나 이전 장으로 되돌아간다.
5. token으로 늦게 도착한 done 이벤트를 무시한다. 이것이 없으면 정지한 뒤에도 자동 발표가 다음 장으로 넘어간다.
6. 창 크기를 고정 픽셀로 정하지 않는다. 화면 배율이 높으면 아래쪽 막대가 잘린다.
7. root의 스페이스바 바인딩은 버튼의 자체 스페이스 동작과 겹친다. 위젯 종류로 걸러 내고, Listbox는 activate로 active 항목을 맞춘다.
8. 이모지(BMP 밖 문자)를 쓰지 않는다. Tk 8.6에서 깨진다.
9. SAPI에는 SVSFIsNotXML을 준다. say에는 "-"로 시작하는 본문을 그대로 넘기지 않는다.
10. OneDrive 파일은 FullName이 URL이다. 동기화 폴더에서 찾고, 그래도 못 찾으면 파일 이름으로 맞춘다.
11. python-pptx의 `slide.notes_slide`는 노트가 없으면 새로 만든다. 반드시 `has_notes_slide`부터 확인한다.
12. macOS에서는 osascript를 부르기 전에 PowerPoint가 설치되어 있는지 확인한다. 자동화 권한 오류(-1743)는 사용자가 따라 할 수 있는 안내 문구로 바꿔서 보여 준다.
13. 테스트와 검증 스크립트는 사용자 홈의 설정 파일을 덮어쓰지 않는다. SETTINGS_FILE을 임시 경로로 바꿔서 실행한다.
14. SAPI(SpVoice)는 Windows의 기본 출력 장치를 따라가지 않고 출력 목록의 첫 장치로 읽는다. 이어폰을 기본 장치로 해 둬도 스피커로 나온다. 읽을 때마다 고른 장치, 없으면 Windows의 지금 기본 장치(IMMDeviceEnumerator, eRender/eConsole)를 찾아 `AudioOutput`에 직접 지정한다. Windows의 '기본 통신 장치'는 eConsole과 다를 수 있으니 혼동하지 않는다.
15. 화면 캡처로 검증할 때는 앱 창을 `-topmost`로 띄우고 창 영역만 찍는다. 창 밖까지 찍으면 사용자의 다른 창(메신저 등)이 찍힌다.
</known_pitfalls>

<workflow>
아래 순서로 작업한다. 단계마다 실제로 실행해서 확인한 뒤 다음 단계로 넘어간다.
1. 환경을 확인한다.
   - Python 버전
   - Windows라면 설치된 음성: 레지스트리 `HKLM\SOFTWARE\Microsoft\Speech\Voices\Tokens`와 `...\Speech_OneCore\Voices\Tokens`
   - PowerPoint 설치 여부와 지금 실행 중인지
   - 프로젝트 안에 `.venv`를 만들고 python-pptx, pywin32, pytest를 설치한다
2. slides.py, tts.py, link.py, app.py, __main__.py, __init__.py, main.py, requirements.txt를 작성한다.
3. 예제 생성기를 실행한다. `--dump`와 `--list-voices` 출력이 <sample_deck>의 기대값과 같은지 확인한다.
4. 테스트 10개를 작성하고 `python -m pytest -q tests`를 실행한다. 10개 모두 통과해야 한다.
5. 실제 음성을 짧게 확인한다(소리가 나므로 짧은 문장 하나로 한정한다).
   - `--say ... --slide 6 --speed 1.5`가 끝까지 읽고 종료되는지 본다.
   - 긴 문장을 읽다가 stop하면 0.2초 안에 done(False)가 오는지 본다.
   - 연달아 speak하면 이벤트가 start(a) → done(a, False) → start(b) → done(b, True) 순서로 오는지 본다.
   - Windows라면 `--list-outputs`의 `*`가 소리 설정의 기본 장치와 같은지 보고, 소리를 내지 않고 `_set_output`만 불러 지정한 장치 / None(기본 장치) / 없는 장치(기본 장치로 돌아감)에서 `AudioOutput.GetDescription()`이 맞는지 확인한다.
6. PowerPoint가 있으면 실제 연동을 확인한다. 사용자 화면을 가리지 않도록 다음처럼 한다.
   - PowerPoint가 원래 실행 중이었다면 사용자 문서가 있을 수 있으니 건드리지 않는다.
   - 연동 시험을 할 때는 내가 PowerPoint를 직접 띄운다. 예제를 열고 앱 창을 최소화한다(WindowState=2).
   - 슬라이드 쇼는 창 모드로 실행한다(`SlideShowSettings.ShowType = 2`).
   - 기대하는 상태 변화: edit(2) → show(1) → goto 3 → Next 시 숨긴 4번을 건너뛰고 5 → 끝의 검은 화면에서 index None → 쇼 종료 후 edit
   - 시험이 끝나면 내가 띄운 PowerPoint만 종료한다.
7. 실제 화면, 실제 음성, 실제 PowerPoint를 함께 돌리는 시나리오를 실행하고 화면을 캡처해서 레이아웃이 잘리지 않는지 눈으로 확인한다. 캡처는 PIL.ImageGrab로 창 영역만 하고, 설정 파일 경로는 임시로 바꾼다.
8. run_windows.bat, run_mac.sh, ppt_reader.spec, .gitignore, .gitattributes, README.md를 작성한다. 줄바꿈이 bat은 CRLF, sh는 LF인지 확인한다.
9. 이번 OS에서 PyInstaller로 빌드한다(dist와 build는 임시 폴더로 지정). 만들어진 실행 파일이 예제 파일을 연 채로 뜨고, 창 제목이 맞고, 정상 종료되는지 확인한다. 이 과정에서 새로 생긴 사용자 설정 파일은 원래 없었다면 지운다.
10. __pycache__와 .pytest_cache를 정리한다.
</workflow>

<acceptance_criteria>
아래를 모두 만족해야 완료다.
- [ ] `python -m pytest -q tests`에서 10개가 통과한다
- [ ] `--dump` 출력이 <sample_deck>의 기대값과 같다(4번 장에 "(숨김)" 표시가 붙는다)
- [ ] 한국어 음성이 있는 Windows에서 `--list-voices` 첫 줄이 `*`로 시작하는 한국어 음성이고, OneCore에만 있는 같은 목소리는 중복으로 나오지 않는다
- [ ] 슬라이드 쇼를 시작하면 첫 장을 바로 읽는다. 자동 발표가 켜져 있으면 숨긴 장을 건너뛰며 끝까지 진행하고, 쇼를 끝내면 "슬라이드 쇼가 끝나서 읽기를 멈췄습니다."가 뜬다
- [ ] 같은 장을 두 번 읽는 일이 없다
- [ ] 이어폰을 Windows 기본 출력 장치로 두면 '시스템 기본 장치'에서 이어폰으로 읽고, 출력 장치 목록에서 고른 장치는 다음 실행에도 유지된다
- [ ] 화면 배율 100%와 150% 모두에서 아래쪽 체크박스와 상태 표시줄이 잘리지 않는다
- [ ] 이 프로그램이 띄운 PowerPoint 프로세스는 시험이 끝나면 남아 있지 않다
- [ ] PyInstaller 결과물이 실행되고 정상 종료된다
</acceptance_criteria>

<output_format>
작업을 마치면 한국어로 짧게 보고한다. 구성은 다음 순서를 따른다.
1. 만든 것: 기능을 한두 문장으로, 실행 방법을 한 줄로
2. 검증한 것: 실제로 실행해 본 항목과 그 결과. 숫자를 넣는다(통과한 테스트 수, 정지 반응 시간 등)
3. 시험 중에 찾아서 고친 문제
4. 확인하지 못한 것: 특히 "이 OS에서 실행하지 못한 플랫폼 코드"가 있으면 이 섹션의 맨 앞에 쓰고, 그 플랫폼에서 바로 확인할 수 있는 명령(`python main.py --probe-ppt`)을 함께 적는다
5. 알아 둘 제약(.ppt 미지원, 저장해야 반영됨 등)
확인하지 않은 것을 확인했다고 쓰지 않는다.
</output_format>

<non_goals>
다음은 만들지 않는다: 온라인 신경망 음성, 발음 사전, Keynote 연동, .ppt(구형 바이너리) 파싱, Linux 지원, 고친 대본을 파일로 저장하는 기능, 연동 설정 저장.
사용자가 요청하면 그때 추가한다.
</non_goals>

</prompt>
````
