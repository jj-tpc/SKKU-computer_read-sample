"""QApplication 시작, session과 화면 신호 잇기, --self-check. 화면 쪽 로직은 두지 않는다."""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Callable

from PySide6.QtCore import QObject, QTimer, qVersion
from PySide6.QtGui import QCursor, QGuiApplication, QScreen
from PySide6.QtWidgets import QApplication, QMessageBox

from ..session import Session
from ..settings import DOGS, Settings, app_folder
from ..slides import to_speech
from ..voice.cache import sentence_plan
from ..voice.cloud import cloud_engine
from . import platform_mac, theme
from .dog import FEET_Y, FRAMES, SWEAT_ROW, DogWindow, load_sheet
from .orb import R, OrbWindow, corner_center
from .qtcore import MainThreadInvoker, QtClock

APP_TITLE = "PPT 읽어주기"
FRAME_MS = 33  # 강아지와 원 버튼을 함께 그리는 타이머(약 30fps)
HAPPY_SECONDS = 1.5


class Controller(QObject):
    """창들을 띄우고 session의 알림을 화면에 옮긴다."""

    def __init__(self, settings: Settings, session: Session, pipeline=None, presynth=None,
                 closers: list[Callable[[], None]] | None = None):
        super().__init__()
        self.settings = settings
        self.session = session
        self.pipeline = pipeline
        self.presynth = presynth
        self.presynth_state: tuple[str, int, int, str] = ("off", 0, 0, "")  # (상태, 만든 수, 전체, 실패 이유). 설정 창이 보인다
        self.closers = closers or []
        self.dog = DogWindow(settings["dog"])
        self.orb = OrbWindow(self.on_action)
        self.orb.set_speed(settings["speed"])
        self._happy_until = 0.0
        self._last = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._frame)
        session.on_state = self._on_state
        session.on_pose = self._on_pose
        session.on_message = self._on_message
        session.on_deck = lambda _deck: self.start_presynth()
        session.on_script = self._on_script

    def start(self) -> None:
        self._place()
        if self.settings["dog_visible"]:
            self.dog.show()
        self.orb.show()
        self.orb.raise_()  # 원 버튼 묶음은 늘 강아지보다 위
        self._timer.start()
        if self.settings.first_run:
            self._on_pose("happy")

    def _screen(self) -> QScreen:
        name = self.settings["monitor"]
        for screen in QGuiApplication.screens():
            if name != "follow" and screen.name() == name:
                return screen
        return QGuiApplication.primaryScreen()

    def _place(self) -> None:
        available = self._screen().availableGeometry()
        self.orb.place(available)
        c = corner_center(available)
        # 원 버튼 왼쪽, 위성 버튼 호 바깥에 앉아 기다린다
        self.dog.move(c.x() - 300, c.y() + R - FEET_Y)

    def _frame(self) -> None:
        now = time.monotonic()
        dt, self._last = min(0.1, now - self._last), now
        frame = self.pipeline.frame() if self.pipeline is not None else None
        if frame is not None and frame.speaking:
            self.dog.set_pose("talk")
            self.dog.mouth = frame.mouth
        else:
            self.dog.set_pose("happy" if now < self._happy_until else "sit")
        level, tone = (frame.level, frame.tone) if frame is not None and frame.speaking else (0.0, 0.5)
        self.orb.level += (level - self.orb.level) * 0.35
        self.orb.tone += (tone - self.orb.tone) * 0.05  # 높낮이 느낌은 천천히 따라간다
        self.dog.tick(dt)
        self.orb.tick(dt, QCursor.pos())

    def _on_state(self, state: str) -> None:
        self.orb.set_state(state)
        engine = getattr(self.pipeline, "os_engine", None)
        factors = dict(getattr(engine, "x5_factors", None) or {})
        if state == "idle" and factors and factors != self.settings["x5_factor"]:
            self.settings.set(x5_factor=factors)  # 음성마다 처음 한 번 잰 x5 배속을 기억한다

    # ------------------------------------------------------------ 대본 소리 미리 만들기

    def start_presynth(self) -> None:
        if self.presynth is None:
            return
        plan = cloud_engine(self.settings.data)
        deck = self.session.deck
        if plan is None or deck is None:
            self.presynth.stop()
            self.presynth_state = ("off", 0, 0, "")
            return
        slides = [sentence_plan(to_speech(self.session.script_for(i))) for i in range(len(deck.slides))]
        self.presynth.start(plan[0], plan[1], slides, max(self.session.current, 0))

    def _on_script(self, index: int) -> None:
        if index < 0 or self.presynth is None or cloud_engine(self.settings.data) is None:
            self.start_presynth()
        else:
            self.presynth.redo(index, sentence_plan(to_speech(self.session.script_for(index))))

    def presynth_progress(self, done: int, total: int) -> None:
        self.presynth_state = ("done" if done >= total else "making", done, total, "")

    def presynth_failed(self, kind: str, detail: str) -> None:
        _, done, total, _ = self.presynth_state
        self.presynth_state = ("failed", done, total, detail or kind)

    def _on_pose(self, pose: str) -> None:
        if pose == "happy":
            self._happy_until = time.monotonic() + HAPPY_SECONDS

    def _on_message(self, kind: str, text: str) -> None:
        if kind == "error":
            QMessageBox.critical(None, APP_TITLE, text)
        elif kind == "warning":
            QMessageBox.warning(None, APP_TITLE, text)

    def on_action(self, key: str) -> None:
        if key == "read":
            self.session.toggle_read()
        elif key == "speed":
            self.orb.set_speed(self.session.cycle_speed())
        elif key == "quit":
            self.quit()

    def quit(self) -> None:
        """[끝내기]: 읽기 정지 → 미리 만들기 취소 → 연동 닫기 → 설정 저장 → 종료."""
        self._timer.stop()
        if self.pipeline is not None:
            self.pipeline.stop()
        if self.presynth is not None:
            self.presynth.close()
        self.session.shutdown()
        for close in self.closers:
            close()
        self.dog.close()
        self.orb.close()
        QApplication.quit()


def _make_app() -> QApplication:
    # 음높이를 지키며 배속하려면 FFmpeg 백엔드여야 한다(Windows 자체 백엔드는 못 한다)
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)  # 보통 창(설정 창)을 닫아도 강아지와 원 버튼은 남는다
    app.setStyleSheet(theme.STYLESHEET)
    platform_mac.become_accessory()
    return app


def run(path: str | None = None) -> int:
    from ..link import PowerPointLink
    from ..voice.cache import Presynth, VoiceCache
    from ..voice.engines import EngineUnavailable, make_engine
    from ..voice.pipeline import Pipeline, VoiceThread
    from ..voice.player import Player

    app = _make_app()
    invoker = MainThreadInvoker()
    settings = Settings()
    cache = VoiceCache(settings.folder)
    closers: list[Callable[[], None]] = []
    pipeline = None
    try:
        os_engine = make_engine(dict(settings["x5_factor"]))
        pipeline = Pipeline(os_engine, Player(), VoiceThread(invoker.post), lambda: cloud_engine(settings.data), cache)
        closers.append(pipeline.close)
    except EngineUnavailable as e:
        QMessageBox.critical(None, APP_TITLE, str(e))

    def link_factory(on_change, on_error):
        return PowerPointLink(invoker.wrap(on_change), invoker.wrap(on_error))

    session = Session(settings, pipeline, QtClock(), link_factory)
    if pipeline is not None:
        pipeline.on_done = session.voice_done
        pipeline.on_error = session.voice_error
        pipeline.on_cloud_failed = session.cloud_voice_failed
        pipeline.on_voice_chosen = session.cloud_voice_chosen
    controller = Controller(settings, session, pipeline, None, closers)
    controller.presynth = Presynth(cache, invoker.wrap(controller.presynth_progress),
                                   invoker.wrap(controller.presynth_failed))
    controller.start()
    if path:
        session.open_file(path)
    return app.exec()


# ---------------------------------------------------------------- --self-check

def self_check(out) -> int:
    """빌드 서버와 받는 사람 확인용. 줄마다 OK/FAIL을 쓰고, 모두 OK면 0을 돌려준다."""
    results: list[bool] = []

    def report(ok: bool, name: str, detail: str) -> None:
        results.append(ok)
        out.write(f"{'OK  ' if ok else 'FAIL'} {name}: {detail}\n")
        out.flush()

    if os.environ.get("QT_QPA_PLATFORM", "").startswith("offscreen"):
        del os.environ["QT_QPA_PLATFORM"]  # 실제 플랫폼으로 창을 만들어 봐야 한다
    app = _make_app()

    # 1. 강아지·원 버튼 창을 화면 밖 좌표에 한 번 만든다
    orb = None
    try:
        dog, orb = DogWindow(), OrbWindow(lambda _key: None)
        for w in (dog, orb):
            w.move(-4000, -4000)
            w.show()
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.02)
        shown = dog.isVisible() and orb.isVisible() and bool(dog.winId()) and bool(orb.winId())
        platform = QGuiApplication.platformName()
        report(shown and platform != "offscreen", "화면", f"Qt {qVersion()}, 플랫폼 {platform}, 강아지·원 버튼 창")
    except Exception as e:
        report(False, "화면", f"{type(e).__name__}: {e}")

    # 2. 스프라이트 세 장
    try:
        bad = [d for d in DOGS if len(load_sheet(d)) != SWEAT_ROW + 1
               or any(f.isNull() for row in load_sheet(d) for f in row[:FRAMES])]
        report(not bad, "스프라이트", "세 장 읽음" if not bad else f"못 읽음: {', '.join(bad)}")
    except Exception as e:
        report(False, "스프라이트", f"{type(e).__name__}: {e}")

    # 3. 기본 음성으로 한 문장 합성(재생하지 않음). 실제처럼 음성 스레드에서 한다
    report(*_check_synth())

    # 4. 설정 폴더
    try:
        folder = app_folder()
        folder.mkdir(parents=True, exist_ok=True)
        report(folder.is_dir(), "설정 폴더", str(folder))
    except OSError as e:
        report(False, "설정 폴더", f"{e}")

    # 5. macOS 보조
    if sys.platform == "darwin":
        ok, detail = platform_mac.check(orb) if orb is not None else (False, "창 없음")
        report(ok, "macOS 보조", detail)
    else:
        report(True, "macOS 보조", "해당 없음")

    # 6. 재생 준비: 소리는 내지 않고, FFmpeg 백엔드가 올라와 음높이를 지키며 늘일 수 있는지만 본다
    report(*_check_playback())

    return 0 if all(results) else 1


def _check_playback() -> tuple[bool, str, str]:
    try:
        from PySide6.QtMultimedia import QMediaDevices, QMediaPlayer

        player = QMediaPlayer()
        availability = player.pitchCompensationAvailability()
        ok = availability != QMediaPlayer.PitchCompensationAvailability.Unavailable
        outputs = len(QMediaDevices.audioOutputs())
        return ok, "재생 준비", f"음높이 유지 {availability.name}, 출력 장치 {outputs}개"
    except Exception as e:
        return False, "재생 준비", f"{type(e).__name__}: {e}"


def _check_synth() -> tuple[bool, str, str]:
    from ..voice.engines import make_engine

    result: dict = {}

    def work():
        engine = None
        try:
            engine = make_engine()
            voices = engine.voices()
            voice = next((v for v in voices if v.is_korean), None)
            text = "안녕하세요. 자가 점검입니다." if voice else "This is a self check."
            synth = engine.synth(text, voice.id if voice else None, 1.0)
            result["ok"] = len(synth.pcm) > 0
            result["detail"] = (f"{voice.name if voice else '기본 음성'}, {synth.seconds:.2f}초, "
                                f"낱말 {len(synth.words)}개")
        except Exception as e:
            result["ok"], result["detail"] = False, f"{type(e).__name__}: {e}"
        finally:
            if engine is not None:
                engine.close()

    worker = threading.Thread(target=work, name="voice-check", daemon=True)
    worker.start()
    worker.join(60)
    if worker.is_alive():
        return False, "음성 합성", "60초 안에 끝나지 않음"
    return bool(result.get("ok")), "음성 합성", result.get("detail", "")

