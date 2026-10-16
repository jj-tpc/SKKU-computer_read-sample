# 운영체제 음성에서 목소리 신호 얻기와 배속 한계

조사일 2026-10-16. 지도 티켓 `04-research-tts-signal-and-speed`(원 버튼 파동과 캐릭터 입을 목소리에 맞춰 움직일 신호, 배속 x1/x1.5/x2/x5)의 답이다. 기준 구현은 `ppt_reader/tts.py`(커밋 37e1156)다.

- Windows 쪽은 이 PC(Windows 11 Pro 10.0.26200, Python 3.14.7, pywin32 312)에서 **직접 실행해 쟀다**. 음성은 이 PC에 있는 세 가지다: Microsoft Heami Desktop(한국어), Microsoft Zira Desktop(영어), Microsoft Heami(OneCore 등록, 한국어).
- macOS 쪽은 실행할 수 없어서 **문서 근거, 미실행**이다.

## 결론 요약

1. **Windows 권장: 미리 합성한 뒤 SAPI로 재생한다.** 대본을 `SpMemoryStream`/`SpFileStream`에 합성하면서 단어·viseme 이벤트를 오디오 위치와 함께 모으고, 순수 파이썬으로 20ms 단위 크기 곡선을 뽑는다(19초 음성에 40ms). 그 소리를 지금의 `SpVoice`(고른 `AudioOutput` 그대로)에서 `SpeakStream`으로 재생한다. 출력 장치 선택이 그대로 유지되고 **새 의존성이 없다**. 재생 위치는 `CurrentDevicePosition`으로 읽어 곡선·viseme과 맞춘다(실측 1.000배로 실시간 진행).
2. 더 단순한 대안은 지금처럼 장치로 바로 `Speak`하면서 단어·viseme 이벤트를 받거나 `SpVoice.Status`를 폴링하는 것이다. 둘 다 **재생에 맞춰** 오고, 해당 오디오 위치보다 수십 ms 늦다(단어 이벤트 실측 7~69ms). 다만 크기 신호인 `AudioLevel` 이벤트는 장치로 낼 때만 오고 약 7Hz(140~150ms 간격)라서 파동에 쓰기에는 거칠다.
3. **배속(SAPI):** Heami는 `Rate` r에서 정확히 3^(r/10)배다. x1.5는 Rate 4(1.55배), x2는 Rate 6(1.93배)이다. `Rate` 하나로는 최대 2.98배(Zira 2.72배)라서 **x5가 안 된다**. `Rate=10`에 SAPI XML `<rate absspeed="5"/>`(SVSFPersistXML)를 더하면 **Heami는 5.17배**까지 간다(최대 8.93배). Zira는 3.47배에서 멈춘다.
4. **x5 대안:** 음성이 낼 수 있는 최고 속도로 합성하고, 남은 배율만(예: 5/2.98 = 1.68배) 음높이를 유지한 채 시간 늘이기로 줄인다. 이렇게 하려면 numpy가 필요하다. audiotsm 위상 보코더로 재 보니 처리에 50~70ms 걸렸다. 음질은 들어 보지 않았다.
5. **첫마디까지 시간:** 문장 하나 합성에 약 20ms, 118자 대본 전체는 70~110ms, 356자는 220~390ms 걸린다. 문장 단위로 합성하거나 블루투스용 1초 무음을 재생하는 동안 합성하면 지연이 가려진다. 실측에서 무음과 본문 사이에 틈이 없었다.
6. **지금 구현의 문제:** 블루투스 대응 `<silence msec="1000"/>`도 `Rate`만큼 짧아진다. x2(Rate 6)에서는 약 525ms, Rate 10에서는 약 339ms만 남아서, 장치가 깨어나는 시간(약 0.5초)을 못 덮을 수 있다. 미리 합성할 때 0 바이트를 앞에 붙이면 배속과 상관없이 정확히 1초가 된다.
7. **macOS(문서 근거, 미실행):** `say`는 크기나 단어 신호를 밖으로 내지 않는다(`-i`의 단어 강조 출력만 있다). 권장 방식은 `say -o`(WAVE, LEI16)로 미리 합성하고 곡선을 뽑아 재생하는 것이다. 다만 **장치를 골라 재생하려면 새 의존성이 필요하다**(pyobjc의 `AVAudioPlayer.currentDevice`, 또는 sounddevice 같은 재생 라이브러리). 단어·음소 콜백은 NSSpeechSynthesizer(macOS 14부터 deprecated, 출력 장치를 고르는 공개 API 없음)와 AVSpeechSynthesizer(`write…toMarkerCallback`, macOS 13+, 마커에 `byteSampleOffset`)에 있다.
8. **배속(macOS):** Apple 문서에 적힌 말하기 속도 범위는 50~500 wpm이다. 지금 코드(1배 = 190 wpm)에서 x5는 950 wpm이라 범위를 넘는다. 음성이 실제로 따르는지는 미확인이므로, x5는 시간 늘이기를 전제로 둔다(`AVAudioUnitTimePitch.rate` 1/32~32). `AVAudioPlayer.rate`는 0.5~2.0이라 x5에 못 쓴다.

---

## 실험 방법과 안전 조치

- 스피커로 소리를 내지 않았다. 대부분은 `SpMemoryStream`에 합성해 샘플을 직접 쟀다.
- 실시간(장치) 측정은 물리 스피커와 연결되지 않은 가상 장치 `스피커(Steam Streaming Speakers)`로 보냈다. TTS는 `Volume=0`으로 냈다. 엔진이 `Volume=0`이면 샘플을 전부 0으로 만든다는 것을 먼저 확인했다(아래 표). 단 `AudioLevel` 값 측정(§1.4)에서는 0이 아닌 데이터를 `SpeakStream`으로 같은 가상 장치에 보냈다. `SpeakStream`은 `Volume`을 적용하지 않기 때문이다(§2.3).
- 실험 스크립트는 저장소 밖 스크래치 폴더에서 돌렸다. 이 문서의 코드 조각은 그 핵심만 옮긴 것이다. makepy 캐시(`gen_py`)도 스크래치 폴더에 만들어 프로젝트 venv는 건드리지 않았다.
- 길이는 앞뒤 무음을 뺀 "말소리 구간"(10ms 창 최대 진폭 > 300)으로 쟀고, 배속은 Rate 0일 때 구간 길이 ÷ 해당 조건의 구간 길이로 계산했다.
- 시험 문장: 한국어 118자(태양계 소개 4문장), 영어 202자(같은 내용).

| 음성 | Volume=100 최대 진폭 | Volume=50 | Volume=0 |
|---|---|---|---|
| Heami Desktop | 17889 | 4242 | **0** |
| Zira Desktop | 20070 | 4759 | **0** |
| Heami OneCore | 17889 | 4242 | **0** |

Heami Desktop과 Heami OneCore는 샘플 수와 최대 진폭이 같았고, 이후 모든 측정에서도 같은 값이 나왔다. 그래서 아래 표에는 Heami 하나로 적는다.

---

## 1. SAPI 이벤트로 신호 받기 (티켓 항목 1)

### 1.1 받는 법 (pywin32)

```python
import pythoncom, win32com.client

class Events:
    def OnWord(self, StreamNumber, StreamPosition, CharacterPosition, Length): ...
    def OnViseme(self, StreamNumber, StreamPosition, Duration, NextVisemeId, Feature, CurrentVisemeId): ...
    def OnPhoneme(self, StreamNumber, StreamPosition, Duration, NextPhoneId, Feature, CurrentPhoneId): ...
    def OnAudioLevel(self, StreamNumber, StreamPosition, AudioLevel): ...
    def OnStartStream(self, StreamNumber, StreamPosition): ...
    def OnEndStream(self, StreamNumber, StreamPosition): ...

sp = win32com.client.DispatchWithEvents("SAPI.SpVoice", Events)
sp.EventInterests = 33790          # SVEAllEvents (AudioLevel 512 포함)
sp.Speak(text, 1 | 16)             # SVSFlagsAsync | SVSFIsNotXML
while not sp.WaitUntilDone(1):     # 이벤트는 이 스레드의 메시지 펌프로 전달된다
    pythoncom.PumpWaitingMessages()
```

- `SpeechVoiceEvents` 값: StartInputStream 2, EndInputStream 4, Word 32, Phoneme 64, Sentence 128, Viseme 256, AudioLevel 512, All 33790 ([SpeechVoiceEvents](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms720886(v=vs.85))).
- 문서는 기본 `EventInterests`에 AudioLevel만 빠져 있다고 한다([AudioLevel event](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms723582(v=vs.85))). 그런데 pywin32 `Dispatch` 직후 실제 값은 **0**이었다. 그러니 직접 설정해야 한다.
- `DispatchWithEvents`는 makepy 지원이 필요하고, 없으면 그 자리에서 생성한다([pywin32 소스 `DispatchWithEvents`](https://github.com/mhammond/pywin32/blob/main/com/win32com/client/__init__.py)). 처음 부를 때 `gen_py` 캐시를 쓴다.
- 이벤트는 STA 스레드의 메시지 펌프로 온다. 지금 `Speaker._run`은 0.05초마다 명령 큐를 보므로, 그 루프에서 `PumpWaitingMessages()`를 부르면 이벤트가 최대 50ms 늦게 처리된다.
- 각 이벤트의 의미([SPEVENTENUM, SAPI 5.4](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee431845(v=vs.85))):
  - WORD_BOUNDARY: 단어의 글자 위치와 길이.
  - PHONEME, VISEME: 길이(ms)와 현재·다음 ID. viseme ID는 [SPVISEMES](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee431873(v=vs.85))의 22가지다.
  - TTS_AUDIO_LEVEL: "fired by SAPI … wParam is the current audio level from zero to 100".

### 1.2 음성별로 실제 오는 이벤트 (메모리 스트림 합성)

| 음성 | 오디오 길이 | start | sentence | word | phoneme | viseme | audio level |
|---|---|---|---|---|---|---|---|
| Heami (118자) | 18.95s | 1 | 4 | 27 | 228 | 215 | **0** |
| Zira (202자) | 14.00s | 1 | 4 | 37 | 146 | 150 | **0** |

- 한국어 Heami도 단어, 음소, viseme 이벤트를 모두 낸다. viseme은 초당 약 11개이고 각각 길이(ms)를 담고 있어 입 모양에 바로 쓸 수 있다.
- 메모리 스트림에 합성하면 이벤트가 합성 속도대로 몰려 온다(19초 분량이 0.07~0.1초 안에 다 온다). 각 이벤트의 `StreamPosition`은 바이트 위치이므로 `위치 ÷ AvgBytesPerSec`로 오디오 시각을 얻는다. 예: Heami의 첫 단어 "오늘은"은 0.10s, "태양계의"는 0.58s.
- **AudioLevel은 메모리·파일 스트림으로 합성할 때는 오지 않는다.** 오디오 장치로 낼 때만 온다(§1.3).

### 1.3 장치로 말할 때 이벤트가 재생에 맞춰 오나 (실제 지연)

가상 장치, `Volume=0`, Rate 0으로 쟀다. "늦음"은 (단어 이벤트 도착 시각 − StartStream 도착 시각) − (단어의 오디오 위치)다.

| 음성 | Speak 호출→StartStream | 호출→첫 단어 이벤트 (첫 단어 오디오 위치) | 단어 이벤트 늦음 최소/중앙/최대 | AudioLevel 이벤트 수 |
|---|---|---|---|---|
| Heami | 64ms | 172ms (100ms) | 7 / 32 / 55ms (27개) | 143 / 19s |
| Zira | 42ms | 166ms (100ms) | 15 / 40 / 69ms (37개) | 107 / 14s |

- 이벤트는 **재생 속도에 맞춰** 온다. 전체 경과도 19.02s로, 오디오 길이 18.95s와 같았다. 단어 이벤트가 도착한 순간에 장치 재생 위치(`CurrentDevicePosition`)는 그 단어 위치보다 18~60ms 앞서 있었다(9개 측정: 24, 42, 30, 60, 41, 60, 18, 52, 23ms). 즉 이벤트는 장치가 그 소리를 내보낸 뒤 수십 ms 안에 온다.
- 문서 근거: "voice status and voice events are closely associated with the status of the audio output device" ([ISpeechVoiceStatus](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms722539(v=vs.85))). 이벤트를 재생 시점에 맞춰 보낸다고 직접 적은 문장은 찾지 못했다. 위 동작은 실측으로 확인한 것이다.
- 무음을 앞에 넣으면(`<silence msec="1000"/>`를 따로 Speak) 이벤트 위치가 두 스트림에 걸쳐 이어서 센다. 본문 첫 단어 위치가 1100ms였고, 이벤트는 호출 뒤 1157ms(Heami), 1163ms(Zira)에 왔다.
- 장치 위치 이후의 OS 믹서와 블루투스 코덱 지연, 즉 귀에 들리기까지의 지연은 소리를 내지 않아 **미확인**이다.

### 1.4 AudioLevel 값은 쓸 만한가

0이 아닌 Heami 음성(10.05s)을 `SpeakStream`으로 가상 장치에 재생하며 받았다.

- 77개가 왔고 간격은 위치 기준 중앙값 149ms, 도착 기준 140ms(0~570ms로 들쭉날쭉)였다. 값은 0~43 사이에서 34가지가 나왔다.
- 값과 원음의 상관: **이벤트 위치에서 시작하는 50ms 창**의 RMS와 0.94, 최대 진폭과 0.97로 가장 높았다. 창을 ±100ms만 옮겨도 0.33~0.43으로 떨어진다. 즉 그 위치의 순간 크기다.
- 결론: 값 자체는 정확하지만 7Hz라서, 매끄러운 파동에는 보간이 필요하다. 미리 합성해서 뽑은 20ms 곡선(§2.4)이 더 촘촘하다.

### 1.5 이벤트 없이 Status 폴링

makepy나 이벤트 연결 없이 일반 `Dispatch`만으로도 된다.

```python
st = sp.Status   # ISpeechVoiceStatus
st.InputWordPosition, st.InputWordLength, st.VisemeId, st.PhonemeId, st.RunningState
```

- 장치(가상)로 Heami를 말하게 하고 계속 읽었더니 초당 약 65번 읽혔다. 단어 위치가 바뀐 시각(호출 기준)은 그 단어의 오디오 위치보다 80~110ms 뒤였다. 여기에는 시작 지연 약 50~70ms가 들어 있다. 예: "태양계의" 0.66s 대 0.58s, "알아보겠습니다" 2.17s 대 2.08s.
- viseme 바뀜은 189번 잡혔다(이벤트로는 215개). 짧은 viseme 일부는 놓친다.
- 문서도 이벤트 대신 Status를 가끔 읽는 쪽을 권할 수 있다고 한다. 다만 파일 스트림으로 말할 때는 늘 비활성으로 나온다([ISpeechVoiceStatus](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms722539(v=vs.85))).

---

## 2. SAPI 미리 합성과 재생 (티켓 항목 2)

### 2.1 합성

```python
ms = win32com.client.Dispatch("SAPI.SpMemoryStream")
ms.Format.Type = 22                      # SAFT22kHz16BitMono
sp.AudioOutputStream = ms                # 이 동안 이벤트를 받으면 위치가 이 스트림 기준
sp.Speak(text, 16)                       # 동기
pcm = bytes(ms.GetData())                # 22050Hz 16bit mono PCM

fs = win32com.client.Dispatch("SAPI.SpFileStream")
fs.Format.Type = 22
fs.Open(path, 3, False)                  # SSFMCreateForWrite → RIFF WAV로 써진다
```

`SpFileStream`으로 쓴 파일은 `wave` 모듈로 22050Hz/16bit/mono/18.95s로 읽혔다.

### 2.2 재생: 같은 SpVoice의 SpeakStream, 장치 선택 유지

```python
play = win32com.client.Dispatch("SAPI.SpMemoryStream")
play.Format.Type = 22
play.SetData(pcm)
sp.AudioOutput = <tts.py의 _set_output이 고른 토큰>      # 지금 코드 그대로
sp.SpeakStream(play, 1)                                   # SVSFlagsAsync
audio = win32com.client.CastTo(sp.AudioOutputStream, "ISpeechMMSysAudio")
pos_bytes = audio.Status.CurrentDevicePosition            # 장치 형식 기준 바이트
```

- [SpeakStream](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee125649(v=vs.85))은 "initiates speaking of a sound file by the voice"다. 장치는 그 `SpVoice`의 `AudioOutput`을 따른다. 그래서 `_set_output`(고른 장치가 없으면 Windows 기본 장치) 로직을 그대로 쓸 수 있다. **재생에 새 의존성이 필요 없다.**
- 실측(18.95s, 무음 데이터, 가상 장치):
  - `SpeakStream`은 1.2ms 만에 돌아오고, 호출 뒤 70ms에 StartStream이 온다. StartStream에서 EndStream까지 18.92s였다.
  - `CurrentDevicePosition`은 호출 뒤 70ms부터 **1.000배 실시간**으로 늘어 18.95s에서 끝났다. SAPI는 장치보다 약 0.5s 앞서 써 둔다(`CurrentSeekPosition − CurrentDevicePosition` 중앙값 523ms).
  - 장치 형식은 16kHz였다. 22kHz로 넣은 데이터를 SAPI가 변환한다. 위치를 시간으로 바꿀 때는 `sp.AudioOutputStream.Format.GetWaveFormatEx().AvgBytesPerSec`를 쓴다.
- `SpeakStream` 재생 중 오는 이벤트는 StartStream, EndStream, AudioLevel뿐이다. 단어와 viseme은 오지 않으므로 합성할 때 받아 둔 목록을 재생 위치에 맞춰 꺼내 쓴다.
- `CastTo`도 makepy가 필요하다. 이를 피하려면 StartStream 시각(또는 `Status.RunningState`가 바뀐 시각)부터 벽시계로 진행 시간을 잴 수 있다. 위 측정상 장치 위치와 벽시계는 1.000배로 같이 갔다.
- [ISpeechAudioStatus](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms720955(v=vs.85)) 문서는 이 인터페이스가 "not a standard Windows multimedia device"용이라고 적지만, 실측에서는 MMSys 출력 장치에서도 값이 정상으로 나왔다.

### 2.3 SpeakStream은 Rate와 Volume을 적용하지 않는다

출력을 메모리 스트림으로 바꿔 쟀다. 들어간 샘플과 나온 샘플이 같았다.

| 재생 SpVoice 설정 | 입력 샘플 → 출력 샘플 | 최대 진폭 |
|---|---|---|
| Rate 0, Volume 100 | 417868 → 417868 | 17889 → 17889 |
| Rate 10, Volume 100 | 417868 → 417868 | 17889 → 17889 |
| Rate 0, Volume 50 | 417868 → 417868 | 17889 → 17889 |
| Rate 0, Volume 0 | 417868 → 417868 | 17889 → 17889 |

배속은 합성할 때 넣어야 하고, 재생 단계에서는 바뀌지 않는다.

### 2.4 파동용 크기 곡선 (numpy 없이)

```python
def envelope(samples, sr, win_ms=20, step=4):    # samples: array('h')
    w = int(sr * win_ms / 1000)
    return [math.sqrt(sum(x*x for x in samples[i:i+w:step]) / len(samples[i:i+w:step])) / 32768
            for i in range(0, len(samples) - w + 1, w)]
```

- 18.95s(22050Hz)에서 947프레임을 뽑는 데, 모든 샘플을 쓰면 40ms, 4개 중 하나만 쓰면(`step=4`) 10ms 걸렸다. `audioop`이 Python 3.13에서 빠졌어도 문제가 없다.
- 재생 위치(초) = `CurrentDevicePosition ÷ AvgBytesPerSec`로 곡선과 viseme 목록의 인덱스를 고른다. tkinter `after()`로 30~60fps로 읽으면 된다. COM 객체는 TTS 스레드에서 읽고 숫자만 넘긴다.

---

## 3. macOS (티켓 항목 3) — 문서 근거, 미실행

### 3.1 `say`

`say` man page는 Apple 웹에 공식 사본이 없어 미러([unix.com의 say(1)](https://www.unix.com/man-page/osx/1/say/), 머리말 "1.0, 2012-09-15")로 확인했다. 최신 macOS의 `man say`와 같은지는 미확인이다.

- `-o`/`--output-file`: "Specify the path for an audio file to be written. AIFF is the default". 형식은 `--file-format`(AIFF, caff, m4af, WAVE)과 `--data-format`(예: `LEI16@22050`)으로 정한다.
- `-a`/`--audio-device`: "Specify, by ID or name prefix, an audio device to be used to play the audio." 지금 `_SayEngine`이 쓰는 기능이다. **파일로 쓸 때는 재생하지 않으므로 `-a`와 `-o`를 함께 쓸 일이 없다.**
- `-i`/`--interactive`: "Print the text line by line during synthesis, highlighting words as they are spoken." 단어 경계를 얻을 수 있는 유일한 출력이다. 터미널 강조 코드를 파이프로 받아 해석할 수 있는지는 미확인이다.
- `--progress`: 합성 진행 막대만 보여 준다. 크기(레벨) 신호를 내는 옵션은 없다.

정리하면 `say` 하나로는 실시간 크기 신호를 얻을 수 없다. 방식별로 보면 다음과 같다.

| 방식 | 크기 신호 | 단어·음소 | 출력 장치 선택 | 추가 의존성 |
|---|---|---|---|---|
| A. `say -o x.wav --file-format=WAVE --data-format=LEI16@22050` → 곡선 계산 → 재생 | 곡선(정확) | 없음 | 재생기에 달림 | 장치를 고르는 재생기 필요(B, C) |
| B. A + pyobjc `AVAudioPlayer`로 재생 | 곡선 또는 `averagePower` 미터링 | 없음 | `currentDevice`(장치 UID) | pyobjc-framework-AVFoundation |
| C. A + sounddevice(PortAudio)로 재생 | 곡선 | 없음 | 장치 이름·번호 | sounddevice(이번에 자세히 조사하지 않음, 미확인) |
| D. `say -a 장치`로 실시간 재생 + 같은 문장을 같은 음성·속도로 `say -o` 해서 곡선만 계산 | 곡선(시작 시각은 어림) | 없음 | `say -a` 그대로 | 없음. 두 프로세스의 시작 지연 차이만큼 어긋난다(미확인) |
| E. pyobjc NSSpeechSynthesizer | 없음 | 단어·음소 콜백 | 공개 API 없음(아래) | pyobjc-framework-Cocoa |
| F. pyobjc AVSpeechSynthesizer `write…toMarkerCallback` → 버퍼 모아 재생 | 버퍼에서 곡선 | 단어·음소 마커(바이트 위치) | 재생기에 달림(B 또는 AVAudioEngine) | pyobjc-framework-AVFoundation, macOS 13+ |

### 3.2 재생기 문서 근거

- [`AVAudioPlayer.currentDevice`](https://developer.apple.com/documentation/avfaudio/avaudioplayer/currentdevice): macOS 10.13+, 장치 고유 ID 문자열이다. `say -a ?`가 보여 주는 이름에서 이 UID를 얻으려면 CoreAudio C API가 필요하다(미확인).
- [`averagePower(forChannel:)`](https://developer.apple.com/documentation/avfaudio/avaudioplayer/averagepower(forchannel:)): dBFS(−160~0), `isMeteringEnabled`와 `updateMeters()`가 필요하다. 파동 신호로 바로 쓸 수 있다.
- [`AVAudioPlayer.rate`](https://developer.apple.com/documentation/avfaudio/avaudioplayer/rate): "range of 0.5 … to 2.0", 음높이를 유지한다. x5에는 못 쓴다.
- [`AVAudioUnitTimePitch.rate`](https://developer.apple.com/documentation/avfaudio/avaudiounittimepitch/rate): "range of supported values is 1/32 to 32.0". AVAudioEngine을 쓰면 출력 장치는 [`AUAudioUnit.setDeviceID(_:)`](https://developer.apple.com/documentation/audiotoolbox/auaudiounit/setdeviceid(_:))(macOS 전용)로 정한다. pyobjc로 이 경로를 실제로 묶을 수 있는지는 미확인이다.

### 3.3 콜백 문서 근거

- [NSSpeechSynthesizer](https://developer.apple.com/documentation/appkit/nsspeechsynthesizer):
  - macOS 10.3~, **14.0부터 deprecated**("Use AVSpeechSynthesizer in AVFoundation instead").
  - `rate`는 wpm이다. `startSpeaking(_:to:)`는 AIFF 파일로 쓴다.
  - 문서에 출력 장치 속성 키가 없다. `startSpeaking(_:)`은 "the system's default sound output device"로 말한다.
- [NSSpeechSynthesizerDelegate](https://developer.apple.com/documentation/appkit/nsspeechsynthesizerdelegate):
  - `speechSynthesizer:willSpeakWord:ofString:`, `speechSynthesizer:willSpeakPhoneme:`는 "Sent just before a synthesized word/phoneme is spoken through the sound output device"다. 재생에 맞춰 온다는 뜻이다.
  - 크기 신호는 없다.
- Carbon Speech Synthesis Manager의 [`kSpeechOutputToAudioDeviceProperty`](https://developer.apple.com/documentation/applicationservices/kspeechoutputtoaudiodeviceproperty)(AudioDeviceID, macOS 10.6+)로는 장치를 고를 수 있다. 하지만 pyobjc는 이 프레임워크를 감싸지 않는다: "*SpeechSynthesis* Definitions in the framework are not yet available in Python" ([pyobjc API notes](https://github.com/ronaldoussoren/pyobjc/blob/main/docs/apinotes/ApplicationServices.rst)).
- [AVSpeechSynthesizer](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer)(macOS 10.14+):
  - 델리게이트 [`willSpeakRangeOfSpeechString`](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizerdelegate)은 단어 범위를, [`willSpeakMarker`](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizerdelegate/speechsynthesizer(_:willspeak:utterance:))는 macOS 14+에서 마커를 준다.
  - [`write(_:toBufferCallback:)`](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer/write(_:tobuffercallback:))(macOS 10.15+)는 오디오 버퍼를 준다. [`write(_:toBufferCallback:toMarkerCallback:)`](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer/write(_:tobuffercallback:tomarkercallback:))(macOS 13+)는 버퍼와 함께 [`AVSpeechSynthesisMarker`](https://developer.apple.com/documentation/avfaudio/avspeechsynthesismarker)(`mark`, `byteSampleOffset`, `textRange`, `phoneme`)를 준다. SAPI 메모리 합성 + 이벤트와 같은 구조다.
  - 출력 경로 지정용 [`outputChannels`](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer/outputchannels)는 가용 플랫폼 목록에 macOS가 없다. 따라서 장치를 고르려면 `write`로 받아 직접 재생해야 한다.
- pyobjc AVFoundation은 `writeUtterance_toBufferCallback_`과 `writeUtterance_toBufferCallback_toMarkerCallback_`의 블록 인자를 지원한다. 마커 종류 상수는 Phoneme 0, Word 1, Sentence 2, Paragraph 3, Bookmark 4다([pyobjc test_avspeechsynthesis.py](https://github.com/ronaldoussoren/pyobjc/blob/main/pyobjc-framework-AVFoundation/PyObjCTest/test_avspeechsynthesis.py)).
- 델리게이트 콜백이 Tk 메인 루프 안에서 제때 오는지(런루프 조건)는 미확인이다.

---

## 4. 첫마디까지 시간과 블루투스 무음 (티켓 항목 4)

### 4.1 지금 방식(장치로 바로 Speak)

- 호출에서 StartStream까지 42~64ms가 걸린다. 엔진은 스스로 앞에 무음을 넣는데, Rate 0에서 110ms, Rate 10에서 40ms였다(말소리 시작 위치 기준). 그래서 첫 단어 이벤트는 호출 뒤 166~172ms에 왔다.
- 블루투스 무음이 들어가면 첫 단어는 호출 뒤 약 1.16s다.

### 4.2 미리 합성할 때 걸리는 시간 (Heami, 동기 Speak)

| 대본 길이 | 오디오 길이(Rate 0) | 메모리 스트림 | 파일 스트림 | 문장마다 Speak(같은 메모리 스트림) | 첫 문장만 |
|---|---|---|---|---|---|
| 118자 | 18.95s | 72~87ms | 110ms | 87ms | 20ms |
| 356자 | 56.85s | 325~391ms | 220ms | 350ms | 16ms |
| 1189자 | 189.5s | 2266~2459ms | 878ms | 2579ms | 21ms |

- 메모리 스트림은 길이에 비례하지 않고 더 빨리 느려진다. 스트림이 커지면서 다시 할당하는 탓으로 보인다(추정). 긴 대본은 파일 스트림을 쓰거나 **문장마다 새 메모리 스트림**에 합성한다.
- Rate 10에서는 오디오가 짧아 1189자도 1224ms였다.

### 4.3 무음을 재생하는 동안 합성하기 (실측)

재생용 SpVoice A로 `<silence msec="1000"/>`를 비동기로 내보냈다. 그 사이 SpVoice B로 본문을 메모리에 합성하고, 끝나면 A에 `SpeakStream`으로 큐에 넣었다. 가상 장치, 무음 데이터로 쟀다.

| 대본 | 합성 끝(호출 기준) | 본문 시작 스트림 위치 | 결과 |
|---|---|---|---|
| 118자 | 126ms | 1000ms | 무음 바로 뒤에 이어짐. 끝 시각이 위치보다 38ms 늦은 정도 |
| 356자 | 358ms | 1000ms | 이어짐(19ms) |
| 1189자 | 2074ms | 1000ms | **본문이 호출 뒤 약 2.1s에 시작**. 끝 시각이 위치보다 1110ms 늦다. 무음이 끝난 뒤 약 1.1초 끊김 |

결론: 블루투스 무음(1s) 안에 합성이 끝나면 지연이 전부 가려진다. 긴 대본은 첫 문장(약 20ms)부터 넣고 나머지를 이어서 큐에 넣으면 된다. **자동 발표**처럼 무음이 없는 경우에는 현재 장을 읽는 동안 다음 장을 미리 합성해 둔다.

### 4.4 지금 구현의 문제: 무음도 배속만큼 짧아진다

`<silence msec="1000"/>`만 따로 합성해 길이를 쟀다.

| Rate(배속) | Heami | Zira |
|---|---|---|
| 0 (x1) | 999ms | 999ms |
| 6 (x2) | **525ms** | **514ms** |
| 10 (x3) | **339ms** | **329ms** |
| 10 + 지속 XML `<rate absspeed="5"/>` | 339ms | 329ms |

`tts.py`는 `self._sp.Rate`를 먼저 설정하고 무음을 Speak하므로, x2부터는 코드 주석에 적힌 "깨어나는 동안(약 0.5초)"보다 짧아질 수 있다. Rate 10에서 고치는 방법을 비교했다(첫 소리까지의 위치).

| 방법 | 첫 소리까지 |
|---|---|
| A. 지금 방식 | 379ms |
| B. Rate=0으로 무음을 비동기 Speak → Rate=10으로 본문 | 379ms (비동기라 이미 바뀐 Rate로 합성된다) |
| C. `<rate speed="-10"><silence msec="1000"/></rate>` | 379ms (XML 속도는 무음에 영향 없음) |
| D. `msec`를 배속만큼 늘림(`1000 × 3^(Rate/10)` = 2990) | 1048ms |

D가 가장 작은 수정이다. 미리 합성 방식에서는 PCM 앞에 0 바이트(`AvgBytesPerSec × 1초`)를 붙이면 Rate와 상관없이 정확하다.

macOS `say`의 `[[slnc N]]`은 "the precise timing of the silence will vary among synthesizers"([Speech Synthesis Programming Guide](https://developer.apple.com/library/archive/documentation/UserExperience/Conceptual/SpeechSynthesisProgrammingGuide/FineTuning/FineTuning.html), 보관 문서)다. 속도에 따라 줄어드는지는 미확인이다. `say -o`로 미리 합성한다면 여기도 0 바이트를 붙이면 된다.

---

## 5. 배속 한계 (티켓 항목 5)

### 5.1 SAPI Rate → 실제 배속 (말소리 구간 길이 비교)

| Rate | -10 | -8 | -6 | -4 | -2 | 0 | 1 | 2 | 3 | **4** | 5 | **6** | 7 | 8 | 9 | **10** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Heami | 0.33 | 0.41 | 0.51 | 0.65 | 0.80 | 1.00 | 1.11 | 1.24 | 1.39 | **1.55** | 1.73 | **1.93** | 2.15 | 2.40 | 2.68 | **2.99** |
| Zira | 0.33 | 0.42 | 0.52 | 0.66 | 0.82 | 1.00 | 1.15 | 1.28 | 1.44 | **1.62** | 1.80 | **1.99** | 2.17 | 2.36 | 2.56 | **2.70** |
| 3^(Rate/10) | 0.33 | 0.42 | 0.52 | 0.64 | 0.80 | 1.00 | 1.12 | 1.25 | 1.39 | 1.55 | 1.73 | 1.93 | 2.16 | 2.41 | 2.69 | 3.00 |

- Heami는 3^(Rate/10)과 거의 일치한다. 지금 코드의 변환식 `round(10·log(speed)/log 3)`가 맞는 셈이다.
  - x1.5 → Rate 4 → 1.55배
  - x2 → Rate 6 → 1.93배(Zira 1.99배)
  - x5 → Rate 10 → **2.99배(Zira 2.70배)**. x5에 못 미친다.
- 문서:
  - `SetRate`는 "Supported values range from -10 to 10 - values outside this range may be truncated", "granularity … is engine dependent"다. XML로 준 속도와 "combine"한다([ISpVoice::SetRate](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee125019(v=vs.85))).
  - SAPI 5.0 엔진 지침은 "-10 … one-third", "+10 … three times"라고 한다. 같은 글이 한 단계를 "10th root of 6 (about 1.2)"라고도 적는데, 이는 양 끝과 맞지 않는다. 실측 한 단계는 3^(1/10) ≈ 1.116이었다([Engine Characteristics](https://learn.microsoft.com/en-us/previous-versions/aa917962(v=msdn.10)), Windows Embedded CE 문서).
- Rate 속성에 11, 15, 20을 넣으면 오류 없이 그 값이 다시 읽히지만, 실제로는 2.99배에서 멈췄다(엔진에서 잘린다).

### 5.2 Rate 10을 넘기기: Rate 속성 + SAPI XML

[XML TTS Tutorial](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms717077(v=vs.85))은 `<rate speed|absspeed>`가 "integer between negative ten and ten … may be truncated by the engine (but are not truncated by SAPI)"이고, "combined with values specified programmatically (using ISpVoice::SetRate)"라고 한다. 실측해 보니 **속성과 XML이 더해지고, 합 20까지 반영됐다.**

| 합계(Rate 10 + XML speed) | 10 | 11 | 12 | 13 | 14 | **15** | 16 | 17 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Heami | 2.99 | 3.33 | 3.71 | 4.15 | 4.62 | **5.17** | 5.77 | 6.38 | 7.14 | 8.02 | 8.93 |
| Zira | 2.70 | 2.89 | 3.00 | 3.13 | 3.19 | 3.27 | 3.32 | 3.36 | 3.40 | 3.45 | 3.47 |

- `absspeed`도 속성에 더해진다. `Rate=0 + <rate absspeed="10">`은 2.99배, `Rate=10 + <rate absspeed="10">`은 8.93배였다.
- XML 값은 정수만 받는다. `speed="4.5"`는 "SSML input not valid; cannot find 'speak' element" 오류가 났다.
- **본문은 지금처럼 NotXML로 두고 속도만 XML로 올리는 법:** `SVSFPersistXML`(32)로 속도 태그만 먼저 Speak한다. 이 플래그는 "Global state changes in the XML markup will persist across speak calls"다([SPEAKFLAGS](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee431843(v=vs.85))).

```python
sp.Rate = 10
sp.Speak('<rate absspeed="5"/>', 8 | 32)   # SVSFIsXML | SVSFPersistXML
sp.Speak(text, 16)                         # SVSFIsNotXML → Heami 5.17배
```

같은 SpVoice로 이어서 실측한 결과다.

| 순서 | 배속 |
|---|---|
| Rate=10 + 지속 `<rate absspeed="5"/>` | 5.17 |
| 그다음 Rate=0, XML 없이 | **1.73 (지속 설정이 남아 있음)** |
| Rate=0 + 지속 `<rate absspeed="0"/>` | 1.00 |
| Rate=10 + 지속 `<rate absspeed="10"/>` | 8.93 |
| Rate=4 + 지속 `<rate absspeed="0"/>` | 1.55 |

→ 매번 읽기를 시작할 때 `<rate absspeed="N"/>`를 지속 플래그로 다시 넣어야 한다(배속이 1~2면 N=0).
→ 이렇게 빠르게 해도 단어 27, 음소 228, viseme 215개가 그대로 왔다.

- SSML(`SVSFParseSsml`=256) `<prosody rate>`도 Heami에서 쟀다.
  - x-slow 0.33, slow 0.65, medium 1.00, fast 1.55, x-fast 2.99
  - "1.5" 1.55, "2.0" 1.93, "5.0"은 2.99(최대 10에서 잘림)
  - "50%"와 "+50%"는 둘 다 1.55. SSML 1.0의 뜻과 다르다.
  - Rate=10과 함께 쓰면 x-fast는 8.93배다.
  - SAPI XML보다 나을 것이 없다.

### 5.3 엔진이 못 내는 배속: 합성 후 시간 늘이기

스크래치 venv(numpy 2.5.4, audiotsm 0.1.2)에서 쟀다. 들어 보지 않았으므로 음질은 미확인이다.

| 원본 | 목표 | 늘이기 배율 | 알고리즘 | 출력 길이 | 실효 배속 | 처리 시간 |
|---|---|---|---|---|---|---|
| Heami Rate 0 (18.95s) | x1.5 | 1.50 | WSOLA / 위상 보코더 | 12.59s / 12.59s | 1.50 / 1.49 | 257ms / 238ms |
| 〃 | x2 | 2.00 | WSOLA / 위상 보코더 | 9.43s / 9.45s | 1.99 / 1.99 | 134ms / 117ms |
| 〃 | x5 | 5.00 | WSOLA | **2.35s** | **7.92 (잘못됨)** | 31ms |
| 〃 | x5 | 5.00 | 위상 보코더 | 3.76s | 4.93 | 46ms |
| Heami Rate 10 (6.35s) | x5 | 1.68 | WSOLA / 위상 보코더 | 3.74s / 3.74s | 5.01 / 4.95 | 48ms / 67ms |

- 권장 순서: 음성이 낼 수 있는 최대 배속으로 합성한다(Heami는 XML 합으로 x5까지 가능하므로 늘이기가 필요 없다). 남은 배율만 늘이기로 처리해서, 늘이기 배율을 2 아래로 둔다(Zira는 3.47배 → 남은 1.44배).
- audiotsm은 MIT이고 마지막 릴리스가 2017-09-21(0.1.2)이다([PyPI](https://pypi.org/project/audiotsm/)). 유지보수가 끊겼고 WSOLA가 높은 배율에서 길이를 잘못 낸다. 넣는다면 numpy로 위상 보코더나 WSOLA를 직접 짜는 편이 낫다. numpy는 PyInstaller 실행 파일 크기를 키운다(크기는 미측정).
- ffmpeg `atempo`는 범위가 [0.5, 100.0]이다. 2를 넘으면 샘플을 섞지 않고 건너뛰니 이어서 쓰라고 권한다([FFmpeg filters: atempo](https://ffmpeg.org/ffmpeg-filters.html#atempo)). 실행 파일을 따로 들고 다녀야 한다.
- 소리를 빠르게만 재생(리샘플)하면 음높이가 5배 올라가서 쓸 수 없다.

### 5.4 macOS 배속 (문서 근거, 미실행)

- `say -r`은 "Speech rate to be used, in words per minute"다. 상한은 man page에 없다.
- [kSpeechRateProperty](https://developer.apple.com/documentation/applicationservices/kspeechrateproperty): "The range of supported rates is not predefined by the Speech Synthesis Manager; each speech synthesizer provides its own range … Average human speech occurs at a rate of 180 to 220 words per minute."
- [Speech Synthesis Programming Guide](https://developer.apple.com/library/archive/documentation/UserExperience/Conceptual/SpeechSynthesisProgrammingGuide/FineTuning/FineTuning.html)(보관 문서)의 `rate` 내장 명령: "translates into a range of 50 to 500 words per minute".
- 지금 코드는 `BASE_WPM = 190`이라 x1.5=285, x2=380, **x5=950 wpm**이다. x2까지는 문서 범위 안이지만 x5는 밖이다. 음성(Yuna 등)이 950을 따르는지, 500에서 잘리는지는 미확인이다. `say`의 실제 기본 wpm도 미확인이다.
- [AVSpeechUtterance.rate](https://developer.apple.com/documentation/avfaudio/avspeechutterance/rate)는 `AVSpeechUtteranceMinimumSpeechRate`~`MaximumSpeechRate` 사이의 소수다. 문서에 수치는 없다. 이 값이 몇 배속인지는 미확인이다.
- x5가 필요하면 미리 합성(`say -o`, 문서 범위 안의 최대 wpm) 뒤 시간 늘이기를 쓴다. pyobjc라면 AVAudioEngine + `AVAudioUnitTimePitch`(1/32~32)를, 아니면 numpy로 직접 늘인다. `AVAudioPlayer.rate`는 2.0이 상한이라 안 된다.

---

## 확인하지 못한 것

- **귀에 들리기까지의 지연**: SAPI 장치 위치 이후의 OS 믹서와 블루투스 코덱 지연. 소리를 내지 않아 재지 못했다.
- **고속 음성과 시간 늘이기의 음질과 알아듣기 쉬운 정도**: x5 Heami(XML 합 15)나 늘이기 결과를 들어 보지 않았다.
- 이 PC에 없는 음성(다른 OneCore 음성, 제3자 SAPI 음성)의 Rate 상한과 이벤트 지원 여부.
- PyInstaller로 묶은 실행 파일에서 `DispatchWithEvents`·`CastTo`의 makepy 생성이 되는지. Status 폴링과 벽시계 방식은 makepy가 필요 없다.
- 메모리 스트림 합성이 길이에 비례하지 않고 느려지는 원인(재할당이라는 것은 추정).
- `AudioLevel`을 볼륨 적용 전에 계산하는지 후에 계산하는지(TTS `Volume=0`에서는 0으로 나왔다).
- macOS 전부 미실행이다.
  - `say -r` 상한과 기본 wpm, `say -i` 출력을 파이프로 해석할 수 있는지
  - say man page 미러가 최신 macOS와 같은지
  - NSSpeechSynthesizer/AVSpeechSynthesizer 델리게이트가 Tk 메인 루프 아래에서 오는지
  - `say -a`의 이름에서 `AVAudioPlayer.currentDevice` UID를 얻는 법
  - AVSpeechUtterance rate 수치와 배속의 관계
  - sounddevice로 장치를 골라 재생하는 방법의 세부
  - 방식 D(실시간 `say` + 따로 계산한 곡선)의 어긋남 정도
- `afplay`에 출력 장치 선택 옵션이 있는지: 1차 문서를 찾지 못했다.

## 출처

**Microsoft SAPI**
- [SPEVENTENUM (SAPI 5.4)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee431845(v=vs.85))
- [SpeechVoiceEvents (SAPI 5.3)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms720886(v=vs.85))
- [SpVoice AudioLevel event (SAPI 5.3)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms723582(v=vs.85))
- [SPVISEMES (SAPI 5.4)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee431873(v=vs.85))
- [ISpeechVoiceStatus (SAPI 5.3)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms722539(v=vs.85))
- [ISpeechAudioStatus (SAPI 5.3)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms720955(v=vs.85))
- [SpVoice SpeakStream method (SAPI 5.4)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee125649(v=vs.85))
- [ISpVoice::SetRate (SAPI 5.4)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee125019(v=vs.85))
- [SPEAKFLAGS (SAPI 5.4)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee431843(v=vs.85))
- [XML TTS Tutorial (SAPI 5.3)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms717077(v=vs.85))
- [Engine Characteristics (Windows Embedded CE, SAPI 5.0 엔진 지침)](https://learn.microsoft.com/en-us/previous-versions/aa917962(v=msdn.10))

**pywin32 / pyobjc 소스**
- [pywin32 `win32com/client/__init__.py` — `DispatchWithEvents`](https://github.com/mhammond/pywin32/blob/main/com/win32com/client/__init__.py)
- [pyobjc API notes: ApplicationServices (SpeechSynthesis 미지원)](https://github.com/ronaldoussoren/pyobjc/blob/main/docs/apinotes/ApplicationServices.rst)
- [pyobjc AVFoundation `test_avspeechsynthesis.py`](https://github.com/ronaldoussoren/pyobjc/blob/main/pyobjc-framework-AVFoundation/PyObjCTest/test_avspeechsynthesis.py)

**Apple**
- [say(1) man page 미러 (unix.com)](https://www.unix.com/man-page/osx/1/say/)
- [Speech Synthesis Programming Guide — Fine-Tuning (보관 문서)](https://developer.apple.com/library/archive/documentation/UserExperience/Conceptual/SpeechSynthesisProgrammingGuide/FineTuning/FineTuning.html)
- [NSSpeechSynthesizer](https://developer.apple.com/documentation/appkit/nsspeechsynthesizer)
- [NSSpeechSynthesizerDelegate](https://developer.apple.com/documentation/appkit/nsspeechsynthesizerdelegate)
- [kSpeechOutputToAudioDeviceProperty](https://developer.apple.com/documentation/applicationservices/kspeechoutputtoaudiodeviceproperty)
- [kSpeechRateProperty](https://developer.apple.com/documentation/applicationservices/kspeechrateproperty)
- [AVSpeechSynthesizer](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer)
- [AVSpeechSynthesizer.write(_:toBufferCallback:)](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer/write(_:tobuffercallback:))
- [AVSpeechSynthesizer.write(_:toBufferCallback:toMarkerCallback:)](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer/write(_:tobuffercallback:tomarkercallback:))
- [AVSpeechSynthesizer.outputChannels](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer/outputchannels)
- [AVSpeechSynthesisMarker](https://developer.apple.com/documentation/avfaudio/avspeechsynthesismarker)
- [AVSpeechSynthesizerDelegate](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizerdelegate)
- [speechSynthesizer(_:willSpeak:utterance:)](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizerdelegate/speechsynthesizer(_:willspeak:utterance:))
- [AVSpeechUtterance.rate](https://developer.apple.com/documentation/avfaudio/avspeechutterance/rate)
- [AVAudioPlayer.currentDevice](https://developer.apple.com/documentation/avfaudio/avaudioplayer/currentdevice)
- [AVAudioPlayer.rate](https://developer.apple.com/documentation/avfaudio/avaudioplayer/rate)
- [AVAudioPlayer.averagePower(forChannel:)](https://developer.apple.com/documentation/avfaudio/avaudioplayer/averagepower(forchannel:))
- [AVAudioUnitTimePitch.rate](https://developer.apple.com/documentation/avfaudio/avaudiounittimepitch/rate)
- [AUAudioUnit.setDeviceID(_:)](https://developer.apple.com/documentation/audiotoolbox/auaudiounit/setdeviceid(_:))

**기타**
- [audiotsm (PyPI)](https://pypi.org/project/audiotsm/)
- [FFmpeg Filters — atempo](https://ffmpeg.org/ffmpeg-filters.html#atempo)
