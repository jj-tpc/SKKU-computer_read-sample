# Qt 음성·소리 모듈로 목소리 신호 얻기

조사일 2026-10-16. 질문은 "PySide6(Qt)로 다시 만드는 앱에서 Qt 모듈이 새 의존성(numpy, pyobjc 등)과 운영체제별 코드를 대신할 수 있는가"다. 앱이 말하는 동안 필요한 것은 네 가지다.

- 20ms 단위 크기 곡선(원 버튼 파동, 강아지 입 3장)
- 단어마다 시작 시각(말풍선에 단어를 소리에 맞춰 띄우기)
- 사용자가 고른 출력 장치로 재생
- 음높이를 유지한 x1, x1.5, x2, x5 배속

SAPI 자체의 동작(메모리 합성, 단어 이벤트, Rate와 XML 배속, 블루투스 앞 무음)은 이전 조사 `docs/research/tts-signal-speed.md`(브랜치 `research/tts-signal-speed`)에 있다. PySide6 6.12 선택과 Qt 라이선스 의무는 `docs/research/gui-toolkit.md`(브랜치 `research/gui-toolkit`)에 있다. 이 문서는 두 문서의 내용을 반복하지 않는다.

**근거 표시**

- **실측**: 이 PC에서 직접 실행해 잰 값
- **문서**: Qt·Microsoft·Apple 공식 문서, Qt 소스 코드(태그 v6.12.0), PyPI 페이지
- **추정**: 위 둘에서 끌어낸 판단. 실행해 보지 않았다.

macOS는 실행할 수 없어서 모두 문서 근거이고 **미실행**이다.

## 결론 요약

1. **재생과 장치 선택은 Qt로 바꿀 수 있다.** `QMediaDevices.audioOutputs()`로 장치를 고르고 `QAudioSink`로 PCM을 재생한다.
   - Windows에서는 고른 장치로 22050Hz 모노 16비트가 그대로 재생됐다(실측).
   - macOS도 같은 코드로 CoreAudio 장치에 묶인다(문서). 그래서 이전 조사에서 macOS 장치 선택에 필요하다고 한 **pyobjc나 sounddevice가 필요 없다**.
2. **x5 배속의 시간 늘이기는 numpy 대신 `QMediaPlayer`로 할 수 있다.** FFmpeg 백엔드의 `pitchCompensation`(Qt 6.10+)이 음높이를 유지한 채 빠르게 재생한다.
   - 실측: Windows에서 지원 여부가 `Available`, 기본값이 켜짐이었다. x1.5, x2, x5 모두 기대한 시간에 끝났다.
   - 문서: 내부 라이브러리(Signalsmith Stretch)는 "0.75~1.5배에서 가장 좋게 들리고", 2배를 넘으면 처리 방식이 바뀐다.
   - 추정: x5 전체를 늘이기로 처리하기보다, 음성이 낼 수 있는 최고 속도로 합성하고 남은 2배 이하만 늘이는 것이 낫다. 음질은 들어 보지 않았다.
3. **합성(PCM)은 Qt로 바꿀 수 없다.** C++의 `QTextToSpeech::synthesize()`는 템플릿 함수라서 **PySide6 6.12에는 없다**(실측: `hasattr` False, 문서: 바인딩 정의에 없음). 따라서 크기 곡선을 얻으려면 지금처럼 OS별 합성 코드가 필요하다. Windows는 SAPI 메모리 합성(pywin32), macOS는 `say -o`다.
4. **`sayingWord`(단어 신호)는 `say()`로 엔진이 직접 재생할 때만 쓸 수 있다.**
   - Windows WinRT 엔진은 강력하다.
     - `audioDevice` 매개변수로 장치를 고를 수 있다.
     - x5가 음성 자체로 된다(rate 0.8에서 4.95배).
     - 단어 신호가 SAPI 메모리 합성의 단어 위치와 1~3ms 안에서 맞았다(실측).
     - 하지만 PCM을 주지 않아 크기 곡선이 없다.
   - macOS darwin 엔진은 장치를 고를 수 없다(문서). 그래서 장치 선택과 단어 시각을 Qt TTS 하나로 함께 얻을 수 없다.
5. **비용(실측, Windows).**
   - PySide6-Addons wheel은 40.5MB(macOS universal2는 90.5MB)다.
   - PyInstaller 결과물은 Multimedia+TextToSpeech를 쓰면 23.8MB 늘고, 그중 FFmpeg DLL이 19.7MB다. Addons를 설치하기만 해도 가상 키보드 플러그인이 Qt Quick을 끌고 와 15.9MB가 더 붙는다.
   - numpy는 31.4MB 늘었다.
   - FFmpeg 9.0.1은 LGPL-2.1+로, 동적 링크 DLL로 들어간다.
6. **버전.** 위 기능에는 PySide6 6.10 이상이 필요하다. 권장은 이미 정한 6.12.x다. Qt 6.12는 Windows 10(1809+)을 지원하는 마지막 버전이고, macOS는 14.4 이상(arm64 포함)을 지원한다(문서).

### 권장 음성 처리 흐름

| 단계 | Windows | macOS (문서·추정, 미실행) |
|---|---|---|
| 합성 | SAPI `SpMemoryStream` 미리 합성(pywin32, 기존 의존성). 이전 조사 방식 그대로 | `say -o x.wav --file-format=WAVE --data-format=LEI16@22050 -r <wpm>` |
| 크기 곡선 | 합성한 PCM에서 순수 파이썬으로 20ms RMS(실측 719프레임에 7~9ms) | 같음 |
| 단어 시각 | 합성할 때 받은 SAPI 단어 이벤트의 오디오 위치(실측 19개) | `say`는 단어 시각을 주지 않는다. 문장(또는 구)마다 따로 합성해 길이를 이어 붙이고, 문장 안 단어는 글자 수에 비례해 나눈다(추정, 근사). 정확한 값이 필요하면 pyobjc `AVSpeechSynthesizer write…toMarkerCallback`(macOS 13+)을 쓴다 |
| 장치 재생 | `QAudioSink(QAudioDevice, format)`. 위치는 `processedUSecs()`(10ms 단위) | 같은 코드(CoreAudio, 장치 UID로 연결) |
| x1.5, x2 | 합성 속도로 낸다(SAPI Rate 4, 6) | `say -r` 285, 380wpm(문서 범위 50~500 안) |
| x5 | Heami는 합성으로 낸다(Rate 10 + XML absspeed 5, 이전 조사 5.17배). 다른 음성은 최고 속도로 합성하고 남은 배율만 `QMediaPlayer.setPlaybackRate` + `pitchCompensation`으로 처리 | `say -r 500`(약 2.6배)으로 합성하고 남은 약 1.9배를 `QMediaPlayer` + `pitchCompensation`으로 처리 |
| 추가 의존성 | **PySide6-Addons만**(QtMultimedia). numpy 없음 | **PySide6-Addons만**. 단어 시각을 정확히 하려면 pyobjc-framework-AVFoundation |

- Windows만 보면 더 짧은 길도 있다. QtTextToSpeech WinRT 엔진으로 `say()`하면 장치, 단어 신호, x5가 모두 된다. 이 경우 파동과 입은 크기 곡선 대신 단어 신호로 움직여야 한다. 그러면 운영체제마다 신호의 종류가 달라진다.
- 블루투스용 앞 무음은 PCM 앞에 0을 붙인다. 단, `QMediaPlayer`로 배속 재생하면 무음도 같은 배율로 짧아진다. 그래서 무음 길이에 재생 배율을 곱해 붙인다(추정, 계산).

---

## 실험 환경과 안전 조치

**환경**

- Windows 11 Pro 10.0.26200, Python 3.14.7
- 스크래치 venv: PySide6-Essentials·Addons 6.12.0(Qt 6.12.0), pywin32 312, PyInstaller 6.22.3, numpy 2.5.4. 프로젝트 venv는 건드리지 않았다.
- 음성
  - SAPI: Microsoft Heami Desktop(한국어), Microsoft Zira Desktop(영어)
  - WinRT: Microsoft Heami(한국어)
- 출력 장치 4개: Realtek 스피커(기본), AMD HDMI 디스플레이, Steam Streaming Microphone, Steam Streaming Speakers. **블루투스 장치는 연결되어 있지 않았다.**

**소리를 내지 않았다.**

- 합성은 메모리에만 했다.
- 재생 시험은 모두 물리 스피커와 연결되지 않은 가상 장치 `스피커(Steam Streaming Speakers)`로만 보냈다. 거기에 더해 볼륨 0이나 0 데이터를 썼다.
  - `QAudioSink`: 0 데이터 + 볼륨 0
  - `QMediaPlayer`: 무음 WAV + 볼륨 0
  - WinRT `say()`: 엔진 볼륨 0. WinRT 엔진에서는 합성기 자체의 `AudioVolume`이다([S7c]).
- 440Hz 음은 `QAudioBufferOutput`만 단 플레이어로 디코드만 했다. 이 경우 출력 장치(싱크)가 만들어지지 않는다([M14b]).

**시험 문장**은 한국어 86자 4문장(태양계 소개)이다. Heami 기준 14.39초다.

---

## 1. QtTextToSpeech (PySide6-Addons)

### 1.1 엔진, 기본 엔진, 기능 플래그

| 항목 | Windows | macOS |
|---|---|---|
| 엔진 | **실측**: `availableEngines()` = `sapi`, `winrt`, `mock`(순서는 실행마다 다름). **문서**: winrt는 MSVC 빌드에서만 만든다 [S1] | **문서**: `darwin`(AVSpeechSynthesizer) 하나다 [S1]. 예전 `macos`(NSSpeechSynthesizer) 엔진은 6.9에서 지웠다 [S9] |
| 기본 엔진 | **실측**: `winrt`. **문서**: 우선순위 winrt 80, sapi 50이고 높은 쪽을 고른다 [S2][S3] | **문서**: `darwin`(우선순위 100) [S2] |
| `engineCapabilities()` | **실측**: sapi와 winrt 모두 `Speak, PauseResume, WordByWordProgress, Synthesize` | **문서**: 같은 4가지 [S2]. 엔진 코드가 아니라 플러그인 JSON에서 읽는 값이다 [S4] |

### 1.2 `synthesize()` — PySide6에서는 쓸 수 없다

| 항목 | 내용 | 근거 |
|---|---|---|
| C++ API | `synthesize(text, receiver, functor)`는 템플릿 함수다. 콜백으로 `(QAudioFormat, QByteArray)`나 `QAudioBuffer`를 여러 번 받는다 | 문서 [S5][Q1] |
| PySide6 6.12 | `QTextToSpeech`에 `synthesize`가 없다. `dir()`에 비슷한 이름은 신호 `aboutToSynthesize`뿐이다 | **실측** |
| | PySide6 바인딩 정의(typesystem)에 `synthesize`가 없다. PySide6 문서도 설명에서는 `synthesize()`를 언급하지만 메서드 목록에는 없다 | 문서 [S11][Q4] |
| | QML `TextToSpeech` 타입에도 없다(wheel의 `plugins.qmltypes`) | **실측** |
| 엔진 객체를 직접 쓰기 | `QTextToSpeechEngine.synthesize`는 노출되어 있다. 하지만 `QTextToSpeech`가 만든 플러그인 엔진은 자식 객체로 잡히지 않았다(`findChildren` 빈 목록) | **실측** |
| 결론 | PySide6에서는 Qt TTS로 PCM을 얻을 수 없다. 크기 곡선용 PCM은 OS별 합성 코드로 얻는다 | 추정 |

참고(문서, C++에서 쓴다면) [S6][S7][S8]:

- 형식: sapi와 winrt는 16kHz 모노 Int16으로 고정이다. darwin은 첫 버퍼의 형식을 따른다.
- 전달: 모두 여러 조각으로 나뉘어 온다.

### 1.3 `sayingWord`(단어 신호)

| 엔진 | 언제 오나 | 오디오와의 시각 | 근거 |
|---|---|---|---|
| winrt | `say()`에서만. `synthesize()`에서는 안 온다 | 합성기의 단어 경계 메타데이터(시작 시각)를 받아 둔다. 그리고 내부 `QAudioSink`가 Active가 된 순간부터 타이머로 낸다. 실제 재생 위치를 읽지는 않는다 | 문서 [S7a][S7b]. Qt 커밋도 "재생과 어긋날 위험"을 인정한다 [S10] |
| | | **실측**: Speaking 상태에서 단어 신호까지의 시간과, SAPI(Heami Desktop) 메모리 합성의 단어 오디오 위치 차이가 19개 모두 1~3ms였다(최소 1, 중앙 1, 최대 3). 예: "오늘은" 101ms, "태양계의" 582ms, "행성들에" 1186ms. 두 음성의 타이밍이 같다는 뜻이기도 하다 | 실측 |
| sapi | `say()`와 `synthesize()` 모두(SAPI 단어 경계 이벤트) | 신호에는 글자 위치만 있고 오디오 위치는 없다. 장치 재생 중 SAPI 단어 이벤트가 7~69ms 늦게 온다는 것은 이전 조사의 실측이다 | 문서 [S6c]. Qt sapi `say()`는 실행하지 않았다(기본 장치로 나가므로) |
| darwin | `say()` 중 AVSpeechSynthesizer 델리게이트 `willSpeakRangeOfSpeechString`에서 | 델리게이트가 부를 때. `synthesize()` 중에도 오는지는 미확인 | 문서 [S8a]. 미실행 |

- 소리 크기 신호는 어느 엔진에도 없다. 그래서 Qt TTS만 쓰면 파동과 입을 단어 신호(말하는 중/쉬는 중)로만 움직일 수 있다(추정).
- `say()`의 단어 신호는 엔진 내부 싱크 기준이다. 블루투스 같은 장치 지연은 들어 있지 않다([M5], 추정).

### 1.4 한국어 음성

| 엔진 | 이 PC에서 보인 음성(실측) | 목록을 만드는 방법(문서) |
|---|---|---|
| sapi | ko_KR: Microsoft Heami Desktop / en_US: Microsoft Zira Desktop. 이전 조사에서 SAPI로 쓴 OneCore 등록 Heami는 목록에 없었다 | SAPI 레지스트리 음성 토큰만 읽는다 [S6d] |
| winrt | ko_KR: Microsoft Heami(성별 Female, 나이 Other) | `SpeechSynthesizer.AllVoices`(OneCore 음성) [S7d][W2] |
| darwin | 미실행 | `AVSpeechSynthesisVoice.speechVoices` [S8d]. 한국어 음성(Yuna 등)을 거르는 코드는 없으므로 설치되어 있으면 보일 것이다(추정) |

- `availableVoices()`는 지금 로캘의 음성만 돌려준다. 한국어를 쓰려면 먼저 `setLocale(QLocale(QLocale.Korean, QLocale.SouthKorea))`를 한다(실측, 문서 [S6d][S7d]).

### 1.5 배속(rate -1.0~1.0)

| 엔진 | rate → 원래 값(문서) | 실측 배속 | x2 / x5 |
|---|---|---|---|
| winrt | rate ≥ 0이면 `SpeakingRate = 1 + 5×rate`(1.0~6.0) [S7e]. MS 문서는 0.5~6.0이고, "음성에 따라 최대값이 6.0보다 작을 수 있다"고 한다 [W1] | Heami, 첫 단어~마지막 단어 간격 기준: rate 0.1 → **1.50배**, 0.2 → **1.99배**, 0.5 → 3.48배, 0.8 → **4.95배**, 1.0 → 5.87배. 재생 시간(Speaking→Ready)은 14409, 9589, 7210, 4120, 2870, 2401ms | **둘 다 된다.** 합성기가 속도를 바꾸므로 음높이는 따로 유지된다(추정, 들어 보지 않음) |
| sapi | `SetRate(int(rate×10))`(-10~10) [S6b] | 미실행. 이전 조사의 SAPI Rate 실측과 합치면 rate 0.4 → 1.55배, 0.6 → 1.93배, 1.0 → 2.99배(Heami) | x2만 된다. Qt sapi `say()`는 본문 앞에 XML(`<pitch …/>`)을 붙이고 XML 해석을 켠 채 넘긴다 [S6a]. 그래서 본문에 `<rate absspeed="5"/>`를 넣으면 x5가 될 수도 있다(추정, 미실행). 반대로 슬라이드 글의 `<`, `&`가 XML로 잘못 해석될 수도 있다(추정) |
| darwin | `utterance.rate = 기본값 + rate×(최대값 − 기본값)` [S8b] | 미실행. Apple 문서에 최소·기본·최대값의 수치가 없어 몇 배인지 알 수 없다 [A1] | 미확인 |

### 1.6 출력 장치 선택

| 엔진 | 장치를 고를 수 있나 | 근거 |
|---|---|---|
| winrt | **된다.** `QTextToSpeech("winrt", {"audioDevice": QAudioDevice})`. 엔진을 만들 때 한 번 읽으므로, 바꾸려면 `setEngine("winrt", params)`로 다시 만든다 | 문서 [Q2][S7f]. **실측**: 가상 장치를 넘긴 `say()`가 정상 재생(Speaking→Ready)되고 단어 신호가 왔다 |
| sapi | 안 된다. 매개변수를 무시하고 SAPI 기본 출력으로 나간다 | 문서 [Q2][S6e] |
| darwin | 안 된다. 매개변수를 무시하고 `speakUtterance`로 시스템 기본 장치에 나간다 | 문서 [Q2][S8c] |

### 1.7 도입 버전

| 기능 | 버전 | 근거 |
|---|---|---|
| 엔진 매개변수(`setEngine(name, params)`), winrt `audioDevice` | 6.4 | 문서 [Q1][S7f] |
| `sayingWord`, `Capability`/`engineCapabilities`, `synthesize`(C++), `enqueue`, `aboutToSynthesize` | 6.6 | 문서 [Q3] |
| darwin 엔진이 macOS 기본 | 6.4(예전 `macos` 엔진은 6.9에서 삭제) | 문서 [S9] |

---

## 2. QtMultimedia

### 2.1 장치 목록과 PCM 재생(`QMediaDevices` + `QAudioSink`)

| 항목 | Windows | macOS (문서, 미실행) |
|---|---|---|
| 장치 목록 | **실측**: 4개가 보였다. `id()`는 WASAPI 엔드포인트 ID(`{0.0.0.00000000}.{GUID}`)다. 이 값은 지금 앱이 저장하는 SAPI 출력 토큰 ID(`…\MMAudioOut\{0.0.0.00000000}.{GUID}`)의 끝부분과 **같았다**. 기존 설정을 옮기기 쉽다 | CoreAudio 장치 UID [M7] |
| 고른 장치로 열기 | **문서**: `IMMDeviceEnumerator::GetDevice(id)`로 그 장치를 연다 [M1a]. **실측**: 가상 장치로 재생됐다 | AUHAL에 `kAudioOutputUnitProperty_CurrentDevice`로 장치를 연결한다 [M6a] |
| 22050Hz 모노 Int16 | **실측**: 4개 장치 모두 `isFormatSupported` True다(장치 기본 형식은 48kHz 스테레오 Float). 그대로 재생됐다. **문서**: 공유 모드 WASAPI의 `AUTOCONVERTPCM`이 변환한다 [M1b][M2] | AUHAL 입력 형식만 정하고 변환은 CoreAudio가 한다(문서 [M6a], 변환은 추정) |
| 블루투스 | 미실측(연결된 장치 없음). 블루투스도 일반 WASAPI 엔드포인트로 나온다(추정). Qt는 블루투스 장치의 잦은 변경 알림을 200ms 모아 처리한다 [M3] | 미실행. 재생 중 장치가 바뀌거나 끊기면 Qt가 싱크를 멈추고 IOError를 낸다는 주석이 있다 [M6b] |
| 장치가 끊기면 | IOError + Stopped. 싱크를 다시 만들어야 한다 [M4] | 같음 [M6b] |
| 기본 장치 따라가기 | 싱크는 만들 때의 장치에 고정된다. 따라가려면 `audioOutputsChanged`를 보고 다시 만든다 [M8] | 같음 |

- `QSoundEffect`도 장치를 고를 수 있지만 원본으로 URL만 받는다. 메모리의 PCM에는 맞지 않는다(문서 [M17]).

### 2.2 재생 위치

| 방법 | 실측(Windows, 가상 장치, 14.39초 무음) | 문서 |
|---|---|---|
| `QAudioSink.processedUSecs()` | `start()`가 33~36ms 만에 돌아오고 곧바로 Active가 된다. 값은 **10ms 단위**로 늘고, 벽시계 대비 0.9999배로 진행한다. `start()` 뒤 경과 시간보다 11~14ms(중앙값) 앞선다. Idle은 14382~14384ms에 왔다(데이터 14387ms). 기본 버퍼는 250ms(11024바이트)다 | 장치 버퍼에 넘긴 양이다. 장치·블루투스 지연은 빼지 않는다 [M5][Q5] |
| `QMediaPlayer.position()` | x1에서는 약 100ms마다(한 번에 93ms) 바뀐다. x5에서는 50ms마다(한 번에 279ms) 바뀐다. 기울기는 1.008, 5.006이다. 처음 0보다 커진 시각은 x1에서 330ms(첫 실행, 초기화 포함), x5에서 70ms였다 | 위치는 **원본 미디어 시각**이다. 그래서 배속과 상관없이 원본 PCM에서 만든 곡선·단어 목록을 그대로 찾아 쓸 수 있다(추정) |

- 파동을 60fps로 그리려면 `QMediaPlayer`에서는 마지막 위치 + 경과 시간 × 배율로 보간해야 한다(추정).
- 귀에 들리기까지의 지연(OS 믹서, 블루투스 코덱)은 어느 값에도 없다. 소리를 내지 않아 재지 못했다. 필요하면 설정에 "입 모양 늦추기" 같은 보정값을 두는 방법이 있다(추정).
- 6.11의 콜백 방식 `start(callable)`[Q8]은 PySide6 6.12에 없다(실측: stub에 `start()`, `start(QIODevice)`만 있음. 문서 [Q14]). 이 앱에는 필요 없다.

### 2.3 배속과 음높이(`QMediaPlayer.setPlaybackRate`, `pitchCompensation`)

| 백엔드 | `pitchCompensationAvailability` / 기본값 | 배속 재생(무음 10초 WAV, 가상 장치, 볼륨 0) | 근거 |
|---|---|---|---|
| FFmpeg(Windows·macOS 기본 [Q10][M15]) | **실측**: `Available` / 켜짐 | **실측**: x1 10048ms, x1.5 6676ms, x2 5037ms, x5 2030ms(기대값 10000, 6667, 5000, 2000) | 문서: Signalsmith Stretch로 음높이를 유지하고, 끄면 리샘플(음높이 변함) [M10][Q7]. 상한 없음(0 이상만) [M9] |
| windows(Media Foundation) | **실측**: `Unavailable` / 꺼짐 | **실측**: x1 10060, x1.5 6945, x2 5178, x5 2198ms | 문서: 음높이 유지를 구현하지 않음 [M13]. 6.10부터 deprecated [Q10] |
| darwin(AVFoundation) | 문서: `Available`(켜면 Spectral 알고리즘), 기본값은 꺼짐 | 미실행 | [M12] |

**x5 음질(문서, 들어 보지 않음)**

- Signalsmith Stretch는 "0.75~1.5배에서 가장 좋게 들린다"고 한다 [M11a].
- 2배(`maxCleanStretch`)를 넘으면 위상을 무작위로 섞는 방식으로 바뀐다 [M11b].
- 그래서 x5 전체를 늘이기로 처리하지 말고, 합성 속도를 최대로 올린 뒤 남은 배율을 2 이하로 두는 편이 낫다(추정). 이전 조사에서 numpy로 직접 늘일 때 세운 원칙과 같다.

**메모리 PCM 재생(실측)**

- WAV 바이트를 `QBuffer`에 담아 `setSourceDevice(buf, QUrl("speech.wav"))`로 넘기면 재생됐다(x1, x5).
- 파일을 디스크에 쓸 필요가 없다.

**QAudioBufferOutput(6.8+)**

- **실측**: x2, x5로 재생해도 버퍼 출력에는 원본 10초가 원래 음높이(440Hz)로 왔다. 오는 속도만 배율만큼 빨랐다.
- **문서**: "재생 배율에 따라 조정되지 않는다"[M14a]. 따라서 늘인 결과를 받아 쓰는 용도로는 못 쓴다.
- **실측**: windows 백엔드에서 버퍼 출력만 달면 `ResourceError: Unable to play`가 났다. 문서도 FFmpeg 전용이라고 한다 [M14b].

**FFmpeg 로딩(실측)**

- `QMediaDevices`와 `QAudioSink`만 써도 FFmpeg 플러그인과 `avcodec-63.dll` 등이 프로세스에 올라왔다.
- 따라서 "QAudioSink만 쓰니 FFmpeg DLL을 빼자"는 그대로는 안전하지 않다. 빼도 동작하는지는 시험하지 않았다.

---

## 3. 섞어 쓰기: SAPI 미리 합성 + Qt 재생

**실측(한 프로세스, Qt 메인 스레드)**

- pywin32로 SAPI `SpMemoryStream`에 합성하면서 단어 이벤트를 받았다.
  - 86자 문장 합성에 50~105ms가 걸렸다.
  - 결과는 14.39초 분량이었고 단어 이벤트는 19개였다.
  - Qt 이벤트 루프의 `processEvents()`와 `PumpWaitingMessages()`로 이벤트가 전달됐다.
- 그 PCM과 같은 길이의 무음을 `QAudioSink`(22050Hz 모노 Int16)로 고른 장치에 재생했다(§2.2 수치).
- 크기 곡선 계산(719프레임)은 7~9ms였다.

이전 조사의 권장(같은 `SpVoice`의 `SpeakStream`)과 비교한다.

| 항목 | SAPI `SpeakStream`(이전 권장) | `QAudioSink` | `QMediaPlayer` |
|---|---|---|---|
| 장치 선택 | SAPI 출력 토큰 | `QAudioDevice`. ID가 SAPI 토큰 끝부분과 같다(실측) | `QAudioOutput(QAudioDevice)` |
| macOS와 같은 코드 | 아니오 | **예** | **예** |
| 재생 위치 | `CurrentDevicePosition`(makepy `CastTo` 필요) 또는 벽시계 | `processedUSecs()`, 10ms 단위(실측) | `position()`, 50~100ms 단위. 보간 필요(실측) |
| 시작 지연 | StartStream까지 70ms(이전 조사) | Active까지 33~36ms(실측) | 첫 위치까지 70~330ms(실측) |
| 배속 | 합성할 때만 | 합성할 때만 | `setPlaybackRate` + 음높이 유지(FFmpeg) |
| 재생 중 COM 이벤트 펌프 | 필요(StartStream/EndStream) | 불필요. COM은 합성할 때만 쓴다 | 불필요 |
| 장치가 끊기면 | 미확인 | IOError + Stopped(문서 [M4]) | 미확인 |
| 추가 의존성 | 없음 | PySide6-Addons | PySide6-Addons(FFmpeg 포함) |

- **장점**: 재생 코드가 Windows와 macOS에서 하나가 된다. 장치 목록도 Qt 하나로 같아진다. 위치가 촘촘하다. x5 늘이기에 numpy가 필요 없다.
- **단점**
  - PySide6-Addons와 FFmpeg가 배포물에 붙는다(§4).
  - 저장된 장치 설정을 SAPI 토큰 ID에서 엔드포인트 ID로 옮겨야 한다.
  - Qt는 Windows에서 `QAudioSink`용 "예열"을 하지 않는다. 그래서 블루투스 앞 무음은 앱이 계속 붙여야 한다. 예열 코드는 기본 장치에만, 그리고 동기식 `QSoundEffect`에서만 쓰인다(문서 [M3b]).

---

## 4. 비용

### 4.1 wheel 크기

| 패키지 | Windows(win_amd64) | macOS(macosx_14_0_universal2) | 근거 |
|---|---|---|---|
| PySide6-Addons 6.12.0 | **40.5MB**(실측 다운로드 40,522,402바이트) | 90.5MB | [P1] |
| PySide6-Essentials 6.12.0 | 82.2MB(실측) | 116.0MB | [P2] |
| numpy 2.5.4(cp314) | 12.7MB | 5.5MB(macosx_14_0_arm64) | [P3] |

- QtMultimedia와 QtTextToSpeech는 Addons에 들어 있다. Essentials에는 없다(실측: wheel 목록).
- Addons의 Multimedia·TTS 관련 파일(Windows)은 압축 해제 기준 24.8MB다. 그중 FFmpeg DLL 5개가 19.7MB다(실측).

### 4.2 PyInstaller 결과물 크기 (실측, Windows, onedir `--windowed`)

MB는 10^6바이트다. gui-toolkit 조사의 "PySide6 빈 창 101MB"는 아래 첫 줄과 같은 빌드를 2^20 단위로 적은 값이다.

| 빌드 | 크기 | 늘어난 부분 |
|---|---|---|
| Essentials만 설치, 빈 창(gui-toolkit 조사 때 같은 PC에서 만든 빌드를 다시 잼) | 105.6MB | 기준 |
| Essentials + Addons 설치, 같은 빈 창 | 121.4MB | +15.9MB. 가상 키보드 입력 플러그인(`qtvirtualkeyboardplugin.dll`)과 그것이 끌고 온 `Qt6Quick` 6.75, `Qt6Qml` 5.39, `Qt6OpenGL` 1.99MB 등 8개 파일. 빌드 설정에서 뺄 수 있을 것이다(추정, 미시험) |
| 위 + QtMultimedia·QtTextToSpeech 사용 | 145.2MB | +23.8MB. `avcodec-63` 14.12, `avformat-63` 2.86, `swscale-10` 1.27, `avutil-61` 1.17, `swresample-7` 0.24MB(FFmpeg 합계 19.7MB). `Qt6Multimedia` 1.40, FFmpeg 플러그인 0.76, windows 미디어 플러그인 0.32MB. TTS 관련은 0.5MB 미만 |
| Essentials + Addons 빈 창 + numpy | 152.8MB | +31.4MB. OpenBLAS 20.6MB, `_multiarray_umath` 3.9MB 등 |

- 세 실행 파일 모두 실행해 정상 종료를 확인했다.
- Multimedia 빌드는 실행 결과로 엔진 3개, 출력 장치 4개, `pitchCompensation` Available을 파일에 기록했다. PyInstaller가 Qt 플러그인과 FFmpeg DLL을 자동으로 넣었다는 뜻이다.
- macOS `.app` 크기는 미측정이다.

### 4.3 라이선스

| 대상 | 라이선스 | 근거 |
|---|---|---|
| Qt Multimedia, Qt TextToSpeech | 상용 / LGPLv3 / GPLv2. 의무는 gui-toolkit 조사의 PySide6 항목과 같다 | 문서 [Q10][Q12] |
| FFmpeg(번들) | **실측**: DLL 버전 정보가 "FFmpeg 9.0.1"이다. **문서**: LGPL-2.1 이상. Qt 온라인 설치본의 FFmpeg에는 GPL·LGPLv3 선택 요소가 없다 [Q11]. 동적 링크이고 소스 제공 등이 필요하다 [F1] | PySide6 wheel의 FFmpeg가 Qt 설치본과 같은 빌드인지는 버전만 맞춰 봤다(추정) |
| Signalsmith Stretch(Qt에 포함) | MIT | 문서 [M16] |
| numpy | BSD-3-Clause 등 허용형 라이선스 | 문서 [P3] |

**정리**

- numpy는 라이선스 부담이 적지만 결과물이 더 크다(31.4MB 대 23.8MB).
- Qt 쪽은 이미 PySide6 때문에 LGPL 의무를 지고 있다. 그래서 FFmpeg 고지와 소스 안내 정도가 늘어난다(추정).
- PyInstaller가 라이선스 파일을 넣어 주지 않는다는 점은 gui-toolkit 조사에 있다.

---

## 5. 버전

| 기능 | 필요한 Qt/PySide6 | 근거 |
|---|---|---|
| `QAudioSink`(장치 지정), `QMediaDevices` | 6.0부터 | 문서 [Q5] |
| winrt 엔진 `audioDevice` | 6.4 | 문서 [S7f] |
| `sayingWord`, `engineCapabilities` | 6.6 | 문서 [Q3] |
| `QAudioBufferOutput` | 6.8 | 문서 [M14b] |
| `QMediaPlayer.pitchCompensation` | **6.10** | 문서 [Q6][Q7] |
| `QAudioSink.setBufferFrameCount` | 6.10 | 문서 [Q7] |
| `QAudioSink.setNativePeriodFrameCount` | 6.12 | 문서 [Q9] |

- **최소 PySide6 6.10**이 필요하다(음높이 유지 배속 때문). 권장은 6.12.x다(gui-toolkit에서 정한 버전, 실측도 6.12.0).
- **Windows**: Qt 6.12는 Windows 10(1809 이상)과 11을 지원한다. "Qt 6.12가 Windows 10을 지원하는 마지막 버전"이다 [Q13]. Windows 10 학교 PC를 계속 지원하려면 **PySide6를 6.12.x에 고정**해야 한다(추정).
- **macOS**: Qt 6.12는 macOS 14.4 이상을 지원하고 arm64를 포함한다 [Q13]. PySide6 6.12.0 wheel은 `macosx_14_0_universal2` 하나다 [P1][P2]. M1 Pro + macOS 14.4 이상이면 맞는다. pip은 14.0~14.3에도 설치하지만 Qt가 공식 지원하지 않는 범위다(문서, 추정).

---

## 확인하지 못한 것

- **macOS 전부 미실행.**
  - darwin TTS 엔진의 음성 목록(Yuna), rate와 배속의 관계, `sayingWord` 시각
  - `QAudioSink`가 고른 장치(블루투스 포함)로 실제 나오는지
  - FFmpeg 백엔드 `pitchCompensation` 동작
  - `say -o` 결과의 형식과 `say -r` 상한
- **블루투스 장치**: 이 PC에 연결된 것이 없어 Windows에서도 재지 못했다.
- **귀에 들리기까지의 지연**: `processedUSecs`, `position()`, `sayingWord` 모두 장치 지연을 빼지 않는다. 소리를 내지 않아 실제 차이를 재지 못했다.
- **음질**
  - `pitchCompensation` x2~x5와 WinRT rate 0.8(4.95배)의 음질, 음높이가 실제로 유지되는지는 들어 보지 않았다.
  - `QAudioBufferOutput`은 늘이기 전 소리를 주므로 이것으로 확인할 수 없었다.
- **Qt sapi 엔진**: `say()`를 실행하지 않았다(기본 장치로 나가므로).
  - 본문에 넣은 XML(`<rate absspeed>`)이 먹는지
  - `<`, `&`가 든 글이 깨지는지
- **배포 크기**
  - 가상 키보드 플러그인과 FFmpeg DLL을 PyInstaller에서 뺄 수 있는지, 빼도 `QAudioSink`가 동작하는지
  - onefile 크기, macOS `.app` 크기
- **macOS 단어 시각의 근사법**: 문장별 합성 + 글자 수 비례의 오차는 재지 않았다.

## 출처

**실측 스크립트**: 저장소 밖 스크래치 폴더에서 실행했다. 엔진·음성 목록, 장치 목록, SAPI 합성 + QAudioSink, QMediaPlayer 배속, WinRT `say()` 단어 시각, FFmpeg 로딩 확인, PyInstaller 빌드 3건이다.

**이전 조사(이 저장소)**
- `docs/research/tts-signal-speed.md`(브랜치 `research/tts-signal-speed`): SAPI 메모리 합성, 단어 이벤트, Rate·XML 배속, 블루투스 무음, macOS `say`·AVFoundation 문서
- `docs/research/gui-toolkit.md`(브랜치 `research/gui-toolkit`): PySide6 6.12 선택, 빈 창 PyInstaller 크기, Qt LGPL 의무

**Qt 문서**
- [Q1] QTextToSpeech: https://doc.qt.io/qt-6/qtexttospeech.html
- [Q2] Qt TextToSpeech Engines: https://doc.qt.io/qt-6/qttexttospeech-engines.html
- [Q3] What's New in Qt 6.6: https://doc.qt.io/qt-6/whatsnew66.html
- [Q4] PySide6 QTextToSpeech: https://doc.qt.io/qtforpython-6/PySide6/QtTextToSpeech/QTextToSpeech.html
- [Q5] QAudioSink: https://doc.qt.io/qt-6/qaudiosink.html
- [Q6] QMediaPlayer(`pitchCompensation`, `setSourceDevice`): https://doc.qt.io/qt-6/qmediaplayer.html
- [Q7] What's New in Qt 6.10: https://doc.qt.io/qt-6/whatsnew610.html
- [Q8] What's New in Qt 6.11: https://doc.qt.io/qt-6/whatsnew611.html
- [Q9] What's New in Qt 6.12: https://doc.qt.io/qt-6/whatsnew612.html
- [Q10] Qt Multimedia(백엔드, 라이선스, 제3자 구성요소): https://doc.qt.io/qt-6/qtmultimedia-index.html
- [Q11] Qt Multimedia FFmpeg 고지: https://doc.qt.io/qt-6/qtmultimedia-attribution-ffmpeg.html
- [Q12] Qt TextToSpeech(라이선스): https://doc.qt.io/qt-6/qttexttospeech-index.html
- [Q13] Qt 6.12 Supported Platforms: https://doc.qt.io/qt-6/supported-platforms.html
- [Q14] PySide6 QAudioSink: https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QAudioSink.html

**qtspeech 소스(v6.12.0)**
- [S1] 플러그인 빌드 조건: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/CMakeLists.txt#L8-L16
- [S2] 우선순위와 기능 플래그
  - https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/winrt/winrt_plugin.json#L5-L11
  - https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/sapi/sapi_plugin.json#L5-L11
  - https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/darwin/darwin_plugin.json#L5-L11
- [S3] 기본 엔진 선택: https://github.com/qt/qtspeech/blob/v6.12.0/src/tts/qtexttospeech.cpp#L43-L57
- [S4] 기능 플래그를 JSON에서 읽음: https://github.com/qt/qtspeech/blob/v6.12.0/src/tts/qtexttospeech.cpp#L544-L578
- [S5] `synthesize` 템플릿: https://github.com/qt/qtspeech/blob/v6.12.0/src/tts/qtexttospeech.h#L100-L129
- [S6] sapi
  - [S6a] `say()`에 XML 접두어: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/sapi/qtexttospeech_sapi.cpp#L105-L122
  - 합성 형식 16kHz: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/sapi/qtexttospeech_sapi.cpp#L124-L141
  - [S6b] rate: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/sapi/qtexttospeech_sapi.cpp#L284-L297
  - [S6c] 이벤트: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/sapi/qtexttospeech_sapi.cpp#L568-L622
  - [S6d] 음성: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/sapi/qtexttospeech_sapi.cpp#L414-L452
  - [S6e] 매개변수 무시: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/sapi/qtexttospeech_sapi.cpp#L64
- [S7] winrt
  - [S7a] 단어 타이머: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/winrt/qtexttospeech_winrt.cpp#L363-L381
  - [S7b] 싱크·상태: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/winrt/qtexttospeech_winrt.cpp#L403-L467
  - 합성: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/winrt/qtexttospeech_winrt.cpp#L508-L551
  - [S7c] 볼륨: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/winrt/qtexttospeech_winrt.cpp#L709-L718
  - [S7d] 음성: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/winrt/qtexttospeech_winrt.cpp#L208-L234
  - [S7e] rate: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/winrt/qtexttospeech_winrt.cpp#L615-L654
  - [S7f] `audioDevice`: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/winrt/qtexttospeech_winrt.cpp#L113-L120
  - 형식 16kHz: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/winrt/qtexttospeech_winrt_audiosource.cpp#L54-L56
- [S8] darwin
  - [S8a] 단어 델리게이트: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/darwin/qtexttospeech_darwin.mm#L78-L94
  - [S8b] rate: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/darwin/qtexttospeech_darwin.mm#L151-L161
  - [S8c] `say()`: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/darwin/qtexttospeech_darwin.mm#L169-L175
  - 합성: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/darwin/qtexttospeech_darwin.mm#L177-L244
  - [S8d] 음성: https://github.com/qt/qtspeech/blob/v6.12.0/src/plugins/tts/darwin/qtexttospeech_darwin.mm#L302-L351
- [S9] `macos` 엔진 삭제 커밋: https://github.com/qt/qtspeech/commit/bb4d0b400d4c129a2a3f51ca7d628ab6db33e6cd
- [S10] winrt 단어 시각 커밋: https://github.com/qt/qtspeech/commit/ea5c48e518789c3387ed9c9d21978eda122e9782
- [S11] PySide6 바인딩 정의: https://github.com/pyside/pyside-setup/blob/v6.12.0/sources/pyside6/PySide6/QtTextToSpeech/typesystem_texttospeech.xml

**qtmultimedia 소스(v6.12.0)**
- [M1] Windows 장치
  - [M1a] 열기: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/windows/qwindowsaudiodevice.cpp#L417-L439
  - [M1b] 형식 변환 주석: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/windows/qwindowsaudiodevice.cpp#L314-L330
- [M2] WASAPI 스트림 플래그: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/windows/qwindowsaudioutils.cpp#L400-L410
- [M3] 블루투스 알림 처리: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/windows/qwindowsaudiodevices.cpp#L249-L264
  - [M3b] 예열 클라이언트: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/windows/qwindows_wasapi_warmup_client.cpp#L33-L59
  - 예열 호출 위치: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/audio/qsoundeffectsynchronous.cpp#L136-L141
- [M4] 장치 오류 처리: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/windows/qwindowsaudiosink.cpp#L263-L306
- [M5] `processedUSecs` 계산: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/audio/qaudiosystem_platform_stream_support.cpp#L150-L207
- [M6] macOS 싱크
  - [M6a] 장치 연결: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/coreaudio/qcoreaaudiosink.mm#L50-L90
  - [M6b] 장치 변경 시 정지: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/coreaudio/qcoreaaudiosink.mm#L325-L345
- [M7] 장치 UID → ID: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/coreaudio/qmacosaudiodatautils.cpp#L149-L196
- [M8] 빈 장치 = 생성 시점의 기본 장치: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/platform/qplatformaudiodevices.cpp#L186-L201
- [M9] FFmpeg
  - 배속 설정: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/plugins/multimedia/ffmpeg/qffmpegmediaplayer.cpp#L146-L159
  - 음높이 유지 지원: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/plugins/multimedia/ffmpeg/qffmpegmediaplayer.cpp#L419-L439
- [M10] 리샘플/늘이기 변환기: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/plugins/multimedia/ffmpeg/playbackengine/qffmpegaudioframeconverter.cpp#L52-L148
- [M11] Signalsmith Stretch
  - [M11a] README: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/3rdparty/signalsmith-stretch/README.md#L5
  - [M11b] `maxCleanStretch`: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/3rdparty/signalsmith-stretch/signalsmith-stretch.h#L293
- [M12] darwin 플레이어
  - 음높이 유지: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/plugins/multimedia/darwin/mediaplayer/avfmediaplayer.mm#L1352-L1372
  - 기본값: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/plugins/multimedia/darwin/mediaplayer/avfmediaplayer_p.h#L135
- [M13] windows 백엔드 기본값 `Unavailable`: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/platform/qplatformmediaplayer.cpp#L46-L61
- [M14] QAudioBufferOutput
  - [M14a] 배율 미적용: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/playback/qmediaplayer.cpp#L640-L667
  - [M14b] 도입 버전과 FFmpeg 전용: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/audio/qaudiobufferoutput.cpp#L11-L28
  - 출력 없이도 렌더러 생성: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/plugins/multimedia/ffmpeg/qffmpegplaybackengine.cpp#L202-L216
- [M15] 백엔드 선택 순서: https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/platform/qplatformmediaintegration.cpp#L53-L76
- [M16] 제3자 고지
  - https://github.com/qt/qtmultimedia/blob/v6.12.0/src/3rdparty/signalsmith-stretch/qt_attribution.json
  - https://github.com/qt/qtmultimedia/blob/v6.12.0/src/3rdparty/ffmpeg/qt_attribution.json
- [M17] QSoundEffect(URL 원본, 장치 속성): https://github.com/qt/qtmultimedia/blob/v6.12.0/src/multimedia/audio/qsoundeffect.h#L24-L63

**PyPI, FFmpeg, Microsoft, Apple**
- [P1] PySide6-Addons 6.12.0: https://pypi.org/project/PySide6-Addons/6.12.0/#files
- [P2] PySide6-Essentials 6.12.0: https://pypi.org/project/PySide6-Essentials/6.12.0/#files
- [P3] numpy 2.5.4: https://pypi.org/project/numpy/#files
- [F1] FFmpeg 라이선스와 준수 목록: https://ffmpeg.org/legal.html
- [W1] SpeechSynthesizerOptions.SpeakingRate: https://learn.microsoft.com/en-us/uwp/api/windows.media.speechsynthesis.speechsynthesizeroptions.speakingrate
- [W2] SpeechSynthesizer.AllVoices: https://learn.microsoft.com/en-us/uwp/api/windows.media.speechsynthesis.speechsynthesizer.allvoices
- [A1] AVSpeechUtterance.rate: https://developer.apple.com/documentation/avfaudio/avspeechutterance/rate
