# 캐릭터 창과 원 버튼을 만들 GUI 툴킷 조사

- 티켓: `02-research-gui-toolkit` (캐릭터 창과 원 버튼을 어떤 GUI 툴킷으로 만들 수 있나)
- 조사일: 2026-10-16
- 비교 대상: tkinter(Tk 9.0.4), PySide6 6.12.0(Qt 6.12). 다른 툴킷(wxPython 등)은 조사하지 않았다.
- 표기: **실측**은 이 PC(Windows 11)에서 직접 실행한 결과다. **소스**는 툴킷 소스 코드를 읽은 결과다. **문서**는 공식 문서다. macOS는 실행할 수 없어 모두 "문서·소스 근거, 미실행"이다.

## 결론 요약

1. **tkinter만으로는 안 되고, tkinter + 운영체제 API 보조로는 된다.** Windows에서 tkinter 단독은 색 키 투명(`-transparentcolor`)과 창 전체 알파(`-alpha`)만 된다. 클릭 통과, 포커스 안 뺏기, 모니터별 작업 영역 API도 없다. ctypes로 Win32를 부르면(`UpdateLayeredWindow`, `WS_EX_NOACTIVATE`, `WS_EX_TRANSPARENT`, `GetMonitorInfo`) 기능 항목 1~6이 모두 된다. 실제 PowerPoint 슬라이드 쇼 위에서 실측했다.
2. **PySide6는 Windows에서 창 플래그만으로 모두 된다(실측).** 다만 Apple 문서가 "다른 앱의 전체 화면 Space에 합류하는 떠 있는 창"용으로 안내하는 `NSWindowCollectionBehaviorCanJoinAllApplications`(macOS 13+)는 Tk도 Qt도 설정하지 않는다(소스). 그래서 **어느 툴킷을 고르든 macOS에는 pyobjc가 필요할 가능성이 높다.** 이것 없이도 되는지는 미확인이다.
3. 슬라이드 쇼 창(`screenClass`)은 topmost가 아니어서(exstyle 0) 두 툴킷의 "항상 위" 창이 쇼 위에 보인다. 원 버튼과 위성 버튼은 `WS_EX_NOACTIVATE`(Qt: `WindowDoesNotAcceptFocus`)를 주면 클릭해도 쇼가 → 키를 계속 받는다. 강아지는 `WS_EX_TRANSPARENT`(Qt: `WindowTransparentForInput`)로 클릭이 쇼로 통과한다. 질문창은 포커스를 받아 입력한 뒤 `SetForegroundWindow`로 쇼에 포커스를 돌려줄 수 있다. 모두 실측했다.
4. 30fps 애니메이션 CPU는 tkinter 11~20%, Qt 20%다(한 코어 기준). 60fps는 tkinter 29~43%, Qt 33~37%다. 16 논리 코어 PC에서는 전체의 3% 이하다. 큰 차이는 없다.
5. 배포 크기(PyInstaller onedir, 빈 창 하나)는 tkinter 25MB, PySide6 101MB다. PySide6는 LGPLv3 의무(라이선스 문구, Qt 소스 제공, 교체 가능)가 붙는다. PySide6 6.12 wheel은 macOS 14 이상에서만 설치되고, Qt 6.12가 Windows 10을 지원하는 마지막 버전이다.
6. **권장: tkinter를 유지하고 운영체제별 보조 모듈(Windows: ctypes, macOS: pyobjc)을 둔다.** 이유는 셋이다. (가) Windows에서 기능 항목 1~6을 실측으로 모두 통과했고, CPU도 Qt와 비슷했다. (나) Qt로 바꿔도 macOS의 pyobjc 보조는 그대로 필요하다. (다) 기존 설정 화면과 대본 화면이 이미 tkinter라 다시 쓰지 않아도 된다. 대가로 그리기 경로가 운영체제별로 두 벌이 된다(Windows: Pillow → `UpdateLayeredWindow`, macOS: 투명 창 위 Tk 그리기).
7. **확정 조건:** macOS는 하나도 실행하지 못했다. 구현 첫 단계에서 Mac 시제품으로 세 가지를 확인한다. 전체 화면 슬라이드 쇼 위에 보이는가, 투명 창에서 알파가 합성되는가, 질문창이 키 입력을 받는가. 여기서 Tk만의 문제가 나오면 PySide6(+pyobjc)로 바꾼다.

## 항목 × 툴킷 × 운영체제 표

칸의 [기호]는 맨 아래 출처 목록의 번호다.

| 항목 | tkinter / Windows | tkinter / macOS | PySide6 / Windows | PySide6 / macOS |
|---|---|---|---|---|
| 1. 투명 배경 | **보조 필요(실측)**: Tk 단독은 색 키·창 전체 알파만 된다. 반투명 링이 마젠타와 섞여 (166,34,244)로 나온다 [T1][T5]. ctypes `UpdateLayeredWindow`로 픽셀 알파가 된다. 측정 (12,157,90), 이론값 (12,156,90) [M1][M4] | **됨(문서·소스, 미실행)**: `wm attributes -transparent 1`과 배경 `systemTransparent`를 주면 NSWindow가 `clearColor`·불투명 해제로 바뀐다 [T1][T12]. 이미지 알파가 합성되는지는 미확인 | **됨(실측)**: `WA_TranslucentBackground`+`FramelessWindowHint`. 측정 (12,157,90) [Q2][Q3][Q9] | **됨(문서, 미실행)**: 같은 속성을 쓴다 [Q3] |
| 2. 항상 위 / 쇼 위 | **됨(실측)**: `-topmost`(`HWND_TOPMOST`) [T5]. 쇼 창은 topmost가 아니다(exstyle 0). 쇼가 활성이어도 오버레이가 위에 보인다 [M2] | **pyobjc 필요(소스·문서, 미실행)**: `-topmost`는 `kCGUtilityWindowLevel`이다. overrideredirect 창은 자동으로 `CanJoinAllSpaces\|FullScreenAuxiliary`를 받는다 [T10]. 다른 앱의 전체 화면 Space에 끼려면 `canJoinAllApplications`(13+)가 필요한데 Tk는 설정하지 않는다 [A6] | **됨(실측)**: `WindowStaysOnTopHint` [Q1] | **pyobjc 필요(소스·문서, 미실행)**: StaysOnTop은 `NSModalPanelWindowLevel`이다 [Q12]. `Tool`은 NSPanel이 되고 앱이 비활성일 때 숨는다. `WA_MacAlwaysShowToolWindow`가 필요하다 [Q2][Q14][Q15][A11]. `canJoinAllApplications`는 설정하지 않는다 |
| 3. 클릭 통과 | **보조 필요(실측)**: Tk 옵션이 없다. ctypes로 `WS_EX_LAYERED\|WS_EX_TRANSPARENT`를 주면 클릭이 쇼로 가서 슬라이드가 넘어간다 [M1][M3] | **됨(소스, 미실행)**: `::tk::unsupported::MacWindowStyle style $w <class> ignoreClicks`가 `setIgnoresMouseEvents:`를 부른다 [T10][T11][A7] | **됨(실측)**: `WindowTransparentForInput` [Q1][Q10] | **됨(소스, 미실행)**: 같은 플래그가 `ignoresMouseEvents`가 된다 [Q13][A7] |
| 4. 포커스 안 뺏기 / 질문창 | **보조 필요(실측)**: 기본 창은 클릭하면 포커스를 가져간다. ctypes `WS_EX_NOACTIVATE`를 주면 쇼가 키를 유지한다 [M3]. 질문창은 `focus_force`로 입력받고 `SetForegroundWindow`로 쇼에 되돌린다 [M5]. 주의: 앱의 첫 창은 Tk가 `SetActiveWindow`를 부른다 [T4] | **부분(소스, 미실행)**: overrideredirect 창은 key 창이 될 수 없어 강아지·원 버튼에 맞다 [T8][T9]. 질문창은 overrideredirect가 아니어야 한다. Tk 9 `-class nspanel`, `-stylemask nonactivatingpanel`이 있다 [T1][T13]. 쇼를 유지한 채 입력이 되는지는 미확인 | **됨(실측)**: `WindowDoesNotAcceptFocus`+`WA_ShowWithoutActivating` [Q1][Q2][Q10][Q11]. 질문창은 `activateWindow`로 입력받는다(실측) | **부분(소스, 미실행)**: `WindowDoesNotAcceptFocus`면 key가 거부된다 [Q16]. Tool·Dialog는 key가 될 수 있다 [Q17]. 앱을 활성화하지 않고 입력하려면 `nonactivatingPanel`을 pyobjc로 줘야 한다 [A8][A9] |
| 5. 전역 커서 | **됨(실측)**: `winfo_pointerxy` = `GetCursorPos` [T7]. 호출당 3.2µs. 음수 좌표의 보조 모니터에서도 정확하다. 단, Python 3.14 tkinter는 기본이 DPI unaware라 좌표가 축소된다. per-monitor v2 설정이 필요하다 [M9] | **됨(소스, 미실행)**: `[NSEvent mouseLocation]`을 쓴다 [T14][A12] | **됨(실측)**: `QCursor.pos()` 2.5µs. 논리 좌표다(150%에서 물리 (100,100) → (67,67)) [Q4] | **됨(소스, 미실행)**: `[NSEvent mouseLocation]` [Q19] |
| 6. 모니터 목록·작업 영역 | **보조 필요(실측)**: Tk API가 없다. `winfo_screenwidth`는 주 모니터, `vroot*`는 가상 화면 전체를 준다 [T2]. ctypes `EnumDisplayMonitors`+`GetMonitorInfo`의 `rcWork`로 작업 영역을 얻는다 [M7][M8] | **pyobjc 필요(문서, 미실행)**: Tk API가 없다. `NSScreen.screens()`의 `visibleFrame`을 쓴다(Dock·메뉴 막대 제외) [A13] | **됨(실측)**: `QScreen.availableGeometry()` = `rcWork`, 논리 px [Q5][Q21]. `name()`은 장치 이름이 아니다('TL140ADMP01') | **됨(소스, 미실행)**: `availableGeometry` = `visibleFrame` [Q20] |
| 7. 애니메이션 CPU(한 코어 기준) | **실측**: 30fps 11~20%, 60fps 29~43%. 다만 `after()`를 마감 시각 기준으로 예약해야 목표 fps가 나온다 | 미측정 | **실측**: 30fps 20%, 60fps 33~37% | 미측정 |
| 8. 배포(PyInstaller) | **실측**: onedir 25MB, onefile 12MB(빈 창). 현재 PPTReader는 51MB. Tcl/Tk는 BSD식 라이선스다 [T16][P4] | **문서**: python.org 3.14.7 설치본이 Tk 9.0.4를 담는다(macOS 10.15+) [P2][P3]. pyobjc는 MIT(core wheel 6.4MB) [O1]. 크기는 미측정 | **실측**: onedir 101MB(그중 `opengl32sw.dll` 20.6MB), onefile 40MB. LGPLv3 의무가 있다 [Q7][Q8]. Qt 6.12가 Windows 10을 지원하는 마지막 버전이다 [Q6] | **문서**: PySide6 6.12 wheel은 `macosx_14_0`이고 [Q22] Qt 6.12는 macOS 14.4+를 지원한다 [Q6]. 크기는 미측정 |

## 시험 환경과 방법

- PC: Windows 11 Pro 10.0.26200, AMD Ryzen AI 7 350(8코어 16스레드).
- 모니터 두 대: 주 모니터 `\\.\DISPLAY1` 2560×1600(150%), 보조 `\\.\DISPLAY5` 1920×1080(100%, 왼쪽, 가상 좌표 x<0).
- Python 3.14.7(python.org 설치 관리자), Tk 9.0.4, Pillow 12.3.0, pywin32 312, PySide6-Essentials 6.12.0(스크래치 venv), PyInstaller 6.22.3, PowerPoint 16(COM `PowerPoint.Application.16`).
- 클릭과 키는 `SendInput`으로 만들었다. 슬라이드 쇼에 포그라운드를 줄 때는 `AttachThreadInput`+`SetForegroundWindow`를 썼다. 발표자가 쇼를 클릭한 상태를 흉내 낸 것이다. 매 단계 전에 대상 창이 맞는지 `WindowFromPoint`/`GetForegroundWindow`로 확인하고, 아니면 멈추게 했다.
- 시험 스크립트는 저장소에 넣지 않았다. 핵심 코드는 각 절에 옮겼다.

## 항목별 상세

### 1. 투명 배경

**tkinter 단독(Windows).** overrideredirect 창은 Tk가 `WS_EX_TOOLWINDOW`만 준다 [T3]. Tk 9.0 매뉴얼에서 Windows 전용 속성은 `-alpha`(창 전체 불투명도), `-transparentcolor`(색 키), `-disabled`, `-toolwindow`가 전부다 [T1]. 소스를 보면 두 속성 모두 `SetLayeredWindowAttributes`(`LWA_ALPHA`/`LWA_COLORKEY`) 하나로 처리한다 [T5]. 픽셀 단위 알파 경로는 없다.

**Win32 문서.** 픽셀 알파가 필요하면 `UpdateLayeredWindow`를 쓴다 [M1]. `SetLayeredWindowAttributes`를 한 번 부른 창은 레이어 스타일을 껐다 켜기 전까지 `UpdateLayeredWindow`가 실패한다 [M1]. 그래서 Tk의 `-alpha`·`-transparentcolor`와 섞어 쓰면 안 된다.

**실측.** 녹색(0,200,0) 창 위에 300×300 오버레이를 띄웠다. 오버레이 그림은 Pillow로 만든 RGBA다. 가운데는 불투명한 파란 원, 바깥은 α=100인 링이다. 화면을 캡처해 픽셀을 비교했다.

| 방식 | 투명 모서리(α=0) | 반투명 링(α=100) | 이론값(녹색 위 합성) |
|---|---|---|---|
| Tk `-transparentcolor #ff00ff` + Canvas에 PNG | (0,200,0) 아래가 보임 | **(166,34,244)** 마젠타와 섞임 | (12,156,90) |
| Tk `-alpha 0.5` | (15,145,115) 창 전체가 반투명 | (15,145,115) | — |
| Tk 창 + ctypes `UpdateLayeredWindow` | (0,200,0) | **(12,157,90)** | (12,156,90) |
| PySide6 `WA_TranslucentBackground` | (0,200,0) | **(12,157,90)** | (12,156,90) |

색 키 방식에서는 Tk가 PNG 알파를 캔버스 배경색(마젠타)과 먼저 섞는다. 그래서 매끄러운 가장자리와 반투명 파동에 분홍 테두리가 생긴다. 다만 점 그림 강아지처럼 알파가 0 또는 255뿐인 그림은 색 키로도 깨끗하다.

<details><summary>tkinter 창에 픽셀 알파를 입히는 핵심 코드(실측에 쓴 것)</summary>

```python
import ctypes, ctypes.wintypes as wt
from PIL import Image
user32, gdi32 = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
# (argtypes/restype 선언은 생략: HWND/HDC/HBITMAP을 포인터 크기로 선언해야 64비트에서 안전)

root = tk.Tk(); root.withdraw()
root.overrideredirect(True); root.attributes("-topmost", True)
root.geometry(f"{W}x{H}+{x}+{y}")
root.update_idletasks()
hwnd = int(root.wm_frame(), 16)          # Tk가 만든 바깥(wrapper) HWND
# 여기서 확장 스타일을 더한다: WS_EX_LAYERED(0x80000), 필요하면 WS_EX_NOACTIVATE(0x08000000)
root.deiconify(); root.update()

# 32비트 top-down DIB 하나를 만들어 두고, 프레임마다 Pillow 그림을 복사해 넣는다
bih = BITMAPINFOHEADER(40, W, -H, 1, 32, 0, 0, 0, 0, 0, 0)
bits = ctypes.c_void_p()
screen_dc = user32.GetDC(None); mem_dc = gdi32.CreateCompatibleDC(screen_dc)
hbmp = gdi32.CreateDIBSection(screen_dc, ctypes.byref(bih), 0, ctypes.byref(bits), None, 0)
gdi32.SelectObject(mem_dc, hbmp)
blend = BLENDFUNCTION(0, 0, 255, 1)       # AC_SRC_OVER, 상수 알파 255, AC_SRC_ALPHA

def push(rgba: Image.Image, x, y):        # 위치 이동과 그림 교체를 한 번에
    r, g, b, a = rgba.convert("RGBa").split()          # 미리 곱한(premultiplied) 알파
    data = Image.merge("RGBA", (b, g, r, a)).tobytes() # BGRA 순서
    ctypes.memmove(bits, data, len(data))
    user32.UpdateLayeredWindow(hwnd, screen_dc, ctypes.byref(wt.POINT(x, y)),
                               ctypes.byref(wt.SIZE(W, H)), mem_dc,
                               ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(blend), 2)  # ULW_ALPHA
```
</details>

**PySide6.** `WA_TranslucentBackground` 문서에 따르면 "Windows에서는 `Qt::FramelessWindowHint`도 있어야 한다" [Q2][Q3]. Qt는 테두리 없는 알파 창을 레이어드 창(`WS_EX_LAYERED`)으로 만들고 `UpdateLayeredWindow`로 갱신한다 [Q9]. 실측에서도 확장 스타일에 `WS_EX_LAYERED`가 켜져 있었다(0x8080088).

**macOS(미실행).** Tk 9.0 매뉴얼의 `-transparent`는 "창 내용 영역을 투명하게 하고 그림자를 끈다"고 한다. 효과를 보려면 배경을 `systemTransparent`처럼 알파가 있는 색으로 해야 한다 [T1]. 소스에서는 `[macWindow setBackgroundColor:[NSColor clearColor]]`와 `setOpaque:NO`를 부른다 [T12]. 그 위에 그린 PhotoImage의 반투명 픽셀이 화면과 제대로 섞이는지는 **미확인**이다. Qt는 `WA_TranslucentBackground`가 macOS에서도 같은 조건으로 된다고 문서에 적혀 있다 [Q3].

### 2. 항상 위 — PowerPoint 슬라이드 쇼 위

**Windows 문서.** topmost 창은 활성·포그라운드 여부와 상관없이 topmost가 아닌 모든 창 위에 놓인다 [M2]. Tk `-topmost`는 `SetWindowPos(HWND_TOPMOST, … SWP_NOACTIVATE)`를 부른다 [T5][M10].

**실측(실제 슬라이드 쇼).** 표본 PPT를 COM으로 열고 쇼를 시작했다. 이 PC에서는 발표자 보기를 꺼도(`ShowPresenterView=0`) 쇼가 보조 모니터 `DISPLAY5`에 떴다. 쇼 창 클래스는 `screenClass`, **확장 스타일은 0**(topmost 아님)이었다.

순서는 실제 사용과 같게 잡았다. (1) 오버레이 앱을 먼저 띄운다. (2) 쇼에 포그라운드를 준다. (3) 오버레이 가운데를 클릭한다. (4) → 키를 보낸다. 오버레이는 160×160 파란 원이고, 쇼 모니터 오른쪽 아래에 둔다.

| 툴킷·모드 | 확장 스타일 | 처음 뜰 때 포그라운드를 가져감 | 쇼가 활성일 때 화면에 보임(픽셀) | 오버레이 클릭 후 포그라운드 | 클릭으로 슬라이드 넘어감 | → 키로 넘어감 | 오버레이가 클릭 받음 |
|---|---|---|---|---|---|---|---|
| tk 기본(overrideredirect+topmost) | 0x80088 | 아니오 | 예 (30,90,230) | 오버레이 | 0 | **0** | 예 |
| tk + `WS_EX_NOACTIVATE` | 0x8080088 | 예 | 예 | **쇼** | 0 | **1** | 예 |
| tk + `WS_EX_TRANSPARENT` | 0x800a8 | 예 | 예 | 쇼 | **1** | 1 | 아니오 |
| Qt `Frameless\|StaysOnTop\|Tool` | 0x80088 | 아니오 | 예 | 오버레이 | 0 | **0** | 예 |
| Qt + `WindowDoesNotAcceptFocus` | 0x8080088 | 아니오 | 예 | **쇼** | 0 | **1** | 예 |
| Qt + `WindowTransparentForInput` | 0x800a8 | 아니오 | 예 | 쇼 | **1** | 1 | 아니오 |

- 두 툴킷의 topmost 창 모두 활성 쇼 위에 보였다. 클릭 통과 창은 `WindowFromPoint`가 아래의 쇼를 돌려주지만 화면에는 그대로 보인다.
- "처음 뜰 때 포그라운드를 가져감"은 Tk에서만 나왔고, 결과도 실행마다 달랐다. Tk는 앱이 처음 띄우는 최상위 창에 `SetActiveWindow`를 부른다 [T4]. 이것이 성공하는지는 그 순간 프로세스가 포그라운드를 바꿀 권한이 있는지에 달려 있다 [M5]. 실제 앱은 쇼보다 먼저 켜지므로 시작할 때 한 번만 생긴다. Qt `Tool` 창은 `SW_SHOWNOACTIVATE`로 띄운다 [Q11].
- 슬라이드 쇼 위에 다른 topmost 창이 나중에 뜨면 그 창이 더 위로 올라갈 수 있다(topmost끼리의 순서). 주기적으로 topmost를 다시 거는 것이 필요한지는 **미확인**이다.

**macOS(문서·소스, 미실행).**
- 창 레벨은 높은 레벨의 창이 낮은 레벨의 모든 창을 가린다 [A1][A2]. Tk `-topmost`는 `kCGUtilityWindowLevel`, Qt `WindowStaysOnTopHint`는 `NSModalPanelWindowLevel`, Qt `Tool`은 `NSFloatingWindowLevel`이다 [T10][Q12].
- 다른 앱이 전체 화면 Space를 쓰는 경우를 보자. Space 관련 동작은 `collectionBehavior`로 정한다 [A3]. Apple 문서의 `canJoinAllSpaces`는 "모든 Space에 나타날 수 있다", `fullScreenAuxiliary`는 "전체 화면 창과 같은 Space에 표시된다"다 [A4][A5]. 다른 앱의 전체 화면 Space에 끼는 동작은 macOS 13의 `canJoinAllApplications`에 적혀 있다. "전체 화면 Space에서 다른 앱의 창에 합류할 수 있다. 떠 있는 창과 시스템 오버레이에 이 동작을 쓰라"는 설명이고, primary·auxiliary와 동시에 쓰지 말라고 한다 [A6].
- Tk는 overrideredirect 창에 `CanJoinAllSpaces|FullScreenAuxiliary`를 자동으로 준다 [T10]. Qt는 `Tool`/`Popup` 창(NSPanel)에 `FullScreenAuxiliary|MoveToActiveSpace`를 준다 [Q15]. 두 소스 어디에도 `CanJoinAllApplications`는 없다. 따라서 pyobjc로 NSWindow를 얻어 `collectionBehavior`를 직접 바꿔야 한다. NSWindow는 Qt에서 `winId()`(=NSView)의 `.window()`로 얻는다 [Q18]. Tk에서는 공개 C 함수 `Tk_MacOSXGetNSWindowForDrawable`이 있지만 [T15] 파이썬에서 부르는 방법은 확인하지 않았다. `NSApp.windows()`를 돌며 찾는 방법도 있다.
- 우리 앱이 활성화되면 macOS가 다른 Space로 넘어갈 수 있다. Dock에 안 나오는 에이전트 앱(`LSUIElement`/`.accessory`)으로 만드는 것이 도움이 될 수 있다 [A14][A15]. 하지만 필요한지는 **미확인**이다.
- PowerPoint for Mac의 슬라이드 쇼가 별도 전체 화면 Space를 쓰는지도 **미확인**이다.

<details><summary>macOS 보조 코드 예시(pyobjc, <b>미실행</b>)</summary>

```python
# 실행해 보지 않은 예시다. 이름은 Apple 문서의 Objective-C 이름을 pyobjc 규칙으로 옮긴 것이다.
import AppKit
def make_overlay(nswindow, click_through: bool):
    b = nswindow.collectionBehavior()
    b &= ~(AppKit.NSWindowCollectionBehaviorFullScreenPrimary
           | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)   # 문서: 셋 중 하나만
    b |= AppKit.NSWindowCollectionBehaviorCanJoinAllApplications     # macOS 13+
    nswindow.setCollectionBehavior_(b)
    nswindow.setIgnoresMouseEvents_(click_through)
```
</details>

### 3. 클릭 통과

**Windows 문서.** 레이어드 창의 히트 테스트는 창의 모양과 투명도를 따른다. 색 키 영역이나 알파 0인 영역은 마우스 메시지를 통과시킨다. `WS_EX_TRANSPARENT`가 있으면 모양을 무시하고 모든 마우스 이벤트를 아래 창으로 보낸다 [M1].

**실측.**
- 두 프로세스로 시험했다. 아래 창과 Tk 색 키 오버레이를 따로 띄웠다. 불투명한 가운데를 클릭하면 오버레이가, 키 색 모서리를 클릭하면 아래 창이 받았다.
- `UpdateLayeredWindow` 창은 알파 0인 모서리 클릭이 아래 창으로 갔고, 불투명한 가운데는 오버레이가 받았다. PySide6 반투명 창도 `WindowFromPoint`로 같은 결과였다.
- 두 툴킷 모두 `WS_EX_TRANSPARENT`를 주면 불투명한 곳까지 클릭이 통과해 슬라이드 쇼가 넘어갔다(2절 표).
- Tk에는 해당 옵션이 없어 ctypes로 확장 스타일을 더했다. Qt는 `WindowTransparentForInput`이 `WS_EX_TRANSPARENT`(+`WS_EX_LAYERED`)가 된다 [Q9][Q10].
- 따라서 원 버튼은 픽셀 알파 창이면 원 바깥의 투명한 구석이 저절로 클릭을 통과시킨다. 강아지는 `WS_EX_TRANSPARENT`로 통째로 통과시킨다.

**macOS(소스, 미실행).** `NSWindow.ignoresMouseEvents`는 "창이 마우스 이벤트에 투명한지"를 뜻한다 [A7]. Tk에는 비공개 명령 `::tk::unsupported::MacWindowStyle style <창> <class> {ignoreClicks …}`가 있다. 이 명령의 `ignoreClicks` 속성이 `setIgnoresMouseEvents:`를 부른다 [T10][T11]. Qt는 `WindowTransparentForInput`이 같은 속성을 켠다. Qt 소스 주석에 따르면 이 속성은 처음에 "창 투명도에 따라 통과시키는" 특수 상태다. 한 번 false로 바꾸면 그 상태로 돌아가지 않는다 [Q13].

### 4. 포커스 안 뺏기와 질문창

**Windows 문서.** `WS_EX_NOACTIVATE`로 만든 최상위 창은 사용자가 클릭해도 포그라운드가 되지 않는다 [M3]. 포그라운드를 바꿀 수 있는 프로세스는 제한된다. 예를 들어 "마지막 입력 이벤트를 받은 프로세스"는 바꿀 수 있다 [M5].

**실측 1(원 버튼).** 2절 표와 같다. 기본 창은 클릭하면 포그라운드를 가져가 → 키가 쇼에 가지 않았다. `WS_EX_NOACTIVATE`(Tk: ctypes, Qt: `WindowDoesNotAcceptFocus`)를 주면 클릭은 받으면서 쇼가 → 키를 계속 받았다.

Tk에 이 스타일을 넣을 때는 순서가 중요하다. 창을 `withdraw()` 상태에서 만들고, `wm_frame()`으로 wrapper HWND를 얻어 스타일을 더한 뒤 `deiconify()`한다. 이후 `overrideredirect`처럼 Tk가 wrapper를 다시 만드는 설정을 바꾸면 더한 스타일이 사라질 수 있다. 그래서 스타일을 다시 확인해야 한다. 실측에서는 `deiconify` 전후에 HWND가 같았다.

Tk 소스를 보면 grab이 없을 때 `WM_MOUSEACTIVATE`를 `DefWindowProcW`에 넘긴다 [T6]. 그래서 `WS_EX_NOACTIVATE`가 그대로 적용된 것으로 보이며, 실측 결과와 맞는다.

**실측 2(질문창 흐름).** 쇼가 포그라운드인 상태에서 다음 순서로 시험했다.
1. `WS_EX_NOACTIVATE`를 준 "Q" 버튼을 클릭한다.
2. 버튼 처리 코드가 그 순간의 포그라운드 창(쇼)을 기억한다.
3. 질문창을 띄우고 포커스를 준다. Tk는 `entry.focus_force()`, Qt는 `activateWindow()`를 쓴다.
4. `abc`를 입력하고 Enter를 누른다.
5. 질문창을 숨기고 기억해 둔 창에 `SetForegroundWindow`를 부른다.
6. → 키를 보낸다.

| 툴킷 | 버튼 클릭 뒤 질문창이 포그라운드 | 입력된 글 | 되돌리기 `SetForegroundWindow` | Enter 뒤 쇼가 포그라운드 | → 키로 넘어감 |
|---|---|---|---|---|---|
| tkinter(overrideredirect 창 + Entry) | 예 | `abc` | 성공 | 예 | 1 |
| PySide6(`QLineEdit`, `Frameless\|StaysOnTop\|Tool`) | 예 | `abc` | 성공 | 예 | 1 |

포커스를 받지 않는 버튼을 클릭해도 그 클릭이 우리 프로세스의 마지막 입력이 된다. 그래서 질문창에 포그라운드를 줄 수 있었다고 본다. 이 해석은 [M5]의 조건에 맞지만, 원인을 따로 확인하지는 않았다.

<details><summary>질문창 흐름 핵심 코드(tkinter, 실측에 쓴 것)</summary>

```python
def open_box(_e):                      # WS_EX_NOACTIVATE 버튼의 <Button-1>
    state["return_to"] = user32.GetForegroundWindow()   # 아직 슬라이드 쇼
    box.deiconify(); box.lift()
    entry.focus_force()                # Tk: focus -force -> SetForegroundWindow

def submit(_e):                        # entry의 <Return>
    ask(entry.get())
    box.withdraw()
    user32.SetForegroundWindow(state["return_to"])      # 쇼가 다시 → 키를 받는다
```
</details>

**macOS(소스·문서, 미실행).**
- Tk는 overrideredirect 창에 `kWindowNoActivatesAttribute`를 켠다 [T9]. Tk의 `canBecomeKeyWindow`는 이 속성이 있으면 NO를 돌려준다 [T8]. 따라서 강아지와 원 버튼에는 맞지만, **질문창은 overrideredirect로 만들면 키 입력을 못 받는다**.
- Tk 9.0은 `wm attributes -class nspanel`과 `-stylemask {… nonactivatingpanel}`로 "앱을 활성화하지 않는 패널"을 만들 수 있다 [T1][T13]. 그런데 Tk의 NSPanel 하위 클래스(`TKPanel`)는 `canBecomeKeyWindow`를 고치지 않는다 [T8]. AppKit 기본값은 제목 막대가 있을 때만 key 창이 될 수 있다 [A10]. 그래서 테두리 없는 Tk 패널이 입력을 받을 수 있는지는 **미확인**이다.
- Qt는 `WindowDoesNotAcceptFocus`·`WindowTransparentForInput`이면 key를 거부한다 [Q16]. NSPanel 계열에서는 `Tool`/`Dialog`만 key가 된다 [Q17]. Apple 문서에 따르면 nonactivating 패널은 클릭한 뷰가 `needsPanelToBecomeKey`로 YES를 줄 때만 key가 된다 [A9]. 이것이 쇼를 유지한 채 질문창에 입력하는 열쇠로 보이지만 **미확인**이다.

### 5. 전역 커서 위치

**소스.**
- Tk `winfo pointerxy`는 Windows에서 `GetCursorPos`를 부른다 [T7][M6]. macOS에서는 `[NSEvent mouseLocation]`을 위아래 뒤집어 돌려준다 [T14][A12].
- Qt `QCursor::pos()`는 "주 화면 기준 전역 좌표"를 돌려준다 [Q4]. macOS 구현은 `[NSEvent mouseLocation]`이다 [Q19].
- Apple 문서의 `mouseLocation`에는 권한 요구가 적혀 있지 않다 [A12]. 실제로 권한 창이 뜨는지는 **미확인**이다.

**실측(Windows).** `SetCursorPos`로 커서를 옮긴 뒤 읽었다. 클릭은 하지 않았다.

| 방법 | 주 모니터 (100,100) | 보조 모니터 (-1820,254) | 호출당 비용 |
|---|---|---|---|
| tkinter `winfo_pointerxy()`(DPI 설정 없음) | (100,100) | (-1820,254) | 3.5µs |
| tkinter `winfo_pointerxy()`(per-monitor v2) | (100,100) | (-1820,254) | 3.2µs |
| ctypes `GetCursorPos` | (100,100) | (-1820,254) | 2.4µs |
| PySide6 `QCursor.pos()` | **(67,67)** 논리 좌표 | (-1820,254) | 2.5µs |

호출당 수 µs라 30~60fps(16~33ms마다 한 번) 폴링은 부담이 없다.

**DPI 주의(실측).** Python 3.14의 tkinter는 기본이 **DPI unaware**였다. 그래서 2560×1600 주 모니터가 1707×1067로 보였다(`winfo_screenwidth`, `GetMonitorInfo` 모두). 프로세스를 per-monitor v2로 바꾸면(`SetProcessDpiAwarenessContext(-4)`, Tk를 만들기 전) 물리 좌표로 일관된다 [M9]. 기존 앱은 `SetProcessDpiAwareness(1)`(system aware)를 쓴다. 배율이 다른 모니터 사이로 강아지가 옮겨 갈 때를 생각하면 per-monitor v2가 맞다. 이때 Tk 위젯 글자 크기가 모니터마다 바르게 바뀌는지는 **미확인**이다. Qt는 기본이 per-monitor다(실측).

### 6. 모니터 목록과 작업 영역

**tkinter.** Tk에는 모니터별 API가 없다. `winfo screenwidth`는 창이 있는 "화면"의 폭이고, `vrootwidth`는 가상 루트다 [T2]. 실측(per-monitor v2)에서 `winfo_screenwidth/height`는 주 모니터(2560×1600)였다. `winfo_vrootwidth`는 4480, `vrootx`는 -1920으로 두 모니터를 합친 값이었다.

**Win32(실측).** `EnumDisplayMonitors`+`GetMonitorInfo`의 `rcWork`는 "작업 영역, 가상 화면 좌표, 주 모니터가 아니면 음수일 수 있음"이다 [M7][M8]. 결과는 다음과 같다.
- `DISPLAY1` 주: monitor (0,0,2560,1600), work (0,0,2560,1528), 작업 표시줄 72px 제외
- `DISPLAY5`: monitor (-1920,154,0,1234), work (-1920,154,0,1186)

**PySide6(실측).** `QScreen.availableGeometry()`는 "작업 표시줄 등을 뺀 영역"이다 [Q5]. Windows 구현은 `rcWork`다 [Q21]. 단위는 논리 px다. 주 모니터는 (0,0,1707,1067)/avail (0,0,1707,1019), dpr 1.5였다. `QScreen.name()`은 'TL140ADMP01', 'Display'처럼 사용자용 이름이었다. 문서도 "고유 식별에 쓰지 말라"고 한다 [Q5]. 설정에 모니터를 저장할 때 이름만으로는 부족하다.

**macOS(문서·소스, 미실행).** `NSScreen.visibleFrame`은 Dock과 메뉴 막대를 뺀 영역이다 [A13]. Qt `availableGeometry`의 macOS 구현이 이것이다 [Q20]. tkinter라면 pyobjc로 `NSScreen.screens()`를 읽어야 한다.

**관찰: 쇼가 뜬 모니터.** 이 PC에서 PowerPoint는 쇼를 **보조 모니터**에, 발표자 보기를 주 모니터에 띄웠다. 발표자 보기를 꺼도 쇼는 보조 모니터에 떴다. 요구사항의 "원 버튼 기본은 주 모니터"를 그대로 두면 프로젝터 화면이 아니라 노트북 화면에 원 버튼이 뜰 수 있다. 쇼 창이 있는 모니터를 고르는 선택지를 기획에서 정할 필요가 있다. 이 관찰은 PC 한 대에서만 본 것이다.

### 7. 애니메이션 부담

**시험 내용.** 테두리 없는 topmost 창 두 개를 8초 동안 그렸다(앞의 1초는 빼고 쟀다).
- 강아지: 96×96, 코드로 만든 점 그림 4프레임. 원을 따라 매 프레임 이동하고, 매 프레임 전역 커서를 읽는다.
- 원 버튼: 240×240, 퍼지는 링 3개.

CPU는 `time.process_time()`(프로세스 전체 스레드)을 실제 경과 시간으로 나눈 값이다. 한 코어가 100%다. 화면 합성(DWM) 비용은 들어가지 않는다.

| 구성 | 30fps 달성 | CPU | 60fps 달성 | CPU |
|---|---|---|---|---|
| tkinter 색 키 + Canvas(PhotoImage 교체, `coords`) | 30.1 | 11.3% (1ms 타이머 14.0%) | 60.2 | 30.6% (1ms 타이머 28.5%) |
| tkinter + `UpdateLayeredWindow`(Pillow 2배 슈퍼샘플링으로 매 프레임 그림) | 30.1 | 17.5% (20.2%) | 59.1 | 43.1% (42.5%) |
| PySide6 `QPainter`(안티에일리어싱) + `QTimer(PreciseTimer)` | 30.4 | 19.7% | 58.9 | 33.4% (첫 회 36.7%) |

- tkinter에서 `after(33)`/`after(16)`을 일한 뒤에 다시 예약하면 목표에 못 미쳤다. 각각 24.8fps, 39.6fps(색 키)였다. 다음 마감 시각을 기준으로 지연을 계산하자 목표 fps가 나왔다.
- ULW 방식의 비용은 대부분 매 프레임 Pillow로 원을 다시 그리는 데서 나온다. 평상시 파동처럼 반복되는 장면은 프레임을 미리 만들어 두면 줄일 수 있다(미측정). 말할 때 목소리를 반영하는 파동은 매 프레임 그려야 한다.
- 16 논리 코어 PC에서 43%는 전체의 약 2.7%다. 학교 PC처럼 느린 CPU에서는 측정하지 못했다.

### 8. 배포

**실측(Windows, PyInstaller 6.22.3, `--windowed`).**

| 빌드 | 크기 |
|---|---|
| tkinter 빈 창, onedir | 25MB |
| tkinter 빈 창, onefile | 12MB |
| 현재 `ppt_reader.spec`(python-pptx, lxml, Pillow, pywin32 포함), onedir | 51MB |
| PySide6 빈 창(QtWidgets), onedir | 101MB (가장 큰 파일 `opengl32sw.dll` 20.6MB, `Qt6Core.dll` 10.5MB, `Qt6Gui.dll` 9.7MB) |
| PySide6 빈 창, onefile | 40MB |

두 빈 창 실행 파일 모두 실행해 정상 종료를 확인했다. 현재 앱에 Qt를 더하면 약 75MB가 늘 것으로 추정한다(빈 창 차이). 실제 앱으로 빌드해 보지는 않았다.

**라이선스.**
- Tcl/Tk: 저작권 표시를 유지하면 어떤 목적으로든 사용·배포할 수 있는 BSD식 조건이다 [T16].
- PyInstaller: 만든 실행 파일은 "의존 패키지의 라이선스를 지키는 한" 원하는 라이선스로 배포할 수 있다 [P4].
- pyobjc: MIT [O1].
- PySide6: PyPI 표기는 `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`다 [Q22]. Qt for Python 문서는 LGPL 또는 상용 라이선스라고 한다 [Q7]. LGPLv3로 배포하려면 Qt 회사가 정리한 의무를 지켜야 한다 [Q8]:
  - LGPL 라이선스 문구와 사용 고지를 제공한다.
  - 수정하지 않았어도 Qt의 소스를 함께 주거나 서면 제안을 한다.
  - 사용자가 라이브러리를 바꿔 다시 링크할 수 있게 한다.
  - 역공학을 막지 않는다.
- PyInstaller onedir은 Qt DLL을 따로 된 파일로 두므로 교체 조건을 맞추기 쉽다. **실측에서 PyInstaller는 Qt·PySide6 라이선스 파일을 결과물에 넣어 주지 않았다.** 직접 넣어야 한다.

**지원 운영체제.**
- tkinter: python.org 3.14.7 설치본은 Windows용과 macOS용 모두 Tk 9.0.4를 담는다 [P1][P2]. macOS 설치본은 10.15 이상용이다 [P3].
- PySide6 6.12: macOS wheel의 태그가 `macosx_14_0`이라 macOS 14 미만에는 설치되지 않는다 [Q22]. Qt 6.12 지원 플랫폼은 macOS 14.4+, Windows 10(1809+)/11이다. "Qt 6.12가 Windows 10을 지원하는 마지막 버전"이라고 적혀 있다 [Q6]. 학교 PC의 운영체제 버전에 따라 제약이 된다.

## 권장안이 뜻하는 구성(참고)

이 조사에서 실측한 조합만 적는다.

- **강아지 창**(Windows): Tk overrideredirect + topmost. 그림은 알파가 0/255뿐인 점 그림이라 색 키로도 되고, `UpdateLayeredWindow`도 된다. 확장 스타일 `WS_EX_LAYERED|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE`로 클릭을 통과시킨다. 매 프레임 커서를 읽어 오른쪽 아래로 옮긴다.
- **원 버튼·위성 버튼**(Windows): Pillow로 그린 RGBA를 `UpdateLayeredWindow`로 올린다. `WS_EX_NOACTIVATE`를 준다. 투명한 구석은 클릭이 통과한다. 버튼 판정은 클릭 좌표로 직접 계산한다(Tk 위젯을 쓰지 않음).
- **질문창**: 일반 Tk 창(Entry)을 쓴다. 열 때 포그라운드 창을 기억하고, 닫을 때 `SetForegroundWindow`로 돌려준다.
- **macOS**: 같은 구조로 하되 투명은 `-transparent`, 클릭 통과는 `MacWindowStyle … ignoreClicks`, 전체 화면 Space는 pyobjc `canJoinAllApplications`를 쓴다. 모두 미실행이며 Mac 시제품에서 확인해야 한다.

## 확인하지 못한 것

- macOS의 모든 항목(실행 환경 없음). 특히 다음이 미확인이다.
  - 다른 앱(PowerPoint for Mac)의 전체 화면 슬라이드 쇼 위에 창이 보이는가. `canJoinAllApplications`만으로 되는가, 에이전트 앱(`LSUIElement`)도 필요한가.
  - PowerPoint for Mac 슬라이드 쇼가 별도 전체 화면 Space를 쓰는가.
  - Tk `-transparent` 창에서 PhotoImage의 반투명 픽셀이 바르게 합성되는가. Tk 캔버스가 안티에일리어싱으로 그리는가.
  - 쇼를 활성으로 둔 채 질문창(Tk 패널, Qt Tool + nonactivating)이 키 입력을 받는가.
  - Tk 창의 NSWindow를 파이썬에서 얻는 방법(`Tk_MacOSXGetNSWindowForDrawable`를 ctypes로 부르기, `NSApp.windows()`로 찾기).
  - `NSEvent.mouseLocation` 폴링에 권한 창이 뜨는가.
  - macOS의 CPU 사용량과 PyInstaller `.app` 크기.
- Windows 10에서의 동작(이 PC는 Windows 11).
- 느린 학교 PC에서의 CPU 사용량. DWM(화면 합성) 쪽 비용.
- 다른 topmost 창(알림, 다른 앱)이 나중에 뜰 때 우리 창이 그 아래로 내려가는지, topmost를 주기적으로 다시 걸어야 하는지.
- per-monitor v2 DPI에서 Tk 위젯(설정 화면 등)의 글자·크기가 모니터마다 바르게 바뀌는지.
- 실제 앱에 PySide6를 넣었을 때의 크기(빈 창 차이로만 추정).
- 같은 Tk 프로세스 안에서 색 키 창 두 개가 겹칠 때의 클릭 전달. 한 프로세스 시험에서 불투명한 곳의 클릭이 아래 창으로 간 결과가 나왔다. 그러나 시험 중 실제 마우스가 함께 움직여 결과를 믿을 수 없다. 두 프로세스로 한 시험은 정상이었다.
- Homebrew Python의 tkinter가 어떤 Tk 버전을 쓰는지.

## 출처 목록

### Tcl/Tk, Python, PyInstaller
- [T1] Tk 9.0 `wm` 매뉴얼(`attributes`: `-alpha`, `-topmost`, `-transparentcolor`, `-transparent`, `-class`, `-stylemask`): https://www.tcl-lang.org/man/tcl9.0/TkCmd/wm.html , 같은 내용의 소스: https://github.com/tcltk/tk/blob/core-9-0-4/doc/wm.n#L46-L205
- [T2] Tk 9.0 `winfo` 매뉴얼(`pointerxy`, `screenwidth`, `vrootwidth`): https://www.tcl-lang.org/man/tcl9.0/TkCmd/winfo.html
- [T3] Tk 소스 `tkWinWm.c` overrideredirect 스타일(`WS_EX_TOOLWINDOW`): https://github.com/tcltk/tk/blob/core-9-0-4/win/tkWinWm.c#L294-L297
- [T4] Tk 소스 `tkWinWm.c` 첫 창 `SetActiveWindow`: https://github.com/tcltk/tk/blob/core-9-0-4/win/tkWinWm.c#L2196-L2209
- [T5] Tk 소스 `tkWinWm.c` `-alpha`/`-transparentcolor`(`SetLayeredWindowAttributes`)와 `-topmost`(`HWND_TOPMOST`): https://github.com/tcltk/tk/blob/core-9-0-4/win/tkWinWm.c#L3140-L3192
- [T6] Tk 소스 `tkWinWm.c` `WM_MOUSEACTIVATE` 처리: https://github.com/tcltk/tk/blob/core-9-0-4/win/tkWinWm.c#L7984-L8006
- [T7] Tk 소스 `tkWinPointer.c` `TkGetPointerCoords`(`GetCursorPos`): https://github.com/tcltk/tk/blob/core-9-0-4/win/tkWinPointer.c#L291-L301
- [T8] Tk 소스 `tkMacOSXWm.c` `canBecomeKeyWindow`(TKWindow 전용): https://github.com/tcltk/tk/blob/core-9-0-4/macosx/tkMacOSXWm.c#L595-L643
- [T9] Tk 소스 `tkMacOSXWm.c` overrideredirect → `kWindowNoActivatesAttribute`: https://github.com/tcltk/tk/blob/core-9-0-4/macosx/tkMacOSXWm.c#L7666-L7695
- [T10] Tk 소스 `tkMacOSXWm.c` `ignoreClicks`→`setIgnoresMouseEvents`, `collectionBehavior`, `-topmost`→`kCGUtilityWindowLevel`: https://github.com/tcltk/tk/blob/core-9-0-4/macosx/tkMacOSXWm.c#L7554-L7622
- [T11] Tk 소스 `tkMacOSXWm.c` `::tk::unsupported::MacWindowStyle` 속성표(`noActivates`, `ignoreClicks`, `nonActivating`): https://github.com/tcltk/tk/blob/core-9-0-4/macosx/tkMacOSXWm.c#L6449-L6481
- [T12] Tk 소스 `tkMacOSXWm.c` `-transparent`(`clearColor`, `setOpaque:`): https://github.com/tcltk/tk/blob/core-9-0-4/macosx/tkMacOSXWm.c#L1970-L1991
- [T13] Tk 소스 `tkMacOSXWm.c` `-class nspanel`(NSPanel, `NSWindowStyleMaskNonactivatingPanel`): https://github.com/tcltk/tk/blob/core-9-0-4/macosx/tkMacOSXWm.c#L6784-L6797
- [T14] Tk 소스 `tkMacOSXMouseEvent.c` `XQueryPointer`(`[NSEvent mouseLocation]`): https://github.com/tcltk/tk/blob/core-9-0-4/macosx/tkMacOSXMouseEvent.c#L637-L675
- [T15] Tk 공개 C API `Tk_MacOSXGetNSWindowForDrawable`: https://github.com/tcltk/tk/blob/core-9-0-4/generic/tkPlatDecls.h#L72
- [T16] Tcl/Tk 라이선스: https://www.tcl-lang.org/software/tcltk/license.html
- [P1] CPython 3.14.7 Windows 빌드 의존성(Tcl/Tk 9.0.4): https://github.com/python/cpython/blob/v3.14.7/PCbuild/get_externals.bat#L57-L83
- [P2] CPython 3.14.7 macOS 설치본 빌드 스크립트(Tcl/Tk 9.0.4): https://github.com/python/cpython/blob/v3.14.7/Mac/BuildScript/build-installer.py#L258-L268
- [P3] Python 3.14.7 배포 페이지(macOS 설치본 "for macOS 10.15 and later"): https://www.python.org/downloads/release/python-3147/
- [P4] PyInstaller 라이선스: https://pyinstaller.org/en/stable/license.html
- 참고: GitHub의 `tcltk/tk`는 공식 fossil 저장소(https://core.tcl-lang.org/tk)의 미러다.

### Microsoft Win32
- [M1] Window Features — Layered Windows(히트 테스트, `WS_EX_TRANSPARENT`, `UpdateLayeredWindow`와 `SetLayeredWindowAttributes`): https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features#layered-windows
- [M2] Window Features — Z-Order(topmost 창): https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features#z-order
- [M3] Extended Window Styles(`WS_EX_NOACTIVATE`, `WS_EX_TRANSPARENT`, `WS_EX_LAYERED`, `WS_EX_TOPMOST`): https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles
- [M4] UpdateLayeredWindow: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-updatelayeredwindow
- [M5] SetForegroundWindow(포그라운드 변경 조건): https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow
- [M6] GetCursorPos: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getcursorpos
- [M7] EnumDisplayMonitors: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumdisplaymonitors
- [M8] MONITORINFO(`rcWork`): https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-monitorinfo
- [M9] SetProcessDpiAwarenessContext: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setprocessdpiawarenesscontext
- [M10] SetWindowPos(`HWND_TOPMOST`): https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos

### Apple AppKit
- [A1] NSWindow.level: https://developer.apple.com/documentation/appkit/nswindow/level-swift.property
- [A2] NSWindow.Level: https://developer.apple.com/documentation/appkit/nswindow/level-swift.struct
- [A3] NSWindow.collectionBehavior: https://developer.apple.com/documentation/appkit/nswindow/collectionbehavior-swift.property
- [A4] canJoinAllSpaces: https://developer.apple.com/documentation/appkit/nswindow/collectionbehavior-swift.struct/canjoinallspaces
- [A5] fullScreenAuxiliary: https://developer.apple.com/documentation/appkit/nswindow/collectionbehavior-swift.struct/fullscreenauxiliary
- [A6] canJoinAllApplications(macOS 13+): https://developer.apple.com/documentation/appkit/nswindow/collectionbehavior-swift.struct/canjoinallapplications
- [A7] ignoresMouseEvents: https://developer.apple.com/documentation/appkit/nswindow/ignoresmouseevents
- [A8] StyleMask.nonactivatingPanel: https://developer.apple.com/documentation/appkit/nswindow/stylemask-swift.struct/nonactivatingpanel
- [A9] NSPanel.becomesKeyOnlyIfNeeded: https://developer.apple.com/documentation/appkit/nspanel/becomeskeyonlyifneeded
- [A10] NSWindow.canBecomeKey: https://developer.apple.com/documentation/appkit/nswindow/canbecomekey
- [A11] NSWindow.hidesOnDeactivate(NSPanel 기본 true): https://developer.apple.com/documentation/appkit/nswindow/hidesondeactivate
- [A12] NSEvent.mouseLocation: https://developer.apple.com/documentation/appkit/nsevent/mouselocation
- [A13] NSScreen.visibleFrame: https://developer.apple.com/documentation/appkit/nsscreen/visibleframe
- [A14] NSApplication.ActivationPolicy.accessory: https://developer.apple.com/documentation/appkit/nsapplication/activationpolicy-swift.enum/accessory
- [A15] LSUIElement: https://developer.apple.com/documentation/bundleresources/information-property-list/lsuielement

### Qt / PySide6
- [Q1] Qt::WindowType(`WindowStaysOnTopHint`, `WindowTransparentForInput`, `WindowDoesNotAcceptFocus`, `FramelessWindowHint`, `Tool`): https://doc.qt.io/qt-6/qt.html#WindowType-enum
- [Q2] Qt::WidgetAttribute(`WA_TranslucentBackground`, `WA_ShowWithoutActivating`, `WA_MacAlwaysShowToolWindow`): https://doc.qt.io/qt-6/qt.html#WidgetAttribute-enum
- [Q3] QWidget — Creating Translucent Windows: https://doc.qt.io/qt-6/qwidget.html#creating-translucent-windows
- [Q4] QCursor::pos: https://doc.qt.io/qt-6/qcursor.html#pos
- [Q5] QScreen(`availableGeometry`, `name`): https://doc.qt.io/qt-6/qscreen.html#availableGeometry-prop
- [Q6] Qt 6.12 Supported Platforms: https://doc.qt.io/qt-6/supported-platforms.html
- [Q7] Qt for Python — Licenses: https://doc.qt.io/qtforpython-6/licenses.html
- [Q8] Qt — Obligations of the LGPL: https://www.qt.io/licensing/open-source-lgpl-obligations
- [Q9] qtbase 소스 `qwindowswindow.cpp` 레이어드 창과 `UpdateLayeredWindow`: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/windows/qwindowswindow.cpp#L491-L524
- [Q10] qtbase 소스 `qwindowswindow.cpp` `WS_EX_NOACTIVATE`/`WS_EX_TRANSPARENT`: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/windows/qwindowswindow.cpp#L814-L855
- [Q11] qtbase 소스 `qwindowswindow.cpp` `SW_SHOWNOACTIVATE`: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/windows/qwindowswindow.cpp#L2030-L2036
- [Q12] qtbase 소스 `qcocoawindow.mm` `windowLevel`: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/cocoa/qcocoawindow.mm#L632-L682
- [Q13] qtbase 소스 `qcocoawindow.mm` `collectionBehavior`와 `ignoresMouseEvents`: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/cocoa/qcocoawindow.mm#L833-L870
- [Q14] qtbase 소스 `qcocoawindow.mm` NSPanel을 쓰는 창 종류: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/cocoa/qcocoawindow.mm#L1853-L1859
- [Q15] qtbase 소스 `qcocoawindow.mm` Tool 창 `hidesOnDeactivate`, NSPanel `collectionBehavior`: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/cocoa/qcocoawindow.mm#L2074-L2084
- [Q16] qtbase 소스 `qcocoawindow.mm` `shouldRefuseKeyWindowAndFirstResponder`: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/cocoa/qcocoawindow.mm#L2205-L2212
- [Q17] qtbase 소스 `qnswindow.mm` `canBecomeKeyWindow`: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/cocoa/qnswindow.mm#L258-L278
- [Q18] qtbase 소스 `qcocoawindow.mm` `winId()` = NSView: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/cocoa/qcocoawindow.mm#L1341-L1344
- [Q19] qtbase 소스 `qcocoacursor.mm` `pos()`: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/cocoa/qcocoacursor.mm#L52-L55
- [Q20] qtbase 소스 `qcocoascreen.mm` `visibleFrame`: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/cocoa/qcocoascreen.mm#L230
- [Q21] qtbase 소스 `qwindowsscreen.cpp` `rcWork`: https://github.com/qt/qtbase/blob/v6.12.0/src/plugins/platforms/windows/qwindowsscreen.cpp#L469
- [Q22] PyPI PySide6-Essentials 6.12.0(라이선스 표기, wheel 목록 `macosx_14_0`): https://pypi.org/project/PySide6-Essentials/6.12.0/#files
- 참고: GitHub의 `qt/qtbase`는 공식 Qt 저장소(https://code.qt.io)의 미러다.

### 기타
- [O1] pyobjc-framework-Cocoa(PyPI, MIT, 12.2.2): https://pypi.org/project/pyobjc-framework-Cocoa/
