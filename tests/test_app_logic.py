"""화면 로직 테스트. 실제 소리와 PowerPoint 대신 가짜 객체를 쓴다."""
import sys
import tkinter as tk
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ppt_reader.app as app_mod  # noqa: E402
from ppt_reader.link import PptState  # noqa: E402
from ppt_reader.tts import AudioOutput, Voice  # noqa: E402

SAMPLE = Path(__file__).resolve().parent.parent / "sample" / "sample_presentation.pptx"
SPEAKERS = AudioOutput("dev-speakers", "스피커(Realtek)")
EARPHONES = AudioOutput("dev-earphones", "헤드폰(Shokz)")


class FakeSpeaker:
    connected = [SPEAKERS, EARPHONES]

    def __init__(self, on_event):
        self.spoken = []  # (text, tag, voice_id)
        self.outputs_used = []
        self.stops = 0

    def voices(self):
        return [Voice("en", "English", "en_US"), Voice("ko", "Korean", "ko_KR")]

    def outputs(self):
        return list(self.connected)

    def default_output(self):
        return SPEAKERS

    def speak(self, text, voice_id=None, speed=1.0, tag=None, output_id=None):
        self.spoken.append((text, tag, voice_id))
        self.outputs_used.append(output_id)

    def stop(self):
        self.stops += 1

    def close(self):
        pass


class FakeLink:
    def __init__(self):
        self.gotos = []

    def goto_slide(self, n):
        self.gotos.append(n)

    def close(self):
        pass


def make_app():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("화면(디스플레이)이 없는 환경")
    root.withdraw()
    return app_mod.App(root, str(SAMPLE))


@pytest.fixture
def app(monkeypatch, tmp_path):
    if not SAMPLE.exists():
        pytest.skip("python tools/make_sample.py 를 먼저 실행하세요")
    monkeypatch.setattr(app_mod, "Speaker", FakeSpeaker)
    monkeypatch.setattr(app_mod, "SETTINGS_FILE", tmp_path / "settings.json")
    a = make_app()
    yield a
    try:
        a.root.destroy()
    except tk.TclError:
        pass  # 테스트 안에서 이미 닫음


def finish(a):
    """지금 읽는 것을 끝까지 읽은 것으로 처리."""
    tag = a.speaker.spoken[-1][1]
    a._on_read_finished(tag, True)


def test_open_and_read(app):
    assert len(app.deck.slides) == 6 and app.current == 0
    assert app.voice_var.get().startswith("Korean")  # 한국어 음성이 기본
    assert "발표하겠습니다" in app.text.get("1.0", "end")
    app.read_current()
    text, _, voice = app.speaker.spoken[-1]
    assert text.startswith("안녕하세요") and voice == "ko"
    finish(app)
    assert app.reading is None and app.current == 0  # 자동 발표가 꺼져 있으면 그대로


def test_auto_next_skips_hidden(app):
    app.auto_next_var.set(True)
    app.read_current()
    visited = [app.current]
    for _ in range(5):
        if app.reading is None:
            break
        finish(app)
        visited.append(app.current)
    assert visited == [0, 1, 2, 4, 5, 5]  # 4번째(숨김)는 건너뜀, 마지막에서 멈춤
    assert app.reading is None


def test_edit_is_used(app):
    app.select(1, user=True)
    app.text.delete("1.0", "end")
    app.text.insert("1.0", "에이아이는 인공지능입니다")
    app.select(2, user=True)
    assert app.edits == {2: "에이아이는 인공지능입니다"}
    app.select(1, user=True)
    app.read_current()
    assert app.speaker.spoken[-1][0] == "에이아이는 인공지능입니다."
    app.stop()
    app.reset_edit()
    assert app.edits == {}


def test_powerpoint_follow(app):
    app.link = link = FakeLink()
    path = str(SAMPLE)
    app._on_ppt_state(PptState("edit", 2, path))  # 연동 직후: 화면만 맞춤
    assert app.current == 1 and not app.speaker.spoken
    app._on_ppt_state(PptState("show", 2, path))  # 슬라이드 쇼 시작: 바로 읽기
    assert app.speaker.spoken[-1][0].startswith("인공지능은")
    app._on_ppt_state(PptState("show", 3, path))  # 발표자가 넘김
    assert app.current == 2 and app.speaker.spoken[-1][0].startswith("학교에서")

    app.auto_next_var.set(True)
    finish(app)  # 다 읽으면 이 프로그램이 PowerPoint를 다음 장(숨김 4번 건너뛰고 5번)으로 넘김
    assert app.current == 4 and link.gotos == [5]
    n = len(app.speaker.spoken)
    app._on_ppt_state(PptState("show", 5, path))  # PowerPoint가 따라옴 -> 두 번 읽지 않음
    assert len(app.speaker.spoken) == n

    app.select(0, user=True)  # 목록에서 직접 고르면 PowerPoint도 이동
    assert link.gotos == [5, 1] and app.reading is None

    app.read_current()
    app._on_ppt_state(PptState("edit", 1, path))  # 쇼를 끝내면 읽기 멈춤
    assert app.reading is None


def test_output_device(app, monkeypatch):
    labels = app.output_box.cget("values")
    assert labels[0] == "시스템 기본 장치 (지금: 스피커(Realtek))" and app.output_var.get() == labels[0]
    app.read_current()
    assert app.speaker.outputs_used[-1] is None  # 기본: 운영체제의 기본 장치

    app.output_var.set("헤드폰(Shokz)")
    app._on_output_change()
    app.stop()
    app.read_current()
    assert app.speaker.outputs_used[-1] == "dev-earphones"

    app.quit()  # 고른 장치는 다음 실행 때도 유지된다
    monkeypatch.setattr(FakeSpeaker, "connected", [SPEAKERS])  # 이어폰 연결이 끊긴 채로 다시 실행
    b = make_app()
    assert b.output_var.get() == "헤드폰(Shokz) (연결 안 됨 - 기본 장치로 읽음)"
    b.read_current()
    assert b.speaker.outputs_used[-1] == "dev-earphones"  # 다시 연결되면 이어폰으로, 그 전엔 엔진이 기본 장치로
    b.quit()


def test_powerpoint_unknown_file(app):
    app.link = FakeLink()
    app._on_ppt_state(PptState("show", 1, "Presentation1"))
    assert "위치를 알 수 없습니다" in app.status.cget("text")
    app._on_ppt_state(PptState("show", 2, "https://d.docs.live.net/x/" + SAMPLE.name))
    assert app.current == 1  # 같은 이름의 파일이 열려 있으면 그대로 따라감
