# Mac 없이 macOS판을 만들고 확인하는 방법 조사

- 티켓: Mac 없이 macOS판을 만들고 확인하는 방법 (빌드, 러너에서 화면 확인, 서명 없이 넘기기, 툴킷별 최소 버전과 크기, 권한)
- 조사일: 2026-10-16
- 받는 기기: Apple Silicon **M1 Pro MacBook**으로 정해졌다. 그래서 **arm64 한 벌만** 만든다. Intel용과 universal2(두 아키텍처를 한 파일에 담는 방식)는 조사 범위에서 뺐다.
- 배경: GUI 툴킷 비교는 `research/gui-toolkit` 가지의 `docs/research/gui-toolkit.md`에 있다. 거기서 정리한 macOS 창 동작(투명, 항상 위, `canJoinAllApplications` 등)은 되풀이하지 않는다.
- 표기
  - **문서**: 공식 문서에 적힌 내용
  - **소스**: 공개 소스 코드를 읽은 결과
  - **분석**: 이 PC(Windows)에서 공개 배포 파일(PyPI 바퀴 파일, python.org 설치본)을 내려받아 바이트를 읽은 결과. 실행한 것이 아니다.
  - **사례**: 공개 저장소의 실제 워크플로나 이슈
  - **추정**: 위 근거들로부터 미루어 짐작한 것
- GitHub Actions는 한 번도 돌리지 않았고, Mac에서 실행해 본 것도 없다. 그래서 이 문서에는 "실측"이 없다.

## 결론 요약

1. **빌드는 러너 하나로 된다(문서·분석).** GitHub Actions 표준 러너 `macos-15`나 `macos-26`에서 `actions/setup-python`으로 Python을 깔고 `pyinstaller ppt_reader.spec`을 돌리면 arm64 `.app`이 나온다. 두 러너는 모두 Apple Silicon(M1)이다 [G1]. setup-python이 까는 Python은 python.org 공식 설치본 그대로다 [G12][G13]. `macos-14`는 2026-11-02에 없어진다 [G3].
2. **비용(문서, 숫자는 추정).** 이 저장소는 비공개라 계정의 월 무료 분에서 깎인다(Free 2,000분, Pro 3,000분) [G7]. macOS는 분당 $0.062로 Linux의 약 10배다 [G8]. 그래서 무료 분은 macOS로 약 200분(Free)·300분(Pro)으로 잡는 것이 안전하다. 저장소를 공개로 바꾸면 표준 러너는 무료다 [G7].
3. **러너에서 화면도 볼 수 있다(소스·사례).** 러너는 `runner` 사용자로 자동 로그인된 GUI 세션이 있다 [G17]. 화면 기록·손쉬운 사용 권한이 이미지에 미리 허용되어 있어 `screencapture`, `osascript` 키 입력, `cliclick` 클릭이 묻지 않고 된다 [G21][E14][E15]. 2026-10-08 공개 실행에서 **테두리 없는 투명 창이 다른 앱의 전체 화면 Space 위에 보이고, 전체 화면 앱이 포커스를 유지하는 것**을 픽셀로 확인한 사례가 있다 [E8][E11][E12]. 다만 화면은 1024×768, 1배율, 검은 배경이고, PowerPoint는 처음 쓸 때 정품 인증을 요구해 러너에서 쓰기 어렵다 [O2]. 실제 M1 Pro 화면과 PowerPoint 슬라이드 쇼는 러너로 대신할 수 없다.
4. **서명 없이 넘길 수 있지만 받는 사람이 한 번 손을 써야 한다(문서).** PyInstaller는 `.app` 전체를 ad-hoc 서명한다 [P7]. 이 서명은 M1에서 실행에는 충분하지만 Gatekeeper는 통과하지 못한다 [A18]. macOS 15부터 Control-클릭 › 열기 우회가 없어졌다 [A20]. 받는 사람은 앱을 한 번 열려고 한 뒤 시스템 설정 › 개인정보 보호 및 보안에서 **"그래도 열기"**를 눌러야 한다 [A21]. 터미널에서 quarantine 속성을 지우는 방법도 있다 [A23]. 공증은 유료 개발자 계정(연 99달러)이 있어야 한다 [A24][A26].
5. **"손상됨" 창을 피하려면 포장을 지켜야 한다(문서·소스·사례).** `upload-artifact`에 `.app` 폴더를 그대로 올리면 실행 권한과 심볼릭 링크가 깨진다 [G14][G15]. 그러면 서명이 무효가 되어 "손상되었기 때문에 열 수 없습니다"가 뜬다 [A22][E5][E7]. 이때는 "그래도 열기"로도 열리지 않는 것으로 보인다(추정). 러너에서 `ditto -c -k --keepParent`로 zip을 만든 뒤 올린다 [A16].
6. **받는 기기와 툴킷 판(문서·분석).** M1 Pro MacBook은 macOS 12로 나왔고 최신 macOS 27까지 지원된다 [A1][A5]. python.org 3.14.8(Tk 9.0.4)과 pyobjc 12.2.2는 이 범위를 모두 덮는다. PySide6는 바퀴 태그로는 macOS 14 이상에서 6.8~6.12가 모두 설치된다. 하지만 Python 3.14로 빌드하면 6.10.1 이상만 깔리고, 6.12는 Qt 문서상 macOS 14.4 이상이다 [Q5][Q6]. Windows 10은 6.8~6.12 모두 지원하고 6.12가 마지막이다 [Q5].
7. **주의할 점 두 가지(분석·문서).**
   - PySide6 6.10~6.12의 바인딩 모듈은 바퀴 태그보다 높은 최소 macOS(6.12.0은 26.0, 6.10·6.11은 15.0)가 박혀 있다. dyld는 이것만으로 거부하지 않는다 [A17]. 하지만 macOS 14·15에서 실제로 import되는지는 미확인이다.
   - python.org는 "macOS 27.0에서 Tk 앱이 메뉴 명령으로 연 대화상자에서 멈출 수 있다"고 경고한다. 수정판 Tk는 아직 나오지 않았다 [P2][P4].
8. **크기(추정).** arm64 한 벌로 tkinter 빈 창은 약 20~30MB, 지금 앱은 약 40~55MB, PySide6 빈 창은 약 75~85MB다. 바이너리의 arm64 조각 크기(분석)와 Windows 실측값으로 추정했다.
9. **권한(문서 + 추정).** 받는 사람이 허용할 것은 **"PowerPoint 제어(자동화)" 하나**다 [A8][A37]. 커서 위치 읽기, 다른 앱 전체 화면 위에 창 띄우기, `say`, 인터넷 HTTPS에는 권한이 필요 없다. 다만 ad-hoc 서명이라 **새 빌드를 줄 때마다 자동화 허용을 다시 받아야 한다** [A11][A32]. 새로 받은 zip에는 quarantine이 다시 붙으므로 "그래도 열기"도 다시 해야 할 것이다(추정).
10. **권장.** `macos-15` 러너에서 수동 실행 워크플로로 빌드한다. 같은 작업 안에서 서명·아키텍처·import 검사를 하고, 가짜 전체 화면 앱 위에 앱을 띄워 스크린숏을 산출물로 남긴다. 받는 사람에게는 한 장짜리 안내(그래도 열기, 자동화 허용)와 러너로 못 보는 항목의 확인표를 함께 준다. 자세한 절차는 맨 아래 "권장 절차"에 있다.

## 1. 빌드: GitHub Actions macOS 러너에서 `.app` 만들기

### 1-1. 러너와 빌드 방법

| 항목 | 내용 | 확인 수준 |
|---|---|---|
| 쓸 러너 | `macos-15`(macOS 15.7)와 `macos-26`(= `macos-latest`). 둘 다 arm64 표준 러너이고 사양은 M1 3코어, 메모리 7GB, 저장 공간 14GB다 [G1][G2] | 문서 |
| 없어지는 러너 | `macos-14`는 **2026-11-02에 폐기**된다 [G3]. 그 전에도 10/16, 19, 23, 26, 29, 30일에 일부러 작업을 실패시키는 기간(brownout)이 있다 [G4]. `macos-13`은 2025-12-04에 폐기됐다 [G6] | 문서 |
| `macos-latest` | 2026-06-15부터 30일에 걸쳐 macOS 15에서 macOS 26으로 바뀌었다 [G5]. 가리키는 판이 바뀌므로 `macos-15`처럼 판을 박아 쓰는 편이 낫다 | 문서, 권장은 추정 |
| arm64 한 벌 만들기 | PyInstaller는 기본으로 "지금 실행 중인 아키텍처"용 단일 아키텍처 결과물을 만든다. universal2 Python에서 빌드해도 모든 바이너리에서 그 아키텍처 조각만 떼어 "완전히 얇은" 빌드를 만든다 [P7]. arm64 러너에서 `pyinstaller ppt_reader.spec`을 그대로 돌리면 arm64 `.app`이 나온다 | 문서 |
| Python | `actions/setup-python`은 Python 3.11 이상을 python.org 공식 universal2 설치본에서 그대로 가져온다고 적혀 있다 [G12]. 3.14.8 arm64 묶음 [G13]을 열어 보니 `python-3.14.8-macos11.pkg`와 이것을 `sudo installer`로 까는 `setup.sh`뿐이었다 | 문서·분석 |
| Tcl/Tk 판 | python.org 설치본 기준 3.14.5 이상은 Tcl/Tk 9.0(3.14.8은 9.0.4), 3.13.16은 8.6.18이다 [P6]. 3.14.8 설치본 안의 `tclConfig.sh`·`tkConfig.sh`도 9.0.4였다. 러너 이미지 설명서의 "Tcl/Tk 8.6.18"은 Homebrew 것이라 setup-python의 Python과는 상관없다 [G16] | 문서·분석, 마지막 문장은 추정 |
| PyInstaller와 Tk 9 | PyInstaller 6.22.0 변경 기록에 "tkinter 훅에서 데이터 묶음을 내장한 Tcl/Tk 9 빌드 지원"이 있다 [P9]. python.org macOS의 Tk 9 프레임워크를 `.app`에 제대로 담는지는 확인하지 못했다. Python 3.14 + tkinter `.app`을 `macos-latest`에서 만드는 공개 사례는 있다 [E4] | 문서·사례, 동작 미확인 |
| 결과물 올리기 | `actions/upload-artifact`는 기본으로 zip으로 묶으면서 **파일 권한을 버린다**(폴더 755, 파일 644) [G14]. 심볼릭 링크는 가리키는 파일의 사본으로 바뀐다 [G15]. PyInstaller 6의 `.app`은 `Contents/Frameworks`와 `Contents/Resources`를 심볼릭 링크로 엮어 두므로 [P8] `.app` 폴더를 그대로 올리면 실행 비트와 링크가 깨진다. 러너에서 `ditto -c -k --keepParent`로 zip을 만든 뒤 [A15][A16] 그 파일 하나를 `archive: false`(v7부터)로 올린다 [G14]. 보관 기간은 기본 90일이다 [G14] | 문서·소스 |
| 공개 사례 | tkinter + pyobjc를 `macos-15`에서 PyInstaller로 빌드하고 `ditto`로 묶는 워크플로 [E1]. PySide6를 `macos-15`에서 빌드하고 `zip -r -y`로 묶는 워크플로 [E2]. `.app`과 DMG를 만드는 워크플로 [E3] | 사례 |

### 1-2. 비용

| 경우 | 비용 | 확인 수준 |
|---|---|---|
| 공개 저장소 + 표준 러너 | "표준 GitHub 호스팅 러너는 공개 저장소에서 무료, 무제한"이다 [G1][G7] | 문서 |
| 비공개 저장소 | 계정의 월 무료 분을 쓰고, 넘으면 분당 요금을 낸다 [G1]. 무료 분은 GitHub Free 2,000분, Pro 3,000분, Team 3,000분이다 [G7]. 작업마다 분 단위로 올림한다 [G8] | 문서 |
| 분당 요금 | macOS 표준(M1 3코어) $0.062, Linux 2코어 $0.006, Windows 2코어 $0.010 [G8]. 2026-01-01에 내린 값이다(macOS $0.080 → $0.062) [G9] | 문서 |
| macOS 분 배수 | 2025-12 전 문서에는 "macOS는 Linux의 10배 속도로 분을 쓴다"는 표가 있었다. 2025-12-16 개정 때 그 표가 빠지고 가격표만 남았다. 이를 묻는 문서 이슈에 GitHub 측은 "삭제는 실수가 아니다"라고만 답했다 [G10]. 가격 비율이 약 10배(0.062 ÷ 0.006)이므로, 무료 분은 macOS로 **Free 약 200분, Pro 약 300분**으로 잡는 것이 안전하다 | 문서, 숫자는 추정 |
| 큰 러너(`-xlarge`, M2 Pro) | 공개 저장소에서도 항상 유료이고 무료 분을 쓸 수 없다. $0.102/분 [G8][G11] | 문서 |
| 이 저장소 | `jj-tpc/SKKU-computer_read-sample`은 GitHub API로 보면 **비공개·개인 소유**다. 플랜은 API로 보이지 않는다. 한 번 빌드에 10분이 걸린다고 치면 Free로 한 달 약 20번이다 | API 조회, 횟수는 추정 |

## 2. 러너에서 화면 확인

| 항목 | 내용 | 확인 수준 |
|---|---|---|
| 로그인된 GUI 세션 | **있다.** 이미지를 만들 때 `runner` 사용자를 잠금 없이 자동 로그인하게 설정한다 [G17]. 화면 잠자기도 끈다 [G18]. 공개 실행 기록에서 단계가 띄운 창이 그려지고 찍혔다 [E8][E9] | 소스·사례 |
| 화면 크기 | 가상 화면 하나, **1024×768, 1배율**이다. `macos-15` [E8]와 `macos-26` [E10] 공개 실행에서 확인됐다. `displayplacer`로 1920×1080으로 바꾼 사례가 있다 [E10]. 러너 관리자는 "가상 머신의 화면 해상도는 거의 조절하지 못한다"고 했다 [G19]. M1 Pro는 레티나(2배율)라 배율 차이는 러너로 볼 수 없다 | 사례 |
| 가상 머신 한계 | arm64 러너는 Apple Virtualization Framework 위의 가상 머신이고 중첩 가상화가 안 된다 [G1]. GPU는 "Apple Paravirtual device"로 보인다 [G20] | 문서·사례 |
| 미리 허용된 권한(TCC) | 이미지에 TCC 데이터베이스 행을 써 둔다. 단계를 실행하는 에이전트 `/opt/hca/hosted-compute-agent`에 **손쉬운 사용, 화면 기록**, Finder·System Events로 보내는 Apple 이벤트가 허용되어 있다. `/bin/bash`와 `osascript`도 손쉬운 사용·Apple 이벤트가 허용되어 있다 [G21] | 소스 |
| macOS 15의 화면 기록 재확인 창 | macOS 15부터 옛 API로 화면을 찍으면 "…이(가) 시스템 개인 창 선택기를 우회하려고 합니다" 창이 반복해서 떠 포커스를 빼앗았다. 2026-08-03에 이미지가 에이전트를 미리 승인하도록 고쳤다. `macos-15`와 `macos-26`에서 시험했다고 적혀 있다 [G21][G22] | 소스 |
| `screencapture` | **된다.** 권한이 없으면 배경 화면만 찍힌다는 2023년 이슈가 있었고 고쳐졌다 [G23]. 2026-10-08 `macos-15` 공개 실행에서 `screencapture -x`가 1024×768 화면과 창을 찍었다 [E8]. 앱 화면을 자동으로 찍어 올리는 다른 공개 워크플로도 있다 [E9] | 사례 |
| 테두리 없는 투명·항상 위 창이 찍히나 | **찍힌다.** 공개 사례 big-arrow는 테두리 없는 투명 NSPanel을 띄우고 찍힌 화면의 픽셀 색으로 보이는지 확인했다(PASS) [E8][E12]. 러너 바탕 화면은 검은색이다. 반투명 가장자리를 보려면 색 있는 창을 뒤에 깔아야 한다 | 사례, 마지막 문장은 추정 |
| 다른 앱 전체 화면 Space 위에 뜨나 | **볼 수 있다.** big-arrow는 작은 Swift 앱을 `fullScreenPrimary` + `toggleFullScreen`으로 자기 전체 화면 Space에 넣었다. 그 위에 오버레이를 띄운 뒤 "전체 화면 앱 위에 표시가 보임(255 83 39)", "전체 화면 앱이 포커스를 유지"를 확인했다(`macos-15` arm64, 2026-10-08) [E8][E11]. 오버레이 설정은 NSPanel, `.borderless`+`.nonactivatingPanel`, 레벨 `.screenSaver`, `canJoinAllSpaces`+`canJoinAllApplications`+`fullScreenAuxiliary`, `ignoresMouseEvents`였다 [E12]. 같은 일은 pyobjc로 만든 가짜 전체 화면 앱으로 흉내 낼 수 있다 | 사례, pyobjc는 추정 |
| PowerPoint를 러너에서 쓰나 | 설치는 된다. Homebrew cask가 있고 [O1], 설치만 하는 공개 액션도 있다 [E13]. 하지만 처음 쓸 때 로그인해 정품 인증을 하라고 묻는다 [O2]. 러너에서 PowerPoint를 실행·조작한 공개 사례는 찾지 못했다. Keynote는 Homebrew cask가 없다 | 문서·사례 |
| 키 입력·클릭 흉내 | **된다.** `osascript`로 System Events `keystroke`를 보낸 공개 실행이 `macos-15`·`macos-26` arm64에서 성공했다 [E14][E9]. `cliclick`(Homebrew)으로 클릭하고, 안 되면 osascript `click at`으로 넘어가는 워크플로가 있다 [E15]. Swift `CGEvent.post` 클릭 시험도 통과했다 [E8]. pyautogui를 macOS 러너에서 쓰는 공개 사례는 찾지 못했다 | 사례 |
| 실행 방식과 권한 | 단계에서 바로 실행한 프로그램은 에이전트가 책임 프로세스라 위 허용을 받는다. 공개 실행의 진단 출력이 "accessibility: granted", "screen recording: granted"였다 [E8]. `open PPTReader.app`으로 띄우면 앱이 스스로 책임 프로세스가 되어 이 허용을 못 물려받을 수 있다. 우리 오버레이 자체는 권한이 필요 없어 상관없다 | 사례, 뒤 두 문장은 추정 |
| Spaces 설정 | 러너는 "디스플레이마다 별도 Space"가 꺼져 있었다(`separate Spaces: no`) [E8]. 보통 Mac과 다를 수 있다 | 사례, 비교는 추정 |
| 두 번째 모니터 | big-arrow는 러너에 가상 디스플레이를 하나 더 붙여 두 화면 시험을 통과했다. 2배율 디스플레이의 배율 보고 시험은 실패했다 [E8] | 사례 |
| 원격으로 들어가 보기 | tmate(SSH)는 macOS를 지원한다고 적혀 있다 [E16]. VNC는 공식 지원이 없고 커뮤니티 방법만 있다. GitHub 약관은 저장소 소프트웨어의 제작·시험과 무관한 사용을 금지한다 [G24]. 스크린숏·녹화를 산출물로 받는 편이 안전하다 | 문서·사례, 권장은 추정 |

**참고: 툴킷 조사에 영향이 있는 새 근거.** Apple DTS 엔지니어가 2026년 5월 포럼에서 다른 앱의 전체 화면 위에 창을 띄우는 조건을 이렇게 답했다 [A19]. 이 답은 `gui-toolkit.md`에 없던 내용이다.
- 앱을 accessory 정책(`LSUIElement`)으로 만든다. "macOS는 일반 앱을 다른 앱의 전체 화면 Space 위에 올리지 않는다."
- NSWindow 대신 `.nonactivatingPanel` NSPanel을 쓴다. "NSWindow는 앞으로 나올 때 앱을 활성화해 전체 화면 앱이 Space를 빠져나가게 할 수 있다."
- 레벨은 `.screenSaver`(1000)여야 한다. "`.floating`(3)과 `.statusBar`(25)는 전체 화면 내용 아래에 놓인다."

`gui-toolkit.md`에 따르면 Tk `-topmost`는 `kCGUtilityWindowLevel`이고 Qt `WindowStaysOnTopHint`는 `NSModalPanelWindowLevel`이다. 둘 다 `.screenSaver`보다 낮다. 그러니 어느 툴킷이든 pyobjc로 레벨과 패널 성격까지 바꿔야 할 가능성이 높다(추정). 러너 화면 시험에서 가장 먼저 확인할 항목이다.

## 3. 서명 없이 넘기기

| 항목 | 내용 | 확인 수준 |
|---|---|---|
| Apple Silicon의 서명 의무 | Apple Silicon에서는 모든 실행 파일이 서명되어야 실행된다. 신원 없는 ad-hoc 서명으로 충분하고, 만든 기계가 아닌 다른 기계에서도 검증된다. 다만 "이런 서명은 유효한 신원이 없어 Gatekeeper를 통과할 수 없다" [A18] | 문서 |
| PyInstaller가 하는 일 | 기본으로 모아 온 바이너리, 실행 파일, `.app` 전체를 ad-hoc(`codesign -s -`, 번들은 `--deep`)으로 서명한다 [P7][P10]. hardened runtime은 실제 인증서를 줄 때만 켠다 [P7] | 문서·소스 |
| 공증(notarization) | Developer ID 인증서가 있어야 하고 [A24], 이 인증서는 유료 Apple Developer Program(연 99달러)의 계정 소유자만 만들 수 있다 [A25][A26]. 무료 계정으로는 공증할 수 없다 | 문서 |
| 받는 사람에게 생기는 일 | Safari 같은 브라우저로 받은 zip에는 `com.apple.quarantine` 속성이 붙고, Finder(압축 해제 유틸리티)로 풀면 풀린 파일에도 붙는다. quarantine이 붙은 앱을 열면 항상 Gatekeeper가 검사한다 [A23]. 공증이 없으니 "Apple은 … 악성 코드가 없음을 확인할 수 없습니다" 창이 뜨고 열리지 않는다 [A22][E6] | 문서·사례 |
| macOS 14까지 | Control-클릭 › 열기로 바로 열 수 있었다 [A21] | 문서 |
| macOS 15·26 | **Control-클릭 우회가 없어졌다** [A20][A27]. 앱을 한 번 열려고 한 뒤, 시스템 설정 › 개인정보 보호 및 보안 › 보안의 **"그래도 열기"**를 누르고 로그인 암호를 넣는다. 이 단추는 열려고 한 뒤 약 1시간 동안만 보인다. 한 번 허용하면 예외로 저장된다 [A21]. macOS 26 안내서의 절차는 15와 같다 [A21] | 문서 |
| macOS 27 | 27 릴리스 노트의 Gatekeeper 항목에는 `spctl` 옵션 추가만 있고 절차 변경은 찾지 못했다 [A28] | 문서(변경 없음은 검색 결과) |
| 터미널로 여는 방법 | `xattr -dr com.apple.quarantine /Applications/PPTReader.app`으로 quarantine 속성을 지운다. Apple DTS 엔지니어는 포럼에서 "내부 배포라면 quarantine을 지워도 괜찮다", "설정을 통째로 끄는 것보다 훨씬 낫다"고 했다 [A23][A29]. support.apple.com에는 이 방법 안내가 없다. 명령 형식은 PyInstaller 관리자 답변을 따랐다 [E5] | 포럼·사례 |
| quarantine이 안 붙는 경우 | `curl`·`scp`로 받거나 `tar`·`unzip`으로 풀면 quarantine이 붙지 않는다 [A23]. USB, AirDrop, 메신저로 보낼 때는 확인하지 못했다 | 포럼, 나머지 미확인 |
| 앱 위치 무작위화(App Translocation) | quarantine이 붙은 앱을 받은 자리에서 처음 열면 무작위의 읽기 전용 경로에서 실행된다. Finder로 다른 곳(예: 응용 프로그램 폴더)으로 옮긴 뒤 열면 일어나지 않는다 [A16][A30][A31]. 지금 앱은 설정을 홈 폴더(`~/.ppt_reader_settings.json`)에 쓰므로 영향이 없다 | 문서·소스 |
| "손상되었기 때문에 열 수 없습니다" | Apple은 "소프트웨어가 수정되거나 손상된 것을 감지하면 열 수 없다고 알린다"고 적었다 [A22]. 심볼릭 링크를 지키지 않은 zip 때문에 이 창이 뜬 PyInstaller 사례가 여럿 있다 [E5][E7]. 서명 뒤 번들이 바뀐 것(링크가 사본으로 바뀜, 실행 비트 손실 등)이 원인으로 보이며, 이때는 "그래도 열기"로도 열리지 않는 것으로 보인다 | 문서·사례, 원인과 우회 불가는 추정 |
| 권한 기억 | ad-hoc 서명 코드의 지정 요구(DR)는 "그 판의 코드에만 묶인다". 코드를 바꿔 다시 실행하면 macOS가 같은 질문을 다시 한다 [A11][A32]. 그래서 **새 빌드를 줄 때마다 자동화 허용을 다시 받아야 한다** | 문서 |
| 포장 | Apple 문서는 `ditto -c -k --keepParent`를 쓰라고 한다. `cp`와 달리 심볼릭 링크를 지킨다. DMG는 `hdiutil create … UDZO`다 [A16]. Finder로 압축하면 확장 속성을 따로 빼 두어 좋지 않다 [A33] | 문서·포럼 |

## 4. 받는 기기와 툴킷의 최소 버전, 크기

### 4-1. M1 Pro MacBook이 돌릴 수 있는 macOS

M1 Pro를 단 MacBook은 "MacBook Pro (14형, 2021)"과 "(16형, 2021)"이다 [A4][A5]. 2021년 10월 macOS 12 Monterey를 담고 나왔다 [A5].

| macOS | M1 Pro | 근거 |
|---|---|---|
| 12 Monterey | 출고 판 | [A5] 문서 |
| 13 Ventura, 14 Sonoma | 설치 가능(추정) | 15·26·27 호환 목록에 들어 있으므로 그 사이 판도 된다고 봤다. 13·14 목록은 직접 보지 않았다 |
| 15 Sequoia | 설치 가능 | [A34] 문서 |
| 26 Tahoe | 설치 가능 | [A2] 문서 |
| 27 Golden Gate(2026-09 출시, 최신) | 설치 가능. 모델 식별 페이지의 "가장 최근 호환 운영체제"가 macOS 27이다 | [A1][A3] 문서 |

받는 사람이 어느 판을 쓰는지는 모른다. 14 이상이라는 전제는 코디네이터가 준 조건이다.

### 4-2. Python과 pyobjc

| 구성 | 최소 macOS | 그 밖의 조건 | 확인 수준 |
|---|---|---|---|
| python.org 3.14.8(Tk 9.0.4) | 설치본 설명은 "macOS 10.15 이상" [P2]. arm64 조각의 minos는 11.0이다(Apple Silicon은 11부터라 당연하다) | M1 Pro의 모든 판에서 된다 | 문서·분석 |
| python.org 3.13.16(Tk 8.6.18) | "macOS 10.13 이상" [P3] | 같다 | 문서 |
| pyobjc 12.2.2 | universal2 바퀴만 있다. cp314는 `macosx_10_15`, cp313은 `macosx_10_13` 태그다 [P11] | **Python 3.10 이상**(12.1부터) [P11] | 문서(PyPI) |
| Pillow 12.3.0, lxml 6.1.3 | Pillow는 `macosx_11_0_arm64` 전용 바퀴, lxml은 universal2 바퀴다 [P12] | Pillow는 Python 3.10 이상 | 문서(PyPI) |

프로젝트는 "Python 3.9 이상"이라고 적혀 있지만, macOS 빌드에 쓸 pyobjc 12.1+, Pillow 12.3, PySide6 6.11+는 모두 3.10 이상을 요구한다. 빌드용 Python은 3.13이나 3.14로 정하면 된다. 3.15.0도 2026-10-09에 나왔지만 [P1] 나온 지 일주일이라 제외했다.

**macOS 27 + tkinter 주의.** python.org 3.14.8·3.15.0 배포 페이지는 "macOS 27.0에서 IDLE 등 Tk 앱이 대화상자를 열 때 멈출 수 있다. 현재 모든 Tk 판에 해당한다고 본다"고 경고한다 [P2]. 추적 이슈를 보면 Tk 8.6.18과 9.0.4 모두 해당되고, 조건은 "macOS 메뉴 막대 명령에서 모달 대화상자를 바로 열 때"다 [P4][P5]. 수정은 2026-10-05에 Tk 8.6·9.0·9.1 브랜치에 합쳐졌지만 정식 판으로는 아직 나오지 않았고, python.org 설치본 갱신도 보류 중이다 [P4]. 지금 앱은 파일 대화상자와 메시지 상자를 메뉴가 아니라 단추에서 연다(`app.py`). 단추에서 연 대화상자도 멈추는지는 이슈에 적혀 있지 않아 **미확인**이다.

### 4-3. PySide6 판별 조건

| 판(PyPI 마지막) | 나온 날 | macOS 바퀴 태그 | Qt 문서의 macOS | Qt 라이브러리 minos(분석) | PySide 바인딩 minos(분석) | Python | Windows 10 |
|---|---|---|---|---|---|---|---|
| 6.8.3 (6.8 LTS) | 2025-03-27 | `macosx_12_0_universal2` | 12 이상 [Q1] | 12.0 | 12.0 | 3.9~3.13 | 1809 이상 지원 [Q1] |
| 6.9.3 | 2025-09-30 | `macosx_12_0_universal2` | 12 이상 [Q2] | 보지 않음 | 보지 않음 | 3.9~3.13 | 지원 [Q2] |
| 6.10.3 | 2026-04-02 | `macosx_13_0_universal2` | 13 이상 [Q3] | 13.0 | **15.0** | 3.9~3.14 (6.10.0만 3.13까지) | 지원 [Q3] |
| 6.11.2 | 2026-08-18 | `macosx_13_0_universal2` | 13 이상 [Q4] | 13.0 | **15.0** | 3.10~3.14 | 지원 [Q4] |
| 6.12.0 | 2026-10-08 | `macosx_14_0_universal2` | **14.4 이상** [Q5] | 14.4 | **26.0** | 3.10~3.15 | 지원, **마지막** [Q5] |

- 태그, 날짜, Python 범위는 PyPI에서 읽었다 [Q6]. macOS 바퀴는 모든 판이 universal2뿐이다. arm64 전용 바퀴는 없다. PyInstaller가 arm64 조각만 떼어 담는다 [P7].
- "Qt 6.12가 Windows 10을 지원하는 마지막 판"이라는 문장은 Qt 6.11·6.12 문서에 있다 [Q4][Q5].
- **M1 Pro + macOS 14 이상에서 쓸 수 있는 판**: 바퀴 태그로는 6.8~6.12가 모두 설치된다. 다만 Python 3.14로 빌드하면 6.10.1 이상만 설치된다(6.8·6.9는 Python 3.14 미만만 허용). 6.12는 Qt 문서상 macOS 14.4 이상이라 14.0~14.3은 지원 밖이다.
- **minos 불일치.** 6.10부터 PySide 바인딩 모듈(`QtCore.abi3.so`, `libpyside6`, `libshiboken6`)의 최소 macOS(LC_BUILD_VERSION minos)가 바퀴 태그보다 높다. 6.12.0은 26.0, 6.10·6.11은 15.0이다(분석). 빌드에 쓴 SDK 판이 그대로 들어간 것으로 보인다(추정). dyld 소스를 보면 minos가 더 높다는 이유만으로 불러오기를 거부하지 않는다. 기호(symbol)가 없어 실패할 때 "(built for macOS … which is newer than running OS)"를 덧붙일 뿐이다 [A17]. 따라서 **macOS 14·15에서 실제로 import되는지는 미확인**이다. 실패한다면 import 순간 "Symbol not found"로 드러난다. `macos-15` 러너에서 `import PySide6.QtWidgets`를 돌리면 15는 확인할 수 있다. 14는 `macos-14` 러너가 2026-11-02까지만 있다.

<details><summary>분석 방법(바퀴·설치본을 열어 Mach-O 머리말 읽기)</summary>

- 대상: PyPI의 `pyside6_essentials` 6.8.3, 6.10.3, 6.11.2, 6.12.0 macOS 바퀴와 6.12.0 Windows 바퀴, `shiboken6` 6.12.0, python.org 3.14.8 설치본(setup-python 묶음 [G13] 안의 `.pkg`).
- 방법: 파이썬으로 zip(바퀴)과 xar → gzip → cpio(설치본)를 풀어 메모리에서만 읽었다. Mach-O universal 머리말(`0xCAFEBABE`)에서 arm64 조각의 위치와 크기를 읽고, 그 조각의 `LC_BUILD_VERSION`에서 minos와 SDK를 읽었다. 아무것도 실행하지 않았다. 스크립트는 저장소에 넣지 않았다.
- 결과 예: 6.12.0 `PySide6/QtCore.abi3.so` 12.26MB, arm64 조각 6.16MB, minos 26.0.0, SDK 26.0.0. 같은 바퀴의 `Qt/lib/QtCore.framework/Versions/A/QtCore` minos 14.4.0. python.org 3.14.8 `Python.framework/Versions/3.14/Python` 14.80MB, arm64 7.23MB, minos 11.0.0.
</details>

### 4-4. PyInstaller `.app` 크기(arm64 한 벌)

Mac에서 빌드하지 못해 실제 크기는 없다. 들어갈 바이너리의 arm64 조각 크기를 재고(분석), Windows 실측값(`gui-toolkit.md`)과 맞춰 추정했다.

| 구성 요소 | universal2 크기 | arm64 조각 | 확인 수준 |
|---|---|---|---|
| python.org 3.14.8 `Python`(libpython) | 14.8MB | 7.2MB | 분석 |
| Tcl 9.0 + Tk 9.0 라이브러리 | 9.7MB | 5.0MB | 분석 |
| Tcl/Tk 스크립트 등(아키텍처 무관) | 4.5MB | 4.5MB | 분석 |
| libssl + libcrypto(HTTPS용) | 12.9MB | 6.0MB | 분석 |
| PySide6 6.12 QtCore·QtGui·QtWidgets(+QtDBus) 프레임워크, 바인딩 3개, 플러그인, 번역 | 104.3MB | **54.3MB** | 분석 |
| 위와 같은 묶음의 Windows판 | 72.2MB(그중 `opengl32sw.dll` 20.6MB) | — | 분석 |

| 빌드 | 추정 크기 | 근거 |
|---|---|---|
| tkinter 빈 창 | 약 20~30MB | Windows 25MB(실측)와 위 구성 요소 합 |
| 지금 앱(python-pptx, lxml, Pillow, pyobjc) | 약 40~55MB | Windows 51MB(실측). pywin32 대신 pyobjc가 들어간다 |
| PySide6 빈 창 | 약 75~85MB | Windows 101MB(실측) − Windows Qt 묶음 72MB + macOS arm64 Qt 묶음 54MB |

모두 추정이다. zip으로 묶으면 더 작아진다.

## 5. 권한

| 하는 일 | 필요한 권한 | 근거 | 확인 수준 |
|---|---|---|---|
| 전역 커서 위치 읽기(`NSEvent.mouseLocation`, Tk `winfo pointerxy`) | **없음** | 문서에 권한 요구가 없다 [A6]. 권한이 필요한 것은 전역 이벤트 감시(`addGlobalMonitorForEvents`, 키 이벤트는 손쉬운 사용 필요)와 CG 이벤트 탭(입력 모니터링)이다 [A7][A35]. 위치를 주기적으로 읽는 것은 이 목록에 없다 | 문서 + 추정 |
| PowerPoint를 AppleScript로 제어(`osascript` 자식 프로세스) | **자동화(Apple 이벤트)**. PowerPoint에 처음 명령을 보낼 때 이 앱이 PowerPoint를 제어해도 되는지 묻는 창이 뜬다(정확한 문구는 미확인) | Info.plist의 `NSAppleEventsUsageDescription`은 "Apple 이벤트를 보내는 API를 쓰면 필수"다 [A8]. 없으면 Apple 이벤트가 권한 오류로 거부된다 [A36]. **`ppt_reader.spec`에 이미 들어 있다.** 앱이 띄운 자식 프로세스는 앱을 "책임 코드"로 보고 앱 이름으로 묻는다. 터미널에서 실행하면 터미널이 묻는다 [A37] | 문서·포럼 |
| 위와 같은 일, entitlement | hardened runtime을 켜지 않으면 `com.apple.security.automation.apple-events`는 필요 없다 | 이 entitlement는 Hardened Runtime 기능의 하위 항목이다 [A9]. PyInstaller는 ad-hoc 서명일 때 hardened runtime을 켜지 않는다 [P7] | 문서 + 추정 |
| 다른 앱 전체 화면 Space 위에 창 띄우기 | **없음** | `canJoinAllApplications` 등 창 동작 문서에 권한·entitlement 언급이 없고 [A10], TCC 서비스 목록에도 해당 항목이 없다 | 추정 |
| `say`로 읽기 | 없음 | 음성 출력용 TCC 항목을 찾지 못했다 | 추정 |
| LLM HTTPS 호출 | 없음 | "로컬 네트워크" 권한은 같은 네트워크의 주소로 보낼 때만 필요하다 [A12]. 네트워크 클라이언트 entitlement는 샌드박스 앱에만 해당한다 [A38] | 문서 + 추정 |
| 화면 기록 | 지금 계획에는 필요 없음 | 다른 앱의 창 제목을 읽거나(CGWindowList) 화면을 찍을 때만 필요하다. 창 위치·크기는 권한 없이 얻는다 [A13] | 문서 |
| 손쉬운 사용 | 지금 계획에는 필요 없음 | 키·클릭을 흉내 내거나 System Events로 UI를 조작할 때만 필요하다 [A35][A39]. `link.py`는 PowerPoint 자체 스크립트 사전만 쓴다 | 문서·소스 |

**받는 사람이 처음 실행할 때 할 일**

1. Gatekeeper: 앱을 한 번 열려고 한 뒤 시스템 설정 › 개인정보 보호 및 보안 › "그래도 열기"(3절). 또는 터미널에서 `xattr -dr com.apple.quarantine`.
2. 자동화: PowerPoint 연동을 처음 쓸 때 뜨는 창에서 "허용". 거부했다면 시스템 설정 › 개인정보 보호 및 보안 › 자동화에서 "PPT 읽어주기" 아래 "Microsoft PowerPoint"를 켠다 [A14]. 꼬였으면 `tccutil reset AppleEvents local.pptreader`(번들 ID는 `ppt_reader.spec` 값) [A40].
3. 새 빌드를 받을 때마다 2를 다시 한다(ad-hoc 서명이라 macOS가 새 판을 같은 앱으로 알아보지 못함) [A11][A32]. 새 zip에는 quarantine이 다시 붙으므로 1도 다시 하게 될 것이다(추정).

## 권장 절차

아래는 근거를 바탕으로 짠 절차다. **한 번도 돌려 보지 않았다.**

1. **빌드 작업.** `.github/workflows/`에 수동 실행(`workflow_dispatch`) 워크플로를 하나 두고 `runs-on: macos-15`로 빌드한다. `macos-latest`는 가리키는 판이 바뀌므로 쓰지 않는다. 비공개 저장소라 무료 분이 macOS로 월 200~300분 정도라서, 커밋마다 돌리지 않고 필요할 때만 돌린다.
2. **Python 판.** Windows판과 같은 3.14(Tk 9.0.4)를 기본으로 한다. Tk 9 전용 기능을 쓰지 않으면 3.13(Tk 8.6.18)도 된다. macOS 27의 Tk 대화상자 문제는 두 판 모두에 해당한다 [P4].
3. **빌드 직후 검사(같은 작업 안).** 모두 명령 한 줄씩이라 러너에서 바로 확인된다.
   - `codesign --verify --deep --strict dist/PPTReader.app`와 `codesign -dv`로 ad-hoc 서명이 온전한지 본다.
   - `lipo -archs`로 실행 파일이 arm64만 담았는지 본다.
   - PySide6를 고르면 `python -c "import PySide6.QtWidgets"`와 빌드된 앱 실행으로 macOS 15에서 import되는지 본다. 14도 보려면 `macos-14`가 없어지는 2026-11-02 전에 한 번 돌린다.
4. **화면 시험(같은 작업 안).**
   - 색 있는 배경 창과 pyobjc로 만든 가짜 전체 화면 앱(`toggleFullScreen_`)을 먼저 띄운다.
   - 빌드된 앱을 `.app` 안의 실행 파일로 직접 띄운다.
   - `cliclick`으로 커서를 몇 군데로 옮기며 `screencapture -x`로 찍는다. 강아지가 따라오는지, 원 버튼이 전체 화면 위에 보이는지, 전체 화면 앱이 포커스를 잃지 않는지 본다. big-arrow처럼 픽셀 색과 맨 앞 앱 이름을 검사하면 자동 판정도 된다 [E11].
   - 스크린숏을 산출물로 올린다.
5. **포장.** `ditto -c -k --keepParent dist/PPTReader.app PPTReader-macos-arm64.zip`으로 묶고 `actions/upload-artifact@v7`에 `archive: false`로 그 zip 하나만 올린다.
6. **받는 사람 안내문.** 한 장으로 쓴다.
   - zip을 풀고 앱을 응용 프로그램 폴더로 옮긴 뒤 연다.
   - 막히면 시스템 설정 › 개인정보 보호 및 보안 › "그래도 열기"를 누른다.
   - PowerPoint 연동 때 뜨는 창에서 "허용"을 누른다.
   - 새 판을 받을 때마다 위 과정을 다시 한다.
7. **러너로 못 보는 것은 받는 사람에게 확인표로 부탁한다.**
   - 실제 PowerPoint 슬라이드 쇼 위에 강아지와 원 버튼이 보이는가
   - 레티나 화면에서 크기와 위치가 맞는가
   - 자동화 허용 창이 앱 이름으로 뜨는가
   - macOS 판 번호(27이면 대화상자 멈춤 여부)

<details><summary>워크플로 뼈대(미실행)</summary>

```yaml
name: macos-build
on: workflow_dispatch
jobs:
  build:
    runs-on: macos-15            # arm64(M1). macos-14는 2026-11-02 폐기
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.14"   # python.org 설치본, Tk 9.0.4
      - run: python -m pip install -r requirements.txt pyinstaller pyobjc-framework-Cocoa
      - run: pyinstaller --noconfirm ppt_reader.spec
      - name: 서명·아키텍처 검사
        run: |
          codesign --verify --deep --strict dist/PPTReader.app
          codesign -dv dist/PPTReader.app 2>&1 | grep -E "Signature|Identifier"
          lipo -archs dist/PPTReader.app/Contents/MacOS/PPTReader
      - name: 화면 시험(가짜 전체 화면 앱 위에 띄우고 찍기)
        run: |
          brew install cliclick
          python tools/fake_fullscreen.py &       # pyobjc로 만든 가짜 쇼(새로 만들 파일)
          sleep 3
          dist/PPTReader.app/Contents/MacOS/PPTReader &
          sleep 5
          mkdir -p shots
          for p in 200,200 800,600; do cliclick m:$p; sleep 1; screencapture -x shots/$p.png; done
      - run: ditto -c -k --keepParent dist/PPTReader.app PPTReader-macos-arm64.zip
      - uses: actions/upload-artifact@v7
        with:
          path: PPTReader-macos-arm64.zip
          archive: false
      - uses: actions/upload-artifact@v7
        with:
          name: screenshots
          path: shots/
```
</details>

## 확인하지 못한 것

- **실행한 것이 없다.** GitHub Actions 워크플로는 지시에 따라 돌리지 않았다. Mac도 없다. 1~5절의 "된다"는 모두 문서·소스·남의 실행 기록에 기댄 것이다.
- **러너가 실제 Mac과 다른 점.** 러너로는 다음을 확인할 수 없다.
  - 화면이 1024×768, 1배율이다(M1 Pro는 레티나).
  - 바탕 화면이 검은색이다.
  - "디스플레이마다 별도 Space"가 꺼져 있다.
  - GPU가 가상화되어 있다.
  - 권한이 미리 허용되어 있다. 받는 사람의 Mac에서 처음 뜨는 권한 창은 러너에서 볼 수 없다.
- **PowerPoint 관련.** 다음은 확인하지 못했다.
  - PowerPoint for Mac 슬라이드 쇼가 별도 전체 화면 Space를 쓰는가. 우리 창이 그 위에 보이는가.
  - 자동화 허용 창의 실제 문구.
- **PySide6 6.10~6.12.** 바인딩 모듈의 minos가 바퀴 태그보다 높은데, macOS 14·15에서 실제로 import되는지 모른다.
- **Tk 9 포장.** PyInstaller가 python.org macOS의 Tk 9.0 프레임워크를 `.app`에 제대로 담는지 모른다.
- **macOS 27 Tk 문제.** 단추에서 연 대화상자와 Cmd+Q 같은 기본 메뉴도 멈추는지 모른다.
- **비용 배수.** 비공개 저장소에서 macOS 1분이 무료 분 몇 분으로 깎이는지 현재 문서에 숫자가 없다(약 10배는 추정).
- **크기.** 4-4절 크기는 추정이다.
- **전달 경로.** AirDrop, 메신저, USB로 보낼 때 quarantine이 붙는지 확인하지 못했다.
- **앱으로 띄울 때의 권한.** 러너에서 `open`으로 띄운 앱이 에이전트의 권한을 물려받는지 모른다.
- **받는 사람의 macOS 판.** "14 이상"이라는 조건만 받았다.
- **원격 접속.** VNC가 arm64 러너에서 실제로 되는지 확인하지 못했다.

## 출처 목록

### GitHub
- [G1] GitHub-hosted runners reference(러너 이름·사양, 공개 저장소 무료, 중첩 가상화 불가, 비밀번호 없는 sudo): https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- [G2] actions/runner-images README(이미지별 이름, `macos-14` deprecated 표시): https://github.com/actions/runner-images
- [G3] macOS 14 러너 이미지 폐기 공지(2026-11-02): https://github.blog/changelog/2026-10-01-github-actions-macos-14-runner-image-retirement/
- [G4] macOS 14 폐기 일정과 brownout 날짜: https://github.com/actions/runner-images/issues/13518
- [G5] `macos-latest` → macOS 26 전환 공지와 완료: https://github.blog/changelog/2026-05-14-github-actions-upcoming-image-migrations/ , https://github.com/actions/runner-images/issues/14167
- [G6] macOS 13 폐기 공지(2025-12-04): https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down/
- [G7] GitHub Actions billing(공개 저장소 무료, 플랜별 무료 분): https://docs.github.com/en/billing/concepts/product-billing/github-actions
- [G8] Actions runner pricing(분당 요금, 분 단위 올림, 큰 러너는 무료 분 불가): https://docs.github.com/en/billing/reference/actions-runner-pricing
- [G9] 2026-01-01 가격 인하 공지와 표: https://github.blog/changelog/2026-01-01-reduced-pricing-for-github-hosted-runners-usage/ , https://github.com/github/roadmap/issues/1196
- [G10] "분 배수가 아직 적용되나" 문서 이슈: https://github.com/github/docs/issues/45138
- [G11] Larger runners(`-xlarge` M2 Pro): https://docs.github.com/en/actions/reference/runners/larger-runners
- [G12] actions/python-versions README("Python 3.11 이상은 python.org universal2 바이너리를 내려받음")와 빌더: https://github.com/actions/python-versions , https://github.com/actions/python-versions/blob/main/builders/macos-python-builder.psm1
- [G13] setup-python용 3.14.8 darwin-arm64 묶음(분석 대상): https://github.com/actions/python-versions/releases/download/3.14.8-36806082737/python-3.14.8-darwin-arm64.tar.gz
- [G14] actions/upload-artifact README(권한 손실, `archive: false`, 보관 90일): https://github.com/actions/upload-artifact
- [G15] actions/toolkit `zip.ts`(심볼릭 링크를 `realpath`로 바꿔 담음)와 관련 이슈: https://github.com/actions/toolkit/blob/main/packages/artifact/src/internal/upload/zip.ts , https://github.com/actions/upload-artifact/issues/693
- [G16] macos-15 arm64 이미지 설명서(설치된 Python, Homebrew Tcl/Tk 8.6.18): https://github.com/actions/runner-images/blob/main/images/macos/macos-15-arm64-Readme.md
- [G17] 이미지 자동 로그인 스크립트: https://github.com/actions/runner-images/blob/e3fa5414d230773024d4a669a8402b50cd28f036/images/macos/scripts/build/configure-autologin.sh#L9-L12
- [G18] 이미지 기계 설정(잠자기 끔): https://github.com/actions/runner-images/blob/e3fa5414d230773024d4a669a8402b50cd28f036/images/macos/scripts/build/configure-machine.sh#L17
- [G19] 화면 해상도 이슈(관리자 답변): https://github.com/actions/runner-images/issues/9345
- [G20] arm64 가상 GPU("Apple Paravirtual device") 이슈: https://github.com/actions/runner-images/issues/14840
- [G21] 이미지 TCC 설정 스크립트(시스템 DB L10-L49, 사용자 DB L55-L96, 화면 기록 재확인 창 억제 L101-L118): https://github.com/actions/runner-images/blob/e3fa5414d230773024d4a669a8402b50cd28f036/images/macos/scripts/build/configure-tccdb-macos.sh
- [G22] 화면 기록 재확인 창 억제 PR(2026-08-03 병합): https://github.com/actions/runner-images/pull/14489
- [G23] 권한 없이 찍으면 배경 화면만 나온다는 이슈: https://github.com/actions/runner-images/issues/8782
- [G24] GitHub 추가 제품 약관 — Actions: https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions

### Python, PyInstaller, PyPI
- [P1] python.org macOS 내려받기 목록(3.15.0 2026-10-09, 3.14.8·3.13.16 2026-09-30): https://www.python.org/downloads/macos/
- [P2] Python 3.14.8 배포 페이지("for macOS 10.15 and later", macOS 27.0 Tk 경고): https://www.python.org/downloads/release/python-3148/
- [P3] Python 3.13.16 배포 페이지("for macOS 10.13 and later"): https://www.python.org/downloads/release/python-31316/
- [P4] CPython 이슈 "IDLE on macOS 27 hangs when a menu command opens a dialog": https://github.com/python/cpython/issues/158053
- [P5] Tk 티켓 "modal dialog opened synchronously from a menu command becomes unresponsive": https://core.tcl-lang.org/tk/tktview/33b3af1ceac681ad0f77
- [P6] CPython macOS 설치본 빌드 스크립트의 Tcl/Tk 판(3.13.16: 8.6.18, 3.14.8: 9.0.4)과 9.0 전환 커밋: https://github.com/python/cpython/blob/v3.13.16/Mac/BuildScript/build-installer.py#L260-L267 , https://github.com/python/cpython/blob/v3.14.8/Mac/BuildScript/build-installer.py#L260-L267 , https://github.com/python/cpython/commit/9d5857cfa363f67f1319c8bbb7626207f6896a52
- [P7] PyInstaller Feature Notes(macOS 다중 아키텍처, 코드 서명, 번들 서명): https://pyinstaller.org/en/stable/feature-notes.html
- [P8] PyInstaller 심볼릭 링크 주의와 macOS 번들 구조: https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#requirements-imposed-by-symbolic-links-in-frozen-application , https://pyinstaller.org/en/stable/usage.html#building-macos-app-bundles
- [P9] PyInstaller 변경 기록(6.18.0, 6.22.0 Tcl/Tk 9): https://pyinstaller.org/en/stable/CHANGES.html
- [P10] PyInstaller 6.22.3 소스 `sign_binary`(신원 없으면 `'-'` ad-hoc, 신원 있으면 `--options=runtime`)와 BUNDLE `deep=True` 서명: https://github.com/pyinstaller/pyinstaller/blob/v6.22.3/PyInstaller/utils/osx.py#L413-L421 , https://github.com/pyinstaller/pyinstaller/blob/v6.22.3/PyInstaller/building/osx.py#L713-L723
- [P11] PyPI pyobjc-core 12.2.2 파일 목록: https://pypi.org/project/pyobjc-core/12.2.2/#files
- [P12] PyPI Pillow 12.3.0, lxml 6.1.3 파일 목록: https://pypi.org/project/pillow/12.3.0/#files , https://pypi.org/project/lxml/6.1.3/#files

### Qt / PySide6
- [Q1] Qt 6.8 Supported Platforms: https://doc.qt.io/qt-6.8/supported-platforms.html
- [Q2] Qt 6.9 Supported Platforms: https://doc.qt.io/qt-6.9/supported-platforms.html
- [Q3] Qt 6.10 Supported Platforms: https://doc.qt.io/qt-6.10/supported-platforms.html
- [Q4] Qt 6.11 Supported Platforms("Qt 6.12 will be the last version to support Windows 10"): https://doc.qt.io/qt-6.11/supported-platforms.html
- [Q5] Qt 6.12 Supported Platforms("macOS 14.4 or higher", Windows 10 마지막): https://doc.qt.io/qt-6.12/supported-platforms.html
- [Q6] PyPI PySide6-Essentials 판별 파일과 shiboken6 6.12.0(분석 대상): https://pypi.org/project/PySide6-Essentials/#history , https://pypi.org/project/PySide6-Essentials/6.12.0/#files , https://pypi.org/project/shiboken6/6.12.0/#files

### Apple
- [A1] macOS 27 Golden Gate 호환 기기(2026-09-14 게시): https://support.apple.com/en-us/127255
- [A2] macOS Tahoe 26 호환 기기: https://support.apple.com/en-us/122867
- [A3] MacBook Pro 모델 식별("Newest compatible operating system: macOS 27 Golden Gate"): https://support.apple.com/en-us/108052
- [A4] MacBook Pro (14형, 2021) 기술 사양(M1 Pro): https://support.apple.com/en-us/111902
- [A5] Apple 뉴스룸 2021-10("come with macOS Monterey", M1 Pro·M1 Max): https://www.apple.com/newsroom/2021/10/apple-unveils-game-changing-macbook-pro/
- [A6] NSEvent.mouseLocation: https://developer.apple.com/documentation/appkit/nsevent/mouselocation
- [A7] NSEvent.addGlobalMonitorForEvents(키 이벤트는 손쉬운 사용 필요): https://developer.apple.com/documentation/appkit/nsevent/addglobalmonitorforevents(matching:handler:)
- [A8] NSAppleEventsUsageDescription("This key is required if your app uses APIs that send Apple events."): https://developer.apple.com/documentation/bundleresources/information-property-list/nsappleeventsusagedescription
- [A9] Apple Events entitlement(Hardened Runtime의 Resource Access 항목): https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.automation.apple-events
- [A10] NSWindow.CollectionBehavior.canJoinAllApplications: https://developer.apple.com/documentation/appkit/nswindow/collectionbehavior-swift.struct/canjoinallapplications
- [A11] TN3127 Inside Code Signing: Requirements(ad-hoc 서명의 DR은 그 판의 코드에만 묶임): https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements
- [A12] TN3179 Understanding local network privacy: https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy
- [A13] WWDC19 701 Advances in macOS Security(화면 기록·입력 모니터링 동의, CGWindowList 메타데이터): https://developer.apple.com/videos/play/wwdc2019/701/
- [A14] Mac 사용 설명서 — 앱이 다른 앱을 제어하도록 허용: https://support.apple.com/guide/mac-help/mchl07817563/mac
- [A15] Customizing the notarization workflow(`ditto -c -k --keepParent`): https://developer.apple.com/documentation/security/customizing-the-notarization-workflow
- [A16] Packaging Mac software for distribution(`ditto`, `hdiutil`, App Translocation): https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution
- [A17] dyld 소스 `Loader::tooNewErrorAddendum`(dyld-1378, minos가 높으면 오류 문구에 덧붙이기만 함): https://github.com/apple-oss-distributions/dyld/blob/dyld-1378/dyld/Loader.cpp#L3163-L3194
- [A18] macOS Big Sur 11.0.1 Universal Apps 릴리스 노트(arm64 서명 의무, ad-hoc으로 충분, Gatekeeper 통과 불가): https://developer.apple.com/documentation/macos-release-notes/macos-big-sur-11_0_1-universal-apps-release-notes
- [A19] Apple 개발자 포럼, DTS 답변 "Overlay window above all windows, even when moving spaces"(2026-05): https://developer.apple.com/forums/thread/826308
- [A20] Updates to runtime protection in macOS Sequoia(2024-08-06, Control-클릭 우회 제거): https://developer.apple.com/news/?id=saqachfa
- [A21] Mac 사용 설명서 — 확인되지 않은 개발자의 앱 열기(macOS 26판, 14판): https://support.apple.com/guide/mac-help/mh40616/26/mac/26 , https://support.apple.com/guide/mac-help/mh40616/14.0/mac/14.0
- [A22] Safely open apps on your Mac: https://support.apple.com/en-us/102445
- [A23] 개발자 포럼 DTS 답변(quarantine 전파, `curl`·`tar`는 quarantine 안 붙임, `xattr`): https://developer.apple.com/forums/thread/706442
- [A24] Notarizing macOS software before distribution(Developer ID 인증서 필요): https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- [A25] Developer ID(계정 소유자만 인증서 생성): https://developer.apple.com/developer-id/
- [A26] Apple Developer Program(연 99달러)과 멤버십 비교(공증은 유료 회원만): https://developer.apple.com/programs/ , https://developer.apple.com/support/compare-memberships/
- [A27] 개발자 포럼 DTS 답변("macOS 15 removed control-click > Open"): https://developer.apple.com/forums/thread/768376
- [A28] macOS 27 릴리스 노트: https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes
- [A29] 개발자 포럼 DTS 답변(내부 배포라면 quarantine 제거 가능): https://developer.apple.com/forums/thread/692774 , https://developer.apple.com/forums/thread/651730
- [A30] Apple 플랫폼 보안 — Gatekeeper와 런타임 보호(무작위 읽기 전용 위치에서 열기): https://support.apple.com/guide/security/gatekeeper-and-runtime-protection-sec5599b66df/web
- [A31] 개발자 포럼 DTS "App Translocation Notes": https://developer.apple.com/forums/thread/724969
- [A32] 개발자 포럼 DTS 답변(ad-hoc 서명은 안정된 DR이 없어 새 판을 같은 코드로 알지 못함): https://developer.apple.com/forums/thread/795739
- [A33] 개발자 포럼 DTS 답변(Finder 압축은 확장 속성을 따로 뺌, `ditto`는 아님): https://developer.apple.com/forums/thread/818269
- [A34] macOS Sequoia 호환 기기: https://support.apple.com/en-us/120282
- [A35] 개발자 포럼 DTS 답변(PostEvent·ListenEvent·Accessibility 권한 구분): https://developer.apple.com/forums/thread/820594
- [A36] 개발자 포럼 DTS 답변(10.14 SDK부터 `NSAppleEventsUsageDescription`이 없으면 Apple 이벤트 거부): https://developer.apple.com/forums/thread/109561
- [A37] 개발자 포럼 DTS 답변(앱이 띄운 자식 프로세스는 앱이 책임 코드, osascript 사례): https://developer.apple.com/forums/thread/756510 , https://developer.apple.com/forums/thread/750802
- [A38] Network client entitlement(샌드박스 앱용): https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.network.client
- [A39] Mac Automation Scripting Guide — UI 자동화는 손쉬운 사용 허용 필요: https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/AutomatetheUserInterface.html
- [A40] `tccutil` 매뉴얼(미러)과 서비스 이름 목록(DTS 답변): https://keith.github.io/xcode-man-pages/tccutil.1.html , https://developer.apple.com/forums/thread/679303
- 참고: Apple 개발자 문서는 자바스크립트로 그려져서, 일부 인용은 같은 내용의 JSON(`developer.apple.com/tutorials/data/documentation/….json`)에서 읽었다. 포럼 글은 자동 추출로 읽어 문장 부호가 조금 다를 수 있다.

### 공개 사례
- [E1] Dejniel/TiMini-Print — `macos-15`, tkinter + pyobjc, PyInstaller, `ditto`: https://github.com/Dejniel/TiMini-Print/blob/HEAD/.github/workflows/release.yml
- [E2] TomBadash/Mouser — `macos-15`, PySide6, `zip -r -y`: https://github.com/TomBadash/Mouser/blob/HEAD/.github/workflows/release.yml
- [E3] mfat/sshpilot — `macos-15`, `.app`과 DMG: https://github.com/mfat/sshpilot/blob/HEAD/.github/workflows/macos-pyinstaller.yml
- [E4] abrignoni/iLEAPP — `macos-latest`, Python 3.14, tkinter `.app`: https://github.com/abrignoni/iLEAPP/blob/HEAD/.github/workflows/release.yml
- [E5] PyInstaller 이슈 #9185(링크를 지키지 않은 zip → 서명 무효, `xattr -r -d com.apple.quarantine`): https://github.com/pyinstaller/pyinstaller/issues/9185
- [E6] PyInstaller 이슈 #9245("Apple could not verify … free of malware"): https://github.com/pyinstaller/pyinstaller/issues/9245
- [E7] PyInstaller 이슈 #8268(GitHub 릴리스에서 받은 앱이 "손상됨"): https://github.com/pyinstaller/pyinstaller/issues/8268
- [E8] franzenzenhofer/big-arrow-on-the-screen 실행 37762304745(`macos-15` arm64, 이미지 20260907.0337.1, 1024×768, 권한 granted, 전체 화면 앱 위 표시 PASS. 작업 전체는 2배율 보고 시험 하나로 실패): https://github.com/franzenzenhofer/big-arrow-on-the-screen/actions/runs/37762304745
- [E9] hoangperry/herminal 스크린숏 워크플로(GUI 세션, System Events 키 입력): https://github.com/hoangperry/herminal/blob/main/.github/workflows/screenshots.yml
- [E10] JaminZhou/codex-ui-kit 실행 34041357514(`macos-26` arm64, `displayplacer` 1024×768 → 1920×1080): https://github.com/JaminZhou/codex-ui-kit/actions/runs/34041357514
- [E11] big-arrow 시험 스크립트(전체 화면 앱 위 픽셀·포커스 검사)와 가짜 전체 화면 앱: https://github.com/franzenzenhofer/big-arrow-on-the-screen/blob/c69739708ef2358d47ae5b89fb1ef2d3c1da50ce/scripts/behaviour-check.sh#L81-L89 , https://github.com/franzenzenhofer/big-arrow-on-the-screen/blob/c69739708ef2358d47ae5b89fb1ef2d3c1da50ce/scripts/backdrop.swift#L27-L31
- [E12] big-arrow 오버레이 패널 설정: https://github.com/franzenzenhofer/big-arrow-on-the-screen/blob/c69739708ef2358d47ae5b89fb1ef2d3c1da50ce/Sources/BigArrowOverlay/OverlayPanel.swift#L7-L19
- [E13] NetOfficeFw/setup-powerpoint(러너에 PowerPoint 설치만): https://github.com/NetOfficeFw/setup-powerpoint
- [E14] GregoryBolshakov/peekme 실행 37144347426(osascript 키 입력, `macos-15`·`macos-26` arm64 성공): https://github.com/GregoryBolshakov/peekme/actions/runs/37144347426
- [E15] JetBrains/ideavim UI 시험 워크플로(`cliclick`, osascript `click at`, 화면 녹화): https://github.com/JetBrains/ideavim/blob/master/.github/workflows/runUiPyTests.yml
- [E16] mxschmitt/action-tmate(macOS 지원, `limit-access-to-actor`): https://github.com/mxschmitt/action-tmate

### 기타
- [O1] Homebrew cask `microsoft-powerpoint`: https://formulae.brew.sh/api/cask/microsoft-powerpoint.json
- [O2] Microsoft Learn — Office for Mac 활성화 개요("prompted to activate Office the first time they use it"): https://learn.microsoft.com/en-us/microsoft-365-apps/mac/overview-of-activation-for-office-for-mac
