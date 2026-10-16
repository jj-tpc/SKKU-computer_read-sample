# 캐릭터 창과 원 버튼을 어떤 GUI 툴킷으로 만들 수 있나

Type: research
Status: resolved

## Question

캐릭터(커서를 따라다니는 도트 강아지)와 원 버튼(파동이 흐르는 파란 원, 위성 버튼, 질문창)을 Windows 10/11과 macOS **양쪽에서** 만들 수 있는 GUI 툴킷은 무엇인가? **tkinter를 기준**으로 각 항목이 되는지 확인하고, 안 되는 항목이 있으면 PySide6(Qt) 등 대안을 같은 항목으로 비교한다.

확인할 항목:
1. **투명 배경**: 테두리 없는 창에서 픽셀 단위 알파(반투명 파동, 매끄러운 원 가장자리)가 되나, 색 키 투명만 되나.
2. **항상 위**: PowerPoint 슬라이드 쇼(전체 화면) 위에도 보이나. 특히 macOS에서 다른 앱이 전체 화면 Space를 쓸 때 그 위에 띄우는 방법(NSWindow collectionBehavior, window level 등)과 그에 필요한 의존성(pyobjc 등).
3. **클릭 통과**: 강아지 창이 아래 슬라이드 쇼의 클릭을 가로막지 않게 하기(Windows `WS_EX_TRANSPARENT`/`WS_EX_LAYERED`, macOS `ignoresMouseEvents`).
4. **포커스 빼앗지 않기**: 강아지와 원 버튼이 떠 있어도 PowerPoint 쇼가 키 입력을 계속 받나. 질문창은 입력 포커스가 필요하다.
5. **전역 커서 위치**: 창 밖 커서 좌표를 30~60fps로 읽는 방법.
6. **모니터 목록**: 모니터마다의 작업 영역(작업 표시줄·Dock 제외)을 얻어 원 버튼을 주 모니터나 고른 모니터의 오른쪽 아래에 두는 방법.
7. **애니메이션 부담**: 스프라이트와 파동을 30~60fps로 그릴 때 CPU 사용량의 대략.
8. **배포**: PyInstaller로 묶었을 때 실행 파일 크기와 라이선스(LGPL 등) 조건.

결과는 항목 × 툴킷 × 운영체제 표로 정리하고, 칸마다 근거(공식 문서, 소스) 링크를 단다.

## Answer

조사 문서: `research/gui-toolkit` 브랜치의 `docs/research/gui-toolkit.md` (커밋 55e0839). Windows는 이 PC(Windows 11, 모니터 두 대)에서 실제 PowerPoint 슬라이드 쇼로 확인했다. macOS는 문서와 소스로만 확인했다.

- **tkinter만으로는 안 되고, tkinter에 운영체제 API를 보태면 된다.**
  - Tk 단독으로는 색 키 투명과 창 전체 알파만 된다. 반투명 파동이 색 키와 섞여 나온다.
  - 클릭 통과, 포커스 안 뺏기, 모니터별 작업 영역 API는 Tk에 없다.
  - Windows는 ctypes로 Win32를 부르면 항목 1~6이 모두 된다(`UpdateLayeredWindow`, `WS_EX_NOACTIVATE`, `WS_EX_TRANSPARENT`, `GetMonitorInfo`).
- **실제 쇼에서 확인한 것**:
  - 쇼 창은 topmost가 아니라서 항상 위 창이 쇼 위에 보인다.
  - `WS_EX_NOACTIVATE` 버튼을 눌러도 쇼가 키를 계속 받는다.
  - `WS_EX_TRANSPARENT` 창은 클릭이 쇼로 통과한다.
  - 질문창은 포커스를 받아 입력한 뒤 `SetForegroundWindow`로 쇼에 돌려줄 수 있다.
- **PySide6**: Windows에서는 창 플래그만으로 같은 결과가 나온다.
  - 하지만 macOS의 다른 앱 전체 화면 Space 위에 띄우는 설정(`canJoinAllApplications`)은 Tk도 Qt도 하지 않는다. 그래서 **macOS는 어느 쪽이든 pyobjc가 필요할 가능성이 높다.**
- **CPU(한 코어 기준)**: 30fps에서 tkinter 11~20%, Qt 20%다. 60fps에서는 각각 29~43%, 33~37%다. 비슷하다.
- **배포(빈 창 기준)**: tkinter 25MB, PySide6 101MB다.
  - PySide6에는 LGPLv3 의무가 붙는다.
  - PySide6 6.12는 macOS 14 이상에서만 설치된다.
  - Qt 6.12가 Windows 10을 지원하는 마지막 버전이다.
- **조사자 권장**: tkinter를 유지하고, Windows는 ctypes, macOS는 pyobjc 보조 모듈을 둔다.
  - 확정 조건: 구현 첫 단계에서 Mac 시제품으로 세 가지를 확인한다. 전체 화면 쇼 위에 보이는가, 알파가 합성되는가, 질문창이 키를 받는가. 실패하면 PySide6(+pyobjc)로 바꾼다.
- **부수 발견**:
  - 이 PC에서 PowerPoint는 쇼를 **보조 모니터**에 띄웠다. 원 버튼 기본이 주 모니터면 프로젝터에 안 보일 수 있다.
  - Python 3.14 tkinter는 DPI unaware가 기본이라 per-monitor v2 설정이 필요하다.
  - tkinter `after()`는 마감 시각 기준으로 예약해야 목표 fps가 나온다.
- 미확인: macOS 전 항목, Windows 10, 느린 학교 PC의 CPU 사용량.
