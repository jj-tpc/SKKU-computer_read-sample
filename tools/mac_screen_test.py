"""macOS 빌드 서버(GitHub Actions macos-15)용 화면 시험. Mac 없이 "전체 화면 쇼 위에 보이는가"를 본다.

    python tools/mac_screen_test.py run dist/Slidog.app shots

1. pyobjc로 만든 가짜 쇼 앱을 자기 전체 화면 Space에 띄운다.
2. 그 위에 빌드한 앱을 켜고, cliclick으로 커서를 옮기고 원 버튼을 누르며 screencapture로 찍는다.
3. 찍은 사진에서 원 버튼(코랄)이 보이는지, 원 버튼을 눌러도 쇼가 맨 앞 앱으로 남는지 판정한다.
사진은 산출물로 올려 사람이 본다. 실제 PowerPoint 쇼와 레티나 화면은 받는 사람 확인표로 본다.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOW_RGB = (28, 112, 168)  # 가짜 쇼 바탕색
CORAL_RGB = (255, 111, 97)
SHIBA_RGB = (233, 161, 79)
ESC_TRIES = 5  # cliclick의 Esc는 세 번째에 닿은 적도, 세 번 모두 안 닿은 적도 있다(앱은 같은 판)


def fake_show() -> None:
    """가짜 쇼: 제목 막대가 있는 보통 창을 전체 화면으로 바꾼다."""
    from AppKit import NSApplication, NSColor, NSMakeRect, NSWindow
    from PyObjCTools import AppHelper

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(0)  # regular: Dock 아이콘이 있는 보통 앱
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(80, 80, 800, 600), 1 | 2 | 4 | 8, 2, False)  # titled, closable, miniaturizable, resizable
    win.setTitle_("Fake Show")
    win.setBackgroundColor_(NSColor.colorWithSRGBRed_green_blue_alpha_(*(c / 255 for c in SHOW_RGB), 1.0))
    win.setCollectionBehavior_(1 << 7)  # FullScreenPrimary
    win.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
    AppHelper.callLater(1.0, win.toggleFullScreen_, None)
    AppHelper.runEventLoop()


def frontmost() -> str:
    try:
        asn = subprocess.run(["lsappinfo", "front"], capture_output=True, text=True, timeout=10).stdout.strip()
        out = subprocess.run(["lsappinfo", "info", "-only", "name", asn], capture_output=True, text=True,
                             timeout=10).stdout
        return out.split("=", 1)[-1].strip().strip('"') or "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def shot(out: Path, name: str) -> Path:
    path = out / f"{name}.png"
    subprocess.run(["screencapture", "-x", str(path)], check=True, timeout=30)
    return path


def screen_scale() -> float:
    from AppKit import NSScreen

    return float(NSScreen.mainScreen().backingScaleFactor())


def find_color(path: Path, rgb, box=(2 / 3, 2 / 3, 1, 1), tol: int = 40):
    """사진의 한 구역(가로·세로 비율)에서 그 색 픽셀들의 가운데(픽셀 좌표)와 개수. 못 찾으면 (None, 0)."""
    from PIL import Image

    im = Image.open(path).convert("RGB")
    w, h = im.size
    box = (int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h))
    xs = ys = n = 0
    px = im.load()
    for y in range(box[1], box[3], 2):
        for x in range(box[0], box[2], 2):
            r, g, b = px[x, y]
            if abs(r - rgb[0]) < tol and abs(g - rgb[1]) < tol and abs(b - rgb[2]) < tol:
                xs, ys, n = xs + x, ys + y, n + 1
    return ((xs / n, ys / n), n) if n else (None, 0)


def question_open(path: Path, orb_px: tuple[float, float], scale: float) -> bool:
    """질문창(흰 알약)이 보이는가. 원 버튼 중심 높이에서, 위성 버튼보다 왼쪽인 띠의 흰 픽셀을 센다."""
    from PIL import Image

    im = Image.open(path).convert("RGB")
    px = im.load()
    y = int(orb_px[1])
    x0, x1 = int(orb_px[0] - 400 * scale), int(orb_px[0] - 170 * scale)
    white = sum(1 for x in range(max(0, x0), max(0, x1), 2) for dy in (-8, 0, 8)
                if all(c > 235 for c in px[x, y + int(dy * scale)]))
    return white > 40


def esc_lines(out: Path) -> int:
    """앱 로그(PPT_READER_TRACE)에서 앱이 Esc를 받았다는 줄의 수."""
    try:
        text = (out / "app_stderr.txt").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if "esc monitor" in line or "] esc " in line)


def cliclick(*commands: str) -> None:
    subprocess.run(["cliclick", *commands], check=True, timeout=30)


def run(app_path: str, out_dir: str) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    log = []

    def note(line: str) -> None:
        print(line, flush=True)
        log.append(line)

    show = subprocess.Popen([sys.executable, __file__, "fake-show"])
    time.sleep(5)  # 전체 화면으로 바뀌는 움직임이 끝날 때까지
    shot(out, "00_fake_show")
    show_front = frontmost()
    note(f"가짜 쇼 맨 앞 앱: {show_front}")

    exe = Path(app_path) / "Contents" / "MacOS" / Path(app_path).stem
    home = Path(tempfile.mkdtemp(prefix="ppt_home_"))
    # 쇼 중에 쓰는 모습을 본다: 처음 켬 설정 창이 뜨지 않게 한다
    (home / "settings.json").write_text('{"first_run_done": true}', encoding="utf-8")
    env = dict(os.environ, PPT_READER_HOME=str(home), PPT_READER_TRACE="1")
    app_log = open(out / "app_stderr.txt", "w", encoding="utf-8")
    app = subprocess.Popen([str(exe), str(ROOT / "sample" / "sample_presentation.pptx")], env=env,
                           stdout=app_log, stderr=subprocess.STDOUT)
    ok = True
    try:
        time.sleep(6)
        first = shot(out, "01_app_over_show")
        scale = screen_scale()
        orb, n = find_color(first, CORAL_RGB)
        corner, _ = find_color(first, SHOW_RGB, (0, 0, 0.2, 0.2), tol=12)
        note(f"화면 배율 {scale}, 쇼 바탕 보임 {corner is not None}, 원 버튼 코랄 픽셀 {n}개")
        if orb is None:
            note("FAIL 원 버튼이 전체 화면 쇼 위에 보이지 않음")
            return 1
        x, y = round(orb[0] / scale), round(orb[1] / scale)
        note(f"OK   원 버튼이 쇼 위에 보임 (중심 약 {x},{y})")

        for i, (dx, dy) in enumerate([(-400, -300), (-200, -100), (-600, -50)]):
            cliclick(f"m:{x + dx},{y + dy}")
            time.sleep(1)
            shot(out, f"02_cursor_{i}")
        # 시바 털색은 코랄 그라데이션의 밝은 쪽과 가까워서, 원 버튼 둘레를 빼고 좁은 허용 범위로 찾는다
        from PIL import Image

        width = Image.open(first).size[0]
        dog_at, dog_n = find_color(out / "02_cursor_2.png", SHIBA_RGB, (0, 0.4, (orb[0] - 90 * scale) / width, 1), tol=16)
        note(f"{'OK  ' if dog_at else 'WARN'} 강아지(시바 털색) 픽셀 {dog_n}개")

        cliclick(f"c:{x},{y}")  # 원 버튼 누르기: 위성 버튼이 펼쳐진다
        time.sleep(1)
        shot(out, "03_satellites")
        after = frontmost()
        keeps = after == show_front
        note(f"{'OK  ' if keeps else 'FAIL'} 원 버튼을 누른 뒤 맨 앞 앱: {after} (쇼: {show_front})")
        ok = ok and keeps
        cliclick(f"m:{x - 200},{y - 300}")
        time.sleep(5)  # 위성 버튼이 4초 뒤 접히는지
        shot(out, "04_collapsed")

        # 두 번째 누르기: 빌드 서버에서 이때 이 앱이 활성이 됐었다. 앱이 쇼에 돌려줘야 한다
        cliclick(f"c:{x},{y}")
        time.sleep(1)
        again = frontmost()
        keeps = again == show_front
        note(f"{'OK  ' if keeps else 'FAIL'} 원 버튼을 다시 누른 뒤 맨 앞 앱: {again} (쇼: {show_front})")
        ok = ok and keeps

        # 질문창: 글을 받고, Esc로 닫히면 쇼가 다시 맨 앞 앱이 되어야 한다
        cliclick(f"c:{x - 132},{y}")  # 위성 버튼 1번 [질문하기]
        time.sleep(1)
        cliclick("t:hello")
        time.sleep(1)
        shot(out, "05_question_typed")
        typed_front = frontmost()
        note(f"INFO 질문창에 글을 치는 동안 맨 앞 앱: {typed_front}")
        # cliclick의 Esc가 앱에 닿지 않을 때가 있다(앱 로그에 Esc 줄이 없음). 그때만 다시 누른다
        closed_ok = False
        for attempt in range(1, ESC_TRIES + 1):
            seen = esc_lines(out)
            cliclick("kp:esc")
            time.sleep(1)
            if not question_open(shot(out, f"06_question_closed_{attempt}"), orb, scale):
                closed_ok = True
                break
            if esc_lines(out) > seen:
                note("FAIL 앱이 Esc를 받았는데 질문창이 남음")
                break
            note(f"INFO Esc {attempt}번째가 앱에 닿지 않음(빌드 서버의 입력 흉내), 다시 누름")
        note(f"{'OK  ' if closed_ok else 'FAIL'} Esc로 질문창이 {'닫힘' if closed_ok else '닫히지 않음'}")
        ok = ok and closed_ok
        closed_front = frontmost()
        back = closed_front == show_front
        note(f"{'OK  ' if back else 'FAIL'} 질문창을 닫은 뒤 맨 앞 앱: {closed_front} (쇼: {show_front})")
        ok = ok and back
    finally:
        app.terminate()
        show.terminate()
        app_log.close()
        (out / "result.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.argv[1:2] == ["fake-show"]:
        fake_show()
    elif sys.argv[1:2] == ["run"] and len(sys.argv) == 4:
        sys.exit(run(sys.argv[2], sys.argv[3]))
    else:
        print(__doc__)
        sys.exit(2)
