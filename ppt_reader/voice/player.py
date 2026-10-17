"""Qt 재생: 출력 장치 고르기, 늘이기(음높이 유지), 블루투스 앞 무음.

늘일 배율 r = 요청 배속 ÷ 엔진이 낸 배속. r이 1이면 QAudioSink로 PCM을 그대로 내고(위치가 10ms 단위로 정확),
1보다 크면 QMediaPlayer로 늘인다. 음높이 유지는 FFmpeg 백엔드에서만 되므로 앱이 QT_MEDIA_BACKEND=ffmpeg을 둔다.
"""
from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QTimer, QUrl
from PySide6.QtMultimedia import (QAudioDevice, QAudioFormat, QAudioOutput, QAudioSink, QMediaDevices,
                                  QMediaPlayer, QtAudio)

from .engines import Synth

# 블루투스 이어폰(그리고 HDMI 모니터 같은 장치)은 소리가 한동안 없으면 연결을 쉬게 했다가, 소리가 다시
# 오면 깨어나는 동안(약 0.5초) 첫마디를 버린다. 그래서 오래 조용했다가 읽기 시작할 때는 앞에 무음을 넣는다.
# Qt는 Windows에서 이 예열을 해 주지 않으므로 앱이 붙여야 한다.
LEAD_SILENCE_MS = 1000
IDLE_BEFORE_LEAD = 2.0  # 이만큼(초) 넘게 조용했으면 장치가 쉬고 있다고 본다
STRETCH_FROM = 1.01


@dataclass
class AudioOutput:
    id: str  # Qt 장치 id. Windows는 "{0.0.0.00000000}.{GUID}", 옛 설정은 SAPI 출력 토큰 id(끝이 같다)
    name: str


def stretch_ratio(speed: float, engine_speed: float) -> float:
    r = speed / max(engine_speed, 0.01)
    return r if r > STRETCH_FROM else 1.0


def need_lead(quiet_since: float | None, now: float, device: str, last_device: str | None) -> bool:
    """처음 읽을 때, 2초 넘게 조용했을 때, 출력 장치가 바뀌었을 때 앞 무음을 넣는다."""
    return quiet_since is None or device != last_device or now - quiet_since > IDLE_BEFORE_LEAD


def lead_samples(rate: int, r: float) -> int:
    """앞 무음의 표본 수. 늘이면 r배 짧아지므로 r을 곱해 두어, 늘인 뒤에도 정확히 1초가 되게 한다."""
    return int(rate * LEAD_SILENCE_MS / 1000 * r)


def wav_bytes(pcm: bytes, rate: int) -> bytes:
    header = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    return header + b"data" + struct.pack("<I", len(pcm)) + pcm


def _device_id(device: QAudioDevice) -> str:
    return bytes(device.id().data()).decode("utf-8", "replace")


def matches(output_id: str, device_id: str, description: str) -> bool:
    a, b = output_id.lower(), device_id.lower()
    return bool(a) and (a == b or a.endswith(b) or b.endswith(a) or output_id == description)


def list_outputs() -> list[AudioOutput]:
    return [AudioOutput(_device_id(d), d.description()) for d in QMediaDevices.audioOutputs()]


def default_output() -> AudioOutput | None:
    d = QMediaDevices.defaultAudioOutput()
    return None if d.isNull() else AudioOutput(_device_id(d), d.description())


def find_device(output_id: str | None) -> QAudioDevice:
    """고른 장치. 없거나 연결이 끊겼으면 지금 기본 장치(문장마다 다시 읽는다)."""
    if output_id:
        for d in QMediaDevices.audioOutputs():
            if matches(output_id, _device_id(d), d.description()):
                return d
    return QMediaDevices.defaultAudioOutput()


def _noop(*_args):
    pass


class Player(QObject):
    """문장 하나씩 재생한다. 화면 스레드에서만 쓴다."""

    def __init__(self):
        super().__init__()
        self.on_finished: Callable[[], None] = _noop
        self.on_failed: Callable[[str], None] = _noop
        self._sink: QAudioSink | None = None
        self._media: QMediaPlayer | None = None
        self._out: QAudioOutput | None = None
        self._buf: QBuffer | None = None
        self._lead = 0.0  # 앞 무음 길이(원래 소리 시각 기준 초)
        self._r = 1.0
        self._seconds = 0.0
        self._pos_ms = 0  # QMediaPlayer가 마지막으로 알려 준 위치와 그 때의 벽시계
        self._pos_wall = 0.0
        self._quiet_since: float | None = None
        self._last_device: str | None = None
        self.busy = False
        # PySide6 6.11은 QAudioSink.stateChanged의 QAudio::State 인자를 파이썬으로 넘기지 못해(신호가 오지 않음)
        # 싱크 상태는 state()를 짧게 자주 읽어 본다
        self._watch = QTimer(self)
        self._watch.setInterval(15)
        self._watch.timeout.connect(self._check_sink)

    def play(self, synth: Synth, speed: float, output_id: str | None) -> None:
        self._release()
        device = find_device(output_id)
        dev_id = _device_id(device)
        now = time.monotonic()
        r = stretch_ratio(speed, synth.engine_speed)
        lead = lead_samples(synth.rate, r) if need_lead(self._quiet_since, now, dev_id, self._last_device) else 0
        self._last_device = dev_id
        data = b"\0\0" * lead + synth.pcm
        self._lead = lead / synth.rate
        self._r = r
        self._seconds = synth.seconds
        self.busy = True
        self._buf = QBuffer()
        if r == 1.0:
            fmt = QAudioFormat()
            fmt.setSampleRate(synth.rate)
            fmt.setChannelCount(1)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self._buf.setData(QByteArray(data))
            self._buf.open(QIODevice.OpenModeFlag.ReadOnly)
            self._sink = QAudioSink(device, fmt, self)
            self._sink.start(self._buf)
            self._watch.start()
        else:
            self._buf.setData(QByteArray(wav_bytes(data, synth.rate)))
            self._buf.open(QIODevice.OpenModeFlag.ReadOnly)
            self._out = QAudioOutput(device, self)
            self._media = QMediaPlayer(self)
            self._media.setAudioOutput(self._out)
            self._media.setPitchCompensation(True)
            self._media.setPlaybackRate(r)
            self._pos_ms, self._pos_wall = 0, now
            self._media.positionChanged.connect(lambda ms: self._media_position(ms))
            self._media.mediaStatusChanged.connect(lambda status: self._media_status(status))
            self._media.errorOccurred.connect(lambda _e, msg: self._fail(msg))
            self._media.setSourceDevice(self._buf, QUrl("speech.wav"))
            self._media.play()

    def position(self) -> float:
        """지금 문장 소리 안의 재생 위치(초). 앞 무음은 뺀다."""
        if self._sink is not None:
            t = self._sink.processedUSecs() / 1e6
        elif self._media is not None:
            # position()은 50~100ms마다만 바뀌어서, 마지막 값에서 벽시계로 보간한다
            t = self._pos_ms / 1000 + (time.monotonic() - self._pos_wall) * self._r
            t = min(t, self._lead + self._seconds)
        else:
            return 0.0
        return max(0.0, t - self._lead)

    def stop(self) -> None:
        if self.busy:
            self._quiet_since = time.monotonic()
        self.busy = False
        self._release()

    # ------------------------------------------------------------ 안쪽

    def _check_sink(self) -> None:
        if self._sink is None:
            self._watch.stop()
            return
        state = self._sink.state()
        if state == QtAudio.State.IdleState and self._buf is not None and self._buf.atEnd():
            self._done()
        elif state == QtAudio.State.StoppedState and self._sink.error() != QtAudio.Error.NoError:
            self._fail(f"소리 장치 오류({self._sink.error().name})")

    def _media_position(self, ms: int) -> None:
        self._pos_ms, self._pos_wall = ms, time.monotonic()

    def _media_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._done()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._fail("소리를 열 수 없음")

    def _done(self) -> None:
        if not self.busy:
            return
        self.busy = False
        self._quiet_since = time.monotonic()
        self._release()
        self.on_finished()

    def _fail(self, message: str) -> None:
        if not self.busy:
            return
        self.busy = False
        self._quiet_since = time.monotonic()
        self._release()
        self.on_failed(message)

    def _release(self) -> None:
        sink, media, out, buf = self._sink, self._media, self._out, self._buf
        self._sink = self._media = self._out = self._buf = None
        self._watch.stop()
        if sink is not None:
            sink.stop()
            sink.deleteLater()
        if media is not None:
            for sig in (media.positionChanged, media.mediaStatusChanged, media.errorOccurred):
                sig.disconnect()
            media.stop()
            media.deleteLater()
        if out is not None:
            out.deleteLater()
        if buf is not None:
            buf.close()
            buf.deleteLater()
