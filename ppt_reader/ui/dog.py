"""강아지 창. 스프라이트 시트(64px 격자)를 ×2로 픽셀 그대로 키워 그린다. 클릭은 아래로 통과한다."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QPainter, QPixmap

from .overlay import OverlayWindow

ASSETS = Path(__file__).resolve().parent.parent / "assets"
CELL = 64
SCALE = 2
SIZE = CELL * SCALE
FRAMES = 4
FEET_Y = 118  # 창 안에서 발바닥이 닿는 높이(px). 원본 59줄 × 2
# 자세: (시트의 줄, 초당 프레임). 말하기는 시간이 아니라 입 모양(0~3)으로 프레임을 고른다.
POSES = {"lie": (0, 3), "walk": (1, 8), "sit": (2, 4), "think": (3, 3), "talk": (4, 0), "happy": (5, 8)}
SWEAT_ROW = 6
SWEAT_FPS = 4


def load_sheet(dog: str) -> list[list[QPixmap]]:
    sheet = QPixmap(str(ASSETS / f"dog_{dog}.png"))
    if sheet.isNull():
        raise FileNotFoundError(ASSETS / f"dog_{dog}.png")
    return [[sheet.copy(c * CELL, r * CELL, CELL, CELL) for c in range(FRAMES)] for r in range(SWEAT_ROW + 1)]


class DogWindow(OverlayWindow):
    def __init__(self, dog: str = "shiba"):
        super().__init__(click_through=True)
        self.resize(SIZE, SIZE)
        self.frames = load_sheet(dog)
        self.pose = "sit"
        self.mouth = 0  # 말하기 자세의 입 모양: 0 닫힘, 1 조금, 2 크게, 3 가로
        self.sweat = False
        self.facing_left = False
        self._t = 0.0
        self._shown: tuple | None = None

    def set_dog(self, dog: str) -> None:
        self.frames = load_sheet(dog)
        self._shown = None
        self.update()

    def set_pose(self, pose: str) -> None:
        if pose != self.pose:
            self.pose = pose
            self._t = 0.0

    def _cell(self) -> tuple[int, int, int]:
        row, fps = POSES[self.pose]
        frame = self.mouth if self.pose == "talk" else int(self._t * fps) % FRAMES
        sweat = int(self._t * SWEAT_FPS) % FRAMES if self.sweat and self.pose == "talk" else -1
        return row, frame, sweat

    def tick(self, dt: float) -> None:
        self._t += dt
        shown = (*self._cell(), self.facing_left)
        if shown != self._shown:  # 바뀐 프레임만 다시 그린다
            self._shown = shown
            self.update()

    def paintEvent(self, _event):
        row, frame, sweat = self._cell()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)  # 도트를 흐리지 않게
        if self.facing_left:
            p.translate(SIZE, 0)
            p.scale(-1, 1)
        target = QRect(0, 0, SIZE, SIZE)
        p.drawPixmap(target, self.frames[row][frame])
        if sweat >= 0:
            p.drawPixmap(target, self.frames[SWEAT_ROW][sweat])
        p.end()
