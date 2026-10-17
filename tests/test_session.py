"""읽기 흐름 시험. 옛 test_app_logic.py(tkinter)의 일곱 시험을 가짜 음성·연동·시계로 옮겼다."""
from __future__ import annotations

from pathlib import Path

import pytest
from fakes import FakeClock, FakeLink, FakeVoice

from ppt_reader import session as session_mod
from ppt_reader.link import PptState
from ppt_reader.session import Session
from ppt_reader.settings import Edits, Settings, text_hash

SAMPLE = Path(__file__).resolve().parent.parent / "sample" / "sample_presentation.pptx"


def make_session(home, voice=None, clock=None):
    s = Session(Settings(home), voice or FakeVoice(), clock or FakeClock(), link_factory=FakeLink)
    s.events = {"state": [], "pose": [], "notice": [], "message": [], "link": [], "slide": []}
    s.on_state = s.events["state"].append
    s.on_pose = s.events["pose"].append
    s.on_notice = s.events["notice"].append
    s.on_message = lambda kind, text: s.events["message"].append((kind, text))
    s.on_link = s.events["link"].append
    s.on_slide = s.events["slide"].append
    return s


@pytest.fixture
def session(app_home):
    if not SAMPLE.exists():
        pytest.skip("python tools/make_sample.py 를 먼저 실행하세요")
    s = make_session(app_home)
    assert s.open_file(SAMPLE)
    return s


def finish(s):
    """지금 읽는 것을 끝까지 읽은 것으로 처리."""
    s.voice_done(s.voice.spoken[-1][1], True)


def test_open_and_read(session):
    assert len(session.deck.slides) == 6 and session.current == 0
    assert session.voice_id() == "ko"  # 한국어 음성이 기본
    assert "발표하겠습니다" in session.script_for(0)
    session.read_current()
    text, _, voice = session.voice.spoken[-1]
    assert text.startswith("안녕하세요") and voice == "ko"
    assert session.state == "reading"
    finish(session)
    assert session.reading is None and session.current == 0  # 자동 발표가 꺼져 있으면 그대로
    assert session.state == "idle" and session.events["pose"] == []


def test_auto_next_skips_hidden_and_ends_happy(session):
    session.set_options(auto_next=True)
    session.read_current()
    visited = [session.current]
    for _ in range(5):
        if session.reading is None:
            break
        finish(session)
        visited.append(session.current)
    assert visited == [0, 1, 2, 4, 5, 5]  # 4번째(숨김)는 건너뜀, 마지막에서 멈춤
    assert session.reading is None and session.state == "idle"
    assert session.events["pose"] == ["happy"]  # 자동 발표가 끝나면 강아지가 기뻐한다


def test_empty_slide_pauses_then_moves_on(app_home):
    clock = FakeClock()
    s = make_session(app_home, clock=clock)
    s.open_file(SAMPLE)
    s.set_options(auto_next=True)
    s.set_edit(1, "   ")  # 읽을 글이 없는 장
    s.select(1)
    s.speak_slide(1)
    n = len(s.voice.spoken)
    clock.advance(1.4)
    assert s.current == 1 and len(s.voice.spoken) == n
    clock.advance(0.2)  # 1.5초 쉰 뒤 다음 장
    assert s.current == 2 and s.voice.spoken[-1][0].startswith("학교에서")


def test_edit_is_used_and_kept(session, app_home):
    session.set_edit(1, "에이아이는 인공지능입니다")
    assert session.edits == {2: "에이아이는 인공지능입니다"}
    again = make_session(app_home)  # 다시 켜도 남는다
    again.open_file(SAMPLE)
    assert again.edits == {2: "에이아이는 인공지능입니다"} and again.source_changed == set()

    session.select(1, user=True)
    session.read_current()
    assert session.voice.spoken[-1][0] == "에이아이는 인공지능입니다."
    session.stop()
    session.reset_edit(1)
    assert session.edits == {} and Edits(app_home).for_deck(SAMPLE) == {}


def test_edit_marks_changed_original(session, app_home):
    Edits(app_home).put(SAMPLE, 3, "고친 대본", "고칠 때의 원래 글")  # 지금 슬라이드 글과 다르다
    s = make_session(app_home)
    s.open_file(SAMPLE)
    assert s.script_for(2) == "고친 대본"  # 고친 대본은 그대로 쓴다
    assert s.source_changed == {3}  # 대본 창에 "원본이 바뀌었어요"
    s.set_edit(2, "다시 고침")
    assert s.source_changed == set()
    assert Edits(app_home).for_deck(SAMPLE)[3]["orig"] == text_hash(s.deck.slides[2].script("notes_first"))


def test_powerpoint_follow(session):
    assert session.set_link(True)
    link = session.link
    path = str(SAMPLE)
    session.ppt_changed(PptState("edit", 2, path))  # 연동 직후: 장만 맞춤
    assert session.current == 1 and not session.voice.spoken
    assert session.events["link"][-1] == "PowerPoint 연결됨 · 편집 화면 2번 장"
    session.ppt_changed(PptState("show", 2, path))  # 슬라이드 쇼 시작: 바로 읽기
    assert session.voice.spoken[-1][0].startswith("인공지능은")
    session.ppt_changed(PptState("show", 3, path))  # 발표자가 넘김
    assert session.current == 2 and session.voice.spoken[-1][0].startswith("학교에서")
    assert session.events["link"][-1] == "PowerPoint 연결됨 · 쇼 진행 중 3번 장"

    session.set_options(auto_next=True)
    finish(session)  # 다 읽으면 이 프로그램이 PowerPoint를 다음 장(숨김 4번 건너뛰고 5번)으로 넘김
    assert session.current == 4 and link.gotos == [5]
    n = len(session.voice.spoken)
    session.ppt_changed(PptState("show", 5, path))  # PowerPoint가 따라옴 -> 두 번 읽지 않음
    assert len(session.voice.spoken) == n

    session.select(0, user=True)  # 대본 창에서 직접 고르면 PowerPoint도 이동
    assert link.gotos == [5, 1] and session.reading is None

    session.read_current()
    session.ppt_changed(PptState("edit", 1, path))  # 쇼를 끝내면 읽기 멈춤
    assert session.reading is None
    session.set_link(False)
    assert link.closed and session.events["link"][-1] == "연동 꺼짐"


def test_slide_change_during_qa_only_moves(session):
    session.set_link(True)
    path = str(SAMPLE)
    session.ppt_changed(PptState("show", 1, path))
    n = len(session.voice.spoken)
    session.state = "thinking"  # 질의응답 중
    session.ppt_changed(PptState("show", 2, path))
    assert session.current == 1 and len(session.voice.spoken) == n  # 장만 맞추고 읽지 않는다


def test_link_lost_notifies_and_stops_auto(session):
    session.set_link(True)
    session.set_options(auto_next=True)
    session.read_current()
    session.ppt_error("PowerPoint 응답 없음")
    assert session.events["notice"] == [session_mod.LINK_LOST]
    assert session.events["link"][-1] == "PowerPoint 연결이 끊겼어요"
    assert session.reading is None and session.link_error == "PowerPoint 응답 없음"


def test_options_saved_at_once(session, app_home):
    session.set_options(source="body")
    assert Settings(app_home)["source"] == "body"  # 적용 단추 없이 바로 저장
    assert session.script_for(0).startswith("인공지능과 우리의 학교생활")  # 대본이 본문으로 바뀜
    session.set_options(voice="English")
    session.read_current()
    assert session.voice.spoken[-1][2] == "en"
    assert [session.cycle_speed() for _ in range(4)] == [1.5, 2.0, 5.0, 1.0]
    session.cycle_speed()
    assert Settings(app_home)["speed"] == 1.5  # 배속은 마지막 값을 기억한다


def test_output_device(session, app_home):
    session.read_current()
    assert session.voice.outputs_used[-1] is None  # 기본: 운영체제의 기본 장치
    session.stop()
    session.set_options(output={"id": "dev-earphones", "name": "헤드폰(Shokz)"})
    session.read_current()
    assert session.voice.outputs_used[-1] == "dev-earphones"
    session.shutdown()

    b = make_session(app_home)  # 고른 장치는 다음 실행 때도 유지된다
    b.open_file(SAMPLE)
    b.read_current()
    assert b.voice.outputs_used[-1] == "dev-earphones"  # 연결이 끊겨 있으면 재생 쪽이 기본 장치로 낸다


def test_powerpoint_unknown_file(session):
    session.set_link(True)
    session.ppt_changed(PptState("show", 1, "Presentation1"))
    assert "위치를 알 수 없습니다" in session.events["message"][-1][1]
    session.ppt_changed(PptState("show", 2, "https://d.docs.live.net/x/" + SAMPLE.name))
    assert session.current == 1  # 같은 이름의 파일이 열려 있으면 그대로 따라감


def test_toggle_read_and_voice_error(session):
    session.toggle_read()
    assert session.state == "reading"
    session.toggle_read()  # 말하는 중이면 멈춘다
    assert session.state == "idle" and session.reading is None
    session.toggle_read()
    session.voice_error(session.voice.spoken[-1][1], "장치 없음")
    assert session.state == "idle" and session.events["notice"] == [session_mod.VOICE_FAILED]


def test_open_old_format_and_broken(session, tmp_path):
    assert not session.open_file(tmp_path / "옛날.ppt")
    assert session.events["message"][-1][1].startswith("'옛날.ppt' 형식은 읽을 수 없습니다.")
    broken = tmp_path / "broken.pptx"
    broken.write_bytes(b"not a pptx")
    assert not session.open_file(broken)
    assert session.events["message"][-1][1].startswith("파일을 열 수 없습니다.\n")
    assert len(session.deck.slides) == 6  # 앞서 연 파일은 그대로


def test_cloud_voice_failure_notices(session, app_home):
    session.settings.set_for("key_ok", "elevenlabs", True)
    session.cloud_voice_failed("elevenlabs", "network")
    assert session.events["notice"][-1] == "ElevenLabs 목소리를 쓸 수 없어 운영체제 음성으로 읽어요."
    assert Settings(app_home)["key_ok"]["elevenlabs"]  # 인터넷 문제는 다음 장에서 다시 시도
    session.cloud_voice_failed("elevenlabs", "key")
    assert session.events["notice"][-1] == "ElevenLabs 키가 맞지 않아 운영체제 음성으로 읽어요."
    assert not Settings(app_home)["key_ok"]["elevenlabs"]  # 키를 다시 확인할 때까지 운영체제 음성
    session.cloud_voice_failed("gemini", "quota")
    assert session.events["notice"][-1] == "Gemini 사용량 한도라 운영체제 음성으로 읽어요."


def test_cloud_voice_chosen_is_saved(session, app_home):
    from ppt_reader.voice.engines import Voice

    session.cloud_voice_chosen("elevenlabs", Voice("a1", "Anna", ""))
    assert Settings(app_home)["cloud_voice"]["elevenlabs"]["voice_id"] == "a1"
    assert Settings(app_home)["cloud_voice"]["elevenlabs"]["voice_name"] == "Anna"


def test_script_changes_are_announced(session):
    changed = []
    session.on_script = changed.append
    session.set_edit(2, "새 대본")
    session.reset_edit(2)
    session.set_options(source="body")
    assert changed == [2, 2, -1]  # -1: 모든 장(대본 소리를 다시 만든다)
