# GUI 툴킷 결정

Type: grilling
Status: resolved
Blocked by: 02

## Question

[캐릭터 창과 원 버튼을 어떤 GUI 툴킷으로 만들 수 있나](02-research-gui-toolkit.md)의 조사 결과를 보고, 캐릭터 창, 원 버튼, 위성 버튼, 질문창, 설정 창을 무엇으로 만들지 정한다.

원칙(지도를 그리며 정함): tkinter를 먼저 검토하고, 필요한 효과가 안 되면 다른 툴킷을 허용한다. 의존성과 실행 파일이 커지는 것은 감수한다.

정할 것:
- 캐릭터와 원 버튼의 툴킷. 운영체제별 보조 의존성(pyobjc, pywin32 등)도 포함한다.
- 설정 창(대본 창 포함)도 같은 툴킷으로 옮기나, 기존 tkinter 화면을 살리나.
- 한 프로세스에서 두 툴킷을 섞는 것을 허용하나.

## Answer

**PySide6(Qt)로 간다.** 캐릭터 창, 원 버튼, 위성 버튼, 질문창, 말풍선, 설정 창(대본 창 포함)을 모두 Qt로 만든다. 한 프로그램에 두 툴킷을 섞지 않으므로 기존 tkinter 화면(`app.py`)은 Qt로 새로 짠다.

- **이유**: 발표자에게 Mac이 없어서, macOS판은 한 번도 돌려 보지 못하고 넘겨야 한다. Qt는 반투명 창, 그리기(부드러운 가장자리, 그라데이션, 글자 배치), 한글 입력을 두 운영체제에서 같은 방식으로 한다. 그래서 Windows에서 확인한 것이 macOS에도 대부분 통하고, 확인하지 못하는 macOS 전용 코드가 가장 적다. tkinter는 Windows에서는 다 됐지만, macOS에서는 Tk와 Cocoa를 직접 잇는 확인 안 된 코드가 많이 필요하다.
- **운영체제 보조**:
  - Windows: 쇼 위에 띄우기, 포커스 안 뺏기, 클릭 통과는 Qt 창 플래그만으로 된다([조사](02-research-gui-toolkit.md)에서 실측). 기존 pywin32는 SAPI 음성과 PowerPoint COM 연동에 그대로 쓴다.
  - macOS: pyobjc로 NSWindow의 `canJoinAllApplications` 등을 몇 줄 설정해서 다른 앱의 전체 화면 위에도 뜨게 한다.
- **대가**:
  - 실행 파일이 약 76MB 커진다(빈 창 기준 PySide6-Essentials 101MB, tkinter 25MB).
  - LGPLv3 의무가 붙는다. 라이선스 문구를 넣고, Qt를 바꿔 끼울 수 있게 동적 링크로 묶는다(PyInstaller onedir).
  - 설정 창을 새로 짠다. 오션·코랄 꾸밈은 Qt 스타일시트로 한다.
- **macOS판**: 받을 사람의 Mac이 M1 Pro이므로 Apple Silicon(arm64)용만 만든다. PySide6 버전 고정(macOS 최소 버전, Qt 6.12가 Windows 10을 지원하는 마지막 버전이라는 점 포함), Mac 없이 빌드하고 확인하는 방법은 [Mac 없이 macOS판을 만들고 확인하는 방법](13-research-mac-without-mac.md)에서 정한다.
- **DPI**: Qt는 기본이 모니터별 DPI라서 따로 설정할 것이 없다.

## Comments

- 2026-10-16 발표자에게는 Mac 기기도 macOS 실행 파일도 없다. 그래서 구현 중에 Mac 시제품으로 확인할 수 없는데, macOS에서도 도는 완성품을 넘겨야 한다. 이 때문에 "구현 첫 단계 Mac 시제품으로 확정"이라는 조사 권장의 조건이 성립하지 않는다. Mac 없이 빌드하고 확인하는 방법은 [Mac 없이 macOS판을 만들고 확인하는 방법](13-research-mac-without-mac.md)으로 조사한다.
- 2026-10-16 받을 사람의 Mac은 **M1 Pro 맥북(Apple Silicon)**이다. macOS판은 Apple Silicon(arm64)용으로만 만들고, Intel은 맞추지 않는다(발표자). macOS 버전은 아직 모른다.
- 2026-10-16 [Mac 없이 macOS판을 만들고 확인하는 방법](13-research-mac-without-mac.md)의 결과: macOS에서 다른 앱의 전체 화면 위에 띄우려면 accessory 정책, 활성화하지 않는 NSPanel, `.screenSaver` 레벨이 함께 필요하다(Apple DTS). 그래서 pyobjc 보조는 `canJoinAllApplications`만이 아니라 창 레벨과 패널 성격까지 바꾼다. Qt의 Tool 창이 NSPanel이 되므로 그 위에서 바꾸면 된다(구현 때 확인). tkinter는 macOS 27에서 대화상자가 멈출 수 있다는 python.org 경고가 있어, Qt로 간 것이 이 위험도 피했다.
