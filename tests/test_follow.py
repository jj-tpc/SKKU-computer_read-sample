"""강아지 따라가기 계산 시험."""
from __future__ import annotations

import pytest

from ppt_reader.follow import DOG, Area, Follower, step, target_for, wait_spot

AREA = Area(0, 0, 1000, 800)
ORB = (944, 744)


def test_speed_formula():
    pos, moving = step((0, 0), (100, 0), 0.1)
    assert moving and pos == pytest.approx((66, 0))  # min(100, 260×0.1 + 100×4×0.1)
    pos, moving = step((0, 0), (1000, 0), 0.01)
    assert pos == pytest.approx((42.6, 0))  # 2.6 + 1000×4×0.01: 멀면 거리 비례 몫이 커서 빨리 온다
    assert step((0, 0), (1.5, 0), 0.1) == ((0, 0), False)  # 2px 안이면 멈춤


def test_target_beside_cursor_and_edges():
    assert target_for((100, 100), AREA) == (112, 108)  # 커서 오른쪽 아래
    assert target_for((950, 100), AREA) == (950 - 12 - DOG, 108)  # 오른쪽에 자리가 없으면 왼쪽
    assert target_for((100, 750), AREA) == (112, 750 - 8 - DOG)  # 아래에 자리가 없으면 위
    assert target_for((950, 780), AREA) == (950 - 12 - DOG, 780 - 8 - DOG)  # 오른쪽 아래 구석
    assert target_for((1810, 5), Area(1000, 0, 800, 600)) == (1810 - 12 - DOG, 13)  # 다른 모니터 좌표에서도


def run(f, seconds, cursor, over_orb=False, stay=False, area=AREA, start=0.0):
    t = start
    pose = ""
    while t < start + seconds:
        t += 1 / 30
        pose = f.update(t, 1 / 30, cursor, area, ORB, over_orb, stay)
    return pose, t


def test_walks_then_sits_then_lies():
    f = Follower((500, 400))
    assert f.update(0.0, 1 / 30, (100, 100), AREA, ORB, False, False) == "walk"
    assert f.facing_left  # 커서 쪽(왼쪽)으로 돈다
    pose, t = run(f, 2.0, (100, 100), start=0.0)
    assert pose == "sit" and f.pos == pytest.approx((112, 108), abs=2)
    pose, _ = run(f, 2.5, (100, 100), start=t)
    assert pose == "lie"  # 커서가 4초 넘게 가만히 있으면 엎드린다


def test_waits_beside_orb():
    spot = wait_spot(ORB, AREA)
    assert spot == (ORB[0] - 300, ORB[1] + 28 - 118)
    f = Follower((100, 100))
    run(f, 3.0, (1500, 300))  # 커서가 다른 모니터에 있다
    assert f.pos == pytest.approx(spot, abs=2)
    f = Follower((100, 100))
    run(f, 3.0, ORB, over_orb=True)  # 원 버튼을 누르는 중
    assert f.pos == pytest.approx(spot, abs=2)


def test_stays_during_qa():
    f = Follower((300, 300))
    pose, _ = run(f, 1.0, (100, 100), stay=True)
    assert f.pos == (300, 300) and pose == "sit"
