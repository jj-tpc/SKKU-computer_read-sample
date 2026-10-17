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
