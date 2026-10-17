# 지도: 캐릭터와 질의응답

## Destination

기존 「PPT 읽어주기」(`ppt_reader`)에 캐릭터(도트 강아지), 원 버튼, 질의응답을 더하는 **구현용 기획서**. 기존 `PROMPT.md`처럼 저장소에 두며, 구현자가 더 물을 것 없이 바로 만들 수 있으면 도착이다. 기획이 끝나면 곧바로 구현에 들어간다.

**도착(2026-10-17)**: 일 20개를 모두 정했고, 기획서를 저장소 루트의 `PROMPT-character-qa.md`로 썼다. 이 문서가 `[보충]`으로 표시한 10곳은 기획 기록에 없던 세부를 채운 것이라 발표자가 훑어본다.

**다시 엶(2026-10-17)**: 1단계 구현 뒤 발표자가 클라우드 음성(ElevenLabs, OpenAI)을 요청해 범위 밖에서 범위 안으로 옮겼다. 일 21, 22를 정해 기획서에 반영했고, 2단계(음성 흐름)에서 함께 만든다.

## Notes

- 분야: Python 데스크톱 앱, Windows 10/11 + macOS 둘 다, 화면 문구는 한국어. 기존 구조는 `README.md`의 "구조" 절과 `PROMPT.md`를 본다.
- 용어: 저장소 루트의 `CONTEXT.md`를 따른다(발표자, 청중, 캐릭터, 질의응답, 원 버튼, 위성 버튼, 질문창, 생각 깊이, 캡션, 개인 지침).
- 디자인의 중심 컨셉은 **오션·코랄**이다. 화면에 보이는 것(원 버튼, 위성 버튼, 말풍선, 설정 창 등)은 이 컨셉에 맞춘다.
- 이 지도는 **기획만** 한다. 티켓마다 결정을 내고, 제품 코드는 짜지 않는다(시제품은 예외, 버려도 되는 코드로).
- 티켓 종류별 스킬: 질문 → `grilling` + `domain-modeling` / 시제품 → `prototype` / 조사 → `research` / LLM 관련 조사에서 Claude 부분 → `claude-api` / 커밋 → `house-style`.
- 조사·시제품 결과물은 `research/<이름>`, `prototype/<이름>` 브랜치에 커밋하고, 티켓의 답에서 그 브랜치와 파일을 가리킨다.
- 바탕이 되는 요구사항은 [목적지와 기본 요구사항 정하기](issues/01-destination-and-requirements.md)에 있다. 티켓을 고르기 전에 한 번 읽는다.

## Decisions so far

- [목적지와 기본 요구사항 정하기](issues/01-destination-and-requirements.md) — 기존 앱을 확장하는 구현용 기획서. 커서를 따라다니는 도트 강아지와 오른쪽 아래 원 버튼만 남기고 기존 창은 없앤다. 발표자가 키보드로 질문하고, Claude·OpenAI·Gemini 중 골라 답한다.
- [슬라이드 속 그림을 LLM에 보여 줄 이미지로 꺼내는 방법](issues/05-research-slide-images.md) — python-pptx + Pillow로 그림을 꺼내고 도표·SmartArt는 글로 읽는 방법이 두 운영체제에서 늘 된다. 슬라이드 전체 렌더는 Windows 연동 중에만 `Slide.Export`로 보충하고, macOS 렌더는 미확인이다.
- [운영체제 음성에서 목소리 신호를 얻는 방법과 배속 한계](issues/04-research-tts-signal-and-speed.md) — Windows는 미리 합성해 크기 곡선과 이벤트를 뽑고 같은 SAPI로 재생하면 출력 장치와 의존성이 그대로다. x5는 Heami만 SAPI XML로 되고, 나머지 음성과 macOS는 시간 늘이기(numpy 등)가 필요하다. 지금 블루투스 무음이 배속만큼 짧아지는 버그도 찾았다.
- [세 LLM 제공자의 현재 모델과 생각 깊이 설정](issues/03-research-llm-providers.md) — 권장 기본 모델은 `claude-haiku-5-5`, `gpt-6-luna`, `gemini-3.5-flash-lite`다. 세 제공자 모두 low/medium/high 생각 깊이, 이미지 입력, SSE 스트리밍을 지원한다. 공식 SDK는 Python 3.10 이상이 필요하다.
- [캐릭터 창과 원 버튼을 어떤 GUI 툴킷으로 만들 수 있나](issues/02-research-gui-toolkit.md) — tkinter 단독으로는 안 되고, Windows ctypes(실측 통과)와 macOS pyobjc를 보태면 된다. PySide6도 macOS에서는 pyobjc가 필요할 가능성이 높고 101MB다. macOS는 미확인이라 구현 첫 단계 Mac 시제품이 조건이다. PowerPoint 쇼는 보조 모니터에 떴다.
- [도트 강아지의 자세와 크기 정하기](issues/06-prototype-dog-sprites.md) — 시바·비숑·비글 세 마리를 64×64로 코드 생성하고 설정에서 고른다. 화면에는 ×2로 그린다. 자세는 엎드림·걷기·앉기·생각 중·말하기·기뻐하기 6개이고, 커서 쪽으로 좌우를 뒤집는다.
- [원 버튼, 위성 버튼, 질문창의 모양과 움직임 정하기](issues/07-prototype-orb-and-satellites.md) — 오션·코랄 컨셉으로 정했다. 원 버튼은 코랄 음파 링이고, 위성 버튼은 4분원 호에 펼친 흰 동그라미다(4초 뒤 접힘, 마우스를 올린 동안은 멈춤). 질문창은 원 버튼 왼쪽의 알약이고 Esc로 닫는다. 말풍선은 산호빛이고 목소리를 따라 낱말이 이어지는 스트림이며, 대본을 읽을 때는 띄우지 않는다. 원 버튼의 모니터는 설정에서 고르고, 생각 깊이 기본값은 low다.
- [GUI 툴킷 결정](issues/09-grilling-gui-toolkit.md) — PySide6(Qt)로 캐릭터, 원 버튼, 설정 창까지 모두 새로 짜고 tkinter와 섞지 않는다. Mac 없이 macOS판을 넘겨야 해서, 확인 못 하는 macOS 전용 코드가 가장 적은 쪽을 골랐다. macOS 보조는 pyobjc 몇 줄이고, macOS판은 받을 사람의 M1 Pro에 맞춰 Apple Silicon용만 만든다.
- [Mac 없이 macOS판을 만들고 확인하는 방법](issues/13-research-mac-without-mac.md) — GitHub Actions `macos-15` 러너(M1)에서 arm64 `.app`을 빌드하고, 그 러너의 화면 세션에서 가짜 전체 화면 위 창을 찍어 확인할 수 있다. 서명 없이 넘기면 받는 사람이 "그래도 열기"와 자동화 허용을 해야 한다. 전체 화면 위에 띄우려면 pyobjc로 NSPanel·`.screenSaver` 레벨까지 바꿔야 하고, 의존성들이 Python 3.10 이상을 요구한다.
- [파동과 강아지 입이 목소리를 따라가는 방식 결정](issues/10-grilling-voice-reactive-motion.md) — 문장마다 미리 합성(Windows SAPI, macOS `say -o`)하고, 그 소리의 크기 곡선으로 파동과 입(닫힘·조금·크게·가로 네 모양)을 움직이며, 재생은 Qt가 고른 장치로 한다. x5는 모든 음성에서 유지하고 모자란 배율은 Qt가 음높이를 지키며 늘인다. macOS 낱말 시각은 어림한다. 새 의존성은 PySide6-Addons 하나다.
- [LLM을 SDK로 부르나, 직접 HTTP로 부르나](issues/12-grilling-llm-client.md) — 세 공식 SDK로 부르고 최소 Python을 3.10으로 올린다(빌드는 3.14). LLM 모듈 안의 제공자별 어댑터가 차이를 감추고, 밖에는 글 조각 흐름과 다섯 가지 공통 오류만 보인다.
- [질의응답 때 LLM에 무엇을 어떻게 넘기나](issues/08-grilling-qa-prompt.md) — 질문마다 자료 전체(본문, 노트, 고친 대본, 캡션)를 장 번호와 함께 넘기고 그림은 보내지 않는다. 개인 지침은 말투와 길이를 바꾸지만 "자료 밖 내용 밝히기"와 말하기 형식은 늘 지킨다. 최근 6번의 질문과 답을 기억하고, 답은 2~4문장의 한국어 말투다.
- [캡션을 언제 만들고 어디에 두나](issues/11-grilling-captions.md) — 설정에서 켜고 끄며 기본값은 꺼짐이다. 켜져 있으면 파일을 열 때 슬라이드마다 그림과 글을 보내 그림 설명을 받고, 그림 해시로 설정 폴더에 저장한다. 대본 창에서 고칠 수 있고, 질의응답 근거에만 쓴다. 파일당 그림 40개, 긴 변 1024px, 생각 깊이 low.
- [강아지가 커서를 따라다니는 방식 정하기](issues/14-grilling-cursor-follow.md) — 시제품처럼 커서 오른쪽 아래를 따라가되 원 버튼이 있는 모니터에만 있고, 커서가 떠나거나 원 버튼 묶음 위에 있으면 원 버튼 옆에 앉아 기다린다. 질의응답 중에는 머물고 대본 읽기 중에는 따라간다. 가장자리에서는 반대쪽으로 가며, 늘 보이되 설정에서 끌 수 있다.
- [오류가 났을 때 캐릭터의 반응 정하기](issues/18-grilling-error-reactions.md) — 강아지는 청중용 짧은 말을 하고(말하기 자세 + 땀방울), 원 버튼 옆 알림 줄이 원인과 할 일을 6초 띄운다. 시간 초과는 첫 글자까지 low 45·mid 90·high 150초이고, 오류가 나면 질문을 질문창에 다시 채운다. 질의응답 밖 오류는 주로 설정 창에 알린다.
- [설정 창 구성 정하기](issues/15-prototype-settings-window.md) — 준비 체크리스트 안(B)으로 정했다. 설정 창은 "발표 준비 n/4"와 접히는 카드 네 장(발표 자료, 목소리, 질의응답, 캐릭터와 화면)이다. 대본은 발표 자료 카드의 [대본 열기]로 여는 대본 창에서 고친다. 바꾸면 바로 저장하고, 처음 켜면 설정 창이 저절로 열린다. 위성 버튼은 다섯 개 그대로다.
- [Qt로 바꾼 뒤의 프로그램 구조 정하기](issues/16-grilling-program-structure.md) — `slides`·`link`는 살리고 `tts`는 `voice/`(합성·신호·재생·문장 줄)로 나누며, `llm/`, `qa`, `captions`, `settings`를 화면과 떼어 두고 Qt 화면은 `ui/`에만 둔다. 일하는 스레드는 Qt 신호로 알린다. 설정·캡션·고친 대본은 운영체제 표준 앱 폴더에 두고, 켜면 강아지와 원 버튼만 뜬다.
- [실행 파일 빌드와 넘기기 정하기](issues/17-grilling-build-and-handoff.md) — PySide6 6.11.x와 Python 3.14로 고정하고, 받는 Mac은 macOS 15 이상이다. 저장소를 공개로 바꿔 GitHub Actions 무료 러너에서 Windows판과 macOS판을 손으로 눌러 빌드한다. 빌드 서버에서 `--self-check`, 서명·arm64 검사, 전체 화면 위 화면 찍기를 한다. zip 꾸러미에 안내문과 받는 사람 확인표, `licenses/`를 넣는다.
- [시험 방법 정하기](issues/19-grilling-test-plan.md) — 화면·인터넷·소리 없이 도는 pytest로 `qa`, `llm`, `voice`, `captions`, `settings`, 따라가기 계산, 오류 시계를 덮는다. 상태 묶음은 Qt를 모르는 `session.py`로 빼서 기존 화면 테스트를 옮기고, Qt는 pytest-qt로 몇 개만 본다. 실제 LLM 시험은 키가 있을 때만 돌고, 사람이 확인할 목록은 기획서 부록에 둔다.
- [기획서의 위치와 목차 정하기](issues/20-grilling-spec-outline.md) — 루트의 `PROMPT-character-qa.md` 한 파일에 `PROMPT.md` 형식의 확장 프롬프트로 쓴다(`PROMPT.md`는 고치지 않음). 조사 문서는 `docs/research/`로 옮기고 시제품은 브랜치@커밋으로 가리킨다. `.scratch/`와 `CONTEXT.md`도 함께 커밋한다. 구현은 macOS 빌드 길을 먼저 뚫는 뼈대부터 여섯 단계로 간다.
- [클라우드 음성 API 조사](issues/22-research-cloud-tts.md) — "gpt-live"는 대화 전용 GPT-Live였고, OpenAI 음성 합성 모델은 2027-01-06에 종료된다. ElevenLabs는 22050Hz PCM과 글자 시각을 줘서 지금 구조에 맞고, Gemini TTS는 한국어와 무료 등급이 있으나 시각·속도가 없다.
- [클라우드 음성을 목소리 엔진으로 넣기](issues/21-grilling-cloud-voice.md) — 운영체제 음성, ElevenLabs, Gemini 중 하나를 골라 대본과 답에 함께 쓴다. x1로 한 번 합성해 `voice_cache/`에 저장하고 배속은 재생 때 늘이며, 파일을 열면 대본을 미리 합성한다. 실패하면 운영체제 음성으로 이어 읽는다. Gemini 키는 질의응답과 함께 쓴다.

## Not yet specified

(없음 — 남은 흐린 부분은 모두 일로 만들었다.)

## Out of scope

- 마이크로 질문 받기 — 질문은 발표자가 키보드로 입력하기로 했다.
- OpenAI 음성(GPT-Live, Realtime 모델, `gpt-4o-mini-tts`) — GPT-Live는 대화 전용이고, 음성 합성 모델은 2027-01-06에 종료되며, 대체 Realtime 모델은 대본을 그대로 읽는다는 보장이 없다. Gemini 음성으로 대신했다([클라우드 음성을 목소리 엔진으로 넣기](issues/21-grilling-cloud-voice.md)).
- 질의응답 자동 시작, 발표 중간 질문 — 발표자가 버튼으로 시작하는 것으로 충분하다고 했다.
- 기능별로 다른 LLM 쓰기, 실패 시 다른 제공자로 자동 전환 — 설정에서 하나를 골라 모두에 쓴다.
- 키를 숨기는 학교 서버, 운영체제 보관함(키체인) 저장 — 키는 설정 파일에 저장한다.
- 도표 값과 SmartArt 글을 꺼내 대본·근거에 넣기, 꺼내지 못한 그림이 있는 슬라이드를 통째 그림으로 보충하기 — 발표자가 지금은 하지 않기로 했다([캡션을 언제 만들고 어디에 두나](issues/11-grilling-captions.md)).
