# Mac 없이 macOS판을 만들고 확인하는 방법

Type: research
Status: resolved

## Question

발표자에게는 Mac도 macOS 실행 파일도 없는데, macOS에서 도는 완성품을 넘겨야 한다([GUI 툴킷 결정](09-grilling-gui-toolkit.md)에서 확인). Mac 없이 macOS 실행 파일을 만들고, 할 수 있는 만큼 확인하는 방법은 무엇인가?

확인할 것:
1. **빌드**: 이 저장소(GitHub `jj-tpc/SKKU-computer_read-sample`)의 GitHub Actions macOS 러너에서 PyInstaller로 `.app`을 만드는 방법. Intel과 Apple Silicon을 어떻게 덮나(universal2, 아키텍처별 두 벌). 비용(공개·비공개 저장소의 무료 분, macOS 배수).
2. **러너에서 화면 확인**: 로그인된 화면 세션이 있나. `screencapture`로 화면을 찍을 수 있나. 테두리 없는 반투명·항상 위 창이 찍히나. 다른 앱의 전체 화면 Space를 만들고 그 위에 창이 뜨는지 볼 수 있나. 키 입력·클릭을 흉내 낼 수 있나. 비슷한 공개 사례.
3. **서명 없이 넘기기**: Apple Developer 계정 없이 넘긴 `.app`을 받는 사람이 여는 방법(Gatekeeper, 격리 속성, ad-hoc 서명)과 한계.
4. **툴킷별 macOS 최소 버전과 크기**: tkinter(python.org 설치본의 Tk 9) + pyobjc, PySide6 버전별(6.8 LTS, 6.12 등) wheel이 요구하는 macOS 최소 버전과 Windows 10 지원.
5. **권한**: 전역 커서 위치 읽기, PowerPoint AppleScript 연동(자동화 권한), 다른 앱의 전체 화면 위에 창 띄우기에 필요한 권한. 처음 실행할 때 받는 사람이 무엇을 허용해야 하나.

받을 사람의 Mac은 M1 Pro 맥북이므로 Apple Silicon(arm64)만 덮는다. Intel과 universal2는 뺀다.

원격 저장소에 push하거나 워크플로를 실제로 돌리지 않는다. 문서, 소스, 공개 사례로 확인한다.

## Answer

조사 문서: `research/mac-build` 브랜치의 `docs/research/mac-without-mac.md`(커밋 1dd352e). 출처는 100건이다. PyPI와 python.org 배포 파일 7개는 이 PC에서 내려받아 바이트를 읽었다. 실제로 실행하거나 워크플로를 돌린 것은 없다.

- **빌드**: GitHub Actions의 `macos-15`나 `macos-26` 러너(M1, arm64)에서 PyInstaller를 돌리면 arm64용 `.app` 한 벌이 나온다. `macos-14`는 2026-11-02에 폐기된다.
- **비용**: 저장소는 비공개 개인 저장소다. 무료 분 안에서 macOS로 쓸 수 있는 것은 약 200분(Free)·300분(Pro)으로 추정된다. 저장소를 공개하면 무료다.
- **러너에서 화면 확인**: 러너에는 자동 로그인된 GUI 세션이 있고, 화면 기록·손쉬운 사용·Apple 이벤트 권한이 미리 허용되어 있다. 그래서 `screencapture`, osascript, cliclick이 묻지 않고 된다. 공개 사례에서 투명 NSPanel이 다른 앱의 전체 화면 위에 보이는 것을 픽셀로 확인했다. 한계: 화면이 1024×768, 1배율이고, PowerPoint는 정품 인증 때문에 러너에서 쓰기 어렵다.
- **전체 화면 위에 띄우기**(Apple DTS 답변): 세 가지가 함께 필요하다. accessory 정책, 활성화하지 않는 NSPanel, `.screenSaver` 레벨이다. Tk `-topmost`나 Qt StaysOnTop보다 높은 레벨이라서, 어느 툴킷이든 pyobjc로 레벨과 패널 성격을 바꿔야 한다.
- **서명 없이 넘기기**: PyInstaller는 ad-hoc 서명을 한다. M1에서 실행은 되지만 Gatekeeper는 통과하지 못한다.
  - macOS 15부터는 Control-클릭 › 열기 우회가 없어졌다. 대신 시스템 설정 › 개인정보 보호 및 보안에서 "그래도 열기"를 누른다. 이 단추는 열려고 한 뒤 약 1시간만 보인다.
  - 공증에는 연 99달러 계정이 필요하다.
- **포장**: `.app`을 그대로 올리면 실행 권한과 심볼릭 링크가 깨져 "손상됨"이 뜬다. 러너에서 `ditto -c -k --keepParent`로 zip을 만들어 올린다.
- **판 조건**:
  - M1 Pro는 macOS 12~27을 돌릴 수 있다.
  - PySide6 6.8~6.12의 wheel은 macOS 14 이상에 설치된다. Python 3.14로 빌드하면 6.10.1 이상만 깔린다.
  - 위험: 바인딩에 박힌 최소 macOS는 6.12.0이 26.0, 6.10·6.11이 15.0으로 wheel 태그보다 높다. 그보다 낮은 macOS에서 import되는지는 확인하지 못했다.
  - Windows 10은 6.8~6.12 모두 지원한다.
  - pyobjc 12.1 이상, Pillow 12.3, PySide6 6.11 이상은 Python 3.10 이상이 필요하다.
- **tkinter의 macOS 27 문제**: python.org가 Tk 대화상자가 멈출 수 있다고 경고한다. Qt로 가므로 피했다.
- **권한**: 받는 사람이 허용할 것은 "PowerPoint 제어(자동화)" 하나다. ad-hoc 서명이라 새 판마다 다시 허용해야 한다. 커서 위치 읽기, 전체 화면 위 창 띄우기, `say`는 권한이 필요 없다(추정 포함).
- **크기(추정)**: arm64 `.app` 기준으로 PySide6 빈 창은 약 75~85MB다.
- **권장 절차**:
  - `macos-15`에 수동 실행 워크플로를 하나 둔다. 빌드한 뒤 같은 작업에서 서명, 아키텍처, import를 확인한다.
  - 가짜 전체 화면 앱 위에 띄워 `screencapture`로 찍는다.
  - `ditto` zip과 받는 사람용 한 장 안내(옮기기, 그래도 열기, 자동화 허용, 새 판마다 반복)를 낸다.
- **러너로 확인할 수 없어 받는 사람에게 확인표로 부탁할 것**: 실제 PowerPoint for Mac 쇼 위에 보이는지, 레티나에서 크기와 위치, 처음 뜨는 권한·Gatekeeper 창, 받는 사람 Mac의 macOS 판.
