"""Qt 화면 시험(pytest-qt, offscreen). 창이 뜨는지, 위성 버튼이 session을 부르는지 본다."""
from __future__ import annotations

from pathlib import Path

import pytest
from fakes import FakeClock, FakeLink, FakeVoice

pytest.importorskip("pytestqt")
from PySide6.QtCore import QPoint, Qt  # noqa: E402

from ppt_reader.session import Session  # noqa: E402
from ppt_reader.settings import DOGS, Settings  # noqa: E402
from ppt_reader.ui import app as app_mod  # noqa: E402
from ppt_reader.ui import dog as dog_mod  # noqa: E402
from ppt_reader.ui import orb as orb_mod  # noqa: E402

SAMPLE = Path(__file__).resolve().parent.parent / "sample" / "sample_presentation.pptx"


@pytest.fixture
def controller(qtbot, app_home, monkeypatch):
    monkeypatch.setattr(app_mod.QApplication, "quit", lambda: None)
    settings = Settings(app_home)
    session = Session(settings, FakeVoice(), FakeClock(), link_factory=FakeLink)
    session.open_file(SAMPLE)
    closed = []
    c = app_mod.Controller(settings, session, closers=[lambda: closed.append(True)])
    c.closed = closed
    c.start()
    qtbot.waitExposed(c.orb)
    yield c
    c._timer.stop()
    c.dog.close()
    c.orb.close()


def click(qtbot, orb, point):
    qtbot.mouseClick(orb, Qt.MouseButton.LeftButton, pos=point.toPoint() if hasattr(point, "toPoint") else point)


def open_satellites(qtbot, orb):
    click(qtbot, orb, orb_mod.CENTER)
    assert orb.is_open
    orb.tick(1.0, QPoint(-9999, -9999))  # 펼침 움직임을 끝낸다


def test_windows_show(controller):
    assert controller.dog.isVisible() and controller.orb.isVisible()
    flags = controller.orb.windowFlags()
    assert flags & Qt.WindowType.WindowStaysOnTopHint and flags & Qt.WindowType.WindowDoesNotAcceptFocus
    assert controller.dog.windowFlags() & Qt.WindowType.WindowTransparentForInput  # 강아지는 클릭 통과
    assert not controller.orb.windowFlags() & Qt.WindowType.WindowTransparentForInput


def test_satellite_read_and_speed(qtbot, controller, app_home):
    orb, session = controller.orb, controller.session
    open_satellites(qtbot, orb)
    click(qtbot, orb, orb._target(1))  # [읽기]
    assert session.state == "reading" and session.voice.spoken[-1][0].startswith("안녕하세요")
    click(qtbot, orb, orb._target(1))  # [정지]
    assert session.state == "idle"
    click(qtbot, orb, orb._target(2))  # [배속]
    assert orb.speed == 1.5 and Settings(app_home)["speed"] == 1.5


def test_satellites_collapse_after_4s_unless_hovered(qtbot, controller):
    orb = controller.orb
    open_satellites(qtbot, orb)
    over = orb.mapToGlobal(orb._target(0).toPoint())
    away = QPoint(-9999, -9999)
    for _ in range(10):
        orb.tick(0.5, over)  # 올려 둔 동안은 세지 않는다
    assert orb.is_open
    orb.tick(3.9, away)
    assert orb.is_open
    orb.tick(0.2, away)
    assert not orb.is_open


def test_quit_satellite_shuts_down(qtbot, controller):
    orb = controller.orb
    controller.session.read_current()
    open_satellites(qtbot, orb)
    click(qtbot, orb, orb._target(4))  # [끝내기]
    assert controller.session.state == "idle" and controller.closed == [True]
    assert not orb.isVisible()


def test_click_outside_buttons_is_ignored(qtbot, controller):
    orb = controller.orb
    click(qtbot, orb, QPoint(5, 5))
    assert not orb.is_open
    assert not orb.mask().contains(QPoint(5, 5))  # 투명한 곳은 마스크 밖이라 쇼로 통과한다


@pytest.mark.parametrize("dog", DOGS)
def test_sprite_sheets(qtbot, dog):
    rows = dog_mod.load_sheet(dog)
    assert len(rows) == dog_mod.SWEAT_ROW + 1 and all(len(r) == dog_mod.FRAMES for r in rows)
    assert all(not f.isNull() and f.width() == dog_mod.CELL for r in rows for f in r)


def test_dog_frames_follow_pose(qtbot):
    w = dog_mod.DogWindow()
    w.set_pose("walk")
    w.tick(0.26)  # 초당 8프레임 → 2번째 프레임
    assert w._cell() == (1, 2, -1)
    w.set_pose("talk")
    w.mouth, w.sweat = 3, True
    w.tick(0.3)
    assert w._cell()[:2] == (4, 3) and w._cell()[2] >= 0
    w.close()


def test_notice_and_shake(qtbot, controller):
    orb = controller.orb
    controller.session.on_notice("PowerPoint 연결이 끊겼어요")
    rect = orb._notice_rect()
    assert orb.mask().contains(rect.center().toPoint())  # 알림 줄 자리는 보인다
    assert rect.right() < orb_mod.CENTER.x() - orb_mod.R and rect.bottom() < orb_mod.CENTER.y()  # 원 버튼 왼쪽 위
    orb.tick(6.1, QPoint(-9999, -9999))
    assert orb._notice == "" and not orb.mask().contains(rect.center().toPoint())  # 6초 뒤 사라짐
    orb.shake()
    orb.grab()  # 흔들리는 중에도 그리기가 된다


def test_dog_waits_when_cursor_over_orb(qtbot, controller, monkeypatch):
    center = controller.orb.orb_center_global()
    monkeypatch.setattr(app_mod.QCursor, "pos", staticmethod(lambda: center))
    for _ in range(90):
        controller._last -= 1 / 30  # 프레임 사이가 1/30초 지난 것으로
        controller._frame()
    spot = app_mod.wait_spot((center.x(), center.y()), controller._area)
    assert controller.follower.pos == pytest.approx(spot, abs=3)
    assert controller.dog.pos().x() == pytest.approx(spot[0], abs=3)


def test_question_window_sends_and_cycles_effort(qtbot, controller):
    from fakes import FakeLLM

    llm = FakeLLM()
    controller.session.llm_start = llm
    controller.settings.set_for("keys", "claude", "k")
    open_satellites(qtbot, controller.orb)
    click(qtbot, controller.orb, controller.orb._target(0))  # [질문하기]
    q = controller.question
    assert q.isVisible() and not controller.orb.is_open and controller.orb.question_open
    pill = q._pill().center().toPoint()
    for expected in ("mid", "high", "low", "mid"):
        qtbot.mouseClick(q, Qt.MouseButton.LeftButton, pos=pill)
        assert q.effort == expected
    qtbot.keyClick(q.edit, Qt.Key.Key_Return)  # 빈 글은 보내지 않는다
    assert llm.calls == []
    q.edit.setText("인공지능이 뭐예요?")
    qtbot.keyClick(q.edit, Qt.Key.Key_Return)
    assert llm.last["req"].effort == "mid" and controller.session.state == "thinking"
    assert q.isVisible() and q.edit.text() == "인공지능이 뭐예요?"  # 보낸 뒤에도 남는다
    qtbot.keyClick(q.edit, Qt.Key.Key_Escape)
    assert not q.isVisible() and not controller.orb.question_open


def test_question_window_closes_on_esc_without_edit_focus(qtbot, controller):
    controller.open_question()
    q = controller.question
    assert q.isVisible()
    qtbot.keyClick(q, Qt.Key.Key_Escape)  # 입력 칸이 아니라 창이 Esc를 받아도 닫힌다
    assert not q.isVisible() and not controller.orb.question_open


def test_bubble_streams_words(qtbot, controller):
    b = controller.bubble
    controller.session.on_bubble(True)
    assert b.isVisible()
    b.set_text("안녕하세요 저는")
    b.tick(0.1)
    assert b.words == ["안녕하세요", "저는"]
    b.set_text("안녕하세요 저는 " + "아주 긴 문장을 계속 말하는 강아지입니다 " * 6)
    assert b._lines() > 3 and b._scroll_to == b._lines() - 3  # 세 줄을 넘으면 위로 밀린다
    b.tick(0.5)
    assert b._scroll == b._scroll_to
    b.grab()
    b.set_text("새 답")  # 앞이 달라지면 처음부터
    assert b.words == ["새", "답"]
    controller.session.on_bubble(False)
    assert not b.isVisible()


# ---------------------------------------------------------------- 설정 창, 대본 창

def test_first_run_opens_settings(qtbot, controller, app_home):
    w = controller.settings_window
    assert w is not None and w.isVisible() and w.windowTitle() == "설정 — PPT 읽어주기"
    assert not Settings(app_home).first_run  # 처음 실행 표시를 저장했다
    # 파일이 열려 있으니 아직 안 된 첫 카드(질의응답)만 펼친다
    assert [c.is_open for c in w.cards] == [False, False, True, False]
    assert w.hero_title.text() == "발표 준비 3 / 4" and w.cards[2].next_tag.isVisibleTo(w)


def test_windows_fit_small_screen(qtbot, controller):
    from PySide6.QtGui import QGuiApplication

    from ppt_reader.ui.app import TITLE_BAR

    avail = QGuiApplication.primaryScreen().availableGeometry()  # offscreen 화면은 800×600
    controller.open_settings()
    w = controller.settings_window
    assert w.height() <= avail.height() - TITLE_BAR and w.width() <= avail.width()
    assert avail.contains(w.frameGeometry().topLeft())


def test_settings_save_at_once(qtbot, controller, app_home):
    w = controller.settings_window
    w.auto_toggle.click()
    assert Settings(app_home)["auto_next"] is True and w.toast.isVisibleTo(w)  # 바로 저장하고 "저장됨"
    w.provider_seg.buttons["openai"].click()
    s = Settings(app_home)
    assert s["provider"] == "openai" and w.qa_key.owner == "openai"
    assert w.model_box.currentData() == "gpt-6-luna"
    w.dog_cards["beagle"].click()
    assert Settings(app_home)["dog"] == "beagle"
    w.engine_seg.buttons["gemini"].click()
    assert Settings(app_home)["voice_engine"] == "gemini" and not w.cloud_notice.isHidden()  # 키 확인 전 안내
    assert w.engine_stack.currentIndex() == 2


def test_key_check(qtbot, controller, app_home, monkeypatch):
    from ppt_reader.llm.base import LLMError

    class P:
        def __init__(self, ok):
            self.ok = ok

        def check_key(self):
            if not self.ok:
                raise LLMError("key", "bad")

    w = controller.settings_window
    monkeypatch.setattr(app_mod, "make_provider", lambda owner, key: P(key == "good-key"))
    w.qa_key.edit.setText("wrong-key")
    w.qa_key.check()
    qtbot.waitUntil(lambda: w.qa_key.result.text() == "✕ 키가 틀렸어요. 다시 확인하세요", timeout=3000)
    assert Settings(app_home)["keys"]["claude"] == "wrong-key" and not Settings(app_home)["key_ok"]["claude"]
    w.qa_key.edit.setText("good-key")
    w.qa_key.check()
    qtbot.waitUntil(lambda: w.qa_key.result.text() == "✓ 키가 맞아요", timeout=3000)
    assert Settings(app_home)["key_ok"]["claude"] and w.hero_title.text() == "발표 준비 끝! 🎉"


def test_script_window_edits(qtbot, controller):
    controller.open_script_window()
    sw = controller.script_window
    assert sw.isVisible() and sw.windowTitle() == "대본 — sample_presentation.pptx" and len(sw.cards) == 6
    sw.select(1, user=True)
    assert sw.heading.text() == "2. 인공지능이란?" and sw.status.text().startswith("자동으로 뽑은 대본")
    sw.editor.setPlainText("새로 고친 대본")
    sw.select(2, user=True)  # 다른 장으로 가면 저장한다
    assert controller.session.edits == {2: "새로 고친 대본"} and sw.cards[1].badges.startswith("✎")
    sw.select(1, user=True)
    assert sw.status.text().startswith("✎ 고친 대본") and sw.editor.toPlainText() == "새로 고친 대본"
    sw.reset_edit()
    assert controller.session.edits == {} and sw.status.text().startswith("자동으로 뽑은 대본")
    controller.session.select(4)  # 쇼가 넘어가면 따라 고른다
    assert sw.index == 4
    assert sw.cap_chip.text() == "캡션 꺼짐"


def test_caption_states(qtbot, controller):
    controller.settings.set(captions=True)
    controller.start_captions()
    assert controller.caption_view()[0] == "캡션 멈춤"  # 키 확인 전
    controller.caption_state = ("making", 2, 5, "")
    assert controller.caption_view()[:3] == ("캡션 만드는 중", "warn", "2 / 5")
    controller.caption_state = ("done", 5, 5, "")
    assert controller.caption_view()[0] == "캡션 완료" and controller.caption_view()[4]
