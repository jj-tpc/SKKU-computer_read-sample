# 운영체제 음성에서 목소리 신호를 얻는 방법과 배속 한계

Type: research
Status: resolved

## Question

운영체제 음성(Windows SAPI via pywin32, macOS `say`)으로 말하는 동안, 원 버튼 파동과 강아지 입이 **목소리를 따라 움직이게 할 신호**를 실시간으로 얻는 방법은 무엇인가? 그리고 배속 **x1 / x1.5 / x2 / x5**를 낼 수 있나?

확인할 것:
1. **SAPI 이벤트**: 단어 경계, 음소, viseme, 오디오 레벨 이벤트(`SPEI_WORD_BOUNDARY`, `SPEI_PHONEME`, `SPEI_VISEME`, audio level interest)를 pywin32에서 받는 방법과 실제 지연.
2. **SAPI 미리 합성**: 메모리·파일 스트림으로 합성한 뒤 직접 재생하는 방법. 이때 기존 출력 장치 선택(`ppt_reader/tts.py`)을 어떻게 유지하나, 재생에 추가 의존성이 필요한가.
3. **macOS**: `say -o`로 파일을 만든 뒤 재생하는 방법, NSSpeechSynthesizer/AVSpeechSynthesizer 콜백(단어·음소)을 pyobjc로 받는 방법, 각 경우 출력 장치 선택(`say -a`) 유지 방법.
4. **첫마디까지 시간**: 미리 합성할 때 말이 시작되기까지 걸리는 시간. 기존 블루투스 대응(2초 넘게 조용하면 1초 무음을 앞에 넣음)과 어떻게 맞물리나.
5. **배속 한계**: SAPI `Rate`(-10~10)가 실제 몇 배속에 해당하나, `say -r`의 상한은 얼마인가. x5가 안 되면 합성 후 재생 속도를 높이는(시간 늘이기) 방법과 그 의존성.

`ppt_reader/tts.py`를 먼저 읽고 현재 구현을 기준으로 조사한다.

## Answer

조사 문서: `research/tts-signal-speed` 브랜치의 `docs/research/tts-signal-speed.md` (커밋 538217e). 측정은 소리를 내지 않고, 메모리 스트림과 가상 장치로 했다.

- **Windows 권장 방식**: 대본을 `SpMemoryStream`/`SpFileStream`에 **미리 합성**한다.
  - 합성하면서 단어·viseme 이벤트를 오디오 위치와 함께 모으고, 20ms 단위 크기 곡선을 뽑는다. 순수 파이썬으로 19초 음성에 40ms가 걸렸다.
  - 그 소리를 같은 `SpVoice`의 `SpeakStream`으로 재생하면 고른 출력 장치가 유지되고, 새 의존성이 없다.
  - 재생 위치는 `CurrentDevicePosition`으로 읽는다. 실측에서 실제 시간과 1.000배로 같이 갔다.
- **더 단순한 대안**: 지금처럼 장치로 바로 말하면서 이벤트를 받거나 `SpVoice.Status`를 계속 읽는다.
  - 단어 이벤트는 해당 소리보다 7~69ms 늦게 온다.
  - `AudioLevel`은 약 7Hz라 파동에 쓰기에는 거칠다.
- **SAPI 배속**: Heami는 Rate r에서 3^(r/10)배다(x1.5 = Rate 4, x2 = Rate 6). Rate만으로는 최대 약 3배다.
- **x5**: `Rate=10`에 SAPI XML `<rate absspeed="5"/>`를 지속 플래그로 더하면 **Heami는 5.17배**까지 간다. 다음 읽기에도 남으므로 매번 다시 넣는다. **Zira는 3.47배가 한계**다.
  - 음성이 x5를 못 내면 최고 속도로 합성하고, 모자란 배율을 음높이를 유지한 시간 늘이기로 메운다. **numpy가 필요**하고, 처리에 50~70ms가 걸린다.
- **첫마디까지 시간**: 합성은 118자에 70~110ms, 356자에 220~390ms가 걸린다.
  - 블루투스용 1초 무음을 재생하는 동안 합성하면 틈 없이 이어진다.
  - 합성이 1초를 넘는 긴 대본은 끊기므로 **문장 단위로 합성**한다.
- **지금 구현의 버그**: `tts.py`의 `<silence msec="1000"/>`가 Rate만큼 짧아진다. x2에서 약 525ms만 남는다.
  - 가장 작은 수정은 msec에 배속을 곱하는 것이다.
  - 미리 합성 방식에서는 소리 앞에 무음을 붙이면 정확히 1초가 된다.
- **macOS (문서 근거, 미실행)**: `say`는 크기나 단어 신호를 밖으로 내지 않는다.
  - 권장 방식은 `say -o`로 미리 합성해 곡선을 계산하는 것이다. 다만 장치를 골라 재생하려면 새 의존성이 필요하다(pyobjc `AVAudioPlayer.currentDevice` 또는 sounddevice).
  - 단어 신호는 AVSpeechSynthesizer(macOS 13 이상)에서 받을 수 있다.
  - 말하기 속도 범위가 50~500 wpm이라 x5에는 시간 늘이기가 필요하다(`AVAudioUnitTimePitch`).
- 미확인: 귀에 들리기까지의 지연, x5와 시간 늘이기의 음질, PyInstaller에서 pywin32 이벤트 동작, macOS 전부.
