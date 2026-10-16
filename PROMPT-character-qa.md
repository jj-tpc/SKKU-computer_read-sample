# 확장 프롬프트: 캐릭터와 질의응답

이 문서는 이 저장소의 「PPT 읽어주기」(`ppt_reader` v1.0.0)를 **확장**하기 위한 구현용 기획서이자 프롬프트입니다. 확장할 내용은 셋입니다.
- 마우스를 따라다니는 도트 강아지
- 화면 구석의 원 버튼
- LLM 질의응답

이 저장소를 연 코딩 에이전트(Claude Code 등)에게 아래 코드 블록 안의 내용 전체를 붙여 넣으세요. 사람이 읽어도 됩니다.

- 대상 에이전트: 이 저장소에서 파일 쓰기와 셸 실행이 가능한 코딩 에이전트
- 바탕: 지금 저장소의 `ppt_reader/`와 `PROMPT.md`(v1.0.0 명세). 이 문서에 없는 기존 동작은 `PROMPT.md`를 따른다.
- 결정의 근거
  - 기획 기록: `.scratch/character-qa/map.md`와 그 아래 일(issue) 20개
  - 조사 문서: `docs/research/`
  - 시제품: `prototype/*` 브랜치
  - 각 절의 `근거:`가 해당 기록을 가리킨다.
- 용어: 저장소 루트의 `CONTEXT.md`를 따른다(발표자, 청중, 대본, 자동 발표, 캡션, 캐릭터, 말풍선, 질의응답, 개인 지침, 원 버튼, 위성 버튼, 질문창, 대본 창, 알림 줄, 생각 깊이).
- `[보충]` 표시: 기획 기록에서 명시적으로 정하지 않아 이 문서를 쓰며 채운 세부다. 구현 전에 발표자가 훑어보고, 다르면 고친다.
- 프롬프트 구성: 역할 → 배경 → 목표 → 제약 → 범위 밖 → 구조 → 화면 명세 → 흐름 → 모듈 명세 → 화면 문구 → 시험 → 빌드와 넘기기 → 함정 → 작업 순서 → 완료 기준 → 보고 형식

````xml
<prompt version="2.0-character-qa">

<role>
당신은 데스크톱 GUI와 음성, LLM API 경험이 많은 Python 엔지니어다.
PySide6(Qt), Windows COM과 SAPI, macOS AppleScript와 pyobjc, Anthropic·OpenAI·Google의 공식 Python SDK를 실무 수준으로 다룬다.
명세를 글자 그대로 구현하고, 명세에 없는 기능은 추가하지 않는다. 직접 실행해서 확인한 것과 확인하지 못한 것을 구분해서 보고한다.
</role>

<context>
<scenario>
교실 발표에서 컴퓨터가 "AI 발표자" 역할을 한다.
- **발표자**(조작하는 학생)가 PowerPoint 쇼를 띄운다.
- 화면 위 **캐릭터**(붉은 목띠를 맨 도트 강아지)가 마우스 커서를 따라다니며 슬라이드의 **대본**을 읽는다.
- 발표가 끝나면 **청중**이 질문하고, 발표자가 그 질문을 키보드로 대신 입력한다. 캐릭터는 발표 자료를 먼저 근거로 삼고 일반 지식으로 보충해 말풍선과 목소리로 답한다.
- 사용자는 한국어 사용자(학생, 교사)다.
- 사용하는 PC는 인터넷에 연결되어 있다. 대본 읽기는 운영체제 음성이라 인터넷이 없어도 된다.
</scenario>
<platforms>
- Windows 10/11과 macOS 15(Sequoia) 이상의 Apple Silicon Mac에서 같은 소스로 동작해야 한다. Intel Mac과 Linux는 대상이 아니다.
- 개발자에게는 Mac이 없다. macOS는 GitHub Actions의 macOS 러너와 받는 사람(M1 Pro 맥북)의 확인표로만 확인한다. 그래서 macOS 전용 코드는 가장 적게 쓴다.
</platforms>
<why_these_choices>
- **툴킷은 PySide6(Qt)**: Mac 없이 macOS판을 넘겨야 한다. Qt는 반투명 창, 그리기, 한글 입력을 두 운영체제에서 같은 방식으로 해서, 확인하지 못하는 macOS 전용 코드가 가장 적다. tkinter는 버린다. 근거: 09, `docs/research/gui-toolkit.md`.
- **음성은 운영체제 음성을 미리 합성하고 Qt로 재생**: 파동과 강아지 입이 목소리 크기를 진짜로 따라가야 하고, 말풍선 글이 낱말 단위로 목소리를 따라 나와야 한다. 근거: 10, `docs/research/tts-signal-speed.md`, `docs/research/qt-audio-tts.md`.
- **LLM은 세 공식 SDK**: Claude, OpenAI, Gemini 중 설정에서 하나를 골라 질의응답과 캡션에 함께 쓴다. 근거: 03, 12, `docs/research/llm-providers.md`.
- **디자인 중심 컨셉은 오션·코랄**: 원 버튼, 위성 버튼, 말풍선은 코랄이고 바탕과 그림자는 바다색이다. 근거: 07, 15.
</why_these_choices>
</context>

<objective>
지금 저장소를 아래와 같이 확장한다. 결과물은 다음 여섯 가지다.
1. `ppt_reader` 패키지
   - 기존 tkinter 창을 없애고, 화면에는 강아지와 원 버튼만 둔다.
   - 설정 창과 대본 창은 원 버튼에서 연다.
   - 음성 흐름을 새로 만들고, LLM 질의응답과 캡션을 더한다.
2. 강아지 스프라이트 생성기 `tools/dog_sprites.py`와 그 결과물 `ppt_reader/assets/dog_{shiba,bichon,beagle}.png`
3. pytest 자동 테스트(<tests>)
4. GitHub Actions 빌드 워크플로, PyInstaller 설정, `licenses/`, 받는 사람용 안내문 두 개
5. 고친 `README.md`. `PROMPT.md`는 고치지 않는다.
6. 사람 확인표(<manual_checklists>)를 채운 결과 보고
</objective>

<hard_constraints>
- **Python 3.10 이상**에서 동작한다. 빌드는 Python 3.14로 한다. 모든 모듈 맨 위에 `from __future__ import annotations`를 둔다.
- **의존성**(`requirements.txt`):
  ```
  python-pptx>=1.0
  PySide6-Essentials==6.11.*
  PySide6-Addons==6.11.*
  anthropic>=1.15
  openai>=3.31
  google-genai>=2.31
  pywin32>=306; sys_platform == "win32"
  pyobjc-framework-Cocoa>=12.1; sys_platform == "darwin"
  ```
  - Pillow는 python-pptx를 따라 들어온다.
  - 개발용 `requirements-dev.txt`는 `-r requirements.txt`, `pytest`, `pytest-qt`, `pyinstaller`다.
  - numpy, sounddevice, pyttsx3, PyQt, tkinter 화면은 쓰지 않는다.
- **PySide6는 6.11.x에 고정**한다. 이유는 넷이다.
  - 음높이 유지 배속(`QMediaPlayer.pitchCompensation`)이 6.10 이상에만 있다.
  - Python 3.14에서는 6.10.1 이상만 깔린다.
  - Windows 10을 지원하는 마지막 판이 6.12다.
  - 바인딩의 최소 macOS가 6.10·6.11은 15, 6.12.0은 26이다.
- **화면 문구**:
  - 사용자에게 보이는 문구는 전부 한국어다. <ui_strings>에 있는 문구는 글자 그대로 쓴다.
  - Qt는 이모지를 그리므로 아이콘으로 써도 된다(📝 등). 다만 강아지가 소리 내어 말하는 글에는 이모지를 넣지 않는다.
- **주석과 docstring**: 한국어로 쓰고, "왜"를 설명할 때만 단다.
- **화면 스레드**: Qt 위젯은 주 스레드에서만 만진다. 일하는 스레드는 화면에 Qt 신호(queued connection)로 알린다. 화면에서 일하는 스레드로는 명령 큐(`queue.Queue`)를 쓴다.
- **COM 객체**: 만든 스레드에서만 쓴다. 스레드 사이에는 문자열이나 숫자만 넘긴다(기존 원칙 그대로).
- **API 키**: 설정 파일에 평문으로 저장한다. 키를 로그, 오류 문구, 알림 줄, 테스트 출력에 찍지 않는다.
- **`ui/` 밖의 모듈은 Qt 화면을 import하지 않는다.** 예외는 둘이다. 소리 재생(`voice/player.py`)은 QtMultimedia를 쓰고, 일하는 스레드는 QtCore의 신호를 써도 된다. 그래야 화면 없이 pytest로 시험할 수 있다.
</hard_constraints>

<non_goals>
다음은 만들지 않는다. 사용자가 요청하면 그때 추가한다.
- 마이크로 질문 받기(질문은 발표자가 키보드로 입력한다)
- 클라우드 음성 합성. 다만 음성 엔진을 나중에 끼워 넣을 수 있게 `voice/engines.py`의 경계를 둔다.
- 질의응답 자동 시작, 발표 중간 질문
- 기능별로 다른 LLM 쓰기, 실패 시 다른 제공자로 자동 전환
- 키를 숨기는 서버, 운영체제 키체인 저장
- 도표 값과 SmartArt 글을 꺼내 대본이나 근거에 넣기
- 꺼내지 못한 그림이 있는 슬라이드를 PowerPoint로 통째 내보내 보충하기(`Slide.Export`)
- 전역 단축키(창이 없으므로 기존의 스페이스바, F5 같은 단축키는 없어진다)
- Intel Mac, Linux, 코드 서명과 공증
근거: map.md "Out of scope", 11.
</non_goals>

<project_structure>
```
main.py                     그대로. ppt_reader.__main__.main()
requirements.txt            <hard_constraints>대로
requirements-dev.txt
ppt_reader.spec             PyInstaller 설정 (<build_and_handoff>)
README.md                   고침
PROMPT.md                   고치지 않음 (v1.0.0 tkinter 명세)
PROMPT-character-qa.md      이 문서
CONTEXT.md                  용어집
licenses/                   의존성 라이선스 원문
handoff/                    받는 사람용 안내문: windows.txt, macos.txt
.github/workflows/build.yml 손으로 누를 때만 도는 빌드
tools/dog_sprites.py        강아지 스프라이트 생성기 (prototype/dog-sprites의 생성기를 정식으로 옮김)
tools/make_sample.py        그대로
ppt_reader/
  __init__.py               __version__ = "2.0.0"
  __main__.py               명령줄. 옵션이 없으면 Qt 화면. --self-check 추가
  slides.py                 그대로 (대본 뽑기)
  link.py                   그대로 (PowerPoint 연동 스레드)
  settings.py               설정 파일, 고친 대본 저장, 옛 설정 옮기기
  session.py                상태 묶음: 읽기 흐름, 자동 발표, PowerPoint 따라가기, 질의응답 흐름 (Qt 화면을 모름)
  follow.py                 강아지 따라가기 계산 (순수 함수)
  voice/
    __init__.py
    engines.py              SAPI 메모리 합성(Windows), say -o(macOS) → 소리 데이터와 낱말 시각
    signal.py               크기 곡선, 입 모양 판정, 음절 시각 어림
    player.py               Qt 재생(QAudioSink / QMediaPlayer), 장치, 늘이기, 블루투스 무음
    pipeline.py             문장 줄: 앞 문장 재생 중 다음 문장 합성, 재생 위치 알림
  llm/
    __init__.py
    base.py                 공통 경계: 요청, 글 조각 흐름, 다섯 공통 오류, 모델 목록
    claude.py  openai.py  gemini.py
  qa.py                     근거 묶음, 지침 합치기, 대화 기억, 답을 문장으로 자르기
  captions.py               그림 꺼내기, 캡션 만들기, 해시로 저장
  ui/
    app.py                  QApplication 시작, session과 화면 신호 잇기
    theme.py                오션·코랄 색과 Qt 스타일시트
    dog.py                  강아지 창
    orb.py                  원 버튼 묶음: 원 버튼, 위성 버튼, 질문창, 생각 깊이, 알림 줄
    bubble.py               말풍선
    settings_window.py      설정 창
    script_window.py        대본 창
    platform_win.py         Windows 창 보조(필요할 때만)
    platform_mac.py         macOS 창 보조(pyobjc)
  assets/                   dog_shiba.png, dog_bichon.png, dog_beagle.png
tests/                      <tests>
```
근거: 16, 19, 20.
</project_structure>

<design_tokens>
오션·코랄. `ui/theme.py` 한 곳에 상수와 Qt 스타일시트로 둔다.

| 이름 | 값 | 쓰는 곳 |
|---|---|---|
| ocean-900 | `#06283D` | 짙은 그림자 |
| ocean-800 | `#0B3A53` | 글자(ink), 설명 풍선 바탕(투명도 .94) |
| ocean-700 | `#0E5E84` | 보조 글자 |
| ocean-600 | `#0E6BA8` | 링크, 진행 막대 끝 |
| aqua | `#2BB3C0` | 입력 칸 포커스, 진행 막대 시작 |
| foam | `#E6F7F8` | 창 위쪽 바탕, 칩 바탕 |
| foam-2 | `#F3FBFC` | 칸 바탕 |
| sand | `#FFF7F1` | 안내 띠 바탕 |
| line | `#D6E6EC` | 테두리 |
| muted | `#5B7A8C` | 회색 설명 글 |
| coral-l / coral / coral-d | `#FF9E6D` / `#FF6F61` / `#E8466E` | 코랄 그라데이션(135도, 가운데 55%) |
| ok / bad / warn | `#1E9E74` / `#E8466E` / `#C2601F` | 상태 칩 |
| satellite glyph | `#F0565E` | 위성 버튼 글자 |

글꼴: Windows "Malgun Gothic", macOS "Apple SD Gothic Neo".
근거: 07, 15, 시제품 `prototype/orb@e1fc8b7`, `prototype/settings@0660347`.
</design_tokens>

<screens>
모든 크기는 논리 픽셀이다. Qt가 모니터별 DPI를 처리한다.

<screen name="창 성격(공통)">
- **강아지 창, 원 버튼 묶음 창, 말풍선 창, 알림 줄 창**
  - 창 성격: 테두리 없음, 배경 투명(`WA_TranslucentBackground`), 항상 위, 작업 표시줄에 안 보임, 포커스를 빼앗지 않음. Qt 플래그는 `FramelessWindowHint | WindowStaysOnTopHint | Tool | WindowDoesNotAcceptFocus`와 `WA_ShowWithoutActivating`이다.
  - 클릭 통과: 강아지 창과 말풍선 창은 클릭을 아래로 통과시킨다(`WindowTransparentForInput`). 원 버튼 묶음은 버튼과 질문창만 클릭을 받고, 투명한 곳은 통과시킨다(마스크).
- **질문창**: 글을 입력해야 하므로 포커스를 받는다. 입력이 끝나 닫히면 포커스를 쇼 창에 돌려준다.
  - Windows: 질문창을 열기 전의 전경 창 핸들을 기억해 두고, 닫을 때 `SetForegroundWindow`로 돌려준다.
- **macOS 보조**(`ui/platform_mac.py`, pyobjc): 다른 앱의 전체 화면 위에 뜨려면 세 가지를 모두 해야 한다.
  - 앱 활성화 정책을 accessory로 둔다(Dock 아이콘 없음).
  - 겹쳐 뜨는 창을 활성화하지 않는 NSPanel(`NSWindowStyleMaskNonactivatingPanel`)로 만든다. Qt의 `Tool` 창이 NSPanel이 되므로 그 NSWindow를 얻어 바꾼다.
  - 레벨을 `NSScreenSaverWindowLevel`로 올리고, collectionBehavior에 `CanJoinAllSpaces | CanJoinAllApplications | FullScreenAuxiliary`를 준다.
  - 설정 창과 대본 창은 보통 창이다.
- 근거: 09, 13, `docs/research/gui-toolkit.md`, `docs/research/mac-without-mac.md`(Apple DTS 답변).
</screen>

<screen name="원 버튼">
- **모니터**: 설정의 "원 버튼 모니터"를 따른다(기본 "쇼가 뜬 모니터 따라가기"). 따라가기일 때 쇼 창이 있는 모니터를 쓰고, 모르면 주 모니터를 쓴다.
  - Windows `[보충]`: PowerPoint 쇼 창(창 클래스 `screenClass`)의 사각형으로 모니터를 찾는다. 구현 때 클래스 이름을 확인한다.
  - macOS `[보충]`: 쇼 창의 모니터를 얻지 못하면 주 모니터를 쓴다.
- **위치**: 그 모니터 작업 영역(작업 표시줄·Dock 제외)의 오른쪽과 아래에서 각각 28px 떨어진 곳이다. 원의 지름은 56px이다.
- **모양**(C 음파 링, 코랄):
  - 반지름 28px 원을 코랄 그라데이션으로 칠한다. 그라데이션 방향은 초당 0.5라디안으로 천천히 돈다.
  - 흰색 2px 테두리(불투명도 .8)를 두른다.
  - 원 둘레 반지름 R+5px에서 바깥으로 막대 36개를 세운다. 굵기 3px, 끝은 둥글게 하고, 색은 그 각도의 그라데이션 색이다.
  - 가운데에 흰 점을 둔다. 반지름은 4 + 목소리 크기 × 5px이다.
  - 코랄 빛 그림자: 불투명도 .35 + 목소리 크기 × .4, 흐림 10 + 목소리 크기 × 18px.
  - 그리는 캔버스는 220px 정사각형이다.
- **상태별 파동**: 막대 길이 L(px)은 상태에 따라 다르다. a는 막대의 각도, t는 초, lv는 0~1의 목소리 크기다.
  - 평상시: `L = 2 + 7 × max(0, cos(a − 1.2t))^6`. 막대 하나가 둘레를 천천히 돈다.
  - 읽는 중: `L = 2 + lv × 11 × (0.35 + 0.65 × spec)`.
  - 말하는 중: `L = 2 + lv × 18 × (0.35 + 0.65 × spec)`.
  - 생각 중: L = 2로 낮게 두고, 원 안쪽 반지름 R−6에서 흰 호(길이 0.6π, 굵기 4px)가 초당 4라디안으로 돈다.
  - spec = `0.5 + 0.5 × sin(a × (2 + round(tone × 3)) + 3t + noise_i × 6)`이다. tone은 목소리 높낮이 느낌(0~1, 천천히 따라감), noise_i는 막대마다 고정된 난수다.
  - lv는 재생 위치의 크기 곡선 값을 `smooth += (lv − smooth) × 0.35`로 부드럽게 한 것이다.
- **오류일 때**: 0.4초 동안 좌우로 살짝 흔들린 뒤 평상시로 돌아간다. 색은 바꾸지 않는다.
- **누르면**: 위성 버튼을 펼치거나 접는다.
- 30~60fps로 그린다. 평상시에는 30fps로 낮춰도 된다.
- 근거: 07, 18, 시제품 `prototype/orb@e1fc8b7`(`drawD`).
</screen>

<screen name="위성 버튼">
- **버튼**: 다섯 개이고, 지름 46px의 흰 동그라미에 코랄 글자(`#F0565E`)를 쓴다. 그림자는 `0 4px 12px rgba(0,0,0,.18)`, 테두리는 `rgba(255,111,97,.4)` 1px이다.

  | 차례 | 글자 | 설명 풍선 | 누르면 |
  |---|---|---|---|
  | 1 | `?` | 질문하기 | 위성 버튼을 접고 질문창과 생각 깊이 버튼을 연다 |
  | 2 | `▶` / `■` | 읽기 / 정지 | 무엇이든 말하는 중이면 멈춘다. 아니면 지금 장의 대본을 읽는다 |
  | 3 | `x1` `x1.5` `x2` `x5` | 배속 (누를 때마다 바뀜) | x1 → x1.5 → x2 → x5 → x1. 마지막 값을 설정에 기억한다 |
  | 4 | `⚙` | 설정 | 위성 버튼을 접고 설정 창을 연다 |
  | 5 | `✕` | 끝내기 | <flow name="끝내기"> |
- **배치**: 원 버튼 중심에서 반지름 132px인 4분원 호에 놓는다. 왼쪽(180도)에서 위(270도)까지 같은 간격이다.
- **펼침**: 각 버튼이 원 버튼 중심에서 제자리로 0.3초 동안 `cubic-bezier(.2,.9,.3,1.3)`로 튀어 나간다. 30ms 간격으로 차례로 나간다.
- **설명 풍선**: 마우스를 올리면 버튼 아래에 뜬다. 바다색 바탕(`rgba(11,58,83,.94)`)에 흰 13px 글자다.
- **접힘**:
  - 4초 동안 아무것도 누르지 않으면 접힌다.
  - 마우스가 원 버튼이나 위성 버튼 위에 있는 동안은 시간을 세지 않는다. 벗어나면 4초를 처음부터 다시 센다.
  - 질문창이 열려 있으면 접지 않는다.
- 근거: 07, 15(📂 위성 버튼을 잠깐 만들었다가 되돌림).
</screen>

<screen name="질문창과 생각 깊이 버튼">
- **질문창**(알약 모양):
  - 크기와 자리: 높이 48px, 너비 360px. 오른쪽 끝이 원 버튼 왼쪽 가장자리에서 30px 떨어지고, 세로 가운데가 원 버튼 중심과 같다.
  - 모양: 흰 바탕, 코랄 2px 테두리, 그림자 `0 6px 20px rgba(0,0,0,.2)`.
  - 오른쪽 끝에 지름 36px 원형 보내기 버튼(코랄 그라데이션, 흰 `↑`)을 둔다.
  - 입력: 한 줄이다. Enter로 보내고, 보낸 뒤에도 창은 남는다. 성공하면 글을 비운다. Esc로 닫는다.
  - 빈 글은 보내지 않는다.
  - 오류가 나면 방금 보낸 질문을 다시 채워 둔다.
- **생각 깊이 버튼**(알약):
  - 크기와 자리: 높이 32px. 오른쪽 끝을 질문창 오른쪽 끝에 맞추고(4px 안쪽), 질문창 위 10px에 둔다.
  - 모양: 흰 바탕, 코랄 글자. 표시는 `생각 low ●○○` / `생각 mid ●●○` / `생각 high ●●●`이다.
  - 동작: 누를 때마다 low → mid → high → low로 돌고, 글자가 0.32초 동안 위아래로 뒤집힌다.
  - 프로그램을 켤 때마다 low로 시작하고, 저장하지 않는다.
  - 질문창과 함께 열리고 함께 닫힌다.
- 근거: 07, 16, 18.
</screen>

<screen name="알림 줄">
- 원 버튼 왼쪽 위에 6초 동안 뜨는 작은 글이다.
- 모양: 바다색 바탕(ocean-800, 불투명도 .94)에 흰 13px 글자, 둥근 모서리.
- 원 버튼과 같은 모니터에 있어 청중도 본다. 그래서 짧게 원인과 할 일만 쓴다.
- 문구는 <ui_strings>에 있다.
- 근거: 18.
</screen>

<screen name="강아지">
- **스프라이트**:
  - 세 마리(시바, 비숑, 비글)이고 설정에서 고른다. 기본은 시바다.
  - 원본은 64×64 격자이고, 화면에는 ×2(128px)로 픽셀을 그대로 키워서(nearest) 그린다.
  - 오른쪽을 보는 그림만 있고, 커서 쪽을 보도록 좌우를 뒤집는다.
- **자세**: 시트의 줄 차례와 같다.

  | 줄 | 자세 | 프레임 | 초당 | 쓰는 때 |
  |---|---|---|---|---|
  | 0 | 엎드림 | 4 | 3 | 커서가 4초 넘게 가만히 있을 때 |
  | 1 | 걷기 | 4 | 8 | 따라 움직일 때 |
  | 2 | 앉기 | 4 | 4 | 멈췄을 때 |
  | 3 | 생각 중 | 4 | 3 | 질의응답에서 답을 기다릴 때 |
  | 4 | 말하기 | 4 | — | 소리를 낼 때. 입 모양(닫힘·조금·크게·가로)을 프레임 0~3으로 고른다(<module name="voice/signal.py">) |
  | 5 | 기뻐하기 | 4 | 8 | 답을 다 말했을 때, 자동 발표가 마지막 장까지 끝났을 때, 프로그램을 처음 켰을 때 1.5초 동안 |

- **덧그림**: 오류를 말할 때는 말하기 자세에 땀방울 덧그림을 얹는다. 생각 중 자세의 구름처럼 생성기가 따로 그리는 덧그림이다. 새 자세는 만들지 않는다.
- **따라가기**: 계산은 `follow.py`의 순수 함수로 둔다.
  - 목표는 커서 끝에서 오른쪽 12px, 아래 8px 지점이다. 커서 화살표를 가리지 않게 구현 때 간격을 화살표 크기에 맞춰 조정한다.
  - 한 프레임에 `min(거리, 260 × dt + 거리 × 4 × dt)`만큼 다가간다(px, dt는 초). 남은 거리가 2px 넘으면 움직이는 중이다.
  - 가로로 1.5px 넘게 움직일 때만 방향을 바꾼다.
- **상태별 움직임**:
  - 질의응답(생각 중, 답하는 중): 그 자리에 앉아 머문다. 말풍선이 사라지면 다시 커서에게 걸어간다.
  - 대본 읽기(자동 발표 포함): 계속 따라간다. 움직일 때는 걷고, 멈추면 말하기 입을 한다.
- **모니터**: 강아지는 원 버튼이 있는 모니터에만 있다. 커서가 다른 모니터로 가면 원 버튼 왼쪽 옆 자리로 돌아가 앉아 기다리고, 커서가 돌아오면 다시 따라간다.
- **화면 가장자리**: 강아지와 말풍선은 늘 그 모니터 작업 영역 안에 있다. 오른쪽에 자리가 없으면 커서 왼쪽으로, 아래에 자리가 없으면 커서 위로 간다.
- **원 버튼과 겹칠 때**: 원 버튼 묶음을 늘 강아지보다 위에 그린다. 커서가 원 버튼 묶음 위에 있는 동안 강아지는 원 버튼 왼쪽 옆 자리에 앉아 기다린다.
- **보이기**: 프로그램이 켜져 있는 동안 늘 보인다. 설정의 "강아지 보이기"로 끌 수 있다.
- **클릭**: 강아지는 클릭을 통과시키고, 누를 수 없다.
- **커서 위치**: `QCursor.pos()`를 30~60fps로 읽는다.
- 근거: 06, 14, 18, 시제품 `prototype/dog-sprites@faa9bd6`.
</screen>

<screen name="말풍선">
- 질의응답 답을 말하는 동안에만 뜬다. **대본을 읽을 때는 뜨지 않는다.**
- **자리**: 강아지 머리 위다. 왼쪽 = 강아지 x + 36, 아래쪽 = 강아지 y + 18이다. 위에 자리가 없으면 강아지 아래에 띄운다. 모니터 작업 영역 안으로 맞춘다.
- **모양**(산호):
  - 바탕: 코랄 그라데이션 135도 `#FF7A59` → `#F2545B`(55%) → `#D93D6A`
  - 글자: 흰 굵은(600) 16px, 줄 높이 1.5, 안쪽 여백 11px 16px. 한국어는 띄어쓰기 단위로 줄을 바꾼다(keep-all).
  - 모서리: 조금씩 다른 둥근 돌 모양(가로 반지름 26/20/24/14px, 세로 반지름 20/26/18/22px)
  - 그림자: 바다색 `0 10px 24px rgba(14,107,168,.3)`
  - 꼬리: 왼쪽에서 24px 지점에서 아래로 9px 삼각형, 색은 `#F2545B`
- **움직임**:
  - 나타날 때: 불투명도 0→1(0.25초), 아래 10px·크기 .94에서 제자리로(0.4초, `cubic-bezier(.2,.9,.3,1.3)`)
  - 떠 있는 동안: 3.2초 주기로 위아래 3px씩 천천히 흔들린다.
- **스트림·이어서**:
  - 너비는 300px로 고정한다.
  - 목소리가 읽기 시작한 낱말까지만 보이고, 문장이 바뀌어도 글이 이어진다.
  - 새 낱말은 0.28초 동안 흐림 2px·아래 4px·투명에서 선명해진다.
  - 세 줄(72px)을 넘으면 0.3초 동안 위로 밀려 올라가고, 맨 윗줄은 위에서 45%까지 흐려지는 마스크로 가린다.
  - 다 말한 뒤 3초 남았다가 사라진다.
- 근거: 07, 시제품 `prototype/orb@e1fc8b7`(`drawOceanBubble`, 산호 + 스트림·이어서).
</screen>

<screen name="설정 창">
- **열기**: [설정] 위성 버튼으로 연다. 프로그램을 처음 켰을 때는 저절로 연다. 보통 창이고 제목은 `설정 — PPT 읽어주기`, 폭은 약 720px이다.
- **바탕**: foam에서 흰색으로 흐르는 바탕이다.
- **저장**:
  - 바꾸면 **바로 저장**하고 화면 아래에 `저장됨`을 1.2초 띄운다. 적용·취소 단추는 없다.
  - API 키는 [확인]을 누르거나 칸을 벗어날 때 저장한다.
- **머리**:
  - 고른 강아지가 앉아 있다(96px, 앉기 자세 애니메이션).
  - 제목은 `발표 준비 {n} / 4` 또는 `발표 준비 끝! 🎉`다.
  - 칩 네 개(발표 자료, 목소리, 질의응답, 캐릭터와 화면)가 각각 `✓` 또는 `!`를 단다.
  - 코랄 그라데이션 진행 막대(폭 320px, 높이 8px)를 둔다.
  - 끝났다고 보는 조건:
    - 발표 자료: 파일이 열려 있다.
    - 목소리: 늘 끝남.
    - 질의응답: 키 확인이 맞았다.
    - 캐릭터와 화면: 늘 끝남.
- **접히는 카드 네 장**: 머리를 누르면 펼치고 접는다.
  - 카드 머리: 번호(끝났으면 `✓`), 이름, 지금 값의 요약.
  - 아직 안 된 첫 카드에 `다음 할 일` 표시를 단다.
  - 처음 실행 때는 그 카드만 펼친다. 평소에는 발표 자료 카드만 펼친다.

  | 카드 | 들어 있는 것 |
  |---|---|
  | 1. 발표 자료 | 파일 이름과 `슬라이드 {N}장 · 노트 있는 장 {k}개 · 고친 대본 {m}장`, [다른 파일…], [📝 대본 열기], PowerPoint 연동 스위치와 상태 칩, 읽을 내용(기존 SOURCES 네 가지). 파일이 없으면 [파일 열기…], 안내, 연동 스위치만 보인다 |
  | 2. 목소리 | 목소리(한국어 음성 먼저)와 [들어 보기], 출력 장치(목록을 펼 때마다 다시 찾기, 기존 규칙), 자동 발표 스위치, 쇼에서 바로 읽기 스위치, 배속 안내 |
  | 3. 질의응답 | AI 제공자(Claude / OpenAI / Gemini 단추 묶음), 모델(목록 + `직접 입력…`), API 키(가린 칸, [보기]/[숨기기], [확인], 결과 글), 개인 지침(여러 줄), 캡션 스위치(기본 꺼짐) |
  | 4. 캐릭터와 화면 | 강아지 카드 세 장(앉기 애니메이션, 이름, 설명, 시바에 `· 기본`), 강아지 보이기 스위치, 원 버튼 모니터(`쇼가 뜬 모니터 따라가기` + 연결된 모니터마다 `{번호}번 — {이름} ({가로}×{세로})`) |

- **맨 아래**: `바꾸면 바로 저장돼요` 글과 `오픈 소스 라이선스` 링크(`licenses/` 폴더를 연다)를 둔다.
- **스위치**: 켜지면 코랄 그라데이션, 꺼지면 `#CFDCE2`인 42×24px 둥근 스위치다.
- **주요 단추**: 코랄 그라데이션에 흰 굵은 글자다.
- **제공자를 바꾸면**: 그 제공자의 기본 모델을 고르고, 그 제공자의 저장된 키를 보인다. 키는 제공자마다 따로 저장한다 `[보충]`.
- **키 확인**: 그 제공자의 모델 목록 API를 한 번 부른다. 성공하면 맞음, 키 문제 오류면 틀림, 그 밖의 오류면 알림 글을 보인다.
- 근거: 15, 시제품 `prototype/settings@0660347`(B안).
</screen>

<screen name="대본 창">
- **열기**: 설정 창 발표 자료 카드의 [📝 대본 열기]로 연다. 보통 창이고 제목은 `대본 — {파일명}`, 크기는 약 1020×640px이다.
- **위**: 바다색(ocean-800) 띠에 슬라이드 카드를 가로로 늘어놓는다.
  - 카드: 150×92px, 흰 바탕. 제목, 본문 첫 줄, `✎`(고친 대본), `🖼{n}`(그림 수), 장 번호를 보인다.
  - 고른 카드는 코랄 테두리를 두른다.
  - PowerPoint 연동 중이면 쇼의 지금 장을 따라 고른다(기존 select 규칙).
- **가운데**:
  - 고른 장의 `{번호}. {제목}`
  - 대본 고치기 칸(여러 줄, 15px)
  - 아래에 상태 글(`✎ 고친 대본 — 고친 대로 읽습니다` 또는 `자동으로 뽑은 대본 — 고치면 고친 대로 읽습니다`)과 [원래 내용으로]
  - 원본이 바뀌었으면 `원본이 바뀌었어요`도 함께 보인다(<module name="ppt_reader/settings.py">).
  - 고친 대본은 칸을 벗어나거나 다른 장으로 갈 때 저장한다.
- **오른쪽**(폭 320px):
  - 캡션 진행 막대
  - `발표자 노트`(읽기만)
  - `그림 캡션`: 그림마다 메타 줄(`그림 {i} 캡션`, 상태)과 고칠 수 있는 칸. 건너뛴 그림은 이유를 기울임 글로 보인다.
- 근거: 11, 15, 16.
</screen>
</screens>

<flows>
<flow name="시작">
1. `python -m ppt_reader [파일]`이나 실행 파일을 켜면 강아지와 원 버튼만 뜬다. 다른 창은 없다.
2. 파일을 주면 그 파일을 연다.
3. 처음 실행(설정 파일에 `first_run_done`이 없음)이면 강아지가 1.5초 기뻐하고 설정 창을 연다. 그 뒤 `first_run_done = true`를 저장한다.
4. 생각 깊이는 늘 low로 시작한다. 배속은 저장된 값으로 시작한다.
근거: 14, 15, 16.
</flow>

<flow name="대본 읽기와 자동 발표">
- 기존 `PROMPT.md`의 <app_logic> 규칙을 그대로 `session.py`로 옮긴다. 해당 규칙은 아래다.
  - token으로 늦은 이벤트 거르기
  - 자동 발표에서 숨긴 장 건너뛰기
  - 빈 장에서 1.5초 쉬기
  - `_on_ppt_state`와 `_follow_file`의 같은 장 두 번 읽지 않기
  - 쇼가 끝나면 멈추기
  - 고친 대본 쓰기
  - 화면 쪽 호출(Listbox, Text 등)은 session의 신호로 바꾼다.
- 소리는 <module name="voice/pipeline.py">로 낸다. 한 장의 대본은 문장으로 잘라 합성하고 이어서 재생한다.
- 읽는 동안 원 버튼은 "읽는 중" 파동, 강아지는 말하기 입을 한다. 말풍선은 띄우지 않는다.
- [읽기/정지] 위성 버튼:
  - 말하는 중(대본이든 답이든)이면 멈춘다.
  - 아니면 지금 장을 읽는다. 지금 장은 연동 중이면 쇼의 장, 아니면 대본 창에서 고른 장, 그것도 없으면 첫 장이다.
- 자동 발표가 마지막 장까지 끝나면 강아지가 1.5초 기뻐한다.
- 질의응답 중(생각 중, 답하는 중)에 쇼의 장이 바뀌면 지금 장만 맞추고 읽지 않는다 `[보충]`.
- 근거: 10, 14, `PROMPT.md`.
</flow>

<flow name="질의응답">
1. [질문하기]를 누르면 질문창이 열린다. 대본을 읽는 중이면 그대로 둔다. 질문을 보낼 때 멈춘다.
2. 보내면:
   - 이전 답의 스트림을 닫고 말하던 것을 멈춘다.
   - 상태를 "생각 중"으로 바꾼다(원 버튼 생각 파동, 강아지 생각 중 자세로 그 자리에 머묾).
   - <module name="ppt_reader/qa.py">로 요청을 만들어 LLM 작업 스레드에 넘긴다.
3. **기다리는 말**: 첫 글자가 오기 전에 8초가 지나면 강아지가 `조금만 기다려 주세요`, 30초가 지나면 `아직 생각하고 있어요`를 한 번씩 말한다. 말풍선 없이 목소리만 낸다 `[보충]`.
4. **시간 초과**: 첫 글자까지 low 45초, mid 90초, high 150초다. 답이 오다가 30초 동안 새 글이 없어도 시간 초과다.
5. **답을 받는 동안**: 글 조각을 문장으로 자른다(<module name="ppt_reader/qa.py">). 문장 하나가 끝날 때마다 음성 합성 줄에 넣는다. 첫 문장이 재생되기 시작하면 상태를 "말하는 중"으로 바꾸고 말풍선을 띄운다.
6. **말풍선과 입**: 말풍선은 재생 중인 낱말까지 이어서 보여 준다. 강아지는 말하기 자세, 원 버튼은 말하는 파동이다.
7. **다 말하면**: 강아지가 1.5초 기뻐하고, 말풍선은 3초 뒤 사라진다. 질문과 답을 대화 기억에 넣는다. 질문창은 비운다.
8. **오류**: <flow name="오류 반응">.
근거: 08, 10, 18.
</flow>

<flow name="캡션">
- 캡션 스위치가 켜져 있고 키 확인이 맞았을 때만 만든다. 기본은 꺼짐이다.
- **시작하는 때**:
  - 파일을 열면 뒤에서 저절로 만든다.
  - 파일이 열린 채로 캡션을 켜도 바로 시작한다.
  - 키 확인이 맞게 바뀌어도 다시 시작한다.
- **차례**: 캡션 작업 스레드 하나가 슬라이드 차례대로 처리한다. 이미 저장된 해시는 건너뛰므로 바뀐 그림만 새로 만든다.
- **진행 상황**: 대본 창의 캡션 진행 막대에 보인다. [멈추기]로 멈추고, [다시 만들기]로 고치지 않은 캡션을 다시 만든다.
- **쓰임**: 질의응답 근거에만 넣고 소리 내어 읽지 않는다.
- **실패**: 대본 창의 진행 막대에만 표시한다. 발표 중에는 알리지 않는다.
- 근거: 11, 18.
</flow>

<flow name="오류 반응">
- **질의응답 오류**: LLM 오류는 다섯 공통 종류로 온다(<module name="llm/base.py">). 강아지는 말하기 자세에 땀방울을 얹고 짧은 말을 말풍선과 목소리로 한다. 동시에 원 버튼이 0.4초 흔들리고, 알림 줄이 6초 뜬다. 문구는 <ui_strings>에 있다.
  - 오류가 나면 질문창에 방금 질문을 다시 채운다.
  - 답하다가 끊기면: 이미 합성 줄에 넣은 문장까지는 끝까지 말한다. 이어서 `앗, 말하다가 연결이 끊겼어요.`라고 말한다. 대화 기억에는 끊긴 답을 끝에 `(끊김)`을 붙여 남긴다.
- **질의응답 밖의 오류**:

  | 오류 | 알리는 곳 |
  |---|---|
  | 캡션 만들기 실패 | 대본 창의 캡션 진행 막대 |
  | 키 확인 실패 | 설정 창 키 칸 아래 글 |
  | PowerPoint 연동이 끊김 | 알림 줄 + 설정 창 연동 칩. 자동 발표를 멈춘다 |
  | 음성 합성 실패 | 질의응답이면 말풍선 글만 보이고, 알림 줄을 띄운다 |

- 근거: 18.
</flow>

<flow name="끝내기">
[끝내기]를 누르면 아래 순서로 정리하고 프로세스를 끝낸다.
1. 읽기를 멈추고 합성 줄을 비운다.
2. LLM 스트림과 캡션 작업을 취소한다.
3. PowerPoint 연동을 닫는다.
4. 고친 대본과 설정을 저장한다.
5. 종료한다.
근거: 16.
</flow>
</flows>

<module_specs>

<module name="ppt_reader/slides.py, ppt_reader/link.py">
그대로 둔다. `PROMPT.md`의 명세를 따른다. SmartArt와 도표는 지금처럼 대본에 넣지 않는다.
</module>

<module name="ppt_reader/settings.py">
- **폴더**: 운영체제 표준 앱 폴더다. `QStandardPaths`를 쓰지 않고 직접 정한다. Qt 없이 시험할 수 있게 하려는 것이다.
  - Windows: `%APPDATA%\PPT읽어주기\`
  - macOS: `~/Library/Application Support/PPT읽어주기/`
  - 시험에서는 환경 변수 `PPT_READER_HOME`으로 바꿀 수 있어야 한다.
- **`settings.json`**(utf-8, `ensure_ascii=False`, indent 2):
  ```json
  {
    "version": 2,
    "first_run_done": true,
    "source": "notes_first",
    "voice": "Microsoft Heami Desktop - Korean",
    "output": {"id": "...", "name": "..."},
    "speed": 1.0,
    "auto_next": false,
    "read_on_change": true,
    "provider": "claude",
    "models": {"claude": "claude-haiku-5-5", "openai": "gpt-6-luna", "gemini": "gemini-3.5-flash-lite"},
    "keys": {"claude": "", "openai": "", "gemini": ""},
    "key_ok": {"claude": false, "openai": false, "gemini": false},
    "persona": "",
    "captions": false,
    "dog": "shiba",
    "dog_visible": true,
    "monitor": "follow",
    "x5_factor": {}
  }
  ```
  - `speed`는 1.0, 1.5, 2.0, 5.0 중 하나다.
  - `monitor`는 `"follow"`이거나 모니터 이름이다.
  - `x5_factor`는 음성 id별로 잰 최고 배속이다(<module name="voice/engines.py">).
  - 생각 깊이는 저장하지 않는다.
  - 읽을 때 OSError나 ValueError가 나면 기본값을 쓴다.
  - 키와 상관없는 값을 저장할 때도 파일 전체를 다시 쓴다. 쓸 때는 임시 파일에 쓴 뒤 바꿔치기한다.
- **옛 설정 옮기기**:
  - 새 파일이 없고 옛 `~/.ppt_reader_settings.json`이 있으면 `source`, `voice`, `output`, `auto_next`, `read_on_change`를 옮긴다.
  - `speed`는 1.0, 1.5, 2.0, 5.0 중 가장 가까운 값으로 옮긴다. 0.5~1.24는 1.0이다.
  - 옛 파일은 건드리지 않는다.
- **고친 대본 `edits.json`**:
  - 형식: `{발표 파일의 정규화 경로: {장 번호: {"text": 고친 대본, "orig": 고칠 때의 원래 대본의 sha256}}}`
  - 저장: 고칠 때마다 저장한다. 원래 대본으로 되돌리면 지운다.
  - 같은 파일을 열 때 장마다 지금 원래 대본의 sha256을 `orig`와 비교한다. 다르면 고친 대본은 그대로 쓰고 대본 창에 `원본이 바뀌었어요`를 보인다.
- **캡션 `captions.json`**: `{그림 키: {"text": ..., "edited": bool, "model": ..., "made_at": ISO 시각}}`. 그림 키는 <module name="ppt_reader/captions.py">에 있다.
- 근거: 16.
</module>

<module name="ppt_reader/session.py">
Qt 화면을 모르는 상태 묶음이다. 기존 `app.py`의 `App` 로직(<app_logic>)을 화면 없이 옮기고, 질의응답을 더한다.
- **바깥과 잇기**: 음성, 연동, LLM, 시계는 생성자에 넣는다. 시험에서는 가짜로 바꾼다.
- **알리기**: 화면에 알릴 일은 콜백(`on_*`)이나 QtCore 신호로 낸다.
  - 상태: idle / reading / thinking / speaking / error
  - 그 밖: 지금 장, 말풍선 낱말, 알림 줄 문구, 강아지 자세 요청
- **상태 규칙**:
  - 읽기와 답하기는 동시에 하지 않는다.
  - 질문을 보내면 읽기를 멈춘다.
  - [읽기/정지]는 무엇이든 멈춘다.
- **대화 기억**: 같은 발표 파일을 쓰는 동안 최근 6번의 질문과 답을 기억한다. 다른 파일을 열거나 프로그램을 다시 켜면 잊는다. 질문창을 닫았다 다시 열어도 이어진다.
- **시계**: 기다리는 말, 시간 초과, 기쁨 1.5초, 말풍선 3초는 넣어 준 시계(`now()`, `call_later()`)로 잰다. 그래서 가짜 시계로 시험할 수 있다.
- 근거: 08, 16, 18, 19.
</module>

<module name="ppt_reader/voice/engines.py">
문장 하나를 소리 데이터로 만드는 경계다. 나중에 클라우드 음성을 끼울 수 있게 아래 인터페이스만 밖에 보인다.
```python
@dataclass
class Synth:
    pcm: bytes            # 22050Hz, 16bit, mono
    words: list[tuple[int, int, float]]   # (글자 시작 위치, 글자 수, 소리 안 시작 초). 대본 글 기준
    engine_speed: float   # 엔진이 실제로 낸 배속(늘이기 전)
class Engine:
    def voices(self) -> list[Voice]: ...
    def synth(self, text: str, voice_id: str | None, speed: float) -> Synth: ...   # 음성 스레드에서만
```
- **Windows SAPI**(pywin32, 음성 스레드에서 `CoInitialize`):
  1. `SAPI.SpMemoryStream`의 `Format.Type = 22`(SAFT22kHz16BitMono)로 둔다. `SpVoice.AudioOutputStream`을 그 스트림으로 바꾼다.
  2. Word 이벤트를 받으며 `Speak(text, SVSFlagsAsync | SVSFIsNotXML)`를 부르고 끝까지 기다린다. Word 이벤트의 `StreamPosition`(바이트)을 `÷ 44100`으로 초로 바꾸고, `CharacterPosition`과 `Length`를 함께 모은다.
  3. `bytes(ms.GetData())`가 PCM이다.
  - 속도:
    - x1, x1.5, x2는 `Rate = round(10 × ln(speed) / ln(3))`(x1.5는 4, x2는 6)이다.
    - x5는 `Rate = 10`에 `<rate absspeed="5"/>`를 SVSFPersistXML로 넣는다. 이 설정은 다음 읽기에도 남으므로 x5가 아닐 때는 `absspeed="0"`으로 되돌린다.
  - `engine_speed`:
    - x5는 음성마다 다르다(Heami는 약 5.17, Zira는 약 3.47).
    - 음성을 처음 x5로 쓸 때 짧은 고정 문장을 Rate 0과 x5 설정으로 각각 합성해 길이 비를 잰다. 그 값을 `settings.x5_factor[voice_id]`에 저장한다 `[보충]`.
    - 나머지 배속은 요청한 값이다.
- **macOS say**:
  - `say -o 임시.wav --file-format=WAVE --data-format=LEI16@22050 -r {wpm} [-v 음성] 글`로 합성한다. wpm = `190 × speed`이고 최대 500이다. x5는 500(약 2.63배)이 `engine_speed`다.
  - say는 낱말 시각을 주지 않는다. 그래서 `words`는 문장 소리 길이를 낱말 글자 수(공백 빼고)에 비례해 나눈 어림값이다.
- 문장 하나씩 합성한다. 긴 대본을 한 번에 합성하면 첫마디까지 늦어진다.
- 근거: 10, `docs/research/tts-signal-speed.md`, `docs/research/qt-audio-tts.md`.
</module>

<module name="ppt_reader/voice/signal.py">
- **크기 곡선**: PCM을 20ms 창으로 나눠 RMS를 구한 목록이다(순수 파이썬, 4샘플에 하나만 써도 된다). 각 값은 그 문장의 최댓값으로 나눠 0~1로 둔다.
- **입 모양**: 재생 위치의 곡선 값 v와 그때 소리 나는 음절로 고른다. 0은 닫힘, 1은 조금, 2는 크게, 3은 가로다.
  - v < 0.2 → 닫힘
  - 그 음절의 중성이 ㅐ ㅒ ㅔ ㅖ ㅢ ㅣ(중성 번호 1, 3, 5, 7, 19, 20) → 가로
  - v < 0.55 → 조금
  - 그 밖 → 크게
  - 한 모양을 60ms 넘게 유지한다. 바꾸려는 모양이 와도 60ms가 지나기 전에는 바꾸지 않는다.
  - 중성 번호는 `(ord(ch) − 0xAC00) % 588 // 28`이다. ㅡ는 은·는·을처럼 너무 자주 나와서 넣지 않는다.
  - 한글이 아닌 글자(영어, 숫자)는 소리 크기만으로 고른다.
- **음절 시각**: 낱말 안에서 음절(한글 글자)마다 시작 시각을 어림한다. 낱말 시작부터 다음 낱말 시작까지를 음절 수로 똑같이 나눈다.
- 근거: 06, 10, 시제품 `prototype/orb@8eb72a1`(`isWide`).
</module>

<module name="ppt_reader/voice/player.py">
- **장치**: `QMediaDevices.audioOutputs()`로 고른다. 기존 설정의 SAPI 출력 토큰 id는 끝부분(`{0.0.0.00000000}.{GUID}`)이 Qt 장치 id와 같으므로 그 부분으로 맞춘다. 고른 장치가 없으면 기본 장치로 재생한다(기존 규칙).
- **두 가지 재생 길**: 늘일 배율 r = 요청 배속 ÷ `engine_speed`에 따라 고른다.
  - r ≤ 1.01: `QAudioSink`(22050Hz, mono, Int16)에 PCM을 넣는다. 재생 위치는 `processedUSecs()`(10ms 단위)다.
  - r > 1.01: WAV 바이트를 `QBuffer`에 담아 `QMediaPlayer.setSourceDevice`로 넘기고 `setPlaybackRate(r)`를 한다. `pitchCompensation`을 켠다. 위치(`position()`)는 원본 시각으로 50~100ms마다만 바뀌므로, 화면 쪽에서 벽시계로 보간한다.
  - FFmpeg 백엔드만 음높이를 지킨다. 그래서 앱 시작 전에 환경 변수 `QT_MEDIA_BACKEND=ffmpeg`을 둔다.
- **블루투스 앞 무음**: 기존 규칙(`LEAD_SILENCE_MS = 1000`, `IDLE_BEFORE_LEAD = 2.0`)을 그대로 따른다.
  - 넣는 때: 처음 읽을 때, 2초 넘게 조용했을 때, 출력 장치가 바뀌었을 때
  - 넣는 법: 첫 문장 PCM 앞에 0을 붙인다. 길이는 1000ms × r이다. 그래서 늘인 뒤에도 정확히 1초가 된다.
  - 이것으로 지금 구현의 버그(SAPI `<silence>`가 배속만큼 짧아짐)가 없어진다.
  - Qt는 Windows에서 이 예열을 해 주지 않으므로 앱이 꼭 붙여야 한다.
- 근거: 10, `docs/research/qt-audio-tts.md`.
</module>

<module name="ppt_reader/voice/pipeline.py">
- **합성 줄**: 문장을 차례로 받아 음성 스레드에서 합성한다. 앞 문장을 재생하는 동안 다음 문장을 합성해서 틈 없이 잇는다.
- **화면에 알리기**: 재생 중 30~60fps로 아래를 화면에 알린다. 원 버튼, 강아지, 말풍선이 이것만 본다.
  - (문장 번호, 재생 위치 초, 곡선 값, 입 모양, 지금까지 시작한 낱말 수)
- **멈추기**: 재생을 멈추고 줄을 비운다. 멈춘 뒤 늦게 온 합성 결과는 token으로 버린다.
- **끝 알림**: 대본 한 장이나 답 하나가 끝나면 session에 done을 알린다. 완주했는지도 함께 보낸다.
- 근거: 10, 16.
</module>

<module name="ppt_reader/llm/base.py, claude.py, openai.py, gemini.py">
**공통 경계**
```python
EFFORT = {"low": "low", "mid": "medium", "high": "high"}
class LLMError(Exception):
    kind: str   # "key" | "quota" | "network" | "timeout" | "other"
    detail: str # 제공자가 보낸 오류 첫 줄 (키 값은 지운다)
@dataclass
class Request:
    model: str
    effort: str            # "low" | "mid" | "high"
    system: str            # 기본 지침 + 개인 지침 (바뀌지 않음)
    grounding: str         # 근거 묶음 (바뀌지 않음, 캐시 대상)
    turns: list[tuple[str, str]]  # 대화 기억 (질문, 답)
    question: str          # 이번 질문 (지금 화면의 장 포함)
    images: list[bytes] = ()      # 캡션 요청에서만
    max_tokens: int = 4096
class Provider:
    def stream(self, req: Request, cancel: threading.Event) -> Iterator[str]: ...  # 답 글 조각만. 생각 조각은 버린다
    def check_key(self) -> None: ...     # 모델 목록 API 한 번. 실패하면 LLMError
```

**제공자별 부르기**: 생각 깊이는 매 요청에 명시한다.

| 제공자 | 부르기 | 생각 깊이 | 글 조각 |
|---|---|---|---|
| Claude | `anthropic`의 `messages.stream`. system에 기본 지침과 근거를 넣고, 근거 블록에 `cache_control: {"type": "ephemeral"}` | `output_config={"effort": ...}` | `text_delta` |
| OpenAI | `openai`의 Responses API 스트림. `instructions`에 지침과 근거, `store=False` | `reasoning={"effort": ...}` | `response.output_text.delta` |
| Gemini | `google-genai`의 `generate_content_stream`. `system_instruction`에 지침과 근거 | `ThinkingConfig(thinking_level=...)` | 조각의 `text` |

**출력 한도**: 생각 토큰도 출력 한도에 들어가므로 넉넉히 잡는다. low 4096, mid 8192, high 16384다 `[보충]`.

**취소**: `cancel`이 서면 스트림을 닫고 끝낸다.

**오류 바꾸기**: SDK 예외를 다섯 공통 종류로 바꾼다.
- `key`: 인증 실패, 권한 없음(401/403)
- `quota`: 요금 부족, 사용량 제한(429, 결제 관련)
- `network`: 연결 실패, 연결 끊김
- `timeout`: SDK 시간 초과. session의 시간 초과도 같은 종류로 다룬다.
- `other`: 그 밖

**모델 목록**: 코드에 둔다. 첫 항목이 기본이다. 설정에서 `직접 입력…`으로 다른 id를 쓸 수 있다.
- Claude: `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-fable-5-1`
- OpenAI: `gpt-6-luna`, `gpt-6.1-sol`, `gpt-6-sol`, `gpt-6-astra`
- Gemini: `gemini-3.5-flash-lite`, `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-4-argon`

근거: 03, 12, `docs/research/llm-providers.md`.
</module>

<module name="ppt_reader/qa.py">
**근거 묶음**: 질문마다 자료 전체를 넣는다. 바뀌지 않으므로 캐시된다.
```
<자료 파일="{파일명}" 장수="{N}">
<슬라이드 번호="{n}" 제목="{제목}">
본문: {body}
발표자 노트: {notes}           (있을 때만)
고친 대본: {edits[n]}           (고쳤을 때만)
그림 {i}: {캡션}                (캡션이 있을 때만)
</슬라이드>
...
</자료>
```
- 숨긴 장도 넣고, 슬라이드 태그에 `숨김="예"`를 단다 `[보충]`.
- 지금 쇼에 떠 있는 장 번호는 바뀌므로 근거가 아니라 질문 쪽에 넣는다. PowerPoint와 연동 중일 때만 `(지금 화면: {n}번 슬라이드)`를 질문 앞에 붙인다.

**기본 지침**(system):
```
너는 발표 화면 위의 도트 강아지 캐릭터다. 발표가 끝난 뒤 청중의 질문에 답한다.
- 먼저 <자료>의 내용을 근거로 답한다. 자료에 없는 내용은 일반 지식으로 보충하되, 그 부분은 "자료에는 없지만"처럼 밝힌다.
- 자료를 가리킬 때는 "3번 슬라이드에"처럼 장 번호로 말한다.
- 답은 소리 내어 읽힌다. 꾸밈 없는 한국어 말투 문장으로 2~4문장을 쓴다. 마크다운, 목록, 이모지, 표, 코드는 쓰지 않는다.
- 늘 한국어로 답한다.
```

**개인 지침이 있으면** 그 뒤에 붙인다.
```
<개인 지침>
{persona}
</개인 지침>
말투, 답 길이, 캐릭터 성격, 답의 언어는 개인 지침을 따른다. 그래도 다음 두 가지는 늘 지킨다.
1. 자료에 없는 내용은 자료에 없다고 밝힌다.
2. 마크다운, 목록, 이모지, 표 없이 소리 내어 읽기 좋은 문장으로 쓰고, 8문장을 넘기지 않는다.
```

**대화 기억**: 최근 6번의 (질문, 답)을 차례로 넣는다. 끊긴 답은 끝에 `(끊김)`이 붙어 있다.

**문장 자르기**: 스트림 글을 받는 대로 문장으로 잘라 낸다.
- 끝: `.` `?` `!` `…` `。` 뒤에 공백이나 줄바꿈이 오는 곳, 그리고 줄바꿈
- 바로 뒤의 닫는 따옴표나 괄호는 그 문장에 붙인다.
- 숫자 사이의 점(`3.5배`, `2.0`)에서는 자르지 않는다.
- 스트림이 끝나면 남은 글을 마지막 문장으로 낸다.
- 말하기 전에 기존 `to_speech`처럼 글머리 기호를 지운다.

**캡션 요청**: 슬라이드 한 장의 그림들과 그 장의 글을 함께 보낸다. 생각 깊이는 늘 low, 모델은 질의응답과 같은 것이다. 지침은 아래와 같다.
```
너는 발표 자료의 그림을 설명하는 사람이다. 슬라이드의 글을 참고해서 그림마다 한국어 1~3문장으로 설명한다.
그림 속 글자와 숫자는 그대로 옮긴다. 장식일 뿐이면 "장식용 그림"이라고만 쓴다.
그림 수만큼 "그림 1: ...", "그림 2: ..." 줄로만 답한다.
```
`그림 k:` 줄을 파싱해 그림마다 저장한다.

근거: 08, 11.
</module>

<module name="ppt_reader/captions.py">
- **꺼내는 그림**: 슬라이드 도형을 재귀로 돌며(그룹 안 포함) `isinstance(sh, Picture)`인 것을 꺼낸다. `shape_type == PICTURE`로 거르면 그림 자리표시자를 놓친다.
  - 바이트는 `sh.part.related_part(sh._element.blip_rId)`의 `blob`이다. 형식은 그 그림 부분의 `content_type`으로 판별한다.
  - 잘라내기 값(`crop_left/top/right/bottom`)은 Pillow로 직접 적용한다.
  - 배경 그림과 그림으로 채운 도형은 XML(`a:blip r:embed`)에서 꺼낸다.
- **건너뛰는 그림**(대본 창에 이유를 보인다):
  - 연결만 된 그림, 대체 그림 없는 SVG: `그림을 꺼낼 수 없는 형식(SVG)이라 건너뜀` / `연결된 그림이라 건너뜀`
  - macOS의 EMF/WMF: `이 컴퓨터에서 바꿀 수 없는 형식(EMF)이라 건너뜀`. Windows에서는 Pillow로 바꾼다.
  - 아주 작은 그림 `[보충]`: 원본 긴 변이 64px 미만이거나, 슬라이드 위 넓이가 슬라이드의 1% 미만
  - 같은 그림이 네 장 이상(세 장 넘게)에 나오는 것: 로고·장식으로 본다.
- **보내기 전**: 긴 변 1024px 이하로 줄이고, PNG(투명이 있으면)나 JPEG로 바꾼다.
- **상한**: 파일 하나에 그림 40개까지 보낸다. 넘으면 대본 창에 `앞 40개만 만들었어요`를 보인다.
- **그림 키**: `sha256(원본 바이트) + 잘라내기 값`이다. 파일 이름을 바꾸거나 옮겨도 다시 쓴다.
- **고친 캡션**: `edited`이고 [다시 만들기]를 해도 덮어쓰지 않는다.
- 근거: 05, 11, `docs/research/slide-images.md`.
</module>

<module name="ppt_reader/ui/*">
- **`app.py`**:
  - `QT_MEDIA_BACKEND=ffmpeg`을 둔 뒤 `QApplication`을 만든다.
  - session, pipeline, 연동, LLM 작업 스레드를 만들고 신호를 잇는다.
  - 화면 쪽 로직은 두지 않는다.
- **`dog.py`, `orb.py`, `bubble.py`**: <screens>대로 그린다. QPainter와 안티에일리어싱을 쓴다. 30~60fps 타이머 하나로 묶어 그린다 `[보충]`.
- **`settings_window.py`, `script_window.py`**: <screens>대로 짜고, `theme.py`의 스타일시트로 꾸민다.
- **`platform_mac.py`**: <screen name="창 성격(공통)">의 macOS 보조를 한다. pyobjc가 없거나 실패하면 Qt 기본 동작으로 둔다. 그 사실은 `--self-check`에 표시한다.
- **`platform_win.py`**: Qt 플래그로 모자랄 때만 ctypes로 보탠다. 쇼 창 모니터 찾기와 질문창 뒤 포커스 돌려주기가 여기에 들어간다.
- 근거: 09, 16.
</module>

<module name="ppt_reader/__main__.py">
- **기존 옵션**: `--list-voices`, `--list-outputs`, `--dump`, `--say`, `--slide`, `--source`, `--voice`, `--output`, `--speed`, `--probe-ppt`는 지금처럼 화면 없이 돈다. Qt 화면을 import하지 않는다.
  - `--say`는 새 음성 흐름을 쓴다. `--speed`는 1.0, 1.5, 2.0, 5.0만 받는다.
- **숨은 옵션 `--self-check`**: 아래를 차례로 하고, 결과를 줄마다 `OK`/`FAIL`로 출력한다. 모두 OK면 0을 돌려준다.
  1. Qt를 offscreen이 아닌 실제 플랫폼으로 띄워 강아지·원 버튼 창을 화면 밖 좌표에 한 번 만든다.
  2. 스프라이트 세 장을 읽는다.
  3. 기본 음성으로 한 문장을 합성한다. 재생은 하지 않는다.
  4. 설정 폴더 경로를 출력한다.
  5. macOS면 pyobjc 보조가 적용됐는지 확인한다.
  - 빌드 서버와 받는 사람 확인에 쓴다.
- **옵션이 없으면**: `ui.app.run(file)`.
- 근거: 16, 17.
</module>
</module_specs>

<ui_strings>
아래 문구를 글자, 띄어쓰기, 문장부호까지 그대로 쓴다. `{}`는 값이 들어가는 자리다. 이모지는 아이콘 자리에만 쓴다.

| 위치 | 문구 |
|---|---|
| 위성 버튼 설명 | `질문하기` / `읽기` / `정지` / `배속 (누를 때마다 바뀜)` / `설정` / `끝내기` |
| 질문창 | 빈 칸 안내 `청중의 질문을 입력하세요`, 보내기 단추 `↑` |
| 생각 깊이 | `생각 low` / `생각 mid` / `생각 high` + 점 `●○○` / `●●○` / `●●●` |
| 기다리는 말(목소리) | `조금만 기다려 주세요` / `아직 생각하고 있어요` |
| 오류, 강아지 말 / 알림 줄: 키 문제 | `앗, 제 열쇠가 맞지 않아요.` / `API 키가 없거나 틀렸어요. 설정에서 확인하세요.` |
| 오류: 요금·한도 | `오늘은 대답을 너무 많이 했나 봐요. 잠깐 쉬었다가 다시 물어봐 주세요.` / `요금 한도나 사용량 제한에 걸렸어요.` |
| 오류: 연결 끊김 | `인터넷이 끊긴 것 같아요.` / `인터넷 연결을 확인하세요.` |
| 오류: 시간 초과 | `생각이 너무 길어졌어요. 다시 물어봐 주시겠어요?` / `답이 늦어요. 생각 깊이를 낮춰 보세요.` |
| 오류: 기타 | `앗, 문제가 생겼어요.` / `{제공자가 보낸 오류의 첫 줄}` |
| 답하다 끊김 | `앗, 말하다가 연결이 끊겼어요.` |
| 알림 줄: 연동 끊김 | `PowerPoint 연결이 끊겼어요` |
| 알림 줄: 음성 실패 | `목소리를 낼 수 없어요. 출력 장치를 확인하세요.` |
| 설정 창 제목 | `설정 — PPT 읽어주기` |
| 머리 | `발표 준비 {n} / 4` / `발표 준비 끝! 🎉` |
| 카드 이름 | `발표 자료` / `목소리` / `질의응답` / `캐릭터와 화면`, 표시 `다음 할 일` |
| 발표 자료 | `슬라이드 {N}장 · 노트 있는 장 {k}개 · 고친 대본 {m}장`, `다른 파일…`, `📝 대본 열기`, `파일 열기…`, `또는 PowerPoint에 자료를 열고 연동을 켜세요`, `PowerPoint 연동`, `읽을 내용` |
| 연동 칩 | `PowerPoint 연결됨 · 쇼 진행 중 {n}번 장` / `PowerPoint 연결됨 · 편집 화면 {n}번 장` / `PowerPoint 찾는 중…` / `PowerPoint에 열린 발표 자료가 없어요` / `PowerPoint 연결이 끊겼어요` / `연동 꺼짐` / `파일 없음` |
| 목소리 | `목소리`, `들어 보기`, `출력 장치`, `다 읽으면 다음 장으로 넘어가기 (자동 발표)`, `쇼에서 장을 넘기면 바로 읽기`, `배속은 원 버튼의 위성 버튼에서 바꿔요.` |
| 질의응답 | `AI 제공자`, `모델`, `{모델} (기본)`, `직접 입력…`, `API 키`, `보기`/`숨기기`, `확인`, `개인 지침`, `모든 답에 반영돼요`, `그림 설명(캡션) 만들기`, `질의응답 근거로만 씀 · 요금이 조금 듦` |
| 키 확인 결과 | `키를 넣고 [확인]을 누르세요` / `확인 중…` / `✓ 키가 맞아요` / `✕ 키가 틀렸어요. 다시 확인하세요` / `확인하지 못했어요: {이유}` |
| 캐릭터와 화면 | `강아지`, `시바`/`치비 시바`, `비숑`/`몽실 비숑`, `비글`/`날씬 비글`, `· 기본`, `강아지 보이기`, `원 버튼 모니터`, `강아지도 이 모니터에서만 다녀요`, `쇼가 뜬 모니터 따라가기`, `{번호}번 — {이름} ({가로}×{세로})` |
| 설정 창 아래 | `바꾸면 바로 저장돼요`, `오픈 소스 라이선스`, 저장 표시 `저장됨` |
| 대본 창 | 제목 `대본 — {파일명}`, `✎ 고친 대본 — 고친 대로 읽습니다` / `자동으로 뽑은 대본 — 고치면 고친 대로 읽습니다`, `원래 내용으로`, `원본이 바뀌었어요`, `발표자 노트`, `(없음)`, `그림 캡션`, `이 장에는 그림이 없어요.` |
| 캡션 메타 | `그림 {i} 캡션`, 상태 `LLM이 만듦` / `✎ 고침` / `기다리는 중` / `캡션 꺼짐`, 건너뜀 `그림 {i}: {이유}` |
| 캡션 진행 막대 | `캡션 꺼짐` + `켜면 그림 설명을 만들어 질의응답 근거로 씁니다.` / `캡션 멈춤` + `API 키를 확인하세요. 키가 맞으면 다시 시작합니다.` / `캡션 만드는 중` + `{done} / {total}` + `멈추기` / `캡션 완료` + `다시 만들기` / `앞 40개만 만들었어요` / `캡션을 만들지 못했어요: {이유}` |
| 기존 문구 | 파일 대화상자, 옛 형식 경고, 열기 실패, 경로 모름, 다시 불러옴은 `PROMPT.md`의 <ui_strings>를 그대로 쓴다 |
</ui_strings>

<tests>
`python -m pytest -q tests`는 화면, 인터넷, 소리 없이 돈다. 설정 폴더는 `PPT_READER_HOME`으로 임시 폴더를 쓴다. 시간이 걸리는 규칙은 가짜 시계로 시험한다.

| 파일 | 시험할 것 |
|---|---|
| `test_slides.py` | 그대로 |
| `test_session.py` | 옛 `test_app_logic.py`의 일곱 시험(열기와 읽기, 자동 발표의 숨긴 장 건너뛰기, 고친 대본, PowerPoint 따라가기, 출력 장치, 모르는 파일, 설정 저장)을 가짜 음성·연동으로 옮긴다. 질의응답 흐름(생각 중 → 말하는 중 → idle, 질문을 보내면 읽기 멈춤, 기쁨 1.5초)도 시험한다 |
| `test_qa.py` | 근거 묶음의 내용과 순서(바뀌지 않는 부분이 앞, 지금 화면은 질문 쪽), 지침 합치기, 대화 기억 6번과 `(끊김)`, 문장 자르기(`3.5배`, 따옴표, 줄바꿈, 스트림 끝) |
| `test_llm.py` | 가짜 SDK 응답으로 세 어댑터: 글 조각만 나오고 생각 조각은 버림, `mid → medium`, SDK 예외를 다섯 종류로 바꾸기, 취소 |
| `test_voice.py` | 가짜 PCM으로 크기 곡선, 입 모양 판정(20%·55%, 가로 입 중성, 60ms 유지, 한글 아닌 글자), 음절 시각 어림, 블루투스 무음 길이 × r, 늘일 배율 r 계산, macOS 낱말 시각 어림. 옛 `test_tts.py`의 앞 무음 규칙을 여기로 옮긴다 |
| `test_captions.py` | 시험용 pptx를 코드로 만들어 그림 꺼내기(그룹, 자리표시자, 잘라내기), 작은 그림과 네 장 이상 반복 그림 빼기, 해시로 다시 쓰기, 고친 캡션 안 덮어쓰기, 40개 상한, 1024px 줄이기, 캡션 답 파싱 |
| `test_settings.py` | 기본값, 옛 설정 옮기기(속도 반올림 포함), 고친 대본 저장과 `원본이 바뀌었어요` 판정, 생각 깊이를 저장하지 않음 |
| `test_follow.py` | 따라가기 계산: 속도 공식, 오른쪽·아래 가장자리에서 반대쪽, 다른 모니터면 원 버튼 옆 자리, 원 버튼 묶음 위면 대기, 질의응답 중 머묾 |
| `test_errors.py` | 가짜 시계로 8초·30초 기다리는 말, low 45·mid 90·high 150초 시간 초과, 30초 멈춤, 오류 때 질문 다시 채우기 |
| `test_ui.py` | pytest-qt, `QT_QPA_PLATFORM=offscreen`: 창들이 뜨는지, 위성 버튼을 누르면 session이 불리는지, 설정 창에서 바꾼 값이 바로 저장되는지 |

- **실제 LLM 시험**: `@pytest.mark.live`를 달고, 환경 변수 `PPT_READER_LIVE_CLAUDE`, `PPT_READER_LIVE_OPENAI`, `PPT_READER_LIVE_GEMINI`에 키가 있을 때만 돈다.
  - 제공자마다 기본 모델, 생각 깊이 low로 짧은 질문 하나와 작은 그림 캡션 하나를 보낸다.
  - 빌드 서버에서는 돌리지 않는다.
- 근거: 19.
</tests>

<manual_checklists>
**Windows(발표자가 넘기기 전에 이 PC에서)**: 결과를 표로 보고한다.
1. 모니터 두 대에서 PowerPoint 쇼를 보조 모니터에 띄웠을 때, 강아지와 원 버튼이 쇼 위에 보인다.
2. 강아지와 투명한 곳은 클릭이 쇼로 통과한다.
3. 원 버튼을 눌러도 쇼가 키 입력을 계속 받는다.
4. 질문창에서 한글 IME로 입력되고, 닫으면 쇼로 포커스가 돌아온다.
5. 말풍선 낱말과 강아지 입(가로 입 포함)이 목소리와 맞는다.
6. x1.5, x2, x5의 음질(Heami와 다른 음성 각각)을 귀로 들어 본다.
7. 블루투스 이어폰으로 처음 읽을 때와 쉬었다가 읽을 때 첫마디가 잘리지 않는다.
8. 자동 발표가 숨긴 장을 건너뛰며 끝까지 가고, 끝에서 강아지가 기뻐한다.
9. 세 제공자 모두로 질의응답이 된다(low/high 각각).
10. 틀린 키, 인터넷 끊김, 답하다 끊김에서 강아지 말과 알림 줄이 맞게 나온다.
11. 캡션을 켜면 그림 설명이 생기고, 고칠 수 있고, 다시 켜도 다시 만들지 않는다.
12. 화면 배율 100%와 150%에서 설정 창과 대본 창이 잘리지 않는다.

**macOS(받는 사람, M1 Pro)**: `handoff/macos.txt`에 넣는다. 결과를 사진으로 돌려받는다.
1. macOS 판이 15 이상이다.
2. 실제 PowerPoint 쇼 위에 강아지와 원 버튼이 보인다.
3. 레티나 화면에서 크기와 위치가 맞는다.
4. 대본 읽기, 질의응답, 말풍선이 된다.
5. `--self-check` 결과(터미널에서 `PPTReader.app/Contents/MacOS/PPTReader --self-check`)를 보낸다.

근거: 17, 19.
</manual_checklists>

<build_and_handoff>
- **저장소 공개**: GitHub Actions 비공개 쿼타가 없어서, 공개 저장소의 무료 표준 러너를 쓴다. 공개는 되돌리기 어려우므로 **공개 전에 발표자에게 확인받고** 아래를 먼저 한다.
  1. 커밋 기록 전체에 API 키 같은 비밀이 없는지 검사한다.
  2. 커밋 작성자 이메일이 공개된다는 것을 발표자에게 알리고, 그대로 둘지 묻는다.
  3. `sample/` 발표 자료를 공개해도 되는지 묻는다.
  4. 원격에 올릴 브랜치(`research/*`, `prototype/*` 포함 여부)를 묻는다.
- **`.github/workflows/build.yml`**: `workflow_dispatch`로만 돈다.
  - 작업 `windows-latest`:
    1. Python 3.14
    2. `pip install -r requirements-dev.txt`
    3. `pytest -q tests`
    4. `pyinstaller ppt_reader.spec`
    5. `dist/PPTReader/PPTReader.exe --self-check`
    6. `licenses/`와 `handoff/windows.txt`를 넣어 `PPTReader-windows.zip`으로 묶어 올린다.
  - 작업 `macos-15`(arm64. `macos-latest`는 가리키는 판이 바뀌므로 쓰지 않는다):
    1. Python 3.14와 pytest
    2. `pyinstaller ppt_reader.spec`
    3. `--self-check`
    4. `codesign --verify --deep --strict dist/PPTReader.app`
    5. `lipo -archs`로 arm64만 담겼는지 확인
    6. 화면 시험: pyobjc로 만든 가짜 전체 화면 앱 위에 앱을 띄우고, cliclick으로 커서를 움직이며 `screencapture -x`로 찍어 산출물로 올린다.
    7. `ditto -c -k --keepParent dist/PPTReader.app PPTReader-macos-arm64.zip`으로 묶어 `actions/upload-artifact@v7`에 `archive: false`로 올린다.
- **`ppt_reader.spec`**:
  - onedir를 유지한다. 그래야 Qt와 FFmpeg가 따로 된 라이브러리로 남아 바꿔 끼울 수 있다(LGPL).
  - `ppt_reader/assets/*.png`를 넣는다.
  - PySide6-Addons에 딸려 오는 가상 키보드 플러그인(`qtvirtualkeyboardplugin`, Qt Quick/Qml 따라옴, 약 16MB)을 빼 본다. 빼도 질문창 입력과 소리가 되는지 `--self-check`와 사람 확인으로 본다.
  - macOS `info_plist`는 기존 세 키를 유지한다.
- **`licenses/`**: Qt(LGPLv3), PySide6, FFmpeg(LGPL-2.1+), anthropic, openai, google-genai, python-pptx, Pillow, pywin32, pyobjc의 라이선스 원문을 넣는다.
- **`handoff/windows.txt`**: 서명이 없어 처음 실행 때 "Windows의 PC 보호"가 뜨면 [추가 정보] → [실행]을 누르라는 안내다.
- **`handoff/macos.txt`**:
  1. macOS 15 이상인지 확인(사과 메뉴 → 이 Mac에 관하여)
  2. `PPTReader.app`을 응용 프로그램 폴더로 옮기기
  3. 열려고 한 뒤 시스템 설정 › 개인정보 보호 및 보안에서 [그래도 열기](약 1시간만 보임). macOS 15부터 Control-클릭 › 열기 우회는 없다.
  4. PowerPoint 제어 허용
  5. 새 판을 받을 때마다 위 과정을 반복하기(ad-hoc 서명이라 자동화 허용도 다시 묻는다)
  6. 확인표(<manual_checklists>)
- 근거: 13, 17, `docs/research/mac-without-mac.md`.
</build_and_handoff>

<known_pitfalls>
`PROMPT.md`의 <known_pitfalls> 1~5, 9~13, 19는 그대로 지킨다. 19의 "출력 형식을 바꾸지 말라"는 말은 "앞 무음 규칙을 지키라"로 읽는다. 14(SAPI가 기본 출력 장치를 따라가지 않음)는 재생이 Qt로 옮겨 가므로 없어진다. 대신 "시스템 기본 장치"를 고른 경우 문장마다 `QMediaDevices.defaultAudioOutput()`을 다시 읽는다. tkinter에만 해당하는 6~8, 15~18도 없어진다. 아래를 더한다.
1. PySide6에는 `QTextToSpeech.synthesize()`가 없다(C++ 템플릿이라 옮겨지지 않음). 그래서 Qt 음성으로는 크기 곡선을 만들 PCM을 얻지 못한다. 합성은 SAPI와 say로 한다.
2. SAPI `SpeakStream`은 Rate와 Volume을 적용하지 않는다. 배속은 합성할 때 넣는다. 미리 합성하면 재생 중에 단어 이벤트가 오지 않으므로, 합성할 때 받은 위치를 쓴다.
3. SAPI x5의 `<rate absspeed="5"/>`(SVSFPersistXML)는 다음 읽기에도 남는다. x5가 아니면 되돌린다.
4. `QMediaPlayer`의 음높이 유지는 FFmpeg 백엔드에서만 된다. Windows 자체 백엔드(Media Foundation)는 안 된다. `QT_MEDIA_BACKEND=ffmpeg`.
5. `QMediaPlayer.position()`은 50~100ms마다만 바뀐다. 보간하지 않으면 입과 말풍선이 뚝뚝 끊긴다.
6. Qt는 Windows에서 `QAudioSink` 예열을 하지 않는다. 블루투스 앞 무음은 앱이 붙인다. 늘일 때는 무음 길이에 배율을 곱한다.
7. python-pptx는 EMF를 `image/x-wmf`로 잘못 알려 준다. 그림 부분의 `content_type`으로 판별한다. 그림 자리표시자는 `isinstance(sh, Picture)`로 골라야 한다.
8. macOS에서 다른 앱의 전체 화면 위에 띄우려면 NSPanel(활성화하지 않음), `NSScreenSaverWindowLevel`, `CanJoinAllApplications`가 함께 필요하다. Qt의 StaysOnTop만으로는 전체 화면 아래로 깔린다.
9. macOS 앱을 `upload-artifact`에 폴더째 올리면 실행 권한과 심볼릭 링크가 깨져 "손상됨"이 뜬다. `ditto`로 묶는다.
10. PySide6 6.12.0 바인딩은 최소 macOS 26으로 빌드되어 있다. 6.11.x에 고정한다.
11. 생각 토큰도 출력 한도에 들어간다. 한도를 작게 잡으면 답이 비거나 잘린다.
12. LLM 키를 로그나 오류 문구에 찍지 않는다. SDK 예외 문자열에 키 일부가 들어 있을 수 있으니 오류 첫 줄에서도 키 모양 문자열을 지운다.
13. 시험과 검증은 사용자의 설정 폴더를 건드리지 않는다. `PPT_READER_HOME`을 임시 폴더로 둔다.
14. 화면을 캡처해 검증할 때는 앱 창 영역만 찍는다. 다른 창(메신저 등)이 찍히지 않게 한다. 실제 클릭이나 키 입력을 흉내 내는 시험은 사용자 PC에서 하지 않는다.
</known_pitfalls>

<workflow>
단계마다 pytest가 통과하고, 그 단계의 확인이 끝나야 다음 단계로 넘어간다. 단계마다 house-style 커밋 양식으로 커밋한다.
1. **뼈대**
   - Qt 앱 시작, `settings.py`(옛 설정 옮기기), `session.py`(옛 흐름 시험 옮기기)
   - `tools/dog_sprites.py`로 스프라이트 PNG 만들기(땀방울 덧그림 포함)
   - `--self-check`, `platform_mac.py`
   - 빌드 워크플로(저장소 공개 전 확인 포함)
   - 확인: 두 운영체제 빌드 성공, macOS 화면 시험 사진에서 가짜 전체 화면 위에 창이 보임
   - macOS는 빌드 서버로만 확인할 수 있으므로 이 길을 먼저 뚫는다.
2. **음성 흐름**: `voice/` 전체. 대본 읽기, 자동 발표, `--say`를 새 흐름으로 옮긴다.
   - 확인: 블루투스 첫마디, 배속 네 가지, 장치 고르기
3. **강아지와 원 버튼**: 따라가기, 자세, 파동, 위성 버튼, 알림 줄
   - 확인: 쇼 위 표시, 클릭 통과, 포커스
4. **질의응답**: `llm/`, `qa.py`, 질문창, 생각 깊이, 말풍선 스트림, 오류 반응
   - 확인: 세 제공자 실제 호출(live), 오류 네 가지
5. **설정 창, 대본 창, 캡션**
   - 확인: 처음 실행 흐름, 바로 저장, 캡션 다시 쓰기
6. **넘기기**: `licenses/`, `handoff/`, `README.md` 고치기, <manual_checklists>의 Windows 확인
</workflow>

<acceptance_criteria>
아래를 모두 만족해야 완료다.
- [ ] `python -m pytest -q tests`가 모두 통과한다(live 제외)
- [ ] 빌드 워크플로가 두 운영체제에서 성공하고, `--self-check`가 모두 OK다
- [ ] macOS 화면 시험 사진에서 가짜 전체 화면 앱 위에 강아지와 원 버튼이 보인다
- [ ] Windows에서 PowerPoint 쇼 위에 강아지와 원 버튼이 보이고, 클릭 통과와 포커스 유지가 된다
- [ ] 강아지 입과 말풍선 낱말이 목소리를 따라가고, ㅣ·ㅔ 소리에서 가로 입이 나온다
- [ ] x1, x1.5, x2, x5가 모든 음성에서 동작하고 음높이가 유지된다
- [ ] 블루투스 첫마디가 잘리지 않고, 앞 무음이 배속과 상관없이 1초다
- [ ] 세 제공자로 질의응답이 되고, 다섯 오류가 <ui_strings>대로 나온다
- [ ] 설정은 바꾸면 바로 저장되고, 고친 대본과 캡션이 다시 켜도 남는다
- [ ] 같은 장을 두 번 읽는 일이 없다(기존 기준)
- [ ] <manual_checklists>의 Windows 항목을 모두 확인했다
</acceptance_criteria>

<output_format>
단계를 마칠 때마다 한국어로 짧게 보고한다. 구성은 `PROMPT.md`의 <output_format>과 같다.
- "이 OS에서 실행하지 못한 플랫폼 코드"(특히 macOS)는 확인하지 못한 것의 맨 앞에 쓴다.
- 빌드 서버에서 확인한 것과 받는 사람 확인표로 넘긴 것을 나눠 적는다.
- 확인하지 않은 것을 확인했다고 쓰지 않는다.
</output_format>

<evidence>
| 번호 | 결정 | 기록 |
|---|---|---|
| 01 | 목적지와 기본 요구사항 | `.scratch/character-qa/issues/01-destination-and-requirements.md` |
| 02 | GUI 툴킷 조사 | `docs/research/gui-toolkit.md` |
| 03 | LLM 제공자, 모델, 생각 깊이 | `docs/research/llm-providers.md` |
| 04 | 음성 신호와 배속 | `docs/research/tts-signal-speed.md` |
| 05 | 슬라이드 그림 꺼내기 | `docs/research/slide-images.md` |
| 06 | 강아지 스프라이트 | `issues/06-prototype-dog-sprites.md`, `prototype/dog-sprites@faa9bd6` |
| 07 | 원 버튼, 위성 버튼, 질문창, 말풍선 | `issues/07-prototype-orb-and-satellites.md`, `prototype/orb@e1fc8b7` |
| 08 | 질의응답 때 LLM에 넘길 것 | `issues/08-grilling-qa-prompt.md` |
| 09 | GUI 툴킷 결정(PySide6) | `issues/09-grilling-gui-toolkit.md` |
| 10 | 목소리를 따라가는 방식 | `issues/10-grilling-voice-reactive-motion.md`, `docs/research/qt-audio-tts.md` |
| 11 | 캡션 | `issues/11-grilling-captions.md` |
| 12 | SDK와 Python 3.10 | `issues/12-grilling-llm-client.md` |
| 13 | Mac 없이 macOS판 만들기 | `docs/research/mac-without-mac.md` |
| 14 | 커서 따라가기 | `issues/14-grilling-cursor-follow.md` |
| 15 | 설정 창 | `issues/15-prototype-settings-window.md`, `prototype/settings@0660347` |
| 16 | 프로그램 구조 | `issues/16-grilling-program-structure.md` |
| 17 | 빌드와 넘기기 | `issues/17-grilling-build-and-handoff.md` |
| 18 | 오류 반응 | `issues/18-grilling-error-reactions.md` |
| 19 | 시험 방법 | `issues/19-grilling-test-plan.md` |
| 20 | 기획서 위치와 목차 | `issues/20-grilling-spec-outline.md` |
`issues/`는 `.scratch/character-qa/issues/`다.
</evidence>

</prompt>
````
