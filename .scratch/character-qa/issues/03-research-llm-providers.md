# 세 LLM 제공자의 현재 모델과 생각 깊이 설정

Type: research
Status: resolved

## Question

Claude(Anthropic), OpenAI, Gemini(Google)에서 **2026년 10월 현재** API로 쓸 수 있는 모델과, 질의응답·캡션 기능을 기획하는 데 필요한 사실은 무엇인가?

1. **모델 목록**: 질의응답에 쓸 만한 모델을 제공자마다 3~5개 고르고, 정확한 API 모델 ID를 적는다. 기본 모델로 권할 것을 하나씩 고른다(빠르고 싼 쪽 기준).
2. **생각 깊이**: reasoning effort / thinking 설정 방식과 허용 값. 세 제공자를 공통 단계 low / mid / high에 어떻게 대응시킬 수 있나. 생각을 끌 수 있나. 모델마다 다르면 표로 적는다.
3. **이미지 입력**(캡션용): 지원 여부, 받는 형식(PNG/JPG/WebP 등), 크기·개수 제한.
4. **지연과 비용**: 근거 5천~2만 토큰에 답 200토큰 정도인 질문 하나의 첫 토큰 지연, 전체 지연, 1회 비용 대략.
5. **스트리밍**: 답을 받는 대로 문장 단위로 읽기 시작할 수 있나.
6. **Python에서 부르기**: 공식 SDK(`anthropic`, `openai`, `google-genai`)를 쓸 때와 표준 라이브러리 HTTP로 직접 부를 때를 비교한다. SDK 설치 크기, PyInstaller 호환, 최소 Python 버전(현재 3.9+).
7. **모델 목록 API**: 키로 사용 가능한 모델 목록을 받아올 수 있나(설정 창 목록을 코드에 박을지 받아올지 정하는 데 쓴다).

Claude 부분은 `claude-api` 스킬을 먼저 읽고 그 내용을 따른다. 나머지는 각 제공자의 공식 문서를 근거로 단다.

## Answer

조사 문서: `research/llm-providers` 브랜치의 `docs/research/llm-providers.md` (커밋 fc5710e). 모델 ID는 2026-10-16 공식 문서에서 그대로 옮겼다. 키가 없어 호출 실험은 하지 않았다.

- **권장 기본 모델**(빠르고 싼 쪽): Claude `claude-haiku-5-5`, OpenAI `gpt-6-luna`, Gemini `gemini-3.5-flash-lite`. 세 모델 모두 이미지 입력과 SSE 스트리밍을 지원한다.
- **목록 후보**:
  - Claude: `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-fable-5-1`
  - OpenAI: `gpt-6.1-sol`, `gpt-6-sol`, `gpt-6-astra`
  - Gemini: `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-4-argon`
- **피할 모델**:
  - 종료 예정: `gpt-5-mini`/`gpt-5-nano` 스냅숏(2026-12-11), `gpt-4o`·`gpt-4.1` 계열(2027-01-14), `gemini-3.1-flash-lite`(2027-05-07)
  - 접근 제한: `gemini-2.5-*`는 예전에 쓴 사용자만 접근할 수 있다.
- **생각 깊이 low/mid/high**: 세 제공자 모두 `"low"`/`"medium"`/`"high"`를 그대로 받는다. 넣는 곳은 Claude `output_config.effort`, OpenAI `reasoning.effort`, Gemini `thinking_level`이다. 후보 12개 모델이 모두 이 세 값을 받는다. 기본값이 모델마다 다르므로 매 요청에 명시한다.
- **생각 끄기**: 일부 모델만 된다(Haiku 5.5 `disabled`, gpt-6-luna `none`, 3.5 Flash-Lite `minimal`). Opus 5.5, gpt-6.1-sol 등은 끌 수 없다.
- **이미지**: 세 제공자 모두 PNG/JPEG/WebP를 받는다. EMF/WMF/TIFF는 PNG로 바꿔야 한다. 개수 한도는 발표 자료 규모보다 훨씬 크다(Claude 600장 등).
- **비용**: 근거 5천~2만 토큰에 답 200토큰인 질문 1회는 생각 토큰을 빼고 약 $0.0006~0.0065다. 생각 토큰은 출력 단가로 따로 붙는다.
- **지연**: 세 제공자 모두 공식 수치가 없다. 직접 재야 한다.
- **스트리밍**: 세 제공자 모두 SSE로 글 조각을 받는 대로 넘겨준다. 그래서 문장 단위로 읽기를 시작할 수 있다. 생각 조각은 이벤트 종류로 걸러 낸다.
- **SDK와 직접 HTTP**:
  - 세 SDK 최신판은 모두 **Python 3.10 이상**을 요구한다. Python 3.9용 google-genai에는 `thinking_level`이 없다.
  - 세 SDK를 다 넣으면 실행 파일이 19.3MB에서 49.7MB로 커진다.
  - 그래서 조사자는 **표준 라이브러리 HTTP 직접 호출**을 권한다. 최소 Python을 3.10으로 올리면 SDK도 쓸 수 있다.
- **모델 목록 API**: 세 제공자 모두 있다. 조사자는 이렇게 권한다: 추천 목록을 코드에 두고, 목록 API는 키 확인과 종료 예정 표시에만 쓰고, 모델 ID 직접 입력을 허용한다.
- 미확인: 실제 지연, Gemini `thinkingLevel` 대소문자, Gemini `minimal`이 생각을 완전히 끄는지, macOS 실행 파일의 HTTPS 인증서.
