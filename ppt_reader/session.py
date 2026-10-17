"""상태 묶음: 대본 읽기, 자동 발표, PowerPoint 따라가기, 질의응답. Qt 화면을 모른다.

화면은 on_* 콜백으로 알림을 받고, 사용자가 누른 것은 메서드로 부른다.
음성, 연동, 시계는 생성자로 받아서 시험에서는 가짜로 바꾼다.
모든 메서드는 화면 스레드에서만 부른다. 다른 스레드의 알림은 화면 쪽이 이 스레드로 옮겨 준다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from .link import LinkError, PptState, resolve_local_path
from .llm.base import LLMError, Request
from .qa import Memory, SentenceSplitter, grounding, question_text, system_prompt
from .settings import SPEEDS, Edits, Settings
from .slides import Deck, load_deck, to_speech
from .voice.cloud import PROVIDER_NAMES

EMPTY_SLIDE_PAUSE = 1.5  # 읽을 글이 없는 장에서 자동 발표가 쉬는 시간(초)

# 화면 문구. 기존 문구는 PROMPT.md, 새 문구는 PROMPT-character-qa.md의 <ui_strings>와 글자까지 같다.
OLD_FORMAT = "'{name}' 형식은 읽을 수 없습니다.\nPowerPoint에서 [다른 이름으로 저장] → .pptx 로 저장한 뒤 여세요."
OPEN_FAILED = "파일을 열 수 없습니다.\n{path}\n\n{error}"
UNKNOWN_PATH = ("PowerPoint의 '{name}' 파일 위치를 알 수 없습니다. "
                "파일을 저장했는지 확인하거나 [파일 열기]로 같은 파일을 직접 여세요.")
RELOADED = "PowerPoint에서 저장한 내용을 다시 불러왔습니다."
LINK_LOST = "PowerPoint 연결이 끊겼어요"
VOICE_FAILED = "목소리를 낼 수 없어요. 출력 장치를 확인하세요."
CLOUD_KEY = "{provider} 키가 맞지 않아 운영체제 음성으로 읽어요."
CLOUD_QUOTA = "{provider} 사용량 한도라 운영체제 음성으로 읽어요."
CLOUD_OTHER = "{provider} 목소리를 쓸 수 없어 운영체제 음성으로 읽어요."
CHIP_SHOW = "PowerPoint 연결됨 · 쇼 진행 중 {n}번 장"
CHIP_EDIT = "PowerPoint 연결됨 · 편집 화면 {n}번 장"
CHIP_SEARCHING = "PowerPoint 찾는 중…"
CHIP_NONE = "PowerPoint에 열린 발표 자료가 없어요"
CHIP_LOST = "PowerPoint 연결이 끊겼어요"
CHIP_OFF = "연동 꺼짐"
WAIT_LINES = ((8.0, "조금만 기다려 주세요"), (30.0, "아직 생각하고 있어요"))  # 말풍선 없이 목소리만
ERROR_LINES = {  # (강아지가 하는 말, 알림 줄)
    "key": ("앗, 제 열쇠가 맞지 않아요.", "API 키가 없거나 틀렸어요. 설정에서 확인하세요."),
    "quota": ("오늘은 대답을 너무 많이 했나 봐요. 잠깐 쉬었다가 다시 물어봐 주세요.", "요금 한도나 사용량 제한에 걸렸어요."),
    "network": ("인터넷이 끊긴 것 같아요.", "인터넷 연결을 확인하세요."),
    "timeout": ("생각이 너무 길어졌어요. 다시 물어봐 주시겠어요?", "답이 늦어요. 생각 깊이를 낮춰 보세요."),
    "other": ("앗, 문제가 생겼어요.", "{detail}"),
}
CUT_LINE = "앗, 말하다가 연결이 끊겼어요."
FIRST_TOKEN_TIMEOUT = {"low": 45.0, "mid": 90.0, "high": 150.0}  # 첫 글자까지
STALL_TIMEOUT = 30.0  # 답이 오다가 새 글이 없으면
BUBBLE_LINGER = 3.0  # 다 말한 뒤 말풍선이 남는 시간

IDLE, READING, THINKING, SPEAKING, ERROR = "idle", "reading", "thinking", "speaking", "error"


class VoicePort(Protocol):
    def voices(self) -> list: ...
    def speak(self, text: str, voice_id: str | None, speed: float, tag=None,
              output_id: str | None = None) -> None: ...
    def stop(self) -> None: ...


class Clock(Protocol):
    def now(self) -> float: ...
    def call_later(self, seconds: float, fn: Callable[[], None]): ...  # 돌려준 것의 cancel()로 취소


def _noop(*_args):
    pass


@dataclass
class _Answer:
    tag: tuple
    question: str
    effort: str
    splitter: SentenceSplitter = field(default_factory=SentenceSplitter)
    spoken: list[str] = field(default_factory=list)
    cancel: object = None  # LLM 스트림을 멈추는 Event
    timers: list = field(default_factory=list)
    stall: object = None
    first_token: bool = False
    error: LLMError | None = None
    cut: bool = False


class Session:
    def __init__(self, settings: Settings, voice: VoicePort | None, clock: Clock,
                 link_factory: Callable | None = None, edits: Edits | None = None,
                 llm_start: Callable | None = None):
        self.settings = settings
        self.voice = voice
        self.clock = clock
        self.link_factory = link_factory  # (on_change, on_error) -> 연동 객체(goto_slide, close)
        # (제공자, 키, Request, on_chunk, on_done, on_error) -> 취소 Event. 콜백은 화면 스레드에서 불려야 한다
        self.llm_start = llm_start
        self.edits_store = edits if edits is not None else Edits(settings.folder)
        self.voice_list = voice.voices() if voice is not None else []
        self.deck: Deck | None = None
        self.deck_mtime = 0.0
        self.current = -1  # 지금 장 (0부터)
        self.edits: dict[int, str] = {}  # 슬라이드 번호 -> 고친 대본
        self.source_changed: set[int] = set()  # 고친 뒤 원래 글이 바뀐 장 번호
        self.token = 0  # 읽기를 시작하거나 멈출 때마다 1씩 늘어난다. 늦게 온 알림을 거른다
        self.reading: tuple[int, int] | None = None  # (token, 읽는 장 위치)
        self.state = IDLE
        self.link = None
        self.ppt_state: PptState | None = None
        self.link_error = ""
        self.memory = Memory()
        self.captions: dict[int, list[str]] = {}  # 장마다 그림 캡션(근거 묶음에 넣는다)
        self.answer: _Answer | None = None
        self._answer_seq = 0
        self.bubble = False  # 말풍선이 떠 있나. 떠 있는 동안 강아지는 그 자리에 머문다
        self.sweat = False  # 오류를 말하는 중(땀방울)
        self._bubble_timer = None

        # 화면이 덮어쓰는 알림
        self.on_state: Callable[[str], None] = _noop
        self.on_slide: Callable[[int], None] = _noop
        self.on_deck: Callable[[Deck | None], None] = _noop
        self.on_notice: Callable[[str], None] = _noop  # 알림 줄
        self.on_message: Callable[[str, str], None] = _noop  # (종류 "warning"/"error"/"info", 문구) 대화상자
        self.on_link: Callable[[str], None] = _noop  # 연동 칩 문구
        self.on_pose: Callable[[str], None] = _noop  # 강아지 자세 요청 ("happy")
        self.on_script: Callable[[int], None] = _noop  # 대본이 바뀐 장(-1이면 모든 장). 대본 소리를 다시 만든다
        self.on_bubble: Callable[[bool], None] = _noop  # 말풍선 보이기·숨기기
        self.on_question: Callable[[str], None] = _noop  # 질문창 글("" 비우기, 글이면 다시 채우기)
        self.on_shake: Callable[[], None] = _noop  # 원 버튼 흔들기

    # ------------------------------------------------------------ 음성과 설정

    def voice_id(self) -> str | None:
        """설정의 음성 이름에 맞는 id. 없으면 한국어 음성, 그것도 없으면 첫 음성."""
        name = self.settings["voice"]
        v = (next((v for v in self.voice_list if v.name == name), None)
             or next((v for v in self.voice_list if v.is_korean), None)
             or (self.voice_list[0] if self.voice_list else None))
        return v.id if v else None

    def output_id(self) -> str | None:
        out = self.settings["output"]
        return out["id"] if out else None

    def set_options(self, **values) -> None:
        """설정을 바꾸고 바로 저장한다. 읽을 내용이 바뀌면 대본도 다시 보인다."""
        source_changed = "source" in values and values["source"] != self.settings["source"]
        self.settings.set(**values)
        if source_changed and self.deck is not None:
            self._load_edits()
            self.on_script(-1)  # 모든 장의 대본이 바뀌었다
            self.on_slide(self.current)

    def cycle_speed(self) -> float:
        speed = self.settings["speed"]
        nxt = SPEEDS[(SPEEDS.index(speed) + 1) % len(SPEEDS)] if speed in SPEEDS else SPEEDS[0]
        self.settings.set(speed=nxt)
        return nxt

    def _set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self.on_state(state)

    # ------------------------------------------------------------ 읽기

    def speak_slide(self, i: int) -> None:
        if self.voice is None or self.deck is None or not (0 <= i < len(self.deck.slides)):
            return
        text = to_speech(self.script_for(i))
        self.token += 1
        self.reading = (self.token, i)
        self._set_state(READING)
        if not text:
            self.voice.stop()
            tok = self.token
            self.clock.call_later(EMPTY_SLIDE_PAUSE, lambda: self.voice_done(tok, True))
            return
        self.voice.speak(text, self.voice_id(), self.settings["speed"], tag=self.token,
                         output_id=self.output_id())

    def read_current(self) -> bool:
        if self.reading is not None or self.deck is None or not self.deck.slides:
            return False
        self.speak_slide(max(self.current, 0))
        return True

    def toggle_read(self) -> None:
        """[읽기/정지]: 무엇이든 말하는 중이면(대본이든 답이든) 멈추고, 아니면 지금 장을 읽는다."""
        if self.reading is not None or self.state in (READING, SPEAKING, THINKING):
            self.stop()
        else:
            self.read_current()

    def stop(self) -> None:
        self.token += 1
        self.reading = None
        if self.answer is not None:
            self._drop_answer()
            self._set_bubble(False)
        if self.voice is not None:
            self.voice.stop()
        self._set_state(IDLE)

    def voice_done(self, tag, completed: bool) -> None:
        """음성이 한 장(또는 답 하나)을 끝냈다. completed는 끝까지 읽었는지다."""
        if self.answer is not None and tag == self.answer.tag:
            self._answer_spoken(completed)
            return
        if self.reading is None or self.reading[0] != tag:
            return  # 그 사이 다른 장을 읽기 시작했거나 멈춤
        i = self.reading[1]
        self.reading = None
        if not completed or not self.settings["auto_next"]:
            self._set_state(IDLE)
            return
        nxt = self._next_index(i)
        if nxt is None:
            self._set_state(IDLE)
            self.on_pose("happy")  # 자동 발표가 마지막 장까지 끝남
            return
        self.select(nxt, sync_ppt=True)
        self.speak_slide(nxt)

    def voice_error(self, tag, _message: str) -> None:
        if self.answer is not None and tag == self.answer.tag:
            self._drop_answer()  # 답의 글은 이미 말풍선에 있다
            self._set_state(IDLE)
            self.on_notice(VOICE_FAILED)
            self._linger_bubble()
            return
        if self.reading is not None and self.reading[0] == tag:
            self.reading = None
            self._set_state(IDLE)
            self.on_notice(VOICE_FAILED)

    def voice_started(self, tag, _index: int) -> None:
        """답의 첫 문장이 소리 나기 시작하면 "말하는 중"으로 바꾸고 말풍선을 띄운다."""
        if self.answer is not None and tag == self.answer.tag and self.state == THINKING:
            self._set_state(SPEAKING)
            self._set_bubble(True)

    def cloud_voice_failed(self, provider: str, kind: str) -> None:
        """클라우드 음성이 실패해 운영체제 음성으로 이어 읽는다. 키 문제·한도면 키를 다시 확인할 때까지 쓰지 않는다."""
        if kind in ("key", "quota"):
            self.settings.set_for("key_ok", provider, False)
        text = {"key": CLOUD_KEY, "quota": CLOUD_QUOTA}.get(kind, CLOUD_OTHER)
        self.on_notice(text.format(provider=PROVIDER_NAMES.get(provider, provider)))

    def cloud_voice_chosen(self, provider: str, voice) -> None:
        """ElevenLabs 목소리를 고르지 않았을 때 엔진이 고른 첫 목소리를 저장한다."""
        if provider == "elevenlabs":
            cloud = {**self.settings["cloud_voice"]}
            cloud["elevenlabs"] = {**cloud["elevenlabs"], "voice_id": voice.id, "voice_name": voice.name}
            self.settings.set(cloud_voice=cloud)

    def _next_index(self, i: int) -> int | None:
        for j in range(i + 1, len(self.deck.slides)):
            if not self.deck.slides[j].hidden:  # 숨긴 장은 슬라이드 쇼처럼 건너뛴다
                return j
        return None

    # ------------------------------------------------------------ 파일과 장

    # ------------------------------------------------------------ 질의응답

    def ask(self, question: str, effort: str = "low") -> bool:
        """질문을 보낸다. 읽던 것과 이전 답을 멈추고 "생각 중"이 된다."""
        q = (question or "").strip()
        if not q:
            return False
        self.stop()
        self._answer_seq += 1
        ans = _Answer(("answer", self._answer_seq), q, effort if effort in FIRST_TOKEN_TIMEOUT else "low")
        self.answer = ans
        self._set_state(THINKING)
        provider = self.settings["provider"]
        key = self.settings["keys"].get(provider, "")
        if not key or self.llm_start is None:
            self._llm_error(ans.tag, LLMError("key", ""))
            return True
        showing = None
        if self.link is not None and self.ppt_state is not None and self.ppt_state.mode in ("show", "edit"):
            showing = self.ppt_state.index
        req = Request(self.settings["models"][provider], ans.effort, system_prompt(self.settings["persona"]),
                      grounding(self.deck, self.edits, self.captions) if self.deck is not None else "",
                      self.memory.turns(), question_text(q, showing))
        for after, line in WAIT_LINES:
            ans.timers.append(self.clock.call_later(after, lambda a=ans, t=line: self._wait_line(a, t)))
        ans.timers.append(self.clock.call_later(
            FIRST_TOKEN_TIMEOUT[ans.effort], lambda a=ans: self._timeout(a, first=True)))
        tag = ans.tag
        ans.cancel = self.llm_start(provider, key, req, lambda text: self._llm_chunk(tag, text),
                                    lambda: self._llm_done(tag), lambda e: self._llm_error(tag, e))
        return True

    def _wait_line(self, ans: _Answer, line: str) -> None:
        if ans is self.answer and not ans.first_token and self.voice is not None:
            self.voice.speak(line, self.voice_id(), self.settings["speed"], tag=("wait", line),
                             output_id=self.output_id())

    def _timeout(self, ans: _Answer, first: bool) -> None:
        if ans is self.answer and (not first or not ans.first_token):
            self._llm_error(ans.tag, LLMError("timeout", ""))

    def _llm_chunk(self, tag, text: str) -> None:
        ans = self.answer
        if ans is None or ans.tag != tag or ans.error is not None:
            return
        if not ans.first_token:
            ans.first_token = True
            for t in ans.timers:
                t.cancel()
            ans.timers = []
        if ans.stall is not None:
            ans.stall.cancel()
        ans.stall = self.clock.call_later(STALL_TIMEOUT, lambda a=ans: self._timeout(a, first=False))
        for sentence in ans.splitter.feed(text):
            self._say(ans, sentence)

    def _say(self, ans: _Answer, sentence: str) -> None:
        text = to_speech(sentence)  # 글머리 기호를 지운다
        if not text or self.voice is None:
            return
        if not ans.spoken:
            self.voice.begin_answer(ans.tag, self.voice_id(), self.settings["speed"], self.output_id())
        ans.spoken.append(text)
        self.voice.add_sentence(text)

    def _llm_done(self, tag) -> None:
        ans = self.answer
        if ans is None or ans.tag != tag or ans.error is not None:
            return
        if ans.stall is not None:
            ans.stall.cancel()
        for sentence in ans.splitter.finish():
            self._say(ans, sentence)
        if not ans.spoken:
            self._llm_error(tag, LLMError("other", "빈 답"))
            return
        self.voice.end_answer()

    def _llm_error(self, tag, error: LLMError) -> None:
        """강아지는 땀방울을 얹고 짧게 말하고, 원 버튼이 흔들리고, 알림 줄이 뜨고, 질문을 질문창에 다시 채운다."""
        ans = self.answer
        if ans is None or ans.tag != tag or ans.error is not None:
            return
        ans.error = error
        self._stop_llm(ans)
        speech, notice = ERROR_LINES.get(error.kind, ERROR_LINES["other"])
        self.on_shake()
        self.on_notice(notice.format(detail=error.detail or speech))
        self.on_question(ans.question)
        if ans.spoken:  # 답하다가 끊김: 이미 넣은 문장까지 말하고 끊겼다고 말한다
            ans.cut = True
            self.voice.add_sentence(CUT_LINE)
            self.voice.end_answer()
            return
        self.sweat = True
        if self.voice is None:
            self._answer_spoken(False)
            return
        self.voice.begin_answer(ans.tag, self.voice_id(), self.settings["speed"], self.output_id())
        self.voice.add_sentence(speech)
        self.voice.end_answer()

    def _answer_spoken(self, completed: bool) -> None:
        ans = self.answer
        self.answer = None
        self.sweat = False
        self._stop_llm(ans)
        self._set_state(IDLE)
        if ans.error is None and completed:
            self.memory.add(ans.question, " ".join(ans.spoken))
            self.on_pose("happy")
            self.on_question("")
        elif ans.cut:
            self.memory.add(ans.question, " ".join(ans.spoken), cut=True)
        if completed:
            self._linger_bubble()
        else:
            self._set_bubble(False)

    def _stop_llm(self, ans: _Answer | None) -> None:
        if ans is None:
            return
        if ans.cancel is not None:
            ans.cancel.set()
        for t in ans.timers + ([ans.stall] if ans.stall is not None else []):
            t.cancel()
        ans.timers, ans.stall = [], None

    def _drop_answer(self) -> None:
        ans, self.answer = self.answer, None
        self.sweat = False
        self._stop_llm(ans)

    def _set_bubble(self, visible: bool) -> None:
        if self._bubble_timer is not None:
            self._bubble_timer.cancel()
            self._bubble_timer = None
        if visible != self.bubble:
            self.bubble = visible
            self.on_bubble(visible)

    def _linger_bubble(self) -> None:
        if self.bubble:
            if self._bubble_timer is not None:
                self._bubble_timer.cancel()
            self._bubble_timer = self.clock.call_later(BUBBLE_LINGER, lambda: self._set_bubble(False))

    # ------------------------------------------------------------ 파일과 장

    def open_file(self, path, keep_position: bool = False) -> bool:
        path = Path(path)
        if path.suffix.lower() in (".ppt", ".pps", ".key"):
            self.on_message("warning", OLD_FORMAT.format(name=path.name))
            return False
        try:
            deck = load_deck(path)
        except Exception as e:
            self.on_message("error", OPEN_FAILED.format(path=path, error=e))
            return False
        self.stop()
        position = self.current if keep_position else 0
        if self.deck is None or not _same_path(self.deck.path, path):
            self.memory.clear()  # 다른 발표 자료면 대화 기억을 잊는다
        self.deck = deck
        self.deck_mtime = _mtime(path)
        self._load_edits()
        self.current = -1
        self.on_deck(deck)
        self.select(min(max(position, 0), len(deck.slides) - 1))
        return True

    def select(self, i: int, user: bool = False, sync_ppt: bool = False) -> None:
        """i번째(0부터) 장을 지금 장으로 한다.

        user=True: 발표자가 직접 고름 -> 읽던 것을 멈추고 PowerPoint 쇼도 같은 장으로 넘긴다.
        sync_ppt=True: PowerPoint 쇼만 같은 장으로 넘긴다(자동 발표).
        """
        if self.deck is None or not (0 <= i < len(self.deck.slides)):
            return
        self.current = i
        self.on_slide(i)
        if user:
            self.stop()
        if (user or sync_ppt) and self.link and self.ppt_state and self.ppt_state.mode == "show":
            self.link.goto_slide(self.deck.slides[i].number)

    def script_for(self, i: int) -> str:
        slide = self.deck.slides[i]
        if slide.number in self.edits:
            return self.edits[slide.number]
        return slide.script(self.settings["source"])

    def set_edit(self, i: int, text: str) -> None:
        """대본 창에서 고친 대본을 저장한다. 원래 대본과 같으면 고친 것을 지운다."""
        if self.deck is None or not (0 <= i < len(self.deck.slides)):
            return
        slide = self.deck.slides[i]
        original = slide.script(self.settings["source"])
        self.source_changed.discard(slide.number)
        if text.strip() == original.strip():
            self.edits.pop(slide.number, None)
            self.edits_store.remove(self.deck.path, slide.number)
        else:
            self.edits[slide.number] = text
            self.edits_store.put(self.deck.path, slide.number, text, original)
        self.on_script(i)

    def reset_edit(self, i: int) -> None:
        if self.deck is None or not (0 <= i < len(self.deck.slides)):
            return
        number = self.deck.slides[i].number
        self.edits.pop(number, None)
        self.source_changed.discard(number)
        self.edits_store.remove(self.deck.path, number)
        self.on_script(i)
        self.on_slide(self.current)

    def _load_edits(self) -> None:
        stored = self.edits_store.for_deck(self.deck.path)
        by_number = {s.number: s for s in self.deck.slides}
        self.edits = {n: e["text"] for n, e in stored.items() if n in by_number}
        self.source_changed = {n for n, e in stored.items() if n in by_number
                               and Edits.source_changed(e, by_number[n].script(self.settings["source"]))}

    # ------------------------------------------------------------ PowerPoint 연동

    def set_link(self, on: bool) -> bool:
        if not on:
            if self.link is not None:
                self.link.close()
            self.link = None
            self.ppt_state = None
            self.on_link(CHIP_OFF)
            return False
        if self.link is not None:
            return True
        if self.link_factory is None:
            return False
        try:
            self.link = self.link_factory(self.ppt_changed, self.ppt_error)
        except LinkError as e:
            self.on_message("error", str(e))
            self.on_link(CHIP_OFF)
            return False
        self.ppt_state = None
        self.link_error = ""
        self.on_link(CHIP_SEARCHING)
        return True

    def ppt_changed(self, st: PptState) -> None:
        if self.link is None:
            return  # 연동을 끈 뒤 늦게 온 알림
        prev = self.ppt_state
        self.ppt_state = st
        self.link_error = ""
        first = prev is None  # 연동을 막 켰을 때는 화면만 맞추고 읽지는 않는다
        if st.mode == "none":
            self.on_link(CHIP_NONE)
            return
        self.on_link((CHIP_SHOW if st.mode == "show" else CHIP_EDIT).format(n=st.index or "-"))
        if prev and prev.mode == "show" and st.mode != "show":
            self.stop()  # 쇼가 끝나면 멈춘다

        loaded = self._follow_file(st.path)
        if loaded is None or st.index is None or self.deck is None:
            return
        i = st.index - 1
        if not (0 <= i < len(self.deck.slides)):
            return
        entered_show = st.mode == "show" and (prev is None or prev.mode != "show")
        if i == self.current and not loaded and not entered_show:
            return  # 이 프로그램이 넘긴 장이라 이미 맞춰져 있음
        self.select(i)
        if st.mode != "show" or first or loaded:
            return
        if self.state in (THINKING, SPEAKING):
            return  # 질의응답 중에는 지금 장만 맞추고 읽지 않는다
        if self.settings["read_on_change"]:
            self.speak_slide(i)
        elif self.reading is not None and self.reading[1] != i:
            self.stop()

    def ppt_error(self, message: str) -> None:
        if self.link is None:
            return
        self.link_error = message
        self.on_link(CHIP_LOST)
        self.on_notice(LINK_LOST)
        if self.reading is not None and self.settings["auto_next"]:
            self.stop()

    def _follow_file(self, ppt_path: str) -> bool | None:
        """PowerPoint에 열린 파일을 불러온다. 새로 불러왔으면 True, 이미 열려 있으면 False, 못 하면 None."""
        local = resolve_local_path(ppt_path)
        if local is None:
            if self.deck is not None and self.deck.name.lower() == _basename(ppt_path).lower():
                return False  # 경로는 모르지만 같은 이름의 파일을 이미 열어 두었음
            self.on_message("warning", UNKNOWN_PATH.format(name=_basename(ppt_path)))
            return None
        if self.deck is not None and _same_path(self.deck.path, local):
            if _mtime(local) != self.deck_mtime:  # PowerPoint에서 고치고 저장했으면 다시 읽는다
                if self.open_file(local, keep_position=True):
                    self.on_message("info", RELOADED)
            return False
        return True if self.open_file(local) else None

    # ------------------------------------------------------------ 끝내기

    def shutdown(self) -> None:
        """[끝내기]: 읽기를 멈추고 연동을 닫고 설정을 저장한다. 고친 대본은 고칠 때마다 저장했다."""
        self.stop()
        if self.link is not None:
            self.link.close()
            self.link = None
        self.settings.save()


def _basename(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def _same_path(a, b) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _mtime(path) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0
