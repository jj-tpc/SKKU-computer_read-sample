"""질의응답 흐름과 오류 반응 시험. 가짜 LLM과 가짜 시계로 시간이 걸리는 규칙을 본다."""
from __future__ import annotations

from pathlib import Path

import pytest
from fakes import FakeAnswerVoice, FakeClock, FakeLink, FakeLLM

from ppt_reader import session as session_mod
from ppt_reader.link import PptState
from ppt_reader.llm.base import LLMError
from ppt_reader.session import Session
from ppt_reader.settings import Settings

SAMPLE = Path(__file__).resolve().parent.parent / "sample" / "sample_presentation.pptx"


@pytest.fixture
def qa(app_home):
    settings = Settings(app_home)
    settings.set_for("keys", "claude", "test-key")
    clock, llm, voice = FakeClock(), FakeLLM(), FakeAnswerVoice()
    s = Session(settings, voice, clock, link_factory=FakeLink, llm_start=llm)
    s.open_file(SAMPLE)
    s.log = {"notice": [], "question": [], "shake": 0, "pose": [], "bubble": [], "state": []}
    s.on_notice = s.log["notice"].append
    s.on_question = s.log["question"].append
    s.on_pose = s.log["pose"].append
    s.on_bubble = s.log["bubble"].append
    s.on_state = s.log["state"].append

    def shake():
        s.log["shake"] += 1

    s.on_shake = shake
    s.clock, s.llm, s.fake_voice = clock, llm, voice
    return s


def speak_out(s):
    """음성이 지금 답을 다 말한 것으로 처리."""
    tag = s.fake_voice.answers[-1]["tag"]
    s.voice_started(tag, 0)
    s.voice_done(tag, True)


def test_answer_flow(qa):
    assert qa.ask("인공지능이 뭐예요?", "mid")
    call = qa.llm.last
    assert qa.state == "thinking" and call["provider"] == "claude" and call["key"] == "test-key"
    req = call["req"]
    assert req.effort == "mid" and req.max_tokens == 8192 and req.model == "claude-haiku-5-5"
    assert req.question == "인공지능이 뭐예요?" and req.grounding.startswith('<자료 파일="sample_presentation.pptx"')
    call["chunk"]("- 인공지능은 3.5배")
    call["chunk"](" 빠르게 배우는 프로그램이에요. 그래서")
    ans = qa.fake_voice.answers[-1]
    assert ans["sentences"] == ["인공지능은 3.5배 빠르게 배우는 프로그램이에요."]  # 글머리 기호를 지우고 문장마다
    qa.voice_started(ans["tag"], 0)
    assert qa.state == "speaking" and qa.log["bubble"] == [True]
    call["chunk"](" 쓸모가 많아요")
    call["done"]()
    assert ans["sentences"][-1] == "그래서 쓸모가 많아요." and ans["ended"]
    qa.voice_done(ans["tag"], True)
    assert qa.state == "idle" and qa.log["pose"] == ["happy"] and qa.log["question"] == [""]
    assert qa.memory.turns() == [("인공지능이 뭐예요?", "인공지능은 3.5배 빠르게 배우는 프로그램이에요. 그래서 쓸모가 많아요.")]
    assert qa.bubble
    qa.clock.advance(3.0)  # 다 말한 뒤 3초 남았다가 사라진다
    assert not qa.bubble and qa.log["bubble"] == [True, False]


def test_ask_stops_reading_and_uses_memory_and_slide(qa):
    qa.read_current()
    assert qa.state == "reading"
    qa.ask("첫 질문")
    assert qa.reading is None and qa.state == "thinking"
    qa.llm.last["chunk"]("첫 답.")
    qa.llm.last["done"]()
    speak_out(qa)
    qa.set_link(True)
    qa.ppt_changed(PptState("show", 3, str(SAMPLE)))
    qa.settings.set(persona="반말로 짧게")
    qa.ask("둘째 질문")
    req = qa.llm.last["req"]
    assert req.turns == [("첫 질문", "첫 답.")]  # 대화 기억
    assert req.question == "(지금 화면: 3번 슬라이드) 둘째 질문"  # 연동 중이면 지금 장을 질문 앞에
    assert "<개인 지침>\n반말로 짧게\n</개인 지침>" in req.system


def test_new_question_cancels_previous(qa):
    qa.ask("하나")
    first = qa.llm.last
    qa.ask("둘")
    assert first["cancel"].is_set() and len(qa.llm.calls) == 2
    first["chunk"]("늦게 온 답.")  # 닫은 스트림의 글은 버린다
    assert qa.fake_voice.answers == []


def test_wait_lines(qa):
    qa.ask("천천히 답해 주세요")
    qa.clock.advance(7.9)
    assert qa.fake_voice.spoken == []
    qa.clock.advance(0.2)
    assert [t[0] for t in qa.fake_voice.spoken] == ["조금만 기다려 주세요"]
    qa.clock.advance(22.0)
    assert [t[0] for t in qa.fake_voice.spoken][-1] == "아직 생각하고 있어요"
    assert qa.fake_voice.answers == []  # 말풍선 없이 목소리만(답 흐름이 아니다)


def test_no_wait_line_after_first_token(qa):
    qa.ask("질문")
    qa.llm.last["chunk"]("답이")
    qa.clock.advance(31.0 - 0.5)
    assert qa.fake_voice.spoken == []


@pytest.mark.parametrize("effort, limit", [("low", 45.0), ("mid", 90.0), ("high", 150.0)])
def test_first_token_timeout(qa, effort, limit):
    qa.ask("어려운 질문", effort)
    call = qa.llm.last
    qa.clock.advance(limit - 0.1)
    assert qa.answer.error is None
    qa.clock.advance(0.2)
    assert call["cancel"].is_set()
    assert qa.log["notice"][-1] == "답이 늦어요. 생각 깊이를 낮춰 보세요."
    assert qa.log["shake"] == 1 and qa.log["question"][-1] == "어려운 질문"  # 질문을 다시 채운다
    ans = qa.fake_voice.answers[-1]
    assert ans["sentences"] == ["생각이 너무 길어졌어요. 다시 물어봐 주시겠어요?"] and qa.sweat
    speak_out(qa)
    assert qa.state == "idle" and not qa.sweat and qa.memory.turns() == []


def test_stall_cuts_answer(qa):
    qa.ask("질문")
    call = qa.llm.last
    call["chunk"]("앞부분 문장입니다. 뒷")
    qa.clock.advance(29.0)
    call["chunk"]("부분")  # 새 글이 오면 30초를 다시 센다
    qa.clock.advance(29.0)
    assert qa.answer.error is None
    qa.clock.advance(1.1)
    ans = qa.fake_voice.answers[-1]
    assert ans["sentences"] == ["앞부분 문장입니다.", session_mod.CUT_LINE] and ans["ended"]
    speak_out(qa)
    # 기억에는 끊긴 답만 남기고 끝에 (끊김)을 붙인다. 강아지가 덧붙인 말은 답이 아니다
    assert qa.memory.turns() == [("질문", "앞부분 문장입니다. (끊김)")]


@pytest.mark.parametrize("kind, speech, notice", [
    ("key", "앗, 제 열쇠가 맞지 않아요.", "API 키가 없거나 틀렸어요. 설정에서 확인하세요."),
    ("quota", "오늘은 대답을 너무 많이 했나 봐요. 잠깐 쉬었다가 다시 물어봐 주세요.", "요금 한도나 사용량 제한에 걸렸어요."),
    ("network", "인터넷이 끊긴 것 같아요.", "인터넷 연결을 확인하세요."),
    ("other", "앗, 문제가 생겼어요.", "500 서버가 바빠요"),
])
def test_error_kinds(qa, kind, speech, notice):
    qa.ask("질문")
    qa.llm.last["error"](LLMError(kind, "500 서버가 바빠요"))
    assert qa.fake_voice.answers[-1]["sentences"] == [speech]
    assert qa.log["notice"][-1] == notice and qa.log["question"][-1] == "질문"


def test_missing_key_is_key_error(qa):
    qa.settings.set_for("keys", "claude", "")
    qa.ask("질문")
    assert qa.llm.calls == [] and qa.fake_voice.answers[-1]["sentences"] == ["앗, 제 열쇠가 맞지 않아요."]


def test_stop_during_answer(qa):
    qa.ask("질문")
    call = qa.llm.last
    call["chunk"]("답 문장. ")
    qa.voice_started(qa.fake_voice.answers[-1]["tag"], 0)
    qa.toggle_read()  # [읽기/정지]는 무엇이든 멈춘다
    assert call["cancel"].is_set() and qa.state == "idle" and not qa.bubble and qa.answer is None
    qa.toggle_read()  # 멈춘 뒤에 누르면 지금 장을 읽는다
    assert qa.state == "reading"
