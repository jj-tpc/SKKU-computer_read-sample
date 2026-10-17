"""목소리 신호: 크기 곡선, 높낮이 느낌, 입 모양 판정, 음절 시각 어림. 순수 파이썬이다."""
from __future__ import annotations

import array
import bisect
import math
import re
import sys

WINDOW = 0.02  # 곡선 한 칸(초)
STEP = 4  # 창 안에서 4샘플에 하나만 써도 모양은 같다

CLOSED, SMALL, OPEN, WIDE = 0, 1, 2, 3
# 입꼬리를 옆으로 당기는 중성: ㅐ ㅒ ㅔ ㅖ ㅢ ㅣ. ㅡ는 은·는·을처럼 너무 자주 나와서 넣지 않는다
WIDE_VOWELS = frozenset({1, 3, 5, 7, 19, 20})
MOUTH_HOLD = 0.06


def _samples(pcm: bytes) -> array.array:
    samples = array.array("h", pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    return samples


def curves(pcm: bytes, rate: int) -> tuple[list[float], list[float]]:
    """20ms 창마다 (크기, 높낮이 느낌). 크기는 RMS를 그 문장의 최댓값으로 나눈 0~1이다.

    높낮이 느낌은 영교차 비율을 0~1로 둔 값이다. 음높이를 정확히 재지 않아도 파동 모양을 바꾸기에는 충분하다.
    """
    samples = _samples(pcm)
    n = max(1, int(rate * WINDOW))
    levels, tones = [], []
    for start in range(0, len(samples), n):
        win = samples[start:start + n:STEP]
        if not win:
            break
        levels.append(math.sqrt(sum(x * x for x in win) / len(win)))
        crossings = sum(1 for a, b in zip(win, win[1:]) if (a < 0) != (b < 0))
        tones.append(crossings / max(1, len(win) - 1))
    for values in (levels, tones):
        peak = max(values, default=0.0)
        if peak > 0:
            values[:] = [v / peak for v in values]
    return levels, tones


def value_at(curve: list[float], t: float) -> float:
    i = int(t / WINDOW)
    return curve[i] if 0 <= i < len(curve) else 0.0


def jungseong(ch: str) -> int | None:
    """한글 음절의 중성 번호(0~20). 한글 음절이 아니면 None."""
    code = ord(ch) - 0xAC00
    if 0 <= code < 11172:
        return code % 588 // 28
    return None


def mouth_shape(level: float, syllable: str | None) -> int:
    """곡선 값과 그때 소리 나는 음절로 입 모양을 고른다. 한글이 아니면 크기만 본다."""
    if level < 0.2:
        return CLOSED
    if syllable and jungseong(syllable) in WIDE_VOWELS:
        return WIDE
    if level < 0.55:
        return SMALL
    return OPEN


class MouthHold:
    """한 모양을 60ms 넘게 유지한다. 바꾸려는 모양이 와도 60ms가 지나기 전에는 바꾸지 않는다."""

    def __init__(self, hold: float = MOUTH_HOLD):
        self.hold = hold
        self.shape = CLOSED
        self.since = -math.inf

    def update(self, want: int, now: float) -> int:
        if want != self.shape and now - self.since >= self.hold:
            self.shape = want
            self.since = now
        return self.shape


def syllable_events(text: str, words: list[tuple[int, int, float]], seconds: float) -> list[tuple[float, str | None]]:
    """(시작 초, 음절) 목록. 낱말 시작부터 다음 낱말 시작까지를 그 낱말의 한글 음절 수로 똑같이 나눈다.

    한글이 없는 낱말(영어, 숫자)은 음절 None 하나로 둔다.
    """
    events: list[tuple[float, str | None]] = []
    for k, (start, length, t0) in enumerate(words):
        t1 = words[k + 1][2] if k + 1 < len(words) else seconds
        hangul = [ch for ch in text[start:start + length] if jungseong(ch) is not None]
        if not hangul:
            events.append((t0, None))
            continue
        span = max(0.0, t1 - t0)
        events.extend((t0 + span * m / len(hangul), ch) for m, ch in enumerate(hangul))
    return events


def syllable_at(events: list[tuple[float, str | None]], t: float) -> str | None:
    i = bisect.bisect_right([e[0] for e in events], t) - 1
    return events[i][1] if i >= 0 else None


def words_started(words: list[tuple[int, int, float]], t: float) -> int:
    return sum(1 for w in words if w[2] <= t)


_WORD = re.compile(r"\S+")


def word_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end() - m.start()) for m in _WORD.finditer(text)]
