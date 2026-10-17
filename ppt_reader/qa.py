"""질의응답: 근거 묶음, 지침 합치기, 대화 기억, 답을 문장으로 자르기.

문장 자르기는 대본 읽기(음성 흐름)도 함께 쓴다. 같은 규칙으로 잘라야 미리 만든 대본 소리의 저장 키가 맞는다.
"""
from __future__ import annotations

from collections import deque

BASE_SYSTEM = """너는 발표 화면 위의 도트 강아지 캐릭터다. 발표가 끝난 뒤 청중의 질문에 답한다.
- 먼저 <자료>의 내용을 근거로 답한다. 자료에 없는 내용은 일반 지식으로 보충하되, 그 부분은 "자료에는 없지만"처럼 밝힌다.
- 자료를 가리킬 때는 "3번 슬라이드에"처럼 장 번호로 말한다.
- 답은 소리 내어 읽힌다. 꾸밈 없는 한국어 말투 문장으로 2~4문장을 쓴다. 마크다운, 목록, 이모지, 표, 코드는 쓰지 않는다.
- 늘 한국어로 답한다."""

PERSONA = """<개인 지침>
{persona}
</개인 지침>
말투, 답 길이, 캐릭터 성격, 답의 언어는 개인 지침을 따른다. 그래도 다음 두 가지는 늘 지킨다.
1. 자료에 없는 내용은 자료에 없다고 밝힌다.
2. 마크다운, 목록, 이모지, 표 없이 소리 내어 읽기 좋은 문장으로 쓰고, 8문장을 넘기지 않는다."""

CAPTION_SYSTEM = """너는 발표 자료의 그림을 설명하는 사람이다. 슬라이드의 글을 참고해서 그림마다 한국어 1~3문장으로 설명한다.
그림 속 글자와 숫자는 그대로 옮긴다. 장식일 뿐이면 "장식용 그림"이라고만 쓴다.
그림 수만큼 "그림 1: ...", "그림 2: ..." 줄로만 답한다."""

MEMORY_TURNS = 6
CUT_MARK = "(끊김)"


def system_prompt(persona: str) -> str:
    """기본 지침 뒤에 개인 지침을 붙인다. 개인 지침이 말투와 길이를 바꿔도 자료 밖 밝히기와 말하기 형식은 지킨다."""
    persona = (persona or "").strip()
    return BASE_SYSTEM + ("\n\n" + PERSONA.format(persona=persona) if persona else "")


def _attr(text: str) -> str:
    return text.replace('"', "'").replace("\n", " ").strip()


def grounding(deck, edits: dict[int, str], captions: dict[int, list[str]] | None = None) -> str:
    """질문마다 넣는 자료 전체. 바뀌지 않으므로 제공자 쪽에서 캐시된다. 지금 장 번호는 바뀌므로 넣지 않는다."""
    captions = captions or {}
    lines = [f'<자료 파일="{_attr(deck.name)}" 장수="{len(deck.slides)}">']
    for s in deck.slides:
        hidden = ' 숨김="예"' if s.hidden else ""
        title = _attr(s.title.split("\n")[0]) if s.title else ""
        lines.append(f'<슬라이드 번호="{s.number}" 제목="{title}"{hidden}>')
        lines.append(f"본문: {s.body}")
        if s.notes:
            lines.append(f"발표자 노트: {s.notes}")
        if s.number in edits:
            lines.append(f"고친 대본: {edits[s.number]}")
        for i, cap in enumerate(captions.get(s.number, []), 1):
            if cap:
                lines.append(f"그림 {i}: {cap}")
        lines.append("</슬라이드>")
    lines.append("</자료>")
    return "\n".join(lines)


def question_text(question: str, showing: int | None) -> str:
    """PowerPoint와 연동 중일 때만 지금 화면의 장 번호를 질문 앞에 붙인다."""
    return f"(지금 화면: {showing}번 슬라이드) {question}" if showing else question


class Memory:
    """같은 발표 파일을 쓰는 동안 최근 6번의 질문과 답. 다른 파일을 열거나 다시 켜면 잊는다."""

    def __init__(self):
        self._turns: deque[tuple[str, str]] = deque(maxlen=MEMORY_TURNS)

    def add(self, question: str, answer: str, cut: bool = False) -> None:
        self._turns.append((question, f"{answer} {CUT_MARK}".strip() if cut else answer))

    def turns(self) -> list[tuple[str, str]]:
        return list(self._turns)

    def clear(self) -> None:
        self._turns.clear()


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
