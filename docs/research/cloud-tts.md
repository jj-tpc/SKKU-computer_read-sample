# 클라우드 음성 합성(ElevenLabs, OpenAI, Gemini) 조사

조사일: 2026-10-17. 설정 화면에서 엔진을 고르고 API 키를 넣는 클라우드 음성 합성을 붙이기 전에 필요한 사실을 모았다. 근거는 ElevenLabs, OpenAI, Google AI for Developers의 공식 문서와 API 레퍼런스, 공식 SDK 소스(GitHub), PyPI 메타데이터다. 출처 번호(예: [E1])는 맨 아래 목록에 있다. 문서에 없고 미루어 짐작한 내용은 (추정)으로 표시했다. API 키가 없어서 실제 호출 실험은 하지 않았다.

우리 쪽 조건(다시 적음): 한 문장씩 합성한다. 엔진은 `Synth(pcm, words, engine_speed)`를 돌려준다. PCM은 지금 22050 Hz, 16비트, 모노다. 단어 시작 시각이 없으면 글자 수로 추정한다. 배속은 x1, x1.5, x2, x5이고, 엔진이 못 내는 배속은 재생 때 QMediaPlayer로 늘인다.

## 결론

1. **"gpt-live"는 OpenAI의 GPT-Live(`gpt-live-1`)일 가능성이 크다.** 듣기와 말하기를 동시에 하는 대화용 음성 모델이다. `v1/live/sessions`로만 쓰고, 텍스트를 음성으로 바꾸는 `v1/audio/speech`는 지원하지 않는다. 정해진 대본을 읽는 용도가 아니다. 사용자가 원하는 것은 "OpenAI 목소리로 읽기"일 것이다(추정). [O13][O14][O15]
2. **OpenAI의 TTS 모델은 모두 2027-01-06에 API에서 제거된다.** 대상은 `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts-2025-03-20`, `gpt-4o-mini-tts-2025-12-15`다(2026-10-01 공지). OpenAI가 권하는 대체는 `gpt-realtime-2.1-mini`(Realtime API)다. 이 모델은 `v1/audio/speech`를 지원하지 않는다. 지금 OpenAI TTS를 붙이면 석 달도 안 돼 Realtime으로 다시 옮겨야 한다. [O8][O9]
3. **단어(글자) 시각을 주는 곳은 ElevenLabs뿐이다.** `/with-timestamps` 엔드포인트가 원문 글자마다 시작·끝 초를 준다(`alignment`). OpenAI(Speech, Realtime)와 Gemini TTS는 시각 정보를 주지 않는다. 이 둘은 지금처럼 글자 수로 추정해야 한다. [E1][E25][O11][G1]
4. **PCM 표본률이 제공자마다 다르다.** ElevenLabs는 `pcm_22050`이 있어 지금 파이프라인(22050 Hz)과 바로 맞는다. 무료 등급에서도 8/16/22.05/24 kHz를 쓸 수 있고, 44.1 kHz는 Pro 이상이다. OpenAI는 Speech와 Realtime 모두 **24 kHz만** 준다. Gemini는 기본 24 kHz다. 그래서 `Synth`가 표본률을 함께 들고 다니거나, 24 kHz를 22.05 kHz로 바꿔야 한다(추정). [E1][E5][E20][O1][O12][G1]
5. **ElevenLabs PCM은 부호 있는 16비트 리틀엔디언(S16LE), 모노다.** OpenAI `pcm`도 24 kHz, 16비트 부호 있는 리틀엔디언, 헤더 없음이다. Gemini 스트리밍 기본도 24 kHz 모노 16비트 리틀엔디언 PCM이다. [E5][O1][G1]
6. **엔진 배속 범위는 좁다.** ElevenLabs `voice_settings.speed`는 0.7~1.2다(Eleven v4는 속도 설정 자체가 없다). OpenAI Speech `speed`는 0.25~4.0이지만, `gpt-4o-mini-tts`에서는 무시된다는 보고와 직원 답변이 있었다. Realtime `audio.output.speed`는 0.25~1.5이고 생성 뒤 후처리다. Gemini TTS는 속도 매개변수가 없다. 따라서 x1.5 이상은 대부분 재생 쪽 시간 늘이기로 처리해야 한다. [E10][E11][E6][O3][O16][O12][G1]
7. **ElevenLabs 한국어 기본 모델로 `eleven_multilingual_v2`를 권한다.** 한국어가 명시돼 있고, 숫자 읽기(정규화)가 낫고, 속도 설정과 문장 잇기(`previous_text`/`next_text`)가 되고, 타임스탬프 예제가 이 모델로 돼 있다. 값은 1천 자당 $0.08다. 싸고 빠른 대안은 `eleven_flash_v2_5`(1천 자당 $0.04, 약 75 ms)지만 숫자 정규화가 기본으로 꺼져 있고, 켜기는 Enterprise 전용이다. 최신 `eleven_v4`(2026-09-28 공개)는 속도 설정이 없고 타임스탬프 지원 여부가 문서에 없다. [E4][E6][E8][E18]
8. **문장 단위 합성의 이음새는 ElevenLabs가 지원한다.** `previous_text`, `next_text`로 앞뒤 문장을 넘기면 억양이 이어진다. `previous_request_ids`(최대 3개, 2시간 이내)는 `request-id` 응답 헤더로 받는다. 둘 다 보내면 텍스트 쪽은 무시된다. `eleven_v3`에서는 쓸 수 없다. [E1][E9]
9. **ElevenLabs 기본(Default) 목소리는 2026-12-31에 모두 만료된다.** 2026년 3월 이후 만든 계정은 처음부터 쓸 수 없다. 목소리 ID를 코드에 박지 말고 `GET /v2/voices`로 받아야 한다. 무료 등급은 API로 Voice Library 목소리를 쓸 수 없다. [E13][E14][E12]
10. **키 확인은 돈이 들지 않는 목록 조회로 한다.** ElevenLabs는 `GET /v2/voices?page_size=1`(헤더 `xi-api-key`)을 권한다. 키는 기본적으로 권한이 제한돼 있고, 목소리 목록에는 "Voices (read)" 권한이 필요하다. 그래서 이 호출이 "목소리를 고를 수 있는 키인가"까지 확인한다(추정). OpenAI는 `GET /v1/models`(`client.models.list()`)다. [E16][E24][E12][O19]
11. **오류 구분.** ElevenLabs: 401 `invalid_api_key`, 402 `insufficient_credits`, 429 `concurrent_limit_exceeded`/`rate_limit_exceeded`/`system_busy`. 본문은 `{"detail": {"type", "code", "message", "request_id", "param"}}`이다. OpenAI SDK: 401 `AuthenticationError`, 429 `RateLimitError`이다. 크레딧 소진과 속도 제한이 둘 다 429라서 `e.code`(`credit_balance_exhausted` 등)로 나눈다. [E15][O17][O18]
12. **의존성.** `openai` 3.33.0은 `httpx`가 아니라 **`httpx2`**에 의존한다. 지금 venv의 `httpx` 0.28.1은 `google-genai`가 끌어온 것이다. ElevenLabs REST는 POST 하나와 JSON(base64 오디오) 응답이라 이미 있는 HTTP 클라이언트로 충분하다. 공식 SDK `elevenlabs` 2.73.0(MIT)은 `httpx`, `requests`, `websockets`, `pydantic`에 의존한다. [O20][E23][L1]
13. **Gemini TTS도 있다.** `gemini-3.8-flash-tts`와 `gemini-3.8-flash-lite-tts`가 한국어를 지원하고, 무료 등급이 있다. 다만 시각 정보와 속도 매개변수가 없다. 이미 쓰는 `google-genai`(2.31)와 Gemini 키로 붙일 수 있다. [G1][G2][G3]

## ElevenLabs

### 1. 엔드포인트와 타임스탬프 응답

엔드포인트 네 가지다. 모두 `POST`, 헤더 `xi-api-key`, 본문은 JSON이다. [E1][E2][E3][E16]

| 용도 | 경로 | 응답 |
|---|---|---|
| 일반 | `/v1/text-to-speech/{voice_id}` | 오디오 바이트 |
| 스트리밍 | `/v1/text-to-speech/{voice_id}/stream` | 오디오 바이트 조각 |
| 타임스탬프 | `/v1/text-to-speech/{voice_id}/with-timestamps` | JSON 하나 |
| 스트리밍 + 타임스탬프 | `/v1/text-to-speech/{voice_id}/stream/with-timestamps` | JSON 여러 개의 스트림 |

- 기본 호스트는 `api.elevenlabs.io`다. 미국, EU, 인도, 싱가포르 호스트도 있다. [E1]
- 쿼리: `output_format`(기본 `mp3_44100_128`), `enable_logging`(false는 Enterprise 전용 무보관 모드). `optimize_streaming_latency`는 폐기 예정이다. [E1]
- 본문 주요 필드: `text`(필수), `model_id`(기본 `eleven_multilingual_v2`), `language_code`(ISO 639-1, multilingual_v2는 미지원), `voice_settings`(`stability`, `similarity_boost`, `style`, `use_speaker_boost`, `speed`), `seed`, `previous_text`, `next_text`, `previous_request_ids`, `next_request_ids`, `apply_text_normalization`(`auto`/`on`/`off`). [E1]
- 잔향(reverb)이나 좌우 위치(`pan`) 효과를 `pcm_*`와 함께 쓰면 400이다. 이 효과는 스테레오를 만들기 때문이다. [E1][E5]

**타임스탬프 응답 모양** (`/with-timestamps`) [E1]

```json
{
  "audio_base64": "...",
  "alignment": {
    "characters": ["H", "e", "l", "l", "o"],
    "character_start_times_seconds": [0, 0.1, 0.2, 0.3, 0.4],
    "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4, 0.5]
  },
  "normalized_alignment": { "characters": [...], "character_start_times_seconds": [...], "character_end_times_seconds": [...] }
}
```

- 시각은 **글자 단위**다. 엔드포인트 설명이 "precise character-level timing information"이다. 단어 단위 시각은 없다. [E1][E25]
- `alignment`는 "원문(original text)의 각 글자", `normalized_alignment`는 "정규화한 글자"의 시각이다. 숫자를 말로 풀어 읽으면 두 배열이 달라진다. 원문 글자 위치에 맞추려면 `alignment`를 쓴다. [E1]
- 원문 인덱스와의 대응: 문서에 "원문 각 글자"라고만 있다. `characters`를 이어 붙인 문자열이 입력과 정확히 같은지, 한글이 음절 하나당 원소 하나인지는 문서에 없다(미확인). 실행 중에 `"".join(characters) == text`를 검사하고, 다르면 글자 수 추정으로 돌아가는 편이 안전하다(추정).
- 단어 시작 시각은 단어 첫 글자의 `character_start_times_seconds`로 만들 수 있다(추정).
- 스트리밍 판은 "JSON 스트림"을 돌려준다. 각 조각에 `audio_base64`, `alignment`, `normalized_alignment`가 있다. 줄바꿈 구분인지 SSE인지는 문서에 없다(미확인). 우리는 문장이 짧으므로 비스트리밍 `/with-timestamps`로 충분하다(추정). [E2]

### 2. 출력 형식

- `output_format` 값: `pcm_8000`, `pcm_16000`, `pcm_22050`, `pcm_24000`, `pcm_32000`, `pcm_44100`, `pcm_48000`. `wav_*`(같은 표본률), `mp3_*`, `opus_48000_*`, `ulaw_8000`, `alaw_8000`도 있다. [E1][E3]
- 등급 제한: "PCM and WAV formats with 44.1kHz sample rate requires ... Pro tier or above." `mp3_44100_192`는 Creator 이상이다. [E1]
- 도움말 표: PCM 8, 16, 22.05, 24 kHz는 Free, Starter, Creator에서 쓴다. 44.1 kHz는 Pro, Scale, Business다. 48 kHz와 32 kHz의 등급은 적혀 있지 않다(미확인). [E20]
- 표본 형식: 기능 소개 페이지가 "PCM (S16LE)", 16비트라고 적는다. 즉 부호 있는 16비트 리틀엔디언이다. 같은 페이지가 `pcm_*`를 "mono"라고 부른다. [E5]
- 결론: `pcm_22050`을 고르면 지금의 22050 Hz, 16비트, 모노와 그대로 맞는다. 무료 등급에서도 된다. [E1][E20]

### 3. 모델 (2026-10 기준)

| 모델 ID | 상태 | 한국어 | 요청당 글자 한도 | 지연 | 1천 자당 가격(API) |
|---|---|---|---|---|---|
| `eleven_v4` | 최신 주력(2026-09-28 공개) | 예 | 10,000 | 문서에 없음 | $0.08 |
| `eleven_v4_turbo` | 최신 저지연 | 예 | 문서에 없음 | 추론 중앙값 약 100 ms | $0.04 |
| `eleven_v3` | 이전 세대 | 예 | 5,000 | 문서에 없음 | $0.08 |
| `eleven_v3_conversational` | 이전 세대 | 예 | 문서에 없음 | 약 280 ms | $0.04 |
| `eleven_multilingual_v2` | 이전 세대, 안정적 | 예(29개 언어에 `ko`) | 10,000 | 문서에 없음 | $0.08 |
| `eleven_flash_v2_5` | 현행 | 예(32개 언어) | 40,000 | 약 75 ms | $0.04 |
| `eleven_turbo_v2_5` | **폐기**(대체: `eleven_flash_v2_5`) | 예 | - | - | - |

- 출처: 모델·한국어·한도·지연은 [E4][E5], v4 공개일과 Turbo 지연은 [E8], 가격은 [E18]이다. 지연 수치는 네트워크 지연을 뺀 값이다. [E4]
- `eleven_flash_v2`, `eleven_turbo_v2`는 영어 전용이다. [E4]
- Flash v2.5는 "지연을 지키려고" 숫자·날짜·통화 정규화가 기본으로 꺼져 있다. `apply_text_normalization: "on"`은 v2.5에서 Enterprise 전용이다. 공식 문서는 숫자가 중요하면 Multilingual v2를 권한다. 슬라이드 대본에는 숫자가 많으므로 중요하다. [E4]
- Eleven v4는 Stability와 Similarity만 있다. "Style and Speed sliders are not available in Eleven v4, and SSML is not supported." [E6][E7]
- **타임스탬프를 지원하는 모델 목록은 어느 문서에도 없다.** API 레퍼런스는 모델 제한을 적지 않는다. 공식 예제는 `eleven_multilingual_v2`를 쓴다. v3와 v4에서 `alignment`가 오는지는 확인하지 못했다(미확인). [E1][E4][E6]

### 4. 속도

- API 레퍼런스: `voice_settings.speed`, 기본 1.0. 1보다 작으면 느리고 크면 빠르다. 범위는 적혀 있지 않다. [E1][E3]
- 도움말: "Possible values range from 0.7 to 1.2." "This setting is available for all voices and all models." [E10]
- 에이전트 문서: "Values outside the 0.7-1.2 range are not supported." 끝값 근처에서는 음질이 나빠질 수 있다. [E11]
- 충돌: v4 문서는 속도 설정이 없다고 한다. 도움말의 "모든 모델"은 v4 이전 문장으로 보인다(추정). [E6][E10]
- 다른 속도 매개변수는 찾지 못했다. 따라서 `engine_speed`는 최대 1.2다. x1.5는 엔진 1.2 × 재생 1.25, x2와 x5는 대부분 재생 쪽에서 맡는다(추정).
- 엔진 속도를 바꾸면 `alignment` 시각도 바뀐 오디오 기준으로 올 것이다(추정, 미확인).

### 5. 문장 사이 연속성

- `previous_text`: "The text that came before the text of the current request." 이어 붙일 때 연속성을 돕는다. `next_text`는 반대 방향이다. [E1]
- `previous_request_ids` / `next_request_ids`: 앞뒤 생성 결과의 요청 ID, 각각 최대 3개다. 텍스트와 ID를 둘 다 보내면 텍스트는 무시된다. 같은 모델일 때 결과가 가장 좋다. [E1]
- 요청 ID는 응답 헤더 `request-id`로 받는다. 2시간보다 오래되면 안 된다. 스트리밍이면 오디오를 끝까지 읽은 뒤에 그 ID를 쓸 수 있다. [E9]
- `eleven_v3`에서는 요청 잇기를 쓸 수 없다. v4 블로그는 v4에서 요청 잇기가 "훨씬 안정적"이라고 한다. [E9][E8]
- 우리 방식(다음 문장을 미리 합성)에서는 앞 문장 ID가 아직 없을 수 있다. 그래서 `previous_text`와 `next_text`를 넘기는 쪽이 맞다(추정). 이 텍스트가 과금 글자 수에 들어가는지는 문서에 없다(미확인).

### 6. 목소리 목록

- `GET /v2/voices`. `page_size`(기본 10, 최대 100), `search`, `voice_type`(`personal`, `community`, `default`, `workspace` 등), `category`(`premade`, `cloned`, `generated`, `professional`), `language`, `next_page_token` 등을 받는다. 응답은 `voices[]`(`voice_id`, `name`, `category`, `labels`, `preview_url`, `verified_languages` 등), `has_more`, `next_page_token`이다. [E12]
- 목소리 ID 예: `DCwhRBWXzGAHq8TQ4Fs18`처럼 영숫자 20자 안팎이다. [E12]
- "All ElevenLabs voices support multiple languages." 한국어 전용 기본 목소리는 문서에 없다. [E13]
- **기본(Default) 목소리는 2026-12-31에 만료된다.** 2026년 3월 이전 계정만 쓸 수 있다. 대체 목소리 표(예: George → Eldrin, Sarah → Talia)가 있으나 1:1 대응은 아니다. [E13][E14]
- 무료 등급 사용자는 API로 Voice Library 목소리를 쓸 수 없다. [E13]
- 결론: 목소리 ID를 코드에 넣지 말고 설정 화면에서 목록을 받아 고르게 한다. 대체 목소리를 API에서 어떤 `voice_type`/`category`로 찾는지는 문서에 없다(미확인).

### 7. 키 확인과 오류

- 인증 헤더는 `xi-api-key`다. 키마다 쓸 수 있는 엔드포인트와 크레딧 한도를 제한할 수 있다. [E16]
- "By default, API keys are restricted." 목소리를 쓰려면 "Voices (read)"와 "Text to Speech" 권한이 필요하다. [E24]
- 권장 확인 호출: `GET /v2/voices?page_size=1`. 크레딧을 쓰지 않고(추정), 우리에게 필요한 목소리 읽기 권한도 함께 확인한다. TTS 권한은 실제 합성 요청으로만 확인된다(추정).
- 남은 크레딧 표시용: `GET /v1/user/subscription`이 `tier`, `character_count`, `character_limit`, `next_character_count_reset_unix`를 준다. [E17] 이 호출에는 User 권한이 필요하다는 제3자 보고가 있다(미확인). 키 확인용으로는 쓰지 않는 편이 낫다.
- 오류 본문 [E15]:

```json
{"detail": {"type": "...", "code": "...", "message": "...", "status": "(옛 필드, 쓰지 말 것)", "request_id": "...", "param": "..."}}
```

| 상황 | HTTP | type | code |
|---|---|---|---|
| 잘못된 키 | 401 | `authentication_error` | `invalid_api_key` |
| 키 없음 | 401 | `authentication_error` | `missing_api_key` |
| 권한 없음 | 403 | `authorization_error` | `insufficient_permissions`, `model_access_denied` 등 |
| 크레딧 부족 | 402 | `payment_required` | `insufficient_credits` |
| 동시 요청 초과 | 429 | `rate_limit_error` | `concurrent_limit_exceeded` |
| 요청 빈도 초과 | 429 | `rate_limit_error` | `rate_limit_exceeded` |
| 서버 바쁨 | 429 | `rate_limit_error` | `system_busy` |
| 목소리 없음 | 404 | `not_found` | `voice_not_found` |
| 글자 너무 김 | 400 | `validation_error` | `text_too_long` |

- 422는 `detail`이 `loc`, `msg`, `type` 목록인 검증 오류다. [E1]
- 공식 안내: 429 `rate_limit_exceeded`는 지수 백오프, `concurrent_limit_exceeded`는 진행 중 요청이 끝나길 기다린다. [E15]
- 제3자 기록에는 권한 부족이 401과 `{"detail": {"status": "missing_permissions", ...}}`로 온 예가 있다(미확인). `code`와 옛 `status`를 둘 다 보는 편이 안전하다(추정).

### 8. 가격과 동시 요청 한도

- API 가격(1천 자당): v4, v3, v2 Multilingual은 $0.08. v4 Turbo, v3 Conversational, Flash/Turbo는 $0.04. [E18]
- 요금제 페이지: Free 월 1만 크레딧, 상업적 이용 불가. Starter 이상은 상업 라이선스가 있다. V2 Multilingual은 글자당 1크레딧, Flash/Turbo는 글자당 0.5~1크레딧이다. Pro부터 "44.1kHz PCM audio output via API"다. [E19]
- 주의: 요금제별 포함 분량이 페이지마다 다르다(예: Creator가 [E19]에서 121k 크레딧, [E18]에서 v4 27만 5천 자). 사용자에게 보여줄 숫자는 링크로 대신하는 편이 낫다.
- 동시 요청 한도(TTS) [E21][E4]:

| 요금제 | Flash·Turbo | 그 밖의 모델 |
|---|---|---|
| Free | 4 | 2 |
| Starter | 6 | 3 |
| Creator | 10 | 5 |
| Pro | 20 | 10 |
| Scale / Business | 30 | 15 |

- 우리는 재생 중 다음 문장 하나만 미리 합성하므로 무료 등급 한도(2)로도 대개 충분하다(추정). 질의응답 답변 합성이 겹치면 2를 넘을 수 있다(추정).
- 한국어 1분 낭독을 약 350자로 잡으면(추정) Multilingual v2는 약 $0.028, Flash v2.5는 약 $0.014다.

### 9. Python SDK

- 공식 패키지는 `elevenlabs`다. 저장소는 https://github.com/elevenlabs/elevenlabs-python 이다. [E22]
- 최신판 2.73.0(2026-10-15 업로드), 라이선스 MIT, Python ≥3.8. 의존성은 `httpx>=0.21.2`, `pydantic`, `requests`, `websockets>=13` 등이다. [E23]
- 이 의존성은 지금 venv에 이미 다 있다(`httpx`, `requests`, `websockets`는 `google-genai`가 끌어옴). 그래도 우리가 쓰는 것은 POST 하나와 헤더 하나, base64 디코딩뿐이다. HTTP 직접 호출로 충분하다(추정). [L1]

## OpenAI

### 10. "gpt-live"는 무엇인가, 그리고 어떤 도구가 맞나

- **GPT-Live** (`gpt-live-1`): "A full-duplex voice model for real-time conversations." 듣기와 말하기를 동시에 하고, 추론과 도구 사용은 뒤의 에이전트에 맡긴다. 엔드포인트는 Live(`v1/live/sessions`)뿐이다. Chat Completions, Responses, Realtime, Speech generation(`v1/audio/speech`)은 **지원하지 않는다.** 분당 $0.05(초 단위 과금), 무료 등급 불가. [O13][O7]
- API 공개 공지는 2026-09-10 커뮤니티 공지다. 새 목소리 12개(Quartz, Ripple 등)를 더했다. ChatGPT 음성에는 2026-07에 들어갔다는 2차 자료가 있다(공식 소개 글은 접근이 막혀 미확인). [O15]
- GPT-Live 안내서는 대화 세션, 백엔드 위임, WebRTC/WebSocket/SIP 연결을 설명한다. 정해진 글을 그대로 읽는 쓰임은 설명하지 않는다. [O14]
- OpenAI 모델 목록의 음성 관련 분류 [O4]:
  - 음성 생성(TTS): `gpt-4o-mini-tts`
  - 실시간: `gpt-live-1`, `gpt-realtime-2.1`, `gpt-realtime-2.1-mini`, `gpt-realtime-2`, `gpt-realtime-translate`, `gpt-realtime-1.5`, `gpt-realtime-mini`(폐기)
- **"주어진 글을 음성으로"에 맞는 도구는 지금은 Audio Speech(`POST /v1/audio/speech`)다.** 공식 안내서도 TTS에는 이 엔드포인트, 음성 비서에는 Realtime을 권한다. [O1]
- **그러나 TTS 모델이 모두 2027-01-06에 제거된다.** 공지 원문: "The following text-to-speech models are deprecated and will be removed from the API on January 6, 2027," "Migrate to `gpt-realtime-2.1-mini` before the shutdown date." 대상은 `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts-2025-03-20`, `gpt-4o-mini-tts-2025-12-15`다. 별칭 `gpt-4o-mini-tts`는 목록에 없지만 가리키는 스냅숏이 사라지므로 함께 못 쓰게 될 것이다(추정). [O8][O5]
- 대체 모델 `gpt-realtime-2.1-mini`는 Realtime(`v1/realtime`)만 지원한다. 텍스트 입력과 오디오 출력은 된다. 대화 모델이라 글을 **그대로** 읽는다는 보장이 없다. 공식 예제는 지시문에 "Say exactly the following:"을 넣는 방식이다. [O9][O11]
- Realtime으로 낭독하기의 사실 [O10][O11][O12][O20]:
  - WebSocket 세션을 열고 `conversation.item.create`로 글을 넣고 `response.create`로 응답을 받는다. 대화 맥락을 안 쓰려면 `response.conversation: "none"`과 `input` 배열을 쓴다.
  - 출력 형식은 `audio/pcm`(24 kHz만), `audio/pcmu`, `audio/pcma`다.
  - 목소리: alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar. 품질은 marin, cedar를 권한다. 세션에서 한 번 소리를 낸 뒤에는 목소리를 바꿀 수 없다.
  - `openai` SDK의 Realtime은 `openai[realtime]` 추가 의존성(`websockets >=13, <16`)이 필요하다. 지금 venv의 `websockets`는 16.1.1이라 범위를 벗어난다(직접 확인). 충돌 여부는 시험하지 않았다(추정).

### 11. Audio Speech 엔드포인트

`POST /v1/audio/speech`. 아래는 API 레퍼런스와 SDK 소스 기준이다. [O2][O3]

- `input`: 최대 4,096자. 단 `gpt-4o-mini-tts` 모델 페이지는 입력 최대 2,000토큰이라고 적는다. 문장 단위면 문제없다. [O3][O5]
- `model`: `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts`, `gpt-4o-mini-tts-2025-12-15`. 모두 2027-01-06 제거 대상이다. 2025-12-15 스냅숏은 정확도를 높인 판이다. [O3][O8][O21]
- `voice`: alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse, marin, cedar(13개). 사용자 정의 목소리는 `{"id": "voice_..."}`. 안내서는 marin, cedar를 최고 품질로 권한다. `tts-1`/`tts-1-hd`는 그중 9개(alloy, ash, coral, echo, fable, onyx, nova, sage, shimmer)만 안내한다. 목소리는 영어에 맞춰져 있다. [O3][O1]
- `instructions`: 말투 지시. "Does not work with `tts-1` or `tts-1-hd`." [O3]
- `speed`: "Select a value from `0.25` to `4.0`. `1.0` is the default." 지금 문서에는 모델 제한이 없다. [O3]
  - 그러나 2025-05-02 OpenAI 커뮤니티 직원 답변: "The `speed` parameter is not supported for `gpt-4o-mini-tts` currently." 2025-06에 이제 된다는 사용자 보고가 있으나 공식 확인은 없다(미확인). [O16]
  - 정리: `tts-1`/`tts-1-hd`는 0.25~4.0을 따른다. `gpt-4o-mini-tts`는 확실하지 않다. 실제 길이를 재서 `engine_speed`를 정하는 편이 안전하다(추정).
- `response_format`: `mp3`(기본), `opus`, `aac`, `flac`, `wav`, `pcm`. 안내서: `pcm`은 "raw samples in 24kHz (16-bit signed, low-endian), without the header"다(low-endian은 little-endian의 오기로 보인다). 가장 빠른 응답에는 `wav`나 `pcm`을 권한다. 모노라는 말은 문서에 없다(미확인). [O3][O1]
- 스트리밍: 청크 전송으로 생성 중 재생할 수 있다. `stream_format`은 `audio`나 `sse`다. `sse`는 `tts-1`/`tts-1-hd`에서 안 된다. SSE 이벤트 모양은 SDK 소스에서 찾지 못했다(미확인). [O1][O3]
- 한국어: 지원 언어는 Whisper 목록을 따르며 한국어가 들어 있다. [O1]
- 사용 정책상 최종 사용자에게 AI 음성임을 밝혀야 한다. [O1]
- 속도 제한(기본): `gpt-4o-mini-tts` Build 2,000 RPM. `tts-1` Free 3 RPM, 200 RPD. [O5][O6]

### 12. 타임스탬프

- Audio Speech 응답에는 시각 정보가 없다. 안내서와 레퍼런스 어디에도 없다. [O1][O2]
- Realtime의 `response.output_audio_transcript.delta`는 텍스트 조각(`delta`)만 준다. 시각 필드가 없다. [O22]
- Realtime 안내서: 모델은 "doesn't have enough information to precisely align transcript and audio." [O11]
- 우회: 만든 오디오를 받아쓰기 API에 다시 넣으면 단어 시각을 받을 수 있다. `timestamp_granularities: ["word"]`는 `verbose_json`에서만 되고, `gpt-4o-transcribe` 계열은 `json`만 지원한다. `whisper-1`은 되지만 2027-02-26에 제거된다. `gpt-transcribe`의 단어 시각 지원은 확인하지 못했다. 비용과 지연이 늘어 권하지 않는다(추정). [O23][O8]
- 결론: OpenAI는 글자 수 추정으로 간다.

### 13. 키 확인, 오류, 가격

- 키 확인: `client.models.list()` = `GET /v1/models`. 과금 여부는 문서에 없다(무료로 추정). [O19]
- SDK의 상태 코드 대응(`_make_status_error`): 400 `BadRequestError`, 401 `AuthenticationError`, 403 `PermissionDeniedError`, 404 `NotFoundError`, 409 `ConflictError`, 422 `UnprocessableEntityError`, 429 `RateLimitError`, 500 이상 `InternalServerError`. 연결 실패는 `APIConnectionError`, 시간 초과는 `APITimeoutError`다. 예외 객체에 `code`, `type`, `param`이 있다. [O18]
- 429는 속도 제한과 결제 문제가 같이 쓴다. 결제 쪽 `error.code`: `credit_balance_exhausted`, `organization_spend_limit_exceeded`, `project_spend_limit_exceeded`, `organization_usage_limit_exceeded`. `error.type`이 `insufficient_quota`일 수 있다. 결제 오류는 다시 시도해도 풀리지 않는다. [O17]
- 401 원인: 키 오타, 삭제된 키, 다른 조직·프로젝트의 키, 그 엔드포인트 권한이 없는 키. 403은 지원하지 않는 국가다. [O17]
- 가격 [O7]:
  - `gpt-4o-mini-tts`: 텍스트 입력 100만 토큰당 $0.60, 오디오 출력 100만 토큰당 $12. 분당 환산값은 문서에 없다.
  - `tts-1`: 100만 자당 $15. `tts-1-hd`: 100만 자당 $30.
  - `gpt-realtime-2.1-mini`: 텍스트 입력 $0.60, 오디오 출력 $20(100만 토큰당). [O9]
  - `gpt-live-1`: 분당 $0.05.

## 14. Gemini TTS (짧게)

- 모델: `gemini-3.8-flash-tts`(130개 넘는 언어), `gemini-3.8-flash-lite-tts`(100개 넘는 언어). 둘 다 언어표에 한국어가 있다. 이전 미리보기 모델은 `gemini-3.1-flash-tts-preview`, `gemini-2.5-pro-preview-tts`다. [G1]
- 호출: `POST /v1beta/interactions`, `"response_format": {"type": "audio"}`, `generation_config.speech_config`에 목소리(예: `Kore`)를 넣는다. 공식 SDK는 `google-genai` 2.25.0 이상이 필요하다. 저장소는 2.31을 쓴다. [G1]
- 출력: 기본은 24 kHz, 모노, 16비트 리틀엔디언 WAV다. 스트리밍은 헤더 없는 `audio/l16` 24 kHz다. `sample_rate`로 16000, 8000도 고를 수 있다. 22050은 목록에 없다. [G1]
- 목소리: 미리 만든 30개(Zephyr, Puck, Kore 등)와 확장 목소리 수백 개. [G1]
- 시각 정보: 문서에 없다. 속도: 매개변수가 없고, 지시문("speaking rapidly")으로만 조절한다. [G1]
- 한도: 입력 8,192토큰, 출력 16,384토큰. [G2]
- 가격(100만 토큰당): Flash TTS 입력 $0.50 / 출력 $9.00(2026-12-31까지), 2027-01-01부터 $1.00 / $18.00. Flash-Lite TTS 출력 $6.00(이후 $12.00). 무료 등급이 있다. 오디오는 초당 25토큰이므로 Flash TTS 1분은 약 $0.0135다. [G3]
- 판단: 이미 Gemini 키와 SDK가 있어 붙이기 쉽다. 하지만 시각 정보와 속도가 없어 OpenAI Speech와 같은 수준이다(추정).
- 추가 확인(2026-10-17, 공식 페이지 재조회):
  - Python 예제는 `client.interactions.create(model="gemini-3.8-flash-tts", input=[{"type": "user_input", "content": [{"type": "text", "text": ...}]}], response_format={"type": "audio"}, generation_config={"speech_config": [{"voice": "Kore"}]})`이고, 소리는 `base64.b64decode(interaction.output_audio.data)`로 꺼낸다. 모델 페이지는 Interactions API와 generateContent를 둘 다 지원한다고 적는다. [G1][G2]
  - 한 번에 받는 응답(`stream=False`)은 RIFF 머리가 있는 WAV(24 kHz, 모노, 16비트 LE)다. 스트리밍은 머리 없는 `audio/l16`이다. [G1]
  - "Gemini 3.8 TTS treats input text strictly as a verbatim transcript." 글 안에 넣은 지시("Say cheerfully: ...")는 소리 내어 읽힐 수 있다. 말투는 `speech_metadata.style`로 따로 준다. [G2]
  - 언어는 스스로 알아낸다. `language_code` 매개변수는 문서에 없다. [G1]
  - 미리 만든 목소리 30개: Zephyr, Puck, Charon, Kore, Fenrir, Leda, Orus, Aoede, Callirrhoe, Autonoe, Enceladus, Iapetus, Umbriel, Algieba, Despina, Erinome, Algenib, Rasalgethi, Laomedeia, Achernar, Alnilam, Schedar, Gacrux, Pulcherrima, Achird, Zubenelgenubi, Vindemiatrix, Sadachbia, Sadaltager, Sulafat. [G1]

## 제공자별 요약 (파이프라인 관점)

| 항목 | ElevenLabs | OpenAI Speech | OpenAI Realtime | Gemini TTS |
|---|---|---|---|---|
| 한국어 기본 모델 | `eleven_multilingual_v2` (권장) | `gpt-4o-mini-tts` | `gpt-realtime-2.1-mini` | `gemini-3.8-flash-tts` |
| PCM 표본률 | 8k~48k, **22050 있음**(44.1k는 Pro+) | 24k만 | 24k만 | 24k(16k, 8k 선택) |
| 표본 형식 | S16LE 모노 | 16비트 부호 있음 LE | PCM16 | 16비트 LE 모노 |
| 글자·단어 시각 | 글자 단위(`alignment`) | 없음 | 없음 | 없음 |
| 엔진 속도 | 0.7~1.2 (v4는 없음) | 0.25~4.0 (`gpt-4o-mini-tts`는 불확실) | 0.25~1.5, 후처리 | 없음 |
| 문장 잇기 | `previous_text`/`next_text` | 없음 | 세션 맥락(대화) | 없음 |
| 요청당 한도 | 10,000자(v2) | 4,096자 | 128k 컨텍스트 | 8,192토큰 |
| 키 확인 | `GET /v2/voices?page_size=1` | `GET /v1/models` | 같음 | (기존 Gemini 확인 재사용) |
| 수명 | v2는 "이전 세대", 폐기 공지 없음 | **2027-01-06 제거** | 현행 | 현행 |

## 확인하지 못한 것

- ElevenLabs `alignment.characters`를 이어 붙이면 입력과 정확히 같은지, 한국어에서 음절 하나가 원소 하나인지. 키가 없어 시험하지 못했다.
- ElevenLabs에서 `eleven_v3`, `eleven_v4`, `eleven_v4_turbo`가 `/with-timestamps`에 `alignment`를 주는지. 문서에 모델별 표가 없다.
- ElevenLabs `speed`가 0.7~1.2를 벗어나면 400인지, 잘라서 적용하는지. v4에 `speed`를 보내면 무시되는지 오류인지.
- ElevenLabs `previous_text`/`next_text`가 과금 글자 수에 들어가는지.
- ElevenLabs `pcm_32000`, `pcm_48000`의 요금제 제한.
- ElevenLabs 대체 목소리(2026-12-31 이후)를 API에서 어떤 `voice_type`/`category`로 찾는지, 무료 계정에서 쓸 수 있는지.
- ElevenLabs 권한이 제한된 키로 `GET /v1/user`, `/v1/user/subscription`을 부르면 어떤 오류가 오는지(공식 문서에 없음).
- ElevenLabs 요금제별 포함 크레딧. 페이지마다 숫자가 다르다.
- OpenAI `gpt-4o-mini-tts`가 지금 `speed`를 따르는지. 2025-05 직원 답변은 "미지원", 이후 사용자 보고는 "된다"였다.
- OpenAI Speech `pcm`이 모노인지(문서에 채널 수가 없다). SSE(`stream_format: "sse"`) 이벤트의 정확한 모양.
- OpenAI `/v1/audio/speech` 엔드포인트 자체가 2027-01-06 뒤에도 남는지. 공지는 모델만 말한다.
- `gpt-realtime-2.1-mini`가 주어진 한국어 문장을 빠짐없이 그대로 읽는지. 대화 모델이라 보장이 없다.
- `openai[realtime]`의 `websockets<16` 제한과 venv의 `websockets` 16.1.1이 실제로 충돌하는지.
- GPT-Live 공식 소개 글(openai.com)은 403으로 열리지 않았다. ChatGPT 출시일은 2차 자료로만 봤다.
- 세 제공자 모두 첫 소리까지 걸리는 시간(네트워크 포함)의 공식 수치가 없다. ElevenLabs 수치는 모델 추론 지연만이다.

## 출처

ElevenLabs
- [E1]: https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps — Create speech with timing
- [E2]: https://elevenlabs.io/docs/api-reference/text-to-speech/stream-with-timestamps — Stream speech with timing
- [E3]: https://elevenlabs.io/docs/api-reference/text-to-speech/convert — Create speech
- [E4]: https://elevenlabs.io/docs/overview/models — Models (언어, 글자 한도, 정규화, 동시 요청 표)
- [E5]: https://elevenlabs.io/docs/overview/capabilities/text-to-speech — Text to Speech 기능 소개 (PCM S16LE)
- [E6]: https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4 — Eleven v4 안내
- [E7]: https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/what-is-eleven-v4 — What is Eleven v4?
- [E8]: https://elevenlabs.io/blog/eleven-v4 — Introducing Eleven v4 (2026-09-28)
- [E9]: https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/request-stitching — Request stitching
- [E10]: https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/can-i-change-the-pace-of-the-voice — 속도 0.7~1.2
- [E11]: https://elevenlabs.io/docs/eleven-agents/customization/voice/speed-control — Speed control
- [E12]: https://elevenlabs.io/docs/api-reference/voices/search — List voices (`GET /v2/voices`)
- [E13]: https://elevenlabs.io/docs/overview/capabilities/voices — Voices (기본 목소리 만료, Voice Library 무료 등급 제한)
- [E14]: https://elevenlabs.io/docs/help-center/product/voices/my-voices/what-are-default-voices — What are Default voices?
- [E15]: https://elevenlabs.io/docs/eleven-api/resources/errors — Errors
- [E16]: https://elevenlabs.io/docs/api-reference/authentication — Authentication (`xi-api-key`, 키 범위 제한)
- [E17]: https://elevenlabs.io/docs/api-reference/user/subscription/get — Get user subscription
- [E18]: https://elevenlabs.io/pricing/api — API pricing
- [E19]: https://elevenlabs.io/pricing — Pricing
- [E20]: https://elevenlabs.io/docs/help-center/troubleshooting/what-audio-formats-do-you-support — 지원 오디오 형식과 등급
- [E21]: https://elevenlabs.io/docs/help-center/technical/how-many-text-to-speech-requests-can-i-make-and-can-i-increase-it — TTS 동시 요청 한도
- [E22]: https://elevenlabs.io/docs/eleven-api/resources/libraries — Libraries & SDKs
- [E23]: https://pypi.org/pypi/elevenlabs/json — `elevenlabs` PyPI 메타데이터 (2.73.0, MIT)
- [E24]: https://elevenlabs.io/docs/help-center/product/voices/my-voices/why-cant-i-access-my-voices-via-third-party-services — 키 기본 제한, 필요한 권한
- [E25]: https://elevenlabs.io/docs/help-center/technical/is-it-possible-to-get-a-time-stamped-transcript-of-the-audio-output — 시각 정보는 글자 단위
- (참고) https://elevenlabs.io/docs/eleven-api/choosing-the-right-model — 모델 고르기

OpenAI
- [O1]: https://developers.openai.com/api/docs/guides/text-to-speech — Text to speech 안내서
- [O2]: https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create — Create speech 레퍼런스
- [O3]: https://github.com/openai/openai-python/blob/main/src/openai/types/audio/speech_create_params.py — SDK 매개변수 정의(`speed` 0.25~4.0, `instructions`, `stream_format`)
- [O4]: https://developers.openai.com/api/docs/models — Models
- [O5]: https://developers.openai.com/api/docs/models/gpt-4o-mini-tts — GPT-4o mini TTS
- [O6]: https://developers.openai.com/api/docs/models/tts-1 — TTS-1
- [O7]: https://developers.openai.com/api/docs/pricing — Pricing
- [O8]: https://developers.openai.com/api/docs/deprecations — Deprecations (2026-10-01 TTS 모델 공지)
- [O9]: https://developers.openai.com/api/docs/models/gpt-realtime-2.1-mini — GPT-Realtime-2.1 mini
- [O10]: https://developers.openai.com/api/docs/guides/realtime — Realtime API 안내서
- [O11]: https://developers.openai.com/api/docs/guides/realtime-conversations — Realtime conversations
- [O12]: https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/realtime_audio_config_output_param.py, https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/realtime_audio_formats_param.py — Realtime 출력 속도·목소리·형식
- [O13]: https://developers.openai.com/api/docs/models/gpt-live-1 — GPT-Live 1
- [O14]: https://developers.openai.com/api/docs/guides/live — GPT-Live 안내서
- [O15]: https://community.openai.com/t/introducing-gpt-live-1-in-the-api/1396471 — Introducing GPT-Live-1 in the API (2026-09-10)
- [O16]: https://community.openai.com/t/new-tts-model-gpt-4o-mini-tts-ignoring-speed-parameter/1154883 — `gpt-4o-mini-tts` speed 무시 (직원 답변 2025-05-02)
- [O17]: https://developers.openai.com/api/docs/guides/error-codes — Error codes
- [O18]: https://github.com/openai/openai-python/blob/main/src/openai/_client.py, https://github.com/openai/openai-python/blob/main/src/openai/_exceptions.py — 상태 코드와 예외 대응
- [O19]: https://developers.openai.com/api/reference/resources/models/methods/list — List models
- [O20]: https://github.com/openai/openai-python/blob/main/pyproject.toml — `openai` 3.33.0 의존성(`httpx2`, `realtime` 추가 의존성)
- [O21]: https://developers.openai.com/blog/updates-audio-models — 2025-12-15 음성 모델 스냅숏 소개
- [O22]: https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/response_audio_transcript_delta_event.py — 전사 조각 이벤트(시각 필드 없음)
- [O23]: https://github.com/openai/openai-python/blob/main/src/openai/types/audio/transcription_create_params.py — 받아쓰기 `timestamp_granularities`

Gemini
- [G1]: https://ai.google.dev/gemini-api/docs/speech-generation — Speech generation (2026-10-12 갱신)
- [G2]: https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts — Gemini 3.8 Flash TTS
- [G3]: https://ai.google.dev/gemini-api/docs/pricing — Pricing

직접 확인
- [L1]: 저장소 `.venv`의 설치 메타데이터(2026-10-17). `openai` 3.33.0은 `httpx2`에 의존한다. `httpx` 0.28.1, `requests`, `websockets` 16.1.1은 `google-genai` 2.31.0이 끌어온다. 파일은 읽기만 했다.
