"""앱 아이콘 파일 생성기. ppt_reader/ui/icon.py의 원 버튼 그림으로 실행 파일 아이콘을 만든다.

    python tools/make_icon.py

ppt_reader/assets/app.ico(Windows)와 app.icns(macOS)를 만들고, 빌드(ppt_reader.spec)가 이 파일을 쓴다.
두 파일 모두 크기마다 따로 그린 PNG를 담는다. Windows Vista와 macOS 10.7부터 이 방식을 읽는다.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from ppt_reader.ui import icon  # noqa: E402

OUT = ROOT / "ppt_reader" / "assets"
ICO_SIZES = icon.SIZES
# macOS 아이콘 칸과 픽셀 크기. ic11~ic14는 레티나(@2x) 칸이다
ICNS_TYPES = ((b"ic11", 32), (b"ic12", 64), (b"ic07", 128), (b"ic13", 256), (b"ic08", 256),
              (b"ic14", 512), (b"ic09", 512), (b"ic10", 1024))


def png(size: int) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    icon.image(size).save(buf, "PNG")
    buf.close()
    return bytes(data)


def ico_bytes() -> bytes:
    images = [png(s) for s in ICO_SIZES]
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = len(head) + 16 * len(images)
    entries = b""
    for s, data in zip(ICO_SIZES, images):
        # 너비·높이 칸은 1바이트라 256은 0으로 적는다
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return head + entries + b"".join(images)


def icns_bytes() -> bytes:
    images = {s: png(s) for s in sorted({s for _, s in ICNS_TYPES})}
    body = b"".join(kind + struct.pack(">I", 8 + len(images[s])) + images[s] for kind, s in ICNS_TYPES)
    return b"icns" + struct.pack(">I", 8 + len(body)) + body


def main():
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in (("app.ico", ico_bytes()), ("app.icns", icns_bytes())):
        path = OUT / name
        path.write_bytes(data)
        print(f"만듦: {path} ({len(data):,}바이트)")


if __name__ == "__main__":
    main()
