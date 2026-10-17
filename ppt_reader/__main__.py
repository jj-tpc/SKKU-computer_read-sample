"""실행: python -m ppt_reader [파일.pptx]  (옵션 없이 실행하면 강아지와 원 버튼이 뜬다)

화면 없이 도는 옵션(--dump, --say 등)은 Qt 화면을 불러오지 않는다.
"""
from __future__ import annotations

import argparse
import os
import queue
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ppt_reader", description="PPT 발표 자료를 소리 내어 읽어 주는 프로그램")
    p.add_argument("file", nargs="?", help="열 .pptx 파일")
    p.add_argument("--list-voices", action="store_true", help="쓸 수 있는 음성 목록 출력")
    p.add_argument("--list-outputs", action="store_true", help="소리를 낼 수 있는 출력 장치 목록 출력")
    p.add_argument("--dump", action="store_true", help="슬라이드별 대본을 화면에 출력 (소리 없음)")
    p.add_argument("--say", action="store_true", help="화면 없이 터미널에서 바로 읽기")
    p.add_argument("--slide", type=int, help="--say: 이 번호의 슬라이드만 읽기")
    p.add_argument("--source", default="notes_first", choices=["notes_first", "body", "notes", "both"],
                   help="읽을 내용 (기본: 노트 우선)")
    p.add_argument("--voice", help="음성 이름 일부 (예: Heami, Yuna)")
    p.add_argument("--output", help="출력 장치 이름 일부 (예: 헤드폰, AirPods). 없으면 기본 장치")
    p.add_argument("--speed", type=float, default=1.0, choices=[1.0, 1.5, 2.0, 5.0], help="배속 1.0, 1.5, 2.0, 5.0")
    p.add_argument("--probe-ppt", action="store_true", help="PowerPoint 연동 상태를 한 번 확인")
    p.add_argument("--self-check", action="store_true", help=argparse.SUPPRESS)  # 빌드 서버와 받는 사람 확인용
    args = p.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔에서 한글이 깨지지 않게
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    if args.list_voices:
        from .voice.engines import EngineUnavailable, make_engine

        try:
            engine = make_engine()
        except EngineUnavailable as e:
            print(e)
            return 1
        for v in engine.voices():
            print(f"{'*' if v.is_korean else ' '} {v.name}  [{v.lang}]")
        return 0

    if args.list_outputs:
        from PySide6.QtCore import QCoreApplication

        from .voice.player import default_output, list_outputs

        _app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])  # noqa: F841 (장치 목록에 필요)
        default = default_output()
        for o in list_outputs():
            print(f"{'*' if default and o.id == default.id else ' '} {o.name}")
        if default:
            print("(* = 지금 기본 출력 장치)")
        return 0

    if args.probe_ppt:
        return _probe_ppt()

    if args.dump or args.say:
        if not args.file:
            p.error("파일을 지정하세요.")
        from .slides import load_deck, to_speech

        deck = load_deck(args.file)
        slides = [s for s in deck.slides if args.slide in (None, s.number)]
        if args.dump:
            for s in slides:
                print(f"===== 슬라이드 {s.number}{' (숨김)' if s.hidden else ''} : {s.title}")
                print(to_speech(s.script(args.source)) or "(읽을 내용 없음)")
            return 0
        return _say(slides, args)

    if args.self_check:
        from .ui.app import self_check

        return self_check(_console_out())

    from .ui.app import run

    return run(args.file)


def _console_out():
    """창 실행 파일(Windows)에는 표준 출력이 없다. 실행한 터미널이 있으면 거기에 쓴다."""
    if sys.stdout is not None:
        return sys.stdout
    if sys.platform == "win32":
        import ctypes

        if ctypes.windll.kernel32.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
            return open("CONOUT$", "w", encoding="utf-8")
    return open(os.devnull, "w", encoding="utf-8")


def _say(slides, args) -> int:
    """화면 없이 운영체제 음성으로 읽는다. 앱과 같은 음성 흐름(문장 합성, Qt 재생, 배속 늘이기)을 쓴다."""
    import signal

    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
    from PySide6.QtCore import QCoreApplication, QTimer

    from .slides import to_speech
    from .ui.qtcore import MainThreadInvoker
    from .voice.engines import EngineUnavailable, make_engine
    from .voice.pipeline import Pipeline, VoiceThread
    from .voice.player import Player, list_outputs

    try:
        engine = make_engine()
    except EngineUnavailable as e:
        print(e)
        return 1
    app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
    voices = engine.voices()
    if args.voice:
        voice_id = next((v.id for v in voices if args.voice.lower() in v.name.lower()), None)
        if voice_id is None:
            print(f"'{args.voice}' 음성을 찾지 못해 기본 음성으로 읽습니다.")
    else:
        voice_id = next((v.id for v in voices if v.is_korean), None)
    output_id = None
    if args.output:
        output_id = next((o.id for o in list_outputs() if args.output.lower() in o.name.lower()), None)
        if output_id is None:
            print(f"'{args.output}' 출력 장치를 찾지 못해 기본 장치로 읽습니다. (--list-outputs 로 확인)")
    todo = [(s.number, to_speech(s.script(args.source))) for s in slides]
    todo = [(n, t) for n, t in todo if t]
    invoker = MainThreadInvoker()
    pipeline = Pipeline(engine, Player(), VoiceThread(invoker.post), lambda: None)
    result = {"code": 0}

    def next_slide(_tag=None, completed=True):
        if not completed or not todo:
            app.quit()
            return
        number, text = todo.pop(0)
        print(f"[{number}] {text}")
        pipeline.speak(text, voice_id, args.speed, tag=number, output_id=output_id)

    def failed(_tag, message):
        print("오류:", message)
        result["code"] = 1
        app.quit()

    pipeline.on_done = next_slide
    pipeline.on_error = failed
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    tick = QTimer()
    tick.start(200)  # Qt 이벤트 루프 중에도 파이썬이 Ctrl+C를 받게 깨운다
    tick.timeout.connect(lambda: None)
    QTimer.singleShot(0, next_slide)
    app.exec()
    pipeline.close()
    return result["code"]


def _probe_ppt() -> int:
    from .link import LinkError, PowerPointLink, resolve_local_path

    got: queue.Queue = queue.Queue()
    try:
        link = PowerPointLink(lambda st: got.put(("state", st)), lambda msg: got.put(("error", msg)))
    except LinkError as e:
        print("연동 불가:", e)
        return 1
    try:
        kind, value = got.get(timeout=15)
    except queue.Empty:
        print("15초 안에 PowerPoint 응답이 없습니다.")
        return 1
    finally:
        link.close()
    if kind == "error":
        print("연동 오류:", value)
        return 1
    print(f"상태: {value.mode}, 슬라이드: {value.index}, 경로: {value.path!r}")
    print(f"이 컴퓨터의 파일: {resolve_local_path(value.path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
