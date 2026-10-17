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
