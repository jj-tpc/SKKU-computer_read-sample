# PPT 읽어주기

학생이 발표할 PPT를 띄워 두면, 컴퓨터가 슬라이드 내용(또는 발표자 노트)을 소리 내어 읽어 주는 프로그램입니다.
**Windows와 macOS**에서 같은 코드로 동작하고, 운영체제에 들어 있는 음성을 쓰므로 **인터넷 없이** 읽습니다.

## 할 수 있는 것

| 기능 | 설명 |
|---|---|
| PPT 파일 읽기 | `.pptx` 파일을 열면 슬라이드별 대본이 만들어집니다. 제목 → 본문 → 표 순서로, 글상자는 위→아래, 왼쪽→오른쪽 순서로 읽습니다. |
| 읽을 내용 선택 | 노트 우선(노트가 없으면 본문) / 슬라이드 본문 / 발표자 노트 / 본문+노트 |
| 대본 고치기 | 오른쪽 칸에서 대본을 고치면 고친 대로 읽습니다. 예: `AI` → `에이아이`처럼 발음을 바로잡을 수 있습니다. |
| **PowerPoint 연동** | PowerPoint에 띄워 둔 파일을 자동으로 불러오고, 슬라이드 쇼에서 장을 넘기면 그 장을 바로 읽습니다. |
| **자동 발표** | 한 장을 다 읽으면 PowerPoint 슬라이드 쇼도 다음 장으로 넘기고 이어서 읽습니다. 숨긴 슬라이드는 건너뜁니다. |
| 목소리·속도 | 설치된 음성 중에서 고르고, 0.5~2배속으로 조절합니다. 설정은 다음 실행 때도 유지됩니다. |
| 출력 장치 | 스피커, 이어폰처럼 소리가 나올 장치를 고릅니다. **시스템 기본 장치**를 고르면 Windows/macOS 소리 설정의 기본 장치를 따라갑니다. 고른 이어폰의 연결이 끊겨 있으면 기본 장치로 읽고, 다시 연결되면 이어폰으로 읽습니다. |

## 실행하기

먼저 [Python 3.9 이상](https://www.python.org/downloads/)을 설치하세요. Windows에서는 설치할 때 **"Add python.exe to PATH"**를 체크합니다.

### Windows
`run_windows.bat`을 더블클릭합니다. 처음 한 번은 필요한 패키지를 설치하느라 1~2분 걸립니다.

### macOS
터미널에서 이 폴더로 이동해 실행합니다.
```bash
bash run_mac.sh
```
python.org에서 받은 Python을 권장합니다. Homebrew Python을 쓴다면 `brew install python-tk`가 필요합니다.

### 직접 실행 (두 운영체제 공통)
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS: source .venv/bin/activate
pip install -r requirements.txt
python main.py                                   # 화면 실행
python main.py sample/sample_presentation.pptx   # 파일을 열면서 실행
```

## 사용 방법

### 1) 파일만 열어서 읽기
1. **[파일 열기...]**로 `.pptx`를 고릅니다. (시연용 예제: `sample/sample_presentation.pptx`)
2. 왼쪽 목록에서 슬라이드를 고르고 **[▶ 읽기]** 또는 **스페이스바**를 누릅니다.
3. 끝까지 쭉 읽게 하려면 **[다 읽으면 다음 장으로 넘어가기]**를 켭니다.

### 2) PowerPoint에 띄워 놓고 읽기 (연동)
1. PowerPoint에서 발표 파일을 열어 둡니다. 저장된 파일이어야 합니다.
2. 이 프로그램에서 **[PowerPoint 연동]**을 켜면 PowerPoint에 열린 파일을 자동으로 불러옵니다.
3. 슬라이드 쇼(F5)를 시작하면 첫 장부터 읽습니다. 발표자가 장을 넘기면 그 장을 바로 읽습니다.
4. **[다 읽으면 다음 장으로 넘어가기]**까지 켜면 프로그램이 읽고 넘기기를 반복합니다. 발표자 없이 진행되는 **자동 발표**입니다.
5. 슬라이드 쇼를 끝내면 읽기도 멈춥니다. 쇼 중에 이 프로그램 창이 가려지면 **[항상 위]**를 켜 두세요.

PowerPoint에서 내용을 고치고 **저장**하면 다음에 장이 바뀔 때 자동으로 다시 불러옵니다. 저장하지 않은 변경은 반영되지 않습니다.

### 단축키
| 키 | 동작 |
|---|---|
| 스페이스바 / F5 | 읽기 / 정지 (대본 칸에서 글을 쓸 때는 제외) |
| Esc | 정지 |
| Page Up / Page Down | 이전 / 다음 슬라이드 |

## 한국어 음성 설치

목소리 목록에 한국어 음성이 없으면 영어 음성으로 읽게 됩니다.

- **Windows**: 설정 → 시간 및 언어 → 음성 → **음성 추가** → 한국어. 한국어판 Windows에는 `Microsoft Heami`가 기본으로 들어 있습니다.
- **macOS**: 시스템 설정 → 손쉬운 사용 → 읽기 및 말하기 → 시스템 음성 옆 **(i)** 또는 '음성 관리' → 한국어 **Yuna** 등을 내려받습니다.

설치한 뒤 프로그램을 다시 실행하세요.

## macOS 권한 (PowerPoint 연동 시)

연동을 처음 켜면 *"…이(가) 'Microsoft PowerPoint'를 제어하려고 합니다"* 창이 뜹니다. **허용**을 누르세요.
실수로 거부했다면 **시스템 설정 → 개인정보 보호 및 보안 → 자동화**에서 터미널(또는 PPTReader)의 Microsoft PowerPoint 항목을 켭니다.

## 실행 파일 만들기 (Python 없는 컴퓨터에 나눠 줄 때)

Windows용은 Windows에서, Mac용은 Mac에서 각각 빌드합니다.
```bash
pip install pyinstaller
pyinstaller ppt_reader.spec
```
- Windows: `dist/PPTReader/` 폴더 전체를 압축해서 나눠 주고, 받은 사람은 `PPTReader.exe`를 실행합니다.
- macOS: `dist/PPTReader.app`이 만들어집니다. 서명하지 않은 앱이라 처음 열 때 **오른쪽 클릭 → 열기**로 실행해야 합니다.

## 문제 해결

| 증상 | 해결 |
|---|---|
| 소리가 안 남 | 목소리 목록에서 다른 음성을 골라 보세요. 출력 장치와 음량도 확인합니다. |
| 이어폰을 꽂았는데 스피커로 나옴 | **[출력 장치]**에서 이어폰을 직접 고르세요. 목록을 펼 때마다 새로 연결된 장치를 다시 찾습니다. Windows에서 이어폰이 '기본 통신 장치'로만 잡혀 있으면 '시스템 기본 장치'는 여전히 스피커입니다. `python main.py --list-outputs`에서 `*`가 붙은 장치가 지금 기본 장치입니다. |
| 연동했는데 "파일 위치를 알 수 없습니다" | PowerPoint 파일을 먼저 저장하세요. OneDrive 파일이 동기화 폴더에 없을 때도 이 문구가 뜹니다. 이때는 **[파일 열기]**로 같은 파일을 직접 열면 이름으로 맞춰서 따라갑니다. |
| `.ppt` 파일이 안 열림 | 예전 형식입니다. PowerPoint에서 **다른 이름으로 저장 → .pptx**로 바꿔 주세요. |
| 연동 상태를 확인하고 싶음 | `python main.py --probe-ppt`를 실행하면 PowerPoint가 알려 주는 현재 상태가 출력됩니다. |

명령줄 도구도 있습니다.
```bash
python main.py --list-voices                       # 쓸 수 있는 음성 목록 (* = 한국어)
python main.py --list-outputs                      # 출력 장치 목록 (* = 지금 기본 장치)
python main.py --dump 발표.pptx                    # 슬라이드별 대본 출력 (소리 없음)
python main.py --say 발표.pptx --slide 2 --speed 1.2   # 화면 없이 바로 읽기
python main.py --say 발표.pptx --output 헤드폰        # 이름에 '헤드폰'이 들어간 장치로 읽기
```

## 구조

```
main.py                 시작점 (python main.py)
ppt_reader/
  app.py                화면(tkinter): 슬라이드 목록, 대본 편집, 읽기 제어, 연동 처리
  slides.py             .pptx에서 제목·본문·표·발표자 노트 추출, 읽기 좋게 다듬기
  tts.py                음성 합성과 출력 장치 선택: Windows = SAPI(pywin32), macOS = say 명령
  link.py               PowerPoint 연동: Windows = COM, macOS = AppleScript(osascript)
  __main__.py           명령줄 옵션(--dump, --say, --list-voices, --probe-ppt)
tools/make_sample.py    예제 발표 자료 생성
tests/                  자동 테스트 (python -m pytest)
ppt_reader.spec         실행 파일 빌드 설정 (PyInstaller)
```

음성 재생과 PowerPoint 확인은 각각 별도 스레드에서 돌아가므로, 읽는 동안에도 화면이 멈추지 않습니다.
PowerPoint 상태는 Windows에서 0.4초, macOS에서 0.7초마다 확인합니다.
