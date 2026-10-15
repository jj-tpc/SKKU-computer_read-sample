"""실행: python -m ppt_reader [파일.pptx]  (옵션 없이 실행하면 화면이 뜬다)"""
from __future__ import annotations

import argparse
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
    p.add_argument("--speed", type=float, default=1.0, help="속도 배수 0.5~2.0")
    p.add_argument("--probe-ppt", action="store_true", help="PowerPoint 연동 상태를 한 번 확인")
    args = p.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔에서 한글이 깨지지 않게
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    if args.list_voices:
        from .tts import Speaker

        sp = Speaker(lambda *a: None)
        for v in sp.voices():
            print(f"{'*' if v.is_korean else ' '} {v.name}  [{v.lang}]")
        sp.close()
        return 0

    if args.list_outputs:
        from .tts import Speaker

        sp = Speaker(lambda *a: None)
        default = sp.default_output()
        for o in sp.outputs():
            print(f"{'*' if default and o.id == default.id else ' '} {o.name}")
        if default:
            print("(* = 지금 기본 출력 장치)")
        sp.close()
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

    from .app import run

    run(args.file)
    return 0


def _say(slides, args) -> int:
    from .slides import to_speech
    from .tts import Speaker

    events: queue.Queue = queue.Queue()
    sp = Speaker(lambda kind, tag, info: events.put((kind, tag, info)))
    voice_id = None
    if args.voice:
        voice_id = next((v.id for v in sp.voices() if args.voice.lower() in v.name.lower()), None)
        if voice_id is None:
            print(f"'{args.voice}' 음성을 찾지 못해 기본 음성으로 읽습니다.")
    else:
        voice_id = next((v.id for v in sp.voices() if v.is_korean), None)
    output_id = None
    if args.output:
        output_id = next((o.id for o in sp.outputs() if args.output.lower() in o.name.lower()), None)
        if output_id is None:
            print(f"'{args.output}' 출력 장치를 찾지 못해 기본 장치로 읽습니다. (--list-outputs 로 확인)")
    try:
        for s in slides:
            text = to_speech(s.script(args.source))
            if not text:
                continue
            print(f"[{s.number}] {text}")
            sp.speak(text, voice_id, args.speed, tag=s.number, output_id=output_id)
            while True:
                kind, tag, info = events.get()
                if kind == "error":
                    print("오류:", info)
                    return 1
                if kind == "done" and tag == s.number:
                    break
    except KeyboardInterrupt:
        sp.stop()
    finally:
        sp.close()
    return 0


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
