# PyInstaller 빌드 설정.  각 운영체제에서 직접 빌드해야 한다(Windows용은 Windows에서, Mac용은 Mac에서).
#   pip install pyinstaller
#   pyinstaller ppt_reader.spec
# 결과: Windows -> dist/PPTReader/PPTReader.exe,  macOS -> dist/PPTReader.app
import sys

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ["main.py"],
    datas=collect_data_files("pptx"),
    hiddenimports=["win32timezone"] if sys.platform == "win32" else [],
)
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
