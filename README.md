# PPT 읽어주기

교실 발표에서 컴퓨터가 "AI 발표자" 역할을 하는 프로그램입니다. 화면 위의 도트 강아지가 마우스 커서를 따라다니며 슬라이드 대본을 소리 내어 읽고, 발표가 끝나면 청중의 질문에 발표 자료를 근거로 답합니다.
**Windows 10/11과 macOS 15 이상(Apple Silicon)**에서 같은 코드로 동작합니다.

## 할 수 있는 것

| 기능 | 설명 |
|---|---|
| 대본 읽기 | `.pptx`에서 슬라이드마다 대본을 만들어 읽습니다. 읽을 내용은 노트 우선 / 본문 / 노트 / 본문+노트 중에서 고릅니다. |
| 대본 고치기 | 대본 창에서 고치면 고친 대로 읽습니다(예: `AI` → `에이아이`). 고친 대본은 다시 켜도 남습니다. |
| PowerPoint 연동 | PowerPoint에 띄운 파일을 불러오고, 쇼에서 장을 넘기면 그 장을 읽습니다. |
| 자동 발표 | 한 장을 다 읽으면 쇼도 다음 장으로 넘기고 이어 읽습니다. 숨긴 장은 건너뜁니다. |
| 배속 | x1, x1.5, x2, x5. 음높이는 그대로입니다. |
| 목소리 엔진 | 운영체제 음성(인터넷 없이), ElevenLabs, Gemini 중에서 고릅니다. 클라우드 음성이 실패하면 그 문장부터 운영체제 음성으로 이어 읽습니다. |
| 질의응답 | 발표자가 청중의 질문을 입력하면 강아지가 자료를 먼저 근거로 삼아 목소리와 말풍선으로 답합니다. Claude, OpenAI, Gemini 중에서 고릅니다. |
| 그림 캡션 | 켜 두면 슬라이드 속 그림 설명을 만들어 질의응답 근거로 씁니다(기본은 꺼짐). |

## 화면

- **강아지**: 커서 오른쪽 아래를 따라다닙니다. 읽는 동안 입이 목소리를 따라 움직이고, 질문을 받으면 생각하는 자세로 기다립니다. 클릭은 아래 화면으로 통과합니다.
- **원 버튼**: 화면 오른쪽 아래의 코랄빛 원입니다. 누르면 위성 버튼 다섯 개가 펼쳐집니다.
  - `?` 질문하기 · `▶/■` 읽기/정지 · `x1` 배속 · `⚙` 설정 · `✕` 끝내기
- **질문창**: [질문하기]를 누르면 원 버튼 왼쪽에 열립니다. Enter로 보내고 Esc로 닫습니다. 위의 "생각 low/mid/high" 버튼으로 생각 깊이를 고릅니다.
- **설정 창**: "발표 준비 n / 4"와 카드 네 장(발표 자료, 목소리, 질의응답, 캐릭터와 화면)이 있습니다. 바꾸면 바로 저장됩니다. 처음 켜면 저절로 열립니다.
- **대본 창**: 설정 창의 [📝 대본 열기]로 엽니다. 슬라이드마다 대본, 발표자 노트, 그림 캡션을 보고 고칩니다.
- **알림 줄**: 문제가 생기면 원 버튼 왼쪽 위에 6초 동안 원인과 할 일을 짧게 보입니다.

## 실행하기

### 실행 파일(권장)
GitHub Actions에서 만든 zip을 받아 압축을 풀고 안의 "먼저 읽어 주세요.txt"를 따릅니다.
- Windows: `PPTReader\PPTReader.exe`
- macOS: `PPTReader.app`(서명이 없어 처음에 [그래도 열기]가 필요합니다)

### 소스로 실행
[Python 3.10 이상](https://www.python.org/downloads/)이 필요합니다.
- Windows: `run_windows.bat`을 두 번 누릅니다.
- macOS: 터미널에서 `bash run_mac.sh`
- 직접:
  ```bash
  python -m venv .venv
  # Windows: .venv\Scripts\activate      macOS: source .venv/bin/activate
  pip install -r requirements.txt
  python main.py                                   # 강아지와 원 버튼
  python main.py sample/sample_presentation.pptx   # 파일을 열면서
  ```

## 질의응답 준비

1. 설정 창 › 질의응답에서 AI 제공자(Claude / OpenAI / Gemini)를 고릅니다.
2. 그 회사의 API 키를 넣고 [확인]을 누릅니다. "✓ 키가 맞아요"가 나오면 됩니다.
3. 필요하면 개인 지침(말투, 답 길이 등)을 적습니다. 모든 답에 반영됩니다.

키는 설정 파일에 그대로 저장됩니다. 함께 쓰는 컴퓨터라면 다 쓴 뒤 지우세요.

## 클라우드 음성(선택)

설정 창 › 목소리 › 목소리 엔진에서 ElevenLabs나 Gemini를 고르고 키를 확인하면 그 목소리로 대본과 답을 읽습니다.
- 파일을 열면 대본 소리를 뒤에서 미리 만들어 둡니다(진행은 목소리 카드에 보입니다). 다 만든 뒤에는 인터넷이 끊겨도 대본을 읽습니다.
- Gemini 음성은 질의응답의 Gemini 키를 함께 씁니다.
- ElevenLabs 무료 등급은 한 달에 약 1만 자라서, 노트가 긴 발표는 미리 만들기만으로 다 쓸 수 있습니다.

## 한국어 음성 설치(운영체제 음성)

- **Windows**: 설정 → 시간 및 언어 → 음성 → 음성 추가 → 한국어. 한국어판 Windows에는 `Microsoft Heami`가 있습니다.
- **macOS**: 시스템 설정 → 손쉬운 사용 → 읽기 및 말하기 → 시스템 음성 → 음성 관리 → 한국어(Yuna 등).

## 문제 해결

| 증상 | 해결 |
|---|---|
| 소리가 안 남 | 설정 › 목소리에서 다른 음성이나 출력 장치를 고르고 [들어 보기]를 누릅니다. |
| 블루투스 이어폰 첫마디가 잘림 | 2초 넘게 조용했다가 읽기 시작할 때 앞에 1초 무음을 넣어 둡니다(배속과 상관없이 1초). |
| 이어폰을 꽂았는데 스피커로 나옴 | 설정 › 출력 장치에서 이어폰을 직접 고릅니다. 목록을 펼 때마다 장치를 다시 찾습니다. |
| "API 키가 없거나 틀렸어요" | 설정 › 질의응답에서 키를 다시 넣고 [확인]을 누릅니다. |
| "답이 늦어요" | 질문창 위의 생각 깊이를 low로 낮춥니다. |
| 연동했는데 "파일 위치를 알 수 없습니다" | PowerPoint 파일을 먼저 저장합니다. OneDrive 파일은 동기화 폴더에 있어야 합니다. |
| `.ppt` 파일이 안 열림 | PowerPoint에서 다른 이름으로 저장 → `.pptx`로 바꿉니다. |
| macOS에서 쇼 위에 안 보임 | 터미널에서 `PPTReader.app/Contents/MacOS/PPTReader --self-check`를 실행해 "macOS 보조" 줄이 OK인지 봅니다. |

명령줄 도구(화면 없이 돕니다):
```bash
python main.py --list-voices                       # 운영체제 음성 목록 (* = 한국어)
python main.py --list-outputs                      # 출력 장치 목록 (* = 지금 기본 장치)
python main.py --dump 발표.pptx                    # 슬라이드별 대본 출력 (소리 없음)
python main.py --say 발표.pptx --slide 2 --speed 1.5   # 화면 없이 읽기 (배속 1.0·1.5·2.0·5.0)
python main.py --probe-ppt                         # PowerPoint 연동 상태 확인
```

## 빌드와 시험

- 자동 시험: `pip install -r requirements-dev.txt` 뒤 `python -m pytest -q tests` (화면·인터넷·소리 없이 돕니다).
  실제 API 시험은 `PPT_READER_LIVE_CLAUDE`, `PPT_READER_LIVE_OPENAI`, `PPT_READER_LIVE_GEMINI`, `PPT_READER_LIVE_ELEVENLABS`에 키를 넣었을 때만 돕니다.
- 실행 파일: GitHub Actions의 `build` 워크플로를 손으로 돌립니다(`gh workflow run build.yml --ref <브랜치>`). Windows판과 macOS판(Apple Silicon)을 함께 만들고, `--self-check`, 서명·arm64 검사, 가짜 전체 화면 위 화면 시험을 합니다.
- 로컬 빌드: `pyinstaller --noconfirm ppt_reader.spec` (Windows는 Windows에서).
- 앱 아이콘: 원 버튼 그림(`ppt_reader/ui/icon.py`)을 바꾸면 `python tools/make_icon.py`로 실행 파일 아이콘(`app.ico`, `app.icns`)을 다시 만듭니다.

## 구조

```
main.py                 시작점
ppt_reader/
  __main__.py           명령줄. 옵션이 없으면 Qt 화면, --self-check
  session.py            상태 묶음: 읽기, 자동 발표, PowerPoint 따라가기, 질의응답 (Qt를 모름)
  settings.py           설정 파일, 고친 대본, 옛 설정 옮기기
  slides.py, link.py    대본 뽑기, PowerPoint 연동
  follow.py             강아지 따라가기 계산
  qa.py                 근거 묶음, 지침, 대화 기억, 문장 자르기
  captions.py           그림 꺼내기와 캡션
  voice/                합성(운영체제·클라우드), 신호, 재생, 문장 줄, 저장
  llm/                  Claude·OpenAI·Gemini 어댑터
  ui/                   Qt 화면: 강아지, 원 버튼, 말풍선, 설정 창, 대본 창, 앱 아이콘
  assets/               강아지 스프라이트, 실행 파일 아이콘
tools/                  스프라이트·아이콘 생성기, 예제 자료, macOS 화면 시험
licenses/               오픈 소스 라이선스
handoff/                받는 사람용 안내문
```

설정·고친 대본·캡션·대본 소리는 운영체제 앱 폴더에 저장됩니다(Windows `%APPDATA%\PPT읽어주기`, macOS `~/Library/Application Support/PPT읽어주기`).
자세한 명세는 `PROMPT-character-qa.md`(이번 판), `PROMPT.md`(v1.0)에 있습니다.
