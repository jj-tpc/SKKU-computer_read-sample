"""강아지 따라가기 계산. 순수 함수라 화면 없이 시험한다.

자리는 강아지 창(128px)의 왼쪽 위 꼭짓점이다. 스프라이트 위쪽에 여백이 있어서, 커서 끝에서 오른쪽 12px·아래 8px에
창을 두면 커서 화살표를 가리지 않는다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

DOG = 128  # 강아지 창 크기(논리 px)
OFFSET_X, OFFSET_Y = 12, 8
SPEED = 260.0  # 초당 px. 여기에 거리 × PULL을 더해 멀면 빨리 오고 가까우면 부드럽게 멈춘다
PULL = 4.0
MOVE_EPS = 2.0  # 남은 거리가 이보다 크면 움직이는 중
TURN_EPS = 1.5  # 가로로 이보다 크게 움직일 때만 방향을 바꾼다
LIE_AFTER = 4.0  # 커서가 이만큼 넘게 가만히 있으면 엎드린다
WAIT_FROM_ORB = 300  # 원 버튼 중심에서 기다리는 자리(창 왼쪽)까지. 위성 버튼 호 바깥이다
FEET_Y = 118  # 창 안에서 발바닥이 닿는 높이


@dataclass(frozen=True)
class Area:
    """모니터 작업 영역(작업 표시줄·Dock 제외). 논리 px."""
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.right and self.y <= py < self.bottom


def clamp_into(x: float, y: float, area: Area, w: int = DOG, h: int = DOG) -> tuple[float, float]:
    return (min(max(x, area.x), area.right - w), min(max(y, area.y), area.bottom - h))


def target_for(cursor: tuple[float, float], area: Area) -> tuple[float, float]:
    """커서 오른쪽 아래. 오른쪽에 자리가 없으면 커서 왼쪽, 아래에 자리가 없으면 커서 위."""
    cx, cy = cursor
    x = cx + OFFSET_X
    if x + DOG > area.right:
        x = cx - OFFSET_X - DOG
    y = cy + OFFSET_Y
    if y + DOG > area.bottom:
        y = cy - OFFSET_Y - DOG
    return clamp_into(x, y, area)


def wait_spot(orb_center: tuple[float, float], area: Area) -> tuple[float, float]:
    """원 버튼 왼쪽 옆, 발을 원 버튼 아래 끝에 맞춘 자리."""
    ox, oy = orb_center
    return clamp_into(ox - WAIT_FROM_ORB, oy + 28 - FEET_Y, area)


def step(pos: tuple[float, float], target: tuple[float, float], dt: float) -> tuple[tuple[float, float], bool]:
    """한 프레임에 min(거리, 260 × dt + 거리 × 4 × dt)만큼 다가간다. (새 자리, 움직이는 중인가)."""
    dx, dy = target[0] - pos[0], target[1] - pos[1]
    dist = math.hypot(dx, dy)
    if dist <= MOVE_EPS:
        return pos, False
    s = min(dist, SPEED * dt + dist * PULL * dt)
    return (pos[0] + dx / dist * s, pos[1] + dy / dist * s), True


class Follower:
    """강아지의 자리, 방향, 기본 자세(걷기·앉기·엎드림)를 정한다. 말하기·생각·기쁨은 화면 쪽이 얹는다."""

    def __init__(self, pos: tuple[float, float] = (0.0, 0.0)):
        self.pos = pos
        self.facing_left = False
        self.moving = False
        self._cursor: tuple[float, float] | None = None
        self._still_since = 0.0

    def update(self, now: float, dt: float, cursor: tuple[float, float], area: Area,
               orb_center: tuple[float, float], over_orb: bool, stay: bool) -> str:
        """stay: 질의응답 중(그 자리에 머묾). over_orb: 커서가 원 버튼 묶음 위. 기본 자세를 돌려준다."""
        if cursor != self._cursor:
            self._cursor = cursor
            self._still_since = now
        if stay:
            target = self.pos
        elif over_orb or not area.contains(*cursor):
            target = wait_spot(orb_center, area)  # 원 버튼을 누르는 중이거나 커서가 다른 모니터에 있다
        else:
            target = target_for(cursor, area)
        dx = target[0] - self.pos[0]
        self.pos, self.moving = step(self.pos, target, dt)
        if self.moving and abs(dx) > TURN_EPS:
            self.facing_left = dx < 0
        if self.moving:
            return "walk"
        return "lie" if now - self._still_since > LIE_AFTER else "sit"
