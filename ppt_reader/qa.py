"""질의응답: 근거 묶음, 지침 합치기, 대화 기억, 답을 문장으로 자르기.

문장 자르기는 대본 읽기(음성 흐름)도 함께 쓴다. 같은 규칙으로 잘라야 미리 만든 대본 소리의 저장 키가 맞는다.
"""
from __future__ import annotations

_ENDERS = ".?!…。"
_CLOSERS = "\"'”’)]}」』"


class SentenceSplitter:
    """스트림으로 오는 글을 받는 대로 문장으로 잘라 낸다.

    끝: 마침표·물음표·느낌표·말줄임표 뒤에 공백이나 줄바꿈이 오는 곳, 그리고 줄바꿈.
    바로 뒤의 닫는 따옴표나 괄호는 그 문장에 붙인다. 숫자 사이의 점(3.5배)은 뒤에 공백이 없어 자르지 않는다.
    """

    def __init__(self):
        self._buf = ""

    def feed(self, chunk: str) -> list[str]:
        self._buf += chunk
        out: list[str] = []
        start = i = 0
        buf = self._buf
        while i < len(buf):
            ch = buf[i]
            if ch == "\n":
                out.append(buf[start:i])
                start = i = i + 1
                continue
            if ch in _ENDERS:
                j = i + 1
                while j < len(buf) and (buf[j] in _CLOSERS or buf[j] in _ENDERS):
                    j += 1
                if j == len(buf):
                    break  # 뒤에 무엇이 올지 아직 모른다
                if buf[j].isspace():
                    out.append(buf[start:j])
                    start = i = j
                    continue
                i = j
                continue
            i += 1
        self._buf = buf[start:]
        return [s.strip() for s in out if s.strip()]

    def finish(self) -> list[str]:
        """스트림이 끝나면 남은 글을 마지막 문장으로 낸다."""
        rest, self._buf = self._buf.strip(), ""
        return [rest] if rest else []


def split_sentences(text: str) -> list[str]:
    splitter = SentenceSplitter()
    return splitter.feed(text) + splitter.finish()
