# 클라우드 음성 API 조사

Type: research
Status: resolved

## Question

[클라우드 음성을 목소리 엔진으로 넣기](21-grilling-cloud-voice.md)를 정하려면 아래 사실이 필요하다. 지금 음성 흐름은 문장마다 합성해 `Synth(pcm, words, engine_speed)`를 돌려받고, PCM에서 크기 곡선을, 낱말 시각으로 말풍선을 맞춘다.
- 두 API가 PCM을 주나, 표본 빈도는 얼마인가
- 낱말·글자 시각을 주나
- 배속 범위와 모델별 지원
- 한국어에 맞는 현재 모델, 지연, 요금
- 문장으로 나눠 합성할 때 앞뒤 문장을 이어 주는 기능
- 목소리 목록, 키 확인, 오류 모양
- "gpt-live"가 가리키는 것

## Answer

조사 문서: `docs/research/cloud-tts.md`(2026-10-17). 핵심과 원문 재확인:
- "gpt-live"는 OpenAI GPT-Live(`gpt-live-1`)다. `v1/live/sessions`만 지원하고 음성 합성(`v1/audio/speech`)은 지원하지 않는 실시간 대화 모델이다(모델 페이지에서 다시 확인).
- OpenAI 음성 합성 모델 네 개(`tts-1`, `tts-1-hd`, `gpt-4o-mini-tts-2025-03-20`, `gpt-4o-mini-tts-2025-12-15`)는 2027-01-06에 API에서 제거된다. 대체는 Realtime 모델 `gpt-realtime-2.1-mini`다(Deprecations 페이지 2026-10-01 항목에서 다시 확인).
- ElevenLabs: PCM `pcm_22050`(S16LE 모노, 무료 등급 가능), `/with-timestamps`가 원문 글자마다 시각을 준다. 엔진 속도는 0.7~1.2(v4는 없음). `previous_text`/`next_text`로 문장 사이 억양을 잇는다. 기본 목소리는 2026-12-31에 만료된다. 키 확인 `GET /v2/voices?page_size=1`. 오류 401 `invalid_api_key`, 402 `insufficient_credits`, 429 `rate_limit_exceeded` 등.
- Gemini TTS: `gemini-3.8-flash-tts`, 한국어, 24kHz 16bit 모노 PCM, 시각 정보와 속도 매개변수 없음, 무료 등급 있음.
- 확인하지 못한 것은 조사 문서 "확인하지 못한 것" 절에 있다(키가 없어 실제 호출은 하지 않음).
