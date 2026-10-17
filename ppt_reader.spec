# PyInstaller 빌드 설정. 운영체제마다 그 운영체제에서 빌드한다(macOS판은 빌드 서버의 macos-15 러너).
#   pip install -r requirements-dev.txt
#   pyinstaller --noconfirm ppt_reader.spec
# 결과: Windows -> dist/PPTReader/PPTReader.exe,  macOS -> dist/PPTReader.app
# onedir를 유지한다. Qt와 FFmpeg가 따로 된 라이브러리로 남아야 사용자가 바꿔 끼울 수 있다(LGPL).
import sys

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ["main.py"],
    datas=collect_data_files("pptx") + [("ppt_reader/assets/*.png", "ppt_reader/assets"), ("licenses/*", "licenses")],
    hiddenimports=["win32timezone"] if sys.platform == "win32" else [],
    excludes=["tkinter"],
)

# PySide6-Addons의 가상 키보드 입력 플러그인은 쓰지 않는다. 그것이 끌고 오는 Qt Quick·QML까지 빼면 약 16MB 준다.
_UNUSED = ("qtvirtualkeyboard", "qt6virtualkeyboard", "qt6quick", "qt6qml", "qtquick", "qtqml")


def _used(entry):
    name = entry[0].replace("\\", "/").lower()
    return not any(part in name for part in _UNUSED)


a.binaries = [b for b in a.binaries if _used(b)]
a.datas = [d for d in a.datas if _used(d)]

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PPTReader", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="PPTReader")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="PPTReader.app",
        bundle_identifier="local.pptreader",
        info_plist={
            "CFBundleDisplayName": "PPT 읽어주기",
            "NSHighResolutionCapable": True,
            # PowerPoint 연동(AppleScript)을 쓰려면 이 문구가 있어야 macOS가 권한을 물어본다.
            "NSAppleEventsUsageDescription": "PowerPoint에서 지금 보이는 슬라이드를 알아내고 넘기기 위해 필요합니다.",
        },
    )
