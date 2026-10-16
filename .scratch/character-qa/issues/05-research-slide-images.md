# 슬라이드 속 그림을 LLM에 보여 줄 이미지로 꺼내는 방법

Type: research
Status: resolved

## Question

캡션을 만들려면 슬라이드 속 그림을 LLM에 이미지로 보여 줘야 한다. `.pptx`에서 어떤 방법으로 이미지를 얻을 수 있나?

1. **그림 개체**: python-pptx로 그림(picture)의 원본 바이트를 꺼내는 방법. 지원 형식(PNG/JPG/GIF/EMF/WMF/SVG), 그룹 안 그림, 자리표시자 그림, 배경 그림, 잘라내기(crop)된 그림.
2. **이미지가 아닌 시각 요소**: 도표(chart), SmartArt, 도형 그림. python-pptx로 도표의 데이터(계열, 값)를 글로 꺼낼 수 있나.
3. **슬라이드 전체를 그림으로**: Windows PowerPoint COM(`Slide.Export`), macOS PowerPoint AppleScript(그림으로 저장), PowerPoint가 없을 때의 방법(LibreOffice 등)과 각각의 속도.
4. **형식 변환**: EMF/WMF처럼 LLM이 받지 않는 형식을 PNG로 바꾸는 방법(Pillow 등)과 운영체제별 지원, 의존성.
5. **규모**: 30장에 그림 50개 정도인 발표 자료에서 꺼내기와 변환에 걸리는 시간 대략.

`ppt_reader/slides.py`와 `ppt_reader/link.py`를 먼저 읽고 현재 구현을 기준으로 조사한다.

## Answer

조사 문서: `research/slide-images` 브랜치의 `docs/research/slide-images.md` (커밋 b1e2324)

- **늘 되는 방법(두 운영체제 공통)**: python-pptx로 그림 부분의 바이트를 꺼내고, Pillow로 잘라내기를 적용한 뒤 긴 변 1568px 이하의 PNG/JPEG로 바꾼다.
  - 그룹 안 그림과 그림 자리표시자도 된다. 자리표시자는 `isinstance(sh, Picture)`로 골라야 한다.
  - 배경 그림과 그림으로 채운 도형은 XML을 직접 읽는다.
  - Pillow는 이미 python-pptx의 의존성이라 새 패키지가 필요 없다.
- **도표와 SmartArt는 그림 대신 글로 꺼낸다.**
  - 도표: 계열·항목·값을 읽는다. python-pptx가 모르는 종류는 XML 캐시에서 읽는다.
  - SmartArt: data 부분에서 글을 읽는다.
  - 캡션보다 정확하고 LLM 호출이 필요 없다. 지금 `slides.py`의 대본에도 둘 다 빠져 있다.
- **이 방법으로 그림을 못 얻는 것**:
  - 대체 PNG가 없는 SVG
  - 연결만 된 그림
  - macOS의 EMF/WMF. Pillow는 Windows에서만 그린다.
  - `mc:AlternateContent` 개체
  - 도형을 모아 그린 그림
  - 이런 슬라이드는 "렌더 필요"로 표시한다.
- **EMF 주의**: python-pptx가 EMF를 `image/x-wmf`로 잘못 알려 준다. 형식은 그림 부분의 content_type으로 판별한다.
- **Windows에서 연동 중일 때만**: `Slide.Export(…, "PNG", 1280, 720)`로 슬라이드를 화면 그대로 내보낸다. 장당 0.11~0.15초, 30장에 4~4.6초가 걸렸다.
  - PowerPoint가 꺼져 있을 때 숨겨 띄우면 시작에 약 3초가 더 든다.
  - 발표자의 PowerPoint와 한 프로세스를 같이 써서 위험하다. 선택 기능으로만 둔다.
- **macOS AppleScript 렌더와 LibreOffice**: 둘 다 미확인이다. 1차 문서가 없고, 이 PC에 설치돼 있지 않다.
- **규모**: 30장에 그림 50개인 최악 사례에서 열기 0.5초, 변환 5~7초였다. 보통 자료(19장, 그림 11개)는 0.23초였다.
- **권하는 조합**: 기본은 python-pptx + Pillow(그림, 도표 값, SmartArt 글)다. 그림을 못 얻은 슬라이드만 Windows 연동 중일 때 `Slide.Export`로 보충한다. macOS나 연동하지 않는 경우에는 그 슬라이드의 캡션을 건너뛴다.
- 미확인: 쇼 진행 중 `Slide.Export`가 쇼에 주는 영향, 마스터에서 물려받은 배경 그림, 새 도표 종류 실물 확인.
