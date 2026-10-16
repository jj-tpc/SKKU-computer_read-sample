# Qt로 바꾼 뒤의 프로그램 구조 정하기

Type: grilling
Status: resolved
Blocked by: 08, 10, 12

## Question

[GUI 툴킷 결정](09-grilling-gui-toolkit.md)으로 `app.py`의 tkinter 창이 Qt로 바뀐다. 그러면 `ppt_reader`의 구조는 어떻게 되나?

정할 것:
- **모듈 경계**: 기존 `slides.py`, `tts.py`, `link.py`를 어떻게 살리고, 캐릭터, 원 버튼, 질의응답, LLM, 캡션, 설정 화면을 어떤 모듈로 나누나.
- **일하는 곳**: 음성 합성·재생, PowerPoint 연동, LLM 요청을 어느 스레드에서 돌리고, 화면과 어떻게 주고받나(Qt 신호 등). 멈추기와 끝내기를 어떻게 전하나.
- **설정 파일**: 형식과 위치, 기존 설정 파일에서 옮겨 오기, API 키 저장(평문으로 저장하기로 함).
- **시작점**: `python -m ppt_reader`와 실행 파일이 무엇을 띄우나. 처음 실행 때 무엇이 보이나.

## Answer

- **모듈**: `ui/` 밖의 모듈은 Qt 화면을 모르게 두어 화면 없이 pytest로 시험할 수 있게 한다(소리 재생 `voice/player.py`만 Qt 소리 모듈을 쓴다).
```
ppt_reader/
  __main__.py     명령줄 그대로. 옵션이 없으면 Qt 화면을 띄운다
  slides.py       그대로 (슬라이드 글 뽑기)
  link.py         그대로 (PowerPoint 연동 스레드)
  settings.py     설정 파일 읽기·쓰기·옛 파일 옮겨 오기
  voice/          tts.py를 나눔
    engines.py      SAPI 메모리 합성, say -o → 소리 데이터와 낱말 시각
    signal.py       크기 곡선, 입 모양 네 가지(중성 판정 포함)
    player.py       Qt 재생, 장치, 배속 늘이기, 블루투스 무음
    pipeline.py     문장 줄: 앞 문장 재생 중 다음 문장 합성
  llm/            공통 경계(base.py) + claude.py, openai.py, gemini.py
  qa.py           근거 묶음, 지침 합치기, 대화 기억 6번, 답을 문장으로 자르기
  captions.py     그림 꺼내기, 캡션 만들기·저장
  ui/             Qt 화면만
    app.py          시작, 상태 묶음, 신호 잇기
    dog.py          강아지 창(따라가기, 자세)
    orb.py          원 버튼 묶음(파동, 위성 버튼, 질문창, 생각 깊이, 알림 줄)
    bubble.py       말풍선(스트림)
    settings_window.py, script_window.py
    mac.py          macOS 보조(pyobjc: 전체 화면 위, NSPanel)
  assets/         강아지 스프라이트 PNG
```
- **스프라이트**: `tools/`의 생성기로 PNG를 미리 만들어 `assets/`에 넣고, 실행할 때는 읽기만 한다.
- **일하는 곳**:

| 일 | 어디서 |
|---|---|
| 화면, 애니메이션(30~60fps), 소리 재생 | Qt 주 스레드 |
| 음성 합성 | 전용 스레드 하나(SAPI는 자기 스레드가 필요) |
| PowerPoint 연동 | 전용 스레드(지금 `link.py` 그대로) |
| LLM 답 받기 | 질문마다 작업 스레드 하나 |
| 캡션 만들기 | 뒤에서 차례로 도는 작업 스레드 하나 |

- **주고받기**: 일하는 스레드 → 화면은 Qt 신호로 보낸다(50ms마다 큐를 들여다보는 방식은 없앤다). 화면 → 일하는 스레드는 지금처럼 명령 큐다.
- **멈추기**: [읽기/정지]로 정지하면 재생을 멈추고 합성 줄을 비운다. 새 질문을 보내면 이전 답의 스트림을 닫는다.
- **끝내기**: [끝내기]는 읽기 정지 → LLM·캡션 취소 → 연동 닫기 → 설정 저장 → 종료 순서다.
- **설정 파일**:
  - 위치: 운영체제 표준 앱 폴더(Windows `%APPDATA%\PPT읽어주기\`, macOS `~/Library/Application Support/PPT읽어주기/`).
  - 담는 것: `settings.json`(버전 번호 포함, API 키는 평문), 캡션, 고친 대본.
  - 옛 설정 옮기기: 처음 켤 때 옛 `~/.ppt_reader_settings.json`이 있으면 값을 옮겨 오고, 옛 파일은 건드리지 않는다.
  - 기억: 배속은 마지막 값을 기억한다. 생각 깊이는 켤 때마다 low로 시작한다.
- **고친 대본 저장**: 발표 파일 경로와 장 번호로 저장한다(지금은 끄면 사라진다). 같은 파일을 다시 열었는데 그 장의 원래 글이 바뀌었으면, 고친 대본은 두고 대본 창에 "원본이 바뀌었어요"를 표시한다.
- **시작점**:
  - `python -m ppt_reader [파일]`과 실행 파일은 강아지와 원 버튼만 띄운다(창 없음). 파일을 주면 연다.
  - 처음 켰을 때는 설정 창도 저절로 연다.
  - `--dump`, `--say`, `--list-voices`, `--list-outputs`, `--probe-ppt`는 지금처럼 화면 없이 돌고, Qt를 불러오지 않는다.

## Comments

- 2026-10-16 화면은 강아지, 원 버튼 묶음(위성 버튼 다섯 개, 질문창, 생각 깊이, 알림 줄, 말풍선), 설정 창, 설정 창에서 여는 대본 창이다([설정 창 구성 정하기](15-prototype-settings-window.md)). 설정은 바꾸면 바로 저장한다.
- 2026-10-17 [시험 방법 정하기](19-grilling-test-plan.md)에서 모듈 하나를 더했다. 읽기 흐름, 자동 발표, PowerPoint 따라가기, 질의응답 흐름 같은 상태 묶음은 Qt를 모르는 `session.py`에 두고, `ui/app.py`는 신호만 잇는다.
