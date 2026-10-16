"""시제품 — 도트 강아지 스프라이트 생성기 (버려도 되는 코드, 제품에 들어가지 않는다).

질문: 캐릭터(붉은 목띠를 맨 도트 강아지)의 생김새, 자세 목록, 크기를 무엇으로 할까?
서로 다른 강아지 세 마리(A 치비 시바 / B 몽실 비숑 / C 날씬 비글)를 64×64로 그려
자세별 스프라이트 시트와 미리보기 HTML을 만든다.

    python tools/prototype_dog_sprites.py
    → tools/prototype_dog_out/preview.html 을 브라우저로 연다 (?variant=A|B|C)
"""
from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path

from PIL import Image

W = H = 64
GROUND = 59  # 발바닥 맨 아래 줄 (외곽선과 그림자는 그 아래)
OUT = Path(__file__).resolve().parent / "prototype_dog_out"

POSES = [
    # key, 이름, 프레임 수, 초당 프레임
    ("lie", "엎드림 (대기)", 4, 3),
    ("walk", "걷기 (이동)", 4, 8),
    ("sit", "앉기", 4, 4),
    ("think", "생각 중", 4, 3),
    ("talk", "말하기", 3, 8),
    ("happy", "기뻐하기", 4, 8),
]


# ---------------------------------------------------------------- 색

def rgba(h: str, a: int = 255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def dark(c, f=0.6):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f), c[3])


# ---------------------------------------------------------------- 도형 (픽셀 집합)

def _box(x0, y0, x1, y1):
    for y in range(max(0, int(y0) - 1), min(H, int(y1) + 2)):
        for x in range(max(0, int(x0) - 1), min(W, int(x1) + 2)):
            yield x, y


def ellipse(cx, cy, rx, ry, rot=0.0):
    c, s = math.cos(rot), math.sin(rot)
    r = max(rx, ry)
    out = set()
    for x, y in _box(cx - r, cy - r, cx + r, cy + r):
        dx, dy = x + 0.5 - cx, y + 0.5 - cy
        u, v = dx * c + dy * s, -dx * s + dy * c
        if (u / rx) ** 2 + (v / ry) ** 2 <= 1.0:
            out.add((x, y))
    return out


def capsule(x1, y1, x2, y2, r):
    vx, vy = x2 - x1, y2 - y1
    l2 = vx * vx + vy * vy or 1e-9
    out = set()
    for x, y in _box(min(x1, x2) - r, min(y1, y2) - r, max(x1, x2) + r, max(y1, y2) + r):
        px, py = x + 0.5 - x1, y + 0.5 - y1
        t = max(0.0, min(1.0, (px * vx + py * vy) / l2))
        dx, dy = px - t * vx, py - t * vy
        if dx * dx + dy * dy <= r * r:
            out.add((x, y))
    return out


def tube(points, r0, r1):
    out = set()
    n = len(points) - 1
    for i in range(n):
        r = r0 + (r1 - r0) * (i / max(1, n - 1))
        out |= capsule(*points[i], *points[i + 1], r)
    return out


def polygon(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    out = set()
    for x, y in _box(min(xs), min(ys), max(xs), max(ys)):
        px, py = x + 0.5, y + 0.5
        inside = False
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
        if inside:
            out.add((x, y))
    return out


def fluff(cx, cy, rx, ry, n, r, rot=0.0, phase=0.0):
    """몽실몽실한 덩어리: 타원 안쪽 + 테두리를 따라 작은 원들."""
    out = ellipse(cx, cy, max(1, rx - r * 0.6), max(1, ry - r * 0.6), rot)
    c, s = math.cos(rot), math.sin(rot)
    for i in range(n):
        a = phase + 2 * math.pi * i / n
        u, v = (rx - r * 0.6) * math.cos(a), (ry - r * 0.6) * math.sin(a)
        out |= ellipse(cx + u * c - v * s, cy + u * s + v * c, r, r)
    return out


def arc_points(cx, cy, r, a0, a1, n):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n + 1)]


# ---------------------------------------------------------------- 그리기 판

class Sprite:
    def __init__(self):
        self.color = {}
        self.owner = {}
        self.parts = []

    def part(self, pixels, base, shade=None, light=None, k=2, edge=False, line=None):
        pid = len(self.parts)
        pix = {p for p in pixels if 0 <= p[0] < W and 0 <= p[1] <= GROUND}
        self.parts.append({"pix": pix, "edge": edge, "line": line})
        for (x, y) in pix:
            c = base
            if light is not None and (x, y - 1) not in pix:
                c = light
            if shade is not None and any((x, y + i) not in pix for i in range(1, k + 1)):
                c = shade
            self.color[(x, y)] = c
            self.owner[(x, y)] = pid
        return pid

    def paint(self, pid, pixels, base, shade=None, k=1):
        """이미 그린 부위(pid) 안에만 무늬를 칠한다."""
        mine = {p for p in pixels if self.owner.get(p) == pid}
        for (x, y) in mine:
            c = base
            if shade is not None and any(
                    (x, y + i) not in mine and self.owner.get((x, y + i)) is not None for i in range(1, k + 1)):
                c = shade
            if shade is not None and any((x, y + i) not in self.color for i in range(1, k + 1)):
                c = shade
            self.color[(x, y)] = c

    def dot(self, x, y, c):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < W and 0 <= y < H:
            self.color[(x, y)] = c

    def inner_edges(self, style, line):
        for pid, part in enumerate(self.parts):
            if not part["edge"]:
                continue
            col = part["line"] or line
            hits = []
            for (x, y) in part["pix"]:
                if self.owner.get((x, y)) != pid:
                    continue
                for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    o = self.owner.get(q)
                    if o is not None and o < pid:
                        hits.append((x, y))
                        break
            for p in hits:
                self.color[p] = col if style == "black" else dark(self.color[p], 0.72)

    def outline(self, style, line):
        if style == "none":
            # 외곽선 대신 바닥 쪽 테두리만 한 톤 어둡게
            for (x, y), c in list(self.color.items()):
                if (x, y + 1) not in self.color and c[3] == 255:
                    self.color[(x, y)] = dark(c, 0.78)
            return
        add = {}
        for (x, y), c in self.color.items():
            for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if q not in self.color and 0 <= q[0] < W and 0 <= q[1] < H:
                    add[q] = line if style == "black" else dark(c, 0.55)
        self.color.update(add)

    def under(self, pixels, c):
        for p in pixels:
            if p not in self.color and 0 <= p[0] < W and 0 <= p[1] < H:
                self.color[p] = c

    def over(self, other: "Sprite"):
        self.color.update(other.color)

    def image(self):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for p, c in self.color.items():
            im.putpixel(p, c)
        return im


# ---------------------------------------------------------------- 강아지 세 마리

VARIANTS = {
    "A": {
        "label": "치비 시바",
        "desc": "머리가 큰 2등신. 진한 외곽선, 2톤 음영. 어떤 배경에서도 또렷하다.",
        "head": (13.0, 11.5), "body": (13.5, 9.0), "leg": 8, "leg_r": 3.0,
        "muzzle": (6.5, 4.6), "muz_at": (0.60, 0.46), "ear": "point", "tail": "curl", "fluffy": False,
        "outline": "black", "eye": "big", "blush": True,
        "pal": {
            "fur": rgba("#E9A14F"), "fur_s": rgba("#C47A2F"), "fur_l": rgba("#F6C680"),
            "cream": rgba("#FFF3E0"), "cream_s": rgba("#EED5B3"),
            "line": rgba("#3A2216"), "collar": rgba("#D7303C"), "collar_s": rgba("#9E1C28"),
            "tag": rgba("#F4C542"), "tag_s": rgba("#C8941F"),
            "nose": rgba("#2B1A12"), "eye": rgba("#21140E"), "tongue": rgba("#F27A8E"),
            "blush": rgba("#F5A3A0"), "ear_in": rgba("#F4B7A2"), "far": rgba("#B06B27"),
        },
    },
    "B": {
        "label": "몽실 비숑",
        "desc": "둥근 솜뭉치 몸. 털색을 따라가는 갈색 외곽선, 3톤 음영. 부드럽고 귀엽다.",
        "head": (12.5, 11.5), "body": (13.5, 9.0), "leg": 9, "leg_r": 3.4,
        "muzzle": (5.0, 3.8), "muz_at": (0.40, 0.36), "ear": "fluff", "tail": "plume", "fluffy": True,
        "outline": "selout", "eye": "round", "blush": True,
        "pal": {
            "fur": rgba("#FFFFFF"), "fur_s": rgba("#E9DDCE"), "fur_l": rgba("#FFFFFF"),
            "cream": rgba("#FFFDF8"), "cream_s": rgba("#EFE3D3"),
            "line": rgba("#8E7660"), "collar": rgba("#D7303C"), "collar_s": rgba("#9E1C28"),
            "tag": rgba("#F4C542"), "tag_s": rgba("#C8941F"),
            "nose": rgba("#2B1F1A"), "eye": rgba("#1C1512"), "tongue": rgba("#F27A8E"),
            "blush": rgba("#F7B3B0"), "ear_in": rgba("#F1E4D4"), "far": rgba("#DCCDBB"),
        },
    },
    "C": {
        "label": "날씬 비글",
        "desc": "다리가 긴 실제 비율. 외곽선 없이 면으로만 그린 깔끔한 그림체.",
        "head": (10.0, 9.0), "body": (16.5, 7.6), "leg": 13, "leg_r": 2.4,
        "muzzle": (6.0, 4.0), "muz_at": (0.62, 0.38), "ear": "long", "tail": "straight", "fluffy": False,
        "outline": "none", "eye": "small", "blush": False,
        "pal": {
            "fur": rgba("#C98A4B"), "fur_s": rgba("#A66A33"), "fur_l": rgba("#DDA266"),
            "cream": rgba("#FBF7F0"), "cream_s": rgba("#DED6C8"),
            "line": rgba("#4A2E1C"), "collar": rgba("#D7303C"), "collar_s": rgba("#9E1C28"),
            "tag": rgba("#F4C542"), "tag_s": rgba("#C8941F"),
            "nose": rgba("#231814"), "eye": rgba("#1E1310"), "tongue": rgba("#F27A8E"),
            "blush": rgba("#F5A3A0"), "ear_in": rgba("#7A4A26"), "far": rgba("#8E5B2C"),
            "saddle": rgba("#3B302C"), "saddle_s": rgba("#28201D"), "saddle_l": rgba("#54463F"),
        },
    },
}


# ---------------------------------------------------------------- 자세별 뼈대

def skeleton(v, pose, f):
    hrx, hry = v["head"]
    brx, bry = v["body"]
    L, lr = v["leg"], v["leg_r"]
    k = {"pose": pose, "eyes": "open", "mouth": "closed", "lift": 0, "bob": f % 2}
    if pose == "walk" or pose == "happy":
        bob = [0, -1, 0, -1][f] if pose == "walk" else 0
        lift = [0, -4, -7, -4][f] if pose == "happy" else 0
        tuck = [0, 0.25, 0.4, 0.25][f] if pose == "happy" else 0
        k["lift"] = lift
        bcx, bcy = 29, GROUND - L - bry * 0.45 + bob + lift
        k["body"] = (bcx, bcy, brx, bry, 0.0)
        sh = (bcx + brx * 0.52, bcy + bry * 0.35)
        hp = (bcx - brx * 0.55, bcy + bry * 0.35)
        s1 = [2.5, 0, -2.5, 0][f] if pose == "walk" else 1.5
        s2 = -s1 if pose == "walk" else -1.5
        up1 = 2 if (pose == "walk" and f == 3) else 0
        up2 = 2 if (pose == "walk" and f == 1) else 0
        foot = GROUND - lr + 0.6

        def paw(x, up):
            y = foot - up + lift
            if tuck:
                y = sh[1] + (foot + lift - sh[1]) * (1 - tuck)
            return (x, y)

        k["legs"] = [
            # (어깨/엉덩이, 발, 가까운 쪽?)
            ((hp[0] - 2.5, hp[1]), paw(hp[0] - 2.5 + s1, up1), False),
            ((sh[0] - 2.5, sh[1]), paw(sh[0] - 2.5 + s2, up2), False),
            ((hp[0] + 0.5, hp[1]), paw(hp[0] + 0.5 + s2, up2), True),
            ((sh[0] + 0.5, sh[1]), paw(sh[0] + 0.5 + s1, up1), True),
        ]
        k["head"] = (bcx + brx * 0.62 + v.get("neck_dx", 0), bcy - bry * 0.55 - hry * 0.5 + (1 if pose == "walk" and f % 2 else 0), 0.0)
        k["tail"] = (bcx - brx * 0.82, bcy - bry * 0.35, [0.25, 0.0, -0.25, 0.0][f] if pose == "walk" else [0.4, -0.4, 0.4, -0.4][f])
        k["shadow"] = (bcx + 2, brx + 4 + lift * 0.6)
        if pose == "happy":
            k["eyes"], k["mouth"] = "happy", "tongue"
        return k

    if pose in ("sit", "think", "talk"):
        bcx, bcy = 27, GROUND - brx * 0.62
        k["body"] = (bcx, bcy, brx * 0.82, bry * 1.02, -1.05)
        k["haunch"] = (bcx - 5, GROUND - bry * 0.55, bry * 0.95, bry * 0.7)
        k["backpaw"] = (bcx + 1, GROUND - 1.2)
        fx = bcx + brx * 0.42
        top = bcy - 1
        foot = GROUND - lr + 0.6
        k["legs"] = [
            ((fx - 3.5, top), (fx - 3.0, foot), False),
            ((fx + 0.5, top), (fx + 1.0, foot), True),
        ]
        hy = bcy - brx * 0.62 - hry * 0.52
        tilt = 0.0
        if pose == "think":
            tilt = [0.0, -0.12, -0.12, 0.0][f]
            k["eyes"] = "up"
            k["mouth"] = "small"
            k["dots"] = [1, 2, 3, 3][f]
        if pose == "talk":
            k["mouth"] = ["closed", "small", "open"][f]
            hy += [0, 0, -1][f]
        if pose == "sit":
            k["eyes"] = "blink" if f == 3 else "open"
        k["head"] = (bcx + brx * 0.55, hy, tilt)
        k["tail"] = ("sit", bcx - brx * 0.62, GROUND - 2.0, [0.35, -0.2, 0.35, -0.2][f] if pose == "sit" else 0.1)
        k["shadow"] = (bcx + 1, brx + 2)
        return k

    if pose == "lie":
        breathe = [0, 0.5, 1.0, 0.5][f]
        bcx = 25
        k["body"] = (bcx, GROUND - bry * 0.62 - breathe * 0.5, brx * 1.05, bry * 0.72 + breathe * 0.4, 0.0)
        k["haunch"] = (bcx - brx * 0.55, GROUND - bry * 0.5, bry * 0.85, bry * 0.62)
        k["backpaw"] = (bcx - brx * 0.05, GROUND - 1.0)
        hx = bcx + brx * 0.95
        k["paws"] = [
            ((hx - 6, GROUND - 2.4), (hx + 7, GROUND - 2.0), False),
            ((hx - 4, GROUND - 1.6), (hx + 10, GROUND - 1.4), True),
        ]
        k["head"] = (hx + 1, GROUND - hry * 0.95 - 1.5, 0.08)
        k["eyes"] = "blink" if f == 3 else "sleepy"
        k["tail"] = ("lie", bcx - brx * 1.0, GROUND - 2.5, [0.0, 0.15, 0.0, -0.15][f])
        k["shadow"] = (bcx + 6, brx + 8)
        return k
    raise ValueError(pose)


# ---------------------------------------------------------------- 강아지 그리기

def draw_dog(vk, pose, f):
    v = VARIANTS[vk]
    P = v["pal"]
    st = v["outline"]
    k = skeleton(v, pose, f)
    sp = Sprite()
    hrx, hry = v["head"]
    lr = v["leg_r"]
    fluffy = v["fluffy"]
    far_c, far_s = P["far"], dark(P["far"], 0.8)
    lift = k["lift"]

    def leg(a, b, near, r=lr):
        if fluffy:
            px = capsule(*a, *b, r) | ellipse(b[0] + 0.5, b[1] - 0.3, r + 0.6, r * 0.85)
        else:
            px = capsule(*a, *b, r) | ellipse(b[0] + 0.8, b[1] + 0.2, r + 0.4, r * 0.75)
        if near:
            pid = sp.part(px, P["fur"], P["fur_s"], k=1, edge=not fluffy)
            if vk == "C":
                sp.paint(pid, {p for p in px if p[1] > (a[1] + b[1]) / 2 - 2}, P["cream"], P["cream_s"])
            if vk == "A":
                sp.paint(pid, {p for p in px if p[1] > b[1] - 2}, P["cream"], P["cream_s"])
        else:
            sp.part(px, far_c, far_s, k=1)

    def body_shape(cx, cy, rx, ry, rot):
        if fluffy:
            return fluff(cx, cy, rx + 1, ry + 1, 11, 3.2, rot, phase=0.3)
        return ellipse(cx, cy, rx, ry, rot)

    # 꼬리 (뒤쪽에 깔리는 경우)
    tail = k["tail"]

    def draw_tail(front):
        style = v["tail"]
        if isinstance(tail[0], str):
            mode, tx, ty, wag = tail
        else:
            mode, (tx, ty, wag) = "stand", tail
        if style == "straight":
            if front:
                return
            ang = -2.2 + wag if mode == "stand" else (-2.6 + wag if mode == "sit" else -3.0 + wag)
            length = 11 if mode != "lie" else 10
            pts = [(tx + math.cos(ang) * length * i / 4, ty + math.sin(ang) * length * i / 4 + (i * i * 0.25 if mode == "lie" else 0)) for i in range(5)]
            px = tube(pts, 2.0, 1.2)
            pid = sp.part(px, P["fur"], P["fur_s"], k=1)
            tip = tube(pts[3:], 1.6, 1.2)
            sp.paint(pid, tip, P["cream"], P["cream_s"])
        elif style == "curl":
            if front != (mode == "stand"):
                return
            if mode == "stand":
                cx, cy = tx + 1.5 + wag * 2, ty - 4.5
            elif mode == "sit":
                cx, cy = tx + 0.5 + wag * 2, ty - 4.0
            else:
                cx, cy = tx + 1.0 + wag * 2, ty - 4.0
            if mode != "stand":
                cx, cy = tx - 1 + wag * 2, ty - 6
            pts = arc_points(cx, cy, 3.4, math.radians(80), math.radians(80 - 260), 8)
            px = tube(pts, 3.0, 1.9)
            pid = sp.part(px, P["fur"], P["fur_s"], P["fur_l"], k=1, edge=front)
            sp.paint(pid, ellipse(cx + 0.5, cy + 0.5, 1.6, 1.6), P["fur_l"], None)
        elif style == "plume":
            if not front:
                return
            if mode == "stand":
                cx, cy = tx + 1 + wag * 2.5, ty - 5
            elif mode == "sit":
                cx, cy = tx + 1 + wag * 2.5, ty - 5
            else:
                cx, cy = tx + 1 + wag * 2.5, ty - 4
            px = fluff(cx, cy, 5.0, 4.5, 7, 2.2, 0.0, phase=wag)
            sp.part(px, P["fur"], P["fur_s"], P["fur_l"], k=2, edge=True)

    # 얼굴 위치
    hx, hy, tilt = k["head"]

    def rot(dx, dy):
        c, s = math.cos(tilt), math.sin(tilt)
        return hx + dx * c - dy * s, hy + dx * s + dy * c

    # 귀 (머리 뒤)
    def ears_back():
        if v["ear"] == "point":
            far = [rot(hrx * 0.10, -hry * 0.70), rot(hrx * 0.78, -hry * 0.48), rot(hrx * 0.52, -hry * 1.40)]
            sp.part(polygon(far), far_c, far_s, k=1)
            near = [rot(-hrx * 0.78, -hry * 0.38), rot(-hrx * 0.02, -hry * 0.86), rot(-hrx * 0.50, -hry * 1.45)]
            pid = sp.part(polygon(near), P["fur"], P["fur_s"], P["fur_l"], k=1)
            inner = [rot(-hrx * 0.58, -hry * 0.55), rot(-hrx * 0.18, -hry * 0.82), rot(-hrx * 0.47, -hry * 1.18)]
            sp.paint(pid, polygon(inner), P["ear_in"], None)
        elif v["ear"] == "long":
            fx, fy = rot(hrx * 0.55, -hry * 0.55)
            sp.part(ellipse(fx + 1, fy + 3, 2.6, 5.0, -0.3), far_c, far_s, k=1)
        elif v["ear"] == "fluff":
            fx, fy = rot(hrx * 0.62, hry * 0.05)
            sp.part(fluff(fx, fy, 3.6, 5.5, 5, 2.0), P["fur_s"], dark(P["fur_s"], 0.92), k=1)

    def ears_front():
        if v["ear"] == "long":
            ex, ey = rot(-hrx * 0.42, -hry * 0.55)
            sway = 0.25 if k["pose"] == "walk" else 0.0
            px = ellipse(ex - 0.5, ey + 5.0, 3.4, 6.6, -0.12 - sway * (1 if (k.get("lift") or 0) else 0))
            px |= ellipse(ex + 0.5, ey + 1.0, 3.0, 3.0)
            sp.part(px, P["ear_in"], dark(P["ear_in"], 0.82), P["fur_s"], k=2, edge=True)
        elif v["ear"] == "fluff":
            ex, ey = rot(-hrx * 0.70, hry * 0.10)
            sp.part(fluff(ex, ey, 4.0, 6.2, 6, 2.2), P["fur"], P["fur_s"], k=2, edge=True)

    # ---- 그리는 순서: 뒤 → 앞
    draw_tail(front=False)
    if "legs" in k:
        for a, b, near in k["legs"]:
            if not near:
                leg(a, b, False)
    if "paws" in k:
        for a, b, near in k["paws"]:
            if not near:
                leg(a, b, False, r=lr * 0.9)

    bx, by, brx_, bry_, brot = k["body"]
    body_px = body_shape(bx, by, brx_, bry_, brot)
    body = sp.part(body_px, P["fur"], P["fur_s"], P["fur_l"], k=2, edge=not fluffy)
    # 무늬
    if vk == "A":
        if k["pose"] in ("sit", "think", "talk"):
            sp.paint(body, ellipse(bx + 5, by + 1, 5.0, 8.5, -0.3), P["cream"], P["cream_s"])
        else:
            sp.paint(body, ellipse(bx + 3, by + bry_ * 0.8, brx_ * 0.85, bry_ * 0.55), P["cream"], P["cream_s"], k=1)
    if vk == "C":
        if k["pose"] in ("sit", "think", "talk"):
            sp.paint(body, ellipse(bx - 5.5, by - 3.5, 5.0, 8.0, -1.05), P["saddle"], P["saddle_s"], k=1)
            sp.paint(body, ellipse(bx + 6, by + 2, 4.0, 8.0, -0.25), P["cream"], P["cream_s"])
        else:
            sp.paint(body, ellipse(bx - 2, by - bry_ * 0.75, brx_ * 0.72, bry_ * 0.75), P["saddle"], P["saddle_s"], k=1)
            sp.paint(body, ellipse(bx + brx_ * 0.6, by + bry_ * 0.55, brx_ * 0.45, bry_ * 0.6), P["cream"], P["cream_s"])

    if "haunch" in k:
        hx2, hy2, hrx2, hry2 = k["haunch"]
        px = fluff(hx2, hy2, hrx2 + 1, hry2 + 1, 7, 2.6) if fluffy else ellipse(hx2, hy2, hrx2, hry2)
        pid = sp.part(px, P["fur"], P["fur_s"], P["fur_l"], k=2, edge=not fluffy)
        if vk == "C":
            sp.paint(pid, ellipse(hx2 - 1, hy2 - hry2 * 0.6, hrx2 * 0.9, hry2 * 0.55), P["saddle"], P["saddle_s"])
        pxp = ellipse(k["backpaw"][0], k["backpaw"][1], lr + 1.2, lr * 0.7)
        pid = sp.part(pxp, P["fur"], P["fur_s"], k=1, edge=not fluffy)
        if vk in ("A", "C"):
            sp.paint(pid, pxp, P["cream"], P["cream_s"])

    draw_tail(front=True)

    if "legs" in k:
        for a, b, near in k["legs"]:
            if near:
                leg(a, b, True)

    ears_back()
    # 머리
    head_px = (fluff(hx, hy, hrx + 0.5, hry + 0.5, 10, 2.6, tilt, phase=0.2) if fluffy
               else ellipse(hx, hy, hrx, hry, tilt))
    head = sp.part(head_px, P["fur"], P["fur_s"], P["fur_l"], k=2, edge=True)
    # 주둥이
    ma, mb = v["muz_at"]
    mx, my = rot(hrx * ma, hry * mb)
    mrx, mry = v["muzzle"]
    muz_px = ellipse(mx, my, mrx, mry, tilt)
    sp.part(muz_px, P["cream"], P["cream_s"], k=1)
    if vk == "A":
        sp.paint(head, ellipse(*rot(-hrx * 0.05, hry * 0.45), hrx * 0.45, hry * 0.32), P["cream"], P["cream_s"])
        sp.paint(head, ellipse(*rot(hrx * 0.30, -hry * 0.30), 1.6, 1.0), P["cream"], None)  # 눈썹 점
        sp.paint(head, ellipse(*rot(-hrx * 0.22, -hry * 0.34), 1.6, 1.0), P["cream"], None)
    if vk == "C":
        sp.paint(head, ellipse(*rot(hrx * 0.25, -hry * 0.2), 1.3, hry * 0.9, -0.15), P["cream"], None)  # 흰 줄

    ears_front()

    # 목띠: 머리 아래 테두리를 따라 두르고, 가운데에 쇠붙이를 단다
    arc = [rot(hrx * 0.86 * math.cos(math.radians(a)), hry * 0.92 * math.sin(math.radians(a)))
           for a in range(68, 161, 12)]
    cr = max(1.3, hry * 0.14)
    sp.part(tube(arc, cr, cr), P["collar"], P["collar_s"], P["collar"], k=1, edge=True)
    tx_, ty_ = rot(hrx * 0.86 * math.cos(math.radians(98)), hry * 0.92 * math.sin(math.radians(98)) + 2.6)
    sp.part(ellipse(tx_, ty_, 1.8, 1.8), P["tag"], P["tag_s"], k=1, edge=True, line=P["tag_s"])

    sp.inner_edges(st, P["line"])

    # ---- 얼굴 (외곽선 없이 직접 찍는다)
    E = P["eye"]
    white = rgba("#FFFFFF")

    def eye(x, y, kind, small=False):
        x, y = int(round(x)), int(round(y))
        if kind in ("open", "up"):
            dy = -1 if kind == "up" else 0
            if v["eye"] == "small" or small:
                for p in ((x, y + dy), (x + 1, y + dy), (x, y + 1 + dy), (x + 1, y + 1 + dy)):
                    sp.dot(*p, E)
                sp.dot(x, y + dy, white)
            elif v["eye"] == "round":
                for ddx in range(3):
                    for ddy in range(3):
                        sp.dot(x + ddx - 1, y + ddy - 1 + dy, E)
                sp.dot(x - 1 + 0, y - 1 + dy, white)
                sp.dot(x + 1, y + 1 + dy, rgba("#6E5A50"))
            else:
                for ddy in range(-1, 3):
                    for ddx in range(-1, 2):
                        sp.dot(x + ddx, y + ddy + dy, E)
                sp.dot(x - 1, y - 1 + dy, white)
                sp.dot(x, y - 1 + dy, white)
                sp.dot(x + 1, y + 2 + dy, rgba("#6E5040"))
        elif kind == "blink":
            sp.dot(x - 1, y + 1, E); sp.dot(x, y + 1, E); sp.dot(x + 1, y + 1, E)
        elif kind == "sleepy":
            sp.dot(x - 1, y + 1, E); sp.dot(x, y + 1, E); sp.dot(x + 1, y + 1, E)
            sp.dot(x, y, E); sp.dot(x + 1, y, E)
        elif kind == "happy":
            sp.dot(x - 1, y + 1, E); sp.dot(x, y, E); sp.dot(x + 1, y, E); sp.dot(x + 2, y + 1, E)

    ne = rot(-hrx * 0.20, -hry * 0.10)
    fe = rot(hrx * 0.36, -hry * 0.14)
    eye(*ne, k["eyes"])
    eye(fe[0], fe[1], k["eyes"], small=(v["eye"] == "small"))

    # 코
    nx, ny = rot(hrx * ma + mrx * 0.72, hry * mb - mry * 0.55)
    nx, ny = int(round(nx)), int(round(ny))
    for p in ((nx - 1, ny), (nx, ny), (nx + 1, ny), (nx - 1, ny + 1), (nx, ny + 1)):
        sp.dot(*p, P["nose"])
    sp.dot(nx - 1, ny, rgba("#7A6A64"))

    # 입
    mox, moy = rot(hrx * ma + mrx * 0.30, hry * mb + mry * 0.30)
    mox, moy = int(round(mox)), int(round(moy))
    m = k["mouth"]
    line = dark(P["cream_s"], 0.55)
    if m == "closed":
        sp.dot(mox, moy, line); sp.dot(mox + 1, moy + 1, line); sp.dot(mox + 2, moy, line)
    elif m == "small":
        sp.dot(mox + 1, moy, P["nose"]); sp.dot(mox + 1, moy + 1, P["nose"]); sp.dot(mox + 2, moy, P["nose"])
    elif m in ("open", "tongue"):
        for ddx in range(3):
            for ddy in range(2):
                sp.dot(mox + ddx, moy + ddy, P["nose"])
        sp.dot(mox + 1, moy + 2, P["tongue"]); sp.dot(mox + 2, moy + 2, P["tongue"])
        if m == "tongue":
            sp.dot(mox + 1, moy + 3, P["tongue"]); sp.dot(mox + 2, moy + 3, dark(P["tongue"], 0.85))
    if v["blush"] and k["eyes"] != "blink":
        bx_, by_ = rot(-hrx * 0.30, hry * 0.30)
        sp.dot(bx_, by_, P["blush"]); sp.dot(bx_ + 1, by_, P["blush"])

    sp.outline(st, P["line"])

    # 그림자
    scx, srx = k["shadow"]
    sh_px = ellipse(scx, GROUND + 2.2, max(6, srx), 1.8)
    sp.under(sh_px, (40, 28, 24, 70))

    # ---- 덧그림: 생각 구름, 하트
    if k.get("dots"):
        ov = Sprite()
        cloud = fluff(14, 11, 10, 6, 7, 3.0, phase=0.4)
        ov.part(cloud, rgba("#FFFFFF"), rgba("#E6EAF0"), k=1)
        ov.part(ellipse(26.5, 20.5, 1.8, 1.8), rgba("#FFFFFF"), None)
        ov.part(ellipse(30, 24, 1.1, 1.1), rgba("#FFFFFF"), None)
        for i in range(k["dots"]):
            ox = 9 + i * 5
            for p in ((ox, 11), (ox + 1, 11), (ox, 12), (ox + 1, 12)):
                ov.dot(*p, rgba("#5B6472"))
        ov.outline("black" if st == "black" else "selout", rgba("#5B6472") if st != "black" else P["line"])
        sp.over(ov)
    if k["pose"] == "happy":
        ov = Sprite()
        heart = [(1, 0), (2, 0), (4, 0), (5, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1),
                 (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2), (1, 3), (2, 3), (3, 3), (4, 3), (5, 3),
                 (2, 4), (3, 4), (4, 4), (3, 5)]
        hx0, hy0 = 9, [16, 12, 8, 4][f]
        for ddx, ddy in heart:
            ov.dot(hx0 + ddx, hy0 + ddy, rgba("#F0475B"))
        ov.dot(hx0 + 1, hy0 + 1, rgba("#FFFFFF"))
        ov.outline("black", P["line"] if st == "black" else dark(rgba("#F0475B"), 0.55))
        sp.over(ov)
    return sp.image()





# ---------------------------------------------------------------- 출력

def sheet(vk):
    cols = max(n for _, _, n, _ in POSES)
    im = Image.new("RGBA", (W * cols, H * len(POSES)), (0, 0, 0, 0))
    for r, (pk, _, n, _) in enumerate(POSES):
        for c in range(n):
            im.paste(draw_dog(vk, pk, c), (c * W, r * H))
    return im


def contact(sheets, scale=4):
    """사람 눈으로 확인하기 위한 큰 한 장 (흰 바탕, 어두운 바탕을 나란히)."""
    sw, sh = sheets["A"].size
    pad = 8
    out = Image.new("RGBA", ((sw * scale + pad) * len(sheets) * 2, sh * scale), (0, 0, 0, 255))
    x = 0
    for vk in sorted(sheets):
        for bg in ((255, 255, 255, 255), (40, 44, 52, 255)):
            panel = Image.new("RGBA", (sw, sh), bg)
            panel.alpha_composite(sheets[vk])
            out.paste(panel.resize((sw * scale, sh * scale), Image.NEAREST), (x, 0))
            x += sw * scale + pad
    return out


def data_uri(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    OUT.mkdir(exist_ok=True)
    sheets = {vk: sheet(vk) for vk in VARIANTS}
    for vk, im in sheets.items():
        im.save(OUT / f"dog_{vk}.png")
    contact(sheets).save(OUT / "contact.png")
    meta = {
        "size": W,
        "poses": [{"key": k, "label": lab, "frames": n, "fps": fps} for k, lab, n, fps in POSES],
        "variants": {vk: {"label": v["label"], "desc": v["desc"], "sheet": data_uri(sheets[vk])}
                     for vk, v in VARIANTS.items()},
    }
    tpl = (Path(__file__).resolve().parent / "prototype_dog_preview.html").read_text(encoding="utf-8")
    (OUT / "preview.html").write_text(tpl.replace("/*META*/null", json.dumps(meta, ensure_ascii=False)),
                                      encoding="utf-8")
    print(f"만듦: {OUT / 'preview.html'}")


if __name__ == "__main__":
    main()
