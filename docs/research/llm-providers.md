# 세 LLM 제공자의 현재 모델과 생각 깊이 설정

조사일: 2026-10-16. 티켓 `03-research-llm-providers`의 답이다. 근거는 Anthropic, OpenAI, Google AI for Developers의 공식 문서와 가격 페이지, PyPI 메타데이터, 이 조사에서 직접 측정한 값이다. 출처 번호(예: [C1])는 맨 아래 출처 목록에 있다. 확인하지 못한 것은 "미확인"으로 적었다. API 키가 없어서 실제 호출 실험은 하지 않았다.

## 결론 요약

- **권장 기본 모델(빠르고 싼 쪽)**: Claude는 `claude-haiku-5-5`, OpenAI는 `gpt-6-luna`, Gemini는 `gemini-3.5-flash-lite`다. 세 모델 모두 이미지 입력과 SSE 스트리밍을 지원한다. [C1][O2][G2]
- **비용**: 근거 5천~2만 토큰에 답 200토큰인 질문 하나에 생각 토큰을 빼고 Haiku 5.5와 gpt-6-luna는 약 $0.0006~0.0021, Gemini 3.5 Flash-Lite는 약 $0.002~0.0065가 든다. 생각 토큰은 출력 단가로 따로 붙는다. 첫 토큰 지연과 전체 지연은 세 제공자 모두 **공식 수치가 없다**.
- **생각 깊이 공통 단계**: low/mid/high를 세 제공자 모두 `"low"` / `"medium"` / `"high"`로 그대로 보낸다. Claude는 `output_config.effort`, OpenAI는 `reasoning.effort`, Gemini는 `thinking_level`에 넣는다. 권장 기본 모델과 상위 모델 모두 세 값을 받는다. 모델마다 기본값이 다르므로(예: Gemini 3.5 Flash-Lite는 `minimal`) 매 요청에 단계를 **명시해서 보낸다**. [C3][O8][G5]
- **생각 끄기**는 일부 모델에서만 된다. Claude Haiku 5.5는 `disabled`, gpt-6-luna는 `none`, Gemini 3.5 Flash-Lite는 `minimal`(거의 생각하지 않음)로 끈다. Claude Opus 5.5, gpt-6.1-sol, gpt-6-astra, Gemini 3.8 Flash, Gemini 4 Argon은 끌 수 없다. 그래서 공통 단계는 low부터 시작한다. [C4][O3][O4][G5]
- **SDK보다 표준 라이브러리 HTTP 직접 호출을 권한다.** 세 공식 SDK의 최신판(`anthropic` 1.15.0, `openai` 3.31.0, `google-genai` 2.31.0)은 모두 **Python 3.10 이상**을 요구한다. 현재 최소 버전인 3.9에서는 옛 판이 깔린다. 특히 `google-genai` 1.47.0에는 Gemini 3 이후 모델의 생각 깊이를 정하는 `thinking_level`이 없다. 세 SDK를 넣으면 PyInstaller 실행 파일이 약 30MB 커진다(직접 측정). 필요한 호출은 POST 한 종류와 SSE 읽기뿐이라 직접 구현하는 부담이 작다. [P1][P2][P3]
- **Python 최소 버전을 3.10 이상으로 올린다면** SDK도 쓸 만하다. 세 SDK 모두 PyInstaller 6.22.3 onedir 빌드에서 import와 클라이언트 생성이 정상 동작했다(직접 측정). 참고로 Python 3.9는 2025-10-31에, 3.10은 2026-10-01에 지원이 끝났다. [P4]
- **모델 목록 API**: 세 제공자 모두 키로 목록을 받을 수 있다. 다만 기능 정보(이미지 입력, 생각 단계)를 함께 주는 곳은 Claude뿐이다. 설정 창에는 **추천 목록을 코드에 두고**, 목록 받기는 "사용 가능 여부 확인"에만 쓰고, 모델 ID 직접 입력도 허용하기를 권한다. [C7][O11][G14]

## 1. 제공자별 모델 표

가격은 표준(동기) 요청 기준, 100만 토큰당 미국 달러다. 생각 토큰은 세 제공자 모두 출력 단가로 과금된다. [C4][O8][G5]

### Claude (Anthropic)

| 모델 ID | 용도 | 이미지 입력 | 생각 깊이 설정 (`output_config.effort`) | 가격 입력 / 출력 |
|---|---|---|---|---|
| `claude-haiku-5-5` **(권장 기본)** | 대량·지연 민감 작업. 공식 비교에서 가장 빠름("Fastest") | 예 | `low`~`max`, 기본 `medium`. `thinking:{type:"disabled"}`는 effort `high` 이하에서만 됨 | $0.10 / $0.50 (프롬프트 10만 토큰 이하), $0.50 / $2.50 (초과) |
| `claude-sonnet-5-5` | 속도와 지능의 균형("Fast") | 예 | `low`~`max`, 기본 `high`. `disabled`는 400 오류. 대신 `between_tools`(effort `high` 이하) | $2 / $10 |
| `claude-opus-5-5` | Anthropic 일반 권장 모델. 긴 에이전트·지식 작업("Moderate") | 예 | `low`~`max`, 기본 `medium`. **생각을 끌 수 없음** | $4 / $20 |
| `claude-fable-5-1` | 가장 높은 성능, 가장 느림("Slower"). 질의응답 용도로는 과함 | 예 | `low`~`max`, 기본 `high`. 생각을 끌 수 없음 | $10 / $50 |

- 출처: 모델 ID, 지연 비교, 기본 effort는 [C1], 가격은 [C2], 생각 설정은 [C3][C4]다. "All current models support text and image input"이라고 적혀 있다. [C1]
- 컨텍스트는 네 모델 모두 1M 토큰, 최대 출력은 128K 토큰이다. [C1]
- 레거시(아직 제공): `claude-haiku-4-5`($1 / $5), `claude-sonnet-4-6`, `claude-opus-4-8` 등이 있다. [C1][C2]
- **지원 종료**: `claude-opus-4-1`, `claude-sonnet-4-0`(Sonnet 4), `claude-opus-4-0`(Opus 4), Haiku 3.5는 Claude API에서 퇴역했다("retired, except on Bedrock and Google Cloud" 등). 목록에 넣지 않는다. [C2]

### OpenAI

| 모델 ID | 용도 | 이미지 입력 | 생각 깊이 설정 (`reasoning.effort`) | 가격 입력 / 출력 |
|---|---|---|---|---|
| `gpt-6-luna` **(권장 기본)** | "가장 효율적인 모델", 대량 작업용 | 예 | `none`, `low`~`max`, 기본 `medium`. `none`으로 끌 수 있음 | $0.10 / $0.50 |
| `gpt-6.1-sol` | Astra에 가까운 성능을 낮은 가격에 | 예 | `low`~`max`, 기본 `medium`. `none`과 `minimal`은 거부됨 | $2 / $10 |
| `gpt-6-sol` | 6.1 Sol의 이전 판 | 예 | `none`, `low`~`max`, 기본 `medium` | $2 / $10 |
| `gpt-6-astra` | 가장 높은 성능. 공식 "시작점" 추천 | 예 | `low`~`max`. 기본값은 문서에 없음(미확인). `none`은 HTTP 400 | $10 / $50 |

- 출처: 목록과 추천은 [O1], 모델별 사양은 [O2][O3][O4][O5], 가격은 [O12], 생각 설정은 [O8]이다.
- 네 모델 모두 컨텍스트 1,050,000 토큰, 최대 출력 128,000 토큰이다. 입력이 27만 2천 토큰을 넘으면 장문 단가가 붙는다(입력 2배, 출력 1.5배). [O2][O12]
- 참고: `gpt-5.6-luna`($0.20 / $1.20), `gpt-5.6-terra`($2 / $12)도 아직 제공된다. [O6][O12]
- **지원 종료 예정(목록에 넣지 않는다)** [O7]:
  - `gpt-5-mini`, `gpt-5-nano`, `gpt-5`의 2025-08-07 스냅숏과 `o3`: 2026-12-11에 종료된다.
  - `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`의 스냅숏: 2027-01-14에 종료된다. 대체 모델은 `gpt-6-luna`다.
  - `gpt-5.4-nano`, `gpt-5.1`: 2027-04-01에 종료된다.
  - `gpt-4.1-nano`, `o4-mini`, `o3-mini`, `o1`: 2026-10-23에 종료된다.

### Gemini (Google)

| 모델 ID | 용도 | 이미지 입력 | 생각 깊이 설정 (`thinking_level`) | 가격 입력 / 출력 |
|---|---|---|---|---|
| `gemini-3.5-flash-lite` **(권장 기본)** | "가장 빠르고 비용 효율적인 3.5 모델". 공식 신규 권장 둘 중 하나 | 예 (PNG/JPEG/WebP/HEIC/HEIF) | `minimal`·`low`·`medium`·`high`, **기본 `minimal`** | $0.30 / $2.50 |
| `gemini-3.8-flash` | 가장 지능 높은 Flash. 공식 신규 권장 둘 중 하나 | 예 | `low`·`medium`·`high`, 기본 `medium`. `minimal`은 오류 | $0.75 / $3.75 (2026-12-31까지), $1.50 / $7.50 (2027-01-01부터) |
| `gemini-3.6-flash` | 이전 세대 Flash | 예 | `minimal`~`high`, 기본 `medium` | $0.75 / $3.75 (2026-12-31까지), $1.50 / $7.50 (2027-01-01부터) |
| `gemini-4-argon` | 최상위 추론 모델. 무료 등급에서 쓸 수 없음 | 예 | `low`·`medium`·`high`, 기본 `medium` | $2 / $10 (2026-11-30까지), $4 / $20 (2026-12-01부터) |

- 출처: 목록과 "For any new projects, use our latest models: 3.5 Flash-Lite or 3.8 Flash"는 [G1], 모델 사양은 [G2][G3][G4], 생각 단계표는 [G5], 가격은 [G7]이다.
- 입력 한도는 1,048,576 토큰이다. 출력 한도는 65,536 토큰이고, Argon은 백그라운드 장문 생성 시 더 길다. [G2][G3][G4]
- 무료 등급(Free Tier)에서는 3.5 Flash-Lite와 3.8 Flash가 무료다. 대신 표의 "Used to improve our products" 항목이 "Yes"다. 유료 등급은 "No"다. [G7]
- **지원 종료 예정·제한**: `gemini-3.1-flash-lite`($0.25 / $1.50)는 2027-05-07에 종료되고 대체는 `gemini-3.5-flash-lite`다. `gemini-2.5-*`는 "과거에 쓴 사용자에게만" 접근이 제한되어 새 키에는 맞지 않는다. `gemini-3-pro-preview`와 `gemini-2.0-flash`는 이미 종료됐다. [G1][G15]

## 2. 생각 깊이 공통 단계 대응표

| 공통 단계 | Claude `output_config.effort` | OpenAI `reasoning.effort` (Responses API) | Gemini `thinking_level` |
|---|---|---|---|
| **low** | `"low"` | `"low"` | `"low"` |
| **mid** | `"medium"` | `"medium"` | `"medium"` |
| **high** | `"high"` | `"high"` | `"high"` |
| 쓰지 않는 상위 값 | `"xhigh"`, `"max"` | `"xhigh"`, `"max"` | 없음 |
| 보내지 않을 때 기본값 | Haiku 5.5·Opus 5.5 `medium`, Sonnet 5.5 `high` | luna·6.1-sol·6-sol `medium`, astra 미확인 | 3.5 Flash-Lite `minimal`, 3.8 Flash·3.6 Flash·4 Argon `medium` |
| (선택) 끄기 | Haiku 5.5: `thinking:{"type":"disabled"}`(effort `high` 이하). Sonnet 5.5: `{"type":"between_tools"}`. Opus 5.5·Fable 5.1: 불가 | luna·6-sol: `"none"`. 6.1-sol·astra: 불가 | 3.5 Flash-Lite·3.6 Flash: `"minimal"`("Little to no thinking"). 3.8 Flash·4 Argon: 불가 |

- 세 단계 모두 표의 12개 후보 모델이 받는 값이다. 다만 OpenAI `gpt-6-astra`는 지원 값 목록만 확인했고 기본값은 미확인이다. [C3][O2][O3][O4][O5][G5]
- 이 대응은 이름만 같을 뿐 **생각의 양이 같다는 보장은 없다**. Claude 문서도 같은 effort 이름이라도 모델마다 생각량이 다르다고 밝힌다(Sonnet 5.5는 "levels are recalibrated"). [C3]
- Gemini 3.5 Flash-Lite는 기본값이 `minimal`이라 "low"를 보내면 기본보다 더 생각한다. 단계를 생략하지 말고 늘 보낸다. [G5]
- 생각 토큰은 Claude의 `max_tokens`, OpenAI의 출력 한도, Gemini의 `max_output_tokens` 안에 함께 들어간다. 답이 200토큰이라도 출력 한도를 넉넉히 잡는다. 한도에 걸리면 답이 비거나 잘린다. [C3][O8][G5]

## 3. 항목별 상세

### 3.1 모델 목록과 기본 모델

- 기본 모델은 티켓 기준("빠르고 싼 쪽")으로 골랐다. Anthropic의 일반 권장은 `claude-opus-5-5`("start with Claude Opus 5.5 for most workloads")다. 하지만 지연 비교에서 Haiku 5.5가 "Fastest"이고 단가도 1/40이다. [C1][C2]
- OpenAI는 "잘 모르겠으면 GPT-6 Astra"를 권한다. 하지만 Luna를 "cost-sensitive, high-volume workloads"용으로 소개한다. [O1]
- Google은 새 프로젝트에 3.5 Flash-Lite나 3.8 Flash를 쓰라고 한다. [G1]
- 세 기본 모델의 입력 단가는 Haiku 5.5와 gpt-6-luna가 같다($0.10). Gemini 3.5 Flash-Lite는 그 3배다($0.30). [C2][O12][G7]

### 3.2 생각 깊이

**Claude** [C3][C4]
- `output_config: {"effort": "low"|"medium"|"high"|"xhigh"|"max"}`로 정한다. 베타 헤더 없이 GA다.
- 현재 모델은 `thinking`을 생략하면 적응형 생각(adaptive)이 켜진다. `thinking:{type:"enabled", budget_tokens:N}`은 현재 모델에서 400 오류다.
- 생각 내용 표시(`display`)는 기본 `"omitted"`라서 생각 블록의 글이 비어서 온다. 과금은 그대로다.
- Haiku 5.5는 `temperature`, `top_p`, `top_k`에 기본값이 아닌 값을 보내면 400 오류다. 이것은 `claude-api` 스킬의 `shared/model-migration.md` "Migrating to Claude Haiku 5.5"에 나온다.
- 안전 분류기 때문에 HTTP 200에 `stop_reason: "refusal"`로 답이 거절될 수 있다. 답을 읽기 전에 확인해야 한다. Haiku 5.5에는 서버 쪽 대체 모델(fallback)이 없다(같은 스킬 문서).

**OpenAI** [O8]
- Responses API는 `reasoning: {"effort": ...}`, Chat Completions는 최상위 `reasoning_effort`로 정한다.
- 허용 값은 `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`다. 모델마다 그중 일부만 받는다.
- 생각(reasoning) 토큰은 API로 볼 수 없다. 하지만 출력 토큰으로 과금된다.
- 지연이 중요한 작업(음성, 분류)에는 `none`이 맞다고 안내한다.
- GPT-6과 GPT-5.6 모델은 별도의 `reasoning.mode`(`standard`/`pro`)도 받는다. 기본값은 `standard`다. 비용이 늘어나므로 쓰지 않는다.

**Gemini** [G5][G6]
- 생각은 기본으로 켜져 있다("dynamic thinking by default").
- Interactions API에서는 `generation_config.thinking_level`로 정한다.
- generateContent API에서는 `generationConfig.thinkingConfig.thinkingLevel`(열거값 `MINIMAL`/`LOW`/`MEDIUM`/`HIGH`)로 정한다. 레퍼런스에는 "Recommended for Gemini 3 or later models. Use with earlier models results in an error."라고 적혀 있다.
- `MINIMAL`의 정의는 "Little to no thinking"이다. 완전히 끈다는 보장은 없다.
- 응답 가격은 "the sum of output tokens and thinking tokens"다.

### 3.3 이미지 입력(캡션용)

| 항목 | Claude | OpenAI | Gemini |
|---|---|---|---|
| 형식 | JPEG, PNG, GIF, WebP (애니메이션은 첫 프레임만) | PNG, JPEG, WEBP, 애니메이션 없는 GIF | PNG, JPEG, WEBP, HEIC, HEIF |
| 넣는 방법 | base64, URL, Files API `file_id` | Responses `input_image`에 URL 또는 base64 data URL, 또는 `file_id` | 인라인 base64, Files API, 외부 URL(파일당 15MB) |
| 장당 크기 | base64 기준 10MB, 최대 8000×8000px | 장당 MB 한도는 문서에 없음. 리사이즈 뒤 30,000 패치를 넘으면 거부 | 인라인은 요청 전체 한도 안에서. 이미지 문서는 20MB, 입력 방법 문서는 100MB로 **서로 다르다** |
| 요청당 개수 | 600장(1M 컨텍스트 모델). 20장을 넘으면 장당 크기 제한이 더 엄격해짐(각 변 2000px 이하면 안전) | 1,500장 | 3,600장 |
| 요청 전체 | 32MB | 512MB | 위 인라인 한도 참고 |
| 이미지 토큰 | `⌈w/28⌉×⌈h/28⌉`. Claude 4.7 이후 모델은 긴 변 2576px·4784토큰까지(1000×1000 → 1,296토큰) | 32px 패치 수 × 모델 배수(1.2). astra `high`에서 1024×1024 → 1,229토큰 | Gemini 3·4 기본 `media_resolution`에서 이미지당 1,120토큰(`low` 280, `medium` 560) |

- 출처: Claude는 [C5], OpenAI는 [O9][O13], Gemini는 [G8][G9][G10]이다.
- Gemini의 인라인 한도는 문서끼리 다르다. 이미지 문서([G8])는 20MB, 입력 방법 문서([G9], 2026-10-07 갱신)는 100MB(PDF는 50MB)라고 적는다. 캡션용 그림은 수 MB 이하로 줄여 보내면 어느 쪽이든 문제가 없다.
- OpenAI의 해상도별 상세 표에는 `gpt-6-astra`와 GPT-5.x만 있고 `gpt-6-luna`·`gpt-6.1-sol`은 없다(미확인). [O9]
- 기획 시사점: PPT 속 그림이 EMF, WMF, TIFF, SVG면 세 제공자 모두 받는 형식이 아니다. PNG나 JPEG로 바꿔 보내야 한다. 긴 변을 2000px 이하로 줄이면 Claude의 많은 이미지 제한과 토큰 비용을 함께 피한다. [C5]

### 3.4 지연과 비용

**지연**: 세 제공자 모두 첫 토큰 지연과 전체 지연의 **공식 수치가 없다**. 공식 문서가 주는 것은 상대 비교뿐이다.
- Claude의 비교 지연은 Haiku 5.5 "Fastest", Sonnet 5.5 "Fast", Opus 5.5 "Moderate", Fable 5.1 "Slower"다. 실제 지연은 "prompt length, output length, and thinking effort"에 달려 있다고 밝힌다. [C1]
- OpenAI는 낮은 effort가 속도에 유리하고 `none`이 지연이 중요한 작업에 맞다고 한다. 유료 가속 모드도 있다(Fast 2배 가격, 6.1-sol Ultrafast 6배 가격). [O3][O8]
- Gemini는 3.5 Flash-Lite를 "Fastest"로 소개한다. 낮은 `thinking_level`이 비용과 지연을 줄인다고 한다. [G1][G5]
- 생각이 켜져 있으면 글자가 나오기 전에 생각부터 한다. 따라서 체감 첫 토큰 지연에는 생각 시간이 들어간다. 정확한 지연은 구현 단계에서 실제 키로 재야 한다.

**1회 비용 추정**: 입력 5,000 / 20,000토큰, 출력 200토큰, 표준 단가 기준이다. 생각 토큰은 빼고 계산했고, 생각 토큰 1,000개당 추가 비용을 따로 적었다. 같은 한국어 글도 토큰 수는 제공자마다 다르다.

| 모델 | 입력 5천 + 출력 200 | 입력 2만 + 출력 200 | 생각 1,000토큰당 추가 |
|---|---|---|---|
| `claude-haiku-5-5` | $0.0006 | $0.0021 | $0.0005 |
| `claude-sonnet-5-5` | $0.012 | $0.042 | $0.010 |
| `claude-opus-5-5` | $0.024 | $0.084 | $0.020 |
| `gpt-6-luna` | $0.0006 | $0.0021 | $0.0005 |
| `gpt-6.1-sol` | $0.012 | $0.042 | $0.010 |
| `gpt-6-astra` | $0.060 | $0.210 | $0.050 |
| `gemini-3.5-flash-lite` | $0.0020 | $0.0065 | $0.0025 |
| `gemini-3.8-flash` (2026년 단가) | $0.0045 | $0.0158 | $0.0038 |
| `gemini-4-argon` (11월 30일까지 단가) | $0.012 | $0.042 | $0.010 |

- 계산 근거는 [C2][O12][G7]이다. 예: Haiku 5.5는 5,000×$0.10/1M + 200×$0.50/1M = $0.0006이다.
- 같은 슬라이드 근거를 여러 질문에 되풀이해 보내므로 프롬프트 캐시가 입력 비용을 크게 줄인다. 캐시 읽기 단가는 Haiku 5.5 $0.01, gpt-6-luna $0.01, 3.5 Flash-Lite $0.03이다. [C2][O2][G7]
- **캡션 1장**(1000×1000 PNG 기준): Claude 1,296토큰, Gemini 1,120토큰, OpenAI(astra `high` 기준) 약 1,229토큰이다. 기본 모델 단가로 치면 장당 약 $0.0001(Haiku 5.5)~$0.0003(3.5 Flash-Lite)이다(출력 캡션 길이 제외). gpt-6-luna의 이미지 토큰 배수는 미확인이다. [C5][G10][O9]

### 3.5 스트리밍과 문장 단위 읽기

세 제공자 모두 SSE(server-sent events)로 글 조각을 받는 즉시 넘겨준다. 앱이 조각을 모아 문장 끝(`.`, `?`, `!`, `다.` 등)이 나올 때마다 TTS로 넘기면 문장 단위로 읽기를 시작할 수 있다.

| | 켜는 법 | 글 조각 이벤트 |
|---|---|---|
| Claude | 요청 본문 `"stream": true` | `content_block_delta` 안의 `delta.type == "text_delta"`의 `delta.text` |
| OpenAI (Responses) | `"stream": true` | `response.output_text.delta`의 `delta` |
| Gemini (Interactions) | `"stream": true` | `step.delta` 중 `delta.type == "text"`의 `delta.text` |
| Gemini (generateContent) | `…:streamGenerateContent?alt=sse` | 응답 조각마다 `candidates[].content.parts[].text` |

- 출처: Claude는 [C6], OpenAI는 [O10], Gemini는 [G11][G6]이다.
- 생각이 켜진 모델은 글 조각보다 생각 조각이 먼저 온다. Claude는 `thinking_delta` 다음에 `signature_delta`가 온다. 이 조각은 TTS에 넘기지 않도록 이벤트 종류로 거른다. [C4]
- Claude 스트림에는 `ping` 이벤트가 섞여 올 수 있다. [C6]

### 3.6 Python에서 부르기: 공식 SDK와 표준 라이브러리 HTTP

**최소 Python 버전(PyPI 메타데이터, 2026-10-16 조회)** [P1][P2][P3]

| SDK | 최신판 | `requires_python` | 3.9에서 깔리는 마지막 판 | 3.9용 판의 문제 |
|---|---|---|---|---|
| `anthropic` | 1.15.0 | `>=3.10` | 0.125.0 (2026-08-19) | `output_config`, effort, adaptive가 들어 있다(휠 내용 확인). 다만 0.x는 이미 끝난 판이다 |
| `openai` | 3.31.0 | `>=3.10` | 2.48.0 (2026-07-23) | `ReasoningEffort`에 `none`~`max`가 모두 있다(휠 내용 확인). 판 차이가 크다 |
| `google-genai` | 2.31.0 | `>=3.10` | 1.47.0 (2025-10-29) | **`thinking_level`과 Interactions API가 없다**(휠 내용 확인). Gemini 3 이후 모델의 생각 깊이를 SDK로 정할 수 없다 |

**설치 크기와 PyInstaller (직접 측정)**
- 측정 환경: Windows 11, Python 3.14.7, 스크래치 venv, PyInstaller 6.22.3, `--onedir`. 메인 `.venv`는 건드리지 않았다.
- 각 스크립트는 SDK를 import하고 가짜 키로 클라이언트를 만든 뒤 판 번호를 출력한다. 네트워크 호출은 하지 않았다.

| 구성 | 의존성 포함 설치 크기 (`pip install --target`) | PyInstaller onedir 결과 크기 | 빌드한 exe 실행 |
|---|---|---|---|
| 표준 라이브러리만 (`urllib`, `ssl`, `json`) | 0 | 19.3MB | 정상 |
| `anthropic` 1.15.0 | 44MB | 44.5MB | 정상 (`anthropic ok 1.15.0`) |
| `openai` 3.31.0 | 44MB | 44.5MB | 정상 (`openai ok 3.31.0`) |
| `google-genai` 2.31.0 | 54MB | 43.1MB | 정상. `ThinkingConfig(thinking_level="low")` 생성과 `client.interactions` 존재 확인 |
| 세 SDK 모두 | 111MB | 49.7MB | 정상 |

- 의존성 차이: `anthropic`과 `openai`는 `httpx2`, `pydantic`, `jiter`를 쓴다. `google-genai`는 `httpx`(0.28), `requests`, `google-auth`, `cryptography`, `websockets`를 따로 끌어온다. [P1][P2][P3]
- 확인하지 않은 것: macOS에서의 PyInstaller 빌드, 실제 HTTPS 연결(TLS 인증서 처리)은 미확인이다.

**비교**

| 기준 | 공식 SDK | 표준 라이브러리 직접 호출 |
|---|---|---|
| Python 3.9 지원 | 최신판 불가. 옛 판 고정 필요. Gemini는 생각 깊이 설정 불가 | 가능 |
| 실행 파일 크기 | +약 30MB (세 SDK 합계, 측정값) | 거의 0 |
| 구현량 | 적다. 스트리밍 도우미, 자동 재시도(`anthropic`은 기본 2회, `claude-api` 스킬), 타입이 있다 | 요청 3종, SSE 읽기, 오류·재시도를 직접 쓴다. 제공자마다 요청 하나와 이벤트 파서 하나다 |
| 판 변화 위험 | 크다. 2026년에만 큰 판이 셋 나왔다: `google-genai` 2.0.0(05-07), `openai` 3.0.0(08-12), `anthropic` 1.0.0(08-20) | API 형식이 바뀔 때만 영향을 받는다 |
| 인증서 | SDK가 처리한다(`truststore`나 `certifi` 의존) | Windows는 `ssl`이 시스템 저장소를 읽는다. macOS python.org 판은 `Install Certificates.command`로 `certifi`를 깐다고 안내한다. 고정 실행 파일에는 `certifi`(휠 137KB, Python ≥3.7)를 넣어 `cafile`로 지정하는 편이 안전하다 [P5][P6] |

**권고**: 최소 버전 3.9를 유지하는 한 **직접 HTTP**가 맞다. 세 제공자의 요청 모양은 아래와 같고, 모두 `urllib.request`로 보낼 수 있다. 응답을 한 줄씩 읽으면 SSE를 처리할 수 있다.
- Claude
  - `POST https://api.anthropic.com/v1/messages`
  - 헤더: `x-api-key`, `anthropic-version: 2023-06-01`
  - 본문: `model`, `max_tokens`, `system`, `messages`, `output_config.effort`, `stream` [C3][C6]
- OpenAI
  - `POST https://api.openai.com/v1/responses`
  - 헤더: `Authorization: Bearer`
  - 본문: `model`, `instructions`, `input`, `reasoning.effort`, `stream`, `store: false` [O8][O10][O13]
  - `store`는 생략하면 `true`이고, 응답이 최소 30일 저장된다. [O13]
- Gemini
  - `POST https://generativelanguage.googleapis.com/v1beta/interactions`
  - 헤더: `x-goog-api-key`
  - 본문: `model`, `system_instruction`, `input`, `generation_config.thinking_level`, `stream` [G12][G11]
  - Interactions는 기본이 `store=true`(서버에 대화 저장)다. `store=false`로 상태 없이 쓸 수 있다. [G13]
  - Google은 새 개발에 Interactions를 권하지만 "generateContent remains fully supported"라고 밝힌다. [G13]

최소 버전을 3.10 이상으로 올리기로 하면, SDK 쪽이 구현량과 유지보수에서 유리하다. 이 경우 크기 증가(+약 30MB)만 감수하면 된다.

### 3.7 모델 목록 API

| | 엔드포인트 | 주는 정보 | 설정 창에 쓸 만한가 |
|---|---|---|---|
| Claude | `GET /v1/models` (`limit` 1~1000, 기본 20) | `id`, `display_name`, `created_at`, `lifecycle`(active/deprecated/retired), `line`(haiku/sonnet/opus…), `max_input_tokens`, `max_tokens`, `capabilities`(`image_input`, effort 단계별 지원, `thinking.types.disabled` 등) | 좋음. 이미지 입력과 effort 지원으로 걸러 낼 수 있다 |
| OpenAI | `GET /v1/models` | `id`, `created`, `owned_by`, `shutdown_date` | 약함. 기능 필드가 없어 음성·이미지 생성·임베딩 모델까지 섞여 온다. 직접 걸러야 한다 |
| Gemini | `GET /v1beta/models` (`pageSize` 기본 50) | `name`, `baseModelId`, `displayName`, `inputTokenLimit`, `outputTokenLimit`, `supportedGenerationMethods`, `thinking`(bool) | 보통. 이미지 입력 여부와 생각 단계 정보가 없다 |

- 출처: [C7][O11][G14]
- 권고: 설정 창의 모델 목록은 이 문서의 제공자별 3~4개를 **코드에 넣는다**. 목록 API는 두 가지로만 쓴다. 하나는 "키 확인" 버튼으로 키가 맞는지, 코드의 모델이 지금 쓸 수 있는지 확인하는 용도다. 다른 하나는 Claude의 `lifecycle`이나 OpenAI의 `shutdown_date`로 종료 예정 모델을 표시하는 용도다. 새 모델에 대비해 모델 ID 직접 입력란을 둔다. 생각 단계 대응(2절)은 모델마다 달라서 받아 온 목록만으로는 자동으로 정할 수 없기 때문이다.

## 4. 확인하지 못한 것

- 세 제공자 모두 첫 토큰 지연과 전체 지연의 공식 수치가 없다. 실측은 API 키가 없어 하지 않았다.
- `gpt-6-astra`의 기본 effort(문서에 없음). [O4][O8]
- `gpt-6-luna`·`gpt-6.1-sol`의 이미지 해상도 한도와 토큰 배수(이미지 문서 표에 없음). [O9]
- OpenAI의 이미지 장당 MB 한도(문서는 요청 전체 512MB와 패치 한도만 밝힘). [O9]
- Gemini 인라인 데이터 한도가 20MB인지 100MB인지(문서끼리 다름). [G8][G9]
- Gemini generateContent REST에서 `thinkingLevel`을 소문자(`"low"`)로 보내도 되는지. 레퍼런스의 열거값은 대문자(`LOW`)다. [G6]
- Gemini 3.5 Flash-Lite의 `minimal`이 생각을 완전히 끄는지("Little to no thinking"이라고만 적혀 있음). [G6]
- 세 제공자의 토크나이저로 같은 한국어 근거가 각각 몇 토큰이 되는지. 그래서 비용표는 "제공자별 5천~2만 토큰" 가정이다.
- macOS에서의 PyInstaller 빌드와 고정 실행 파일의 실제 HTTPS 연결.
- OpenAI `GET /v1/models`가 키로 쓸 수 있는 모델만 주는지(문서는 "currently available models"라고만 적음). [O11]

## 5. 출처

조회일은 모두 2026-10-16이다.

Claude (Anthropic)
- [C1]: https://platform.claude.com/docs/en/about-claude/models/overview — Models overview
- [C2]: https://platform.claude.com/docs/en/about-claude/pricing — Pricing
- [C3]: https://platform.claude.com/docs/en/build-with-claude/effort — Effort
- [C4]: https://platform.claude.com/docs/en/build-with-claude/thinking — Thinking (모델별 `thinking` 값 표, 끄기, 스트리밍)
- [C5]: https://platform.claude.com/docs/en/build-with-claude/vision — Vision
- [C6]: https://platform.claude.com/docs/en/build-with-claude/streaming — Streaming messages
- [C7]: https://platform.claude.com/docs/en/api/models/list — List Models API
- `claude-api` 스킬(Claude Code 번들, 2026-10-06 캐시): `shared/models.md`, `shared/model-migration.md`의 "Migrating to Claude Haiku 5.5"

OpenAI
- [O1]: https://developers.openai.com/api/docs/models — Models
- [O2]: https://developers.openai.com/api/docs/models/gpt-6-luna
- [O3]: https://developers.openai.com/api/docs/models/gpt-6.1-sol
- [O4]: https://developers.openai.com/api/docs/models/gpt-6-astra
- [O5]: https://developers.openai.com/api/docs/models/gpt-6-sol
- [O6]: https://developers.openai.com/api/docs/models/all — All models
- [O7]: https://developers.openai.com/api/docs/deprecations — Deprecations
- [O8]: https://developers.openai.com/api/docs/guides/reasoning — Reasoning
- [O9]: https://developers.openai.com/api/docs/guides/images-vision — Images and vision
- [O10]: https://developers.openai.com/api/docs/guides/streaming-responses — Streaming API responses
- [O11]: https://developers.openai.com/api/reference/resources/models/methods/list — List models
- [O12]: https://developers.openai.com/api/docs/pricing — Pricing
- [O13]: https://developers.openai.com/api/reference/resources/responses/methods/create — Create a response (`store`, `input_image`)

Gemini (Google AI for Developers)
- [G1]: https://ai.google.dev/gemini-api/docs/models — Models
- [G2]: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- [G3]: https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- [G4]: https://ai.google.dev/gemini-api/docs/models/gemini-4-argon
- [G5]: https://ai.google.dev/gemini-api/docs/thinking — Thinking (모델별 `thinking_level` 표)
- [G6]: https://ai.google.dev/api/generate-content — generateContent API 레퍼런스 (`ThinkingConfig`, `ThinkingLevel`, `streamGenerateContent`)
- [G7]: https://ai.google.dev/gemini-api/docs/pricing — Pricing
- [G8]: https://ai.google.dev/gemini-api/docs/image-understanding — Image understanding
- [G9]: https://ai.google.dev/gemini-api/docs/file-input-methods — File input methods
- [G10]: https://ai.google.dev/gemini-api/docs/media-resolution — Media resolution
- [G11]: https://ai.google.dev/gemini-api/docs/streaming — Streaming interactions
- [G12]: https://ai.google.dev/gemini-api/docs/text-generation — Text generation (Interactions REST, `system_instruction`)
- [G13]: https://ai.google.dev/gemini-api/docs/migrate-to-interactions — Migrating to the Interactions API
- [G14]: https://ai.google.dev/api/models — Models API 레퍼런스
- [G15]: https://ai.google.dev/gemini-api/docs/deprecations — Deprecations
- (참고) https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash

Python과 패키지
- [P1]: https://pypi.org/pypi/anthropic/json — `anthropic` PyPI 메타데이터 (판별 `requires-python`은 https://pypi.org/simple/anthropic/ JSON 색인)
- [P2]: https://pypi.org/pypi/openai/json — `openai` PyPI 메타데이터
- [P3]: https://pypi.org/pypi/google-genai/json — `google-genai` PyPI 메타데이터
- [P4]: https://devguide.python.org/versions/ — Python 판별 지원 종료일
- [P5]: https://docs.python.org/3/using/mac.html — Using Python on macOS (`Install Certificates.command`)
- [P6]: https://pypi.org/pypi/certifi/json, https://pypi.org/pypi/truststore/json — `certifi`(≥3.7), `truststore`(≥3.10)

직접 측정
- SDK 설치 크기, 3.9 호환 마지막 판의 휠 내용, PyInstaller onedir 크기와 실행 결과를 측정했다.
- 스크래치 venv(Windows 11, Python 3.14.7, PyInstaller 6.22.3)에서 2026-10-16에 측정했다.
- 메인 `.venv`와 저장소 코드는 바꾸지 않았다.
