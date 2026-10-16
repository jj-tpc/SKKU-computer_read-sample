# LLM을 SDK로 부르나, 직접 HTTP로 부르나

Type: grilling
Status: resolved
Blocked by: 03

## Question

[세 LLM 제공자의 현재 모델과 생각 깊이 설정](03-research-llm-providers.md)의 조사 결과, 세 공식 SDK의 최신판은 모두 Python 3.10 이상을 요구한다. 기존 프로그램의 원칙은 Python 3.9 이상이다. 세 SDK를 다 넣으면 실행 파일이 약 30MB 커진다. 무엇을 택하나?

정할 것:
- 최소 Python 버전을 3.9로 유지하나, 3.10으로 올리나.
- 세 제공자를 공식 SDK로 부르나, 표준 라이브러리 HTTP(SSE 스트리밍 직접 해석)로 부르나, 섞나.
- 세 제공자의 차이(요청 형식, 생각 깊이 필드, 스트리밍 이벤트, 오류)를 감싸는 공통 경계를 어디에 두나.

## Answer

**세 공식 SDK(anthropic, openai, google-genai)로 부른다.** 근거: [세 LLM 제공자의 현재 모델과 생각 깊이 설정](03-research-llm-providers.md).

- **최소 Python 3.10**: 세 SDK, PySide6 6.11 이상, Pillow 최신판, pyobjc 12.1 이상이 모두 3.10 이상을 요구해서, 기존 "3.9 이상"에서 올린다. 실행 파일은 Python 3.14로 빌드한다. 받는 사람은 실행 파일을 쓰므로 Python이 필요 없다.
- **크기**: 세 SDK로 실행 파일이 약 30MB 커진다(조사: 19.3MB → 49.7MB). "의존성이 커지는 것은 감수한다"는 원칙 안이다. SDK가 인증서 묶음(certifi)을 가져오므로, 조사에서 미확인으로 남은 macOS 실행 파일의 HTTPS 인증서 문제도 줄어든다(빌드 때 확인).
- **공통 경계**: LLM 모듈 하나 안에 제공자마다 얇은 어댑터를 둔다. 나머지 프로그램이 아는 것은 아래뿐이다.
  - 넣는 것: 제공자, 모델, 키, 생각 깊이(low/mid/high, 어댑터가 각 제공자의 `"low"`/`"medium"`/`"high"` 자리에 넣는다), 지침, 대화, 근거 글과 그림
  - 받는 것: 답 글 조각의 흐름. 생각 조각은 어댑터에서 걸러 낸다.
  - 오류: 다섯 가지 공통 종류로 바꾼다. 키 문제, 요금·한도, 연결 끊김, 시간 초과, 기타.
- **같은 모듈을 쓰는 곳**: 질의응답, 캡션 만들기(그림 입력), 설정 창의 키 확인과 모델 목록.

## Comments

- 2026-10-16 툴킷이 PySide6(Qt)로 정해졌다([GUI 툴킷 결정](09-grilling-gui-toolkit.md)). 최소 Python 버전을 정할 때 고정할 PySide6 버전이 요구하는 Python 하한도 함께 본다. HTTP와 SSE 스트리밍은 표준 라이브러리, 공식 SDK 말고 QtNetwork로도 부를 수 있다.
- 2026-10-16 [Mac 없이 macOS판을 만들고 확인하는 방법](13-research-mac-without-mac.md)의 결과: pyobjc 12.1 이상, Pillow 12.3, PySide6 6.11 이상이 모두 Python 3.10 이상을 요구한다. Python 3.14로 빌드하면 PySide6는 6.10.1 이상만 깔린다. 그래서 최소 Python을 3.9로 지키기는 사실상 어렵다.
