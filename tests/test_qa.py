"""질의응답 시험. 지금은 문장 자르기(대본 읽기와 함께 씀)만 있다."""
from __future__ import annotations

from ppt_reader.qa import SentenceSplitter, split_sentences


def test_numbers_are_not_cut():
    assert split_sentences("속도가 3.5배 빨라요. 버전 2.0도 나왔어요") == ["속도가 3.5배 빨라요.", "버전 2.0도 나왔어요"]


def test_closing_quotes_and_brackets_stay():
    assert split_sentences('그는 "좋아요." 라고 했다. (정말이에요!) 끝') == [
        '그는 "좋아요."', "라고 했다.", "(정말이에요!)", "끝"]


def test_newline_and_marks():
    assert split_sentences("첫 줄\n\n둘째 줄이에요? 네. 음... 그렇군요… 알겠어요!") == [
        "첫 줄", "둘째 줄이에요?", "네.", "음...", "그렇군요…", "알겠어요!"]


def test_no_space_after_mark_is_not_an_end():
    assert split_sentences("정말요?!그렇다니까요") == ["정말요?!그렇다니까요"]


def test_stream_waits_for_what_comes_next():
    sp = SentenceSplitter()
    assert sp.feed("안녕하세요.") == []  # 뒤에 3.5처럼 숫자가 올 수도 있어 기다린다
    assert sp.feed(" 반가워") == ["안녕하세요."]
    assert sp.feed("요. 오늘은") == ["반가워요."]
    assert sp.feed(" 3.") == []
    assert sp.feed("5배") == []
    assert sp.finish() == ["오늘은 3.5배"]
    assert sp.finish() == []


# ---------------------------------------------------------------- 근거 묶음, 지침, 기억

from pathlib import Path  # noqa: E402

from ppt_reader.qa import BASE_SYSTEM, Memory, grounding, question_text, system_prompt  # noqa: E402
from ppt_reader.slides import load_deck  # noqa: E402

SAMPLE = Path(__file__).resolve().parent.parent / "sample" / "sample_presentation.pptx"


def test_grounding_contents_and_order():
    deck = load_deck(SAMPLE)
    g = grounding(deck, {2: "고친 대본입니다"}, {3: ["막대 그래프", ""]})
    lines = g.splitlines()
    assert lines[0] == '<자료 파일="sample_presentation.pptx" 장수="6">' and lines[-1] == "</자료>"
    assert g.index('<슬라이드 번호="1"') < g.index('<슬라이드 번호="2"') < g.index('<슬라이드 번호="6"')
    assert '<슬라이드 번호="4" 제목=' in g and '숨김="예">' in g  # 숨긴 장도 넣고 표시한다
    assert "고친 대본: 고친 대본입니다" in g and "그림 1: 막대 그래프" in g and "그림 2:" not in g
    assert "지금 화면" not in g  # 바뀌는 지금 장은 근거가 아니라 질문 쪽에 넣는다
    assert grounding(deck, {}) == grounding(deck, {})  # 바뀌지 않아 캐시된다


def test_system_and_question():
    assert system_prompt("") == BASE_SYSTEM
    s = system_prompt("  반말로  ")
    assert s.startswith(BASE_SYSTEM) and "<개인 지침>\n반말로\n</개인 지침>" in s
    assert "1. 자료에 없는 내용은 자료에 없다고 밝힌다." in s and "8문장을 넘기지 않는다" in s
    assert question_text("왜요?", None) == "왜요?" and question_text("왜요?", 4) == "(지금 화면: 4번 슬라이드) 왜요?"


def test_memory_keeps_last_six_and_marks_cut():
    m = Memory()
    for i in range(8):
        m.add(f"질문{i}", f"답{i}")
    assert [q for q, _ in m.turns()] == [f"질문{i}" for i in range(2, 8)]
    m.add("끊긴 질문", "답하다가", cut=True)
    assert m.turns()[-1] == ("끊긴 질문", "답하다가 (끊김)")
    m.clear()
    assert m.turns() == []
