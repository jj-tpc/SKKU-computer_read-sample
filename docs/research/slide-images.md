# 슬라이드 속 그림을 LLM에 보여 줄 이미지로 꺼내는 방법

조사일: 2026-10-16 · 티켓: `05-research-slide-images` · 용어는 [CONTEXT.md](../../CONTEXT.md)를 따른다.

## 결론 요약

- **PowerPoint 연동과 상관없이 늘 되는 방법(Windows, macOS 공통)**: python-pptx로 그림 부분(part)의 원본 바이트를 꺼내고, Pillow로 잘라내기(crop)를 적용한 뒤 긴 변 1568px 이하의 PNG/JPEG로 바꾼다. 그룹 안 그림, 그림 자리표시자는 API로 되고, 배경 그림과 그림으로 채운 도형은 XML을 직접 읽으면 된다. Pillow는 이미 python-pptx의 의존성이라 새 패키지가 필요 없다.
- **도표와 SmartArt는 그림 대신 글로 꺼낸다**: 도표는 계열 이름·항목·값이 파일 안에 캐시돼 있어 python-pptx(지원하지 않는 종류는 XML)로 그대로 읽힌다. SmartArt는 data 부분의 글자를 읽는다. 캡션보다 정확하고 LLM 호출도 필요 없다.
- **이 방법으로 그림을 못 얻는 것**: 대체 PNG가 없는 SVG(이 PC의 PowerPoint로 넣은 SVG가 그랬다), 연결만 된 그림, macOS의 EMF/WMF(Pillow가 Windows에서만 그린다), `mc:AlternateContent`로 싼 개체, 도형을 모아 그린 그림.
- **연동 중일 때만 되는 방법(Windows)**: 열려 있는 프레젠테이션에 `Slide.Export`를 불러 슬라이드 전체를 PNG로 받는다. 1280×720 기준 장당 약 0.11~0.15초(30장 4.0~4.6초)였고, 도표·SmartArt·SVG·EMF가 화면 그대로 나온다. PowerPoint가 꺼져 있으면 숨겨 띄워도 되지만, 시작에 2.4~2.8초가 더 들고 발표자의 PowerPoint와 한 프로세스를 같이 쓴다(시험 중 실제로 부딪혔다).
- **macOS의 슬라이드 전체 그림**: PowerPoint AppleScript로 PNG를 저장하는 1차 문서를 찾지 못했다. 포럼에는 그 명령이 아무것도 만들지 않는다는 보고가 있다. 미확인이다. LibreOffice도 이 PC에 없어 실행하지 못했다(미확인).
- **규모**: 30장·그림 50개(81.6MB, 압축이 잘 안 되는 최악 사례)에서 python-pptx로 열기 0.46~0.51초, 그림 50개 변환 5.0~7.2초였다. 대부분 4032×3024 JPEG 10개를 줄이는 데 들었다. 실제 Office 서식(19장, 그림 11개)은 열기와 변환을 합쳐 0.23초였다.
- **권하는 조합**: 기본은 python-pptx와 Pillow(그림 하나하나 + 도표 데이터 글 + SmartArt 글)다. 위 방법으로 못 얻은 시각 요소가 있는 슬라이드만 "렌더 필요"로 표시한다. Windows에서 연동 중이면 그 슬라이드만 `Slide.Export`로 보충한다. macOS와 연동하지 않는 경우에는 그 슬라이드의 캡션을 건너뛴다.

## 시험 환경과 시험 파일

| 항목 | 값 |
|---|---|
| OS | Windows 11 Pro 10.0.26200 (macOS는 실행하지 못함) |
| Python / 패키지 | Python 3.14.7, python-pptx 1.0.2, Pillow 12.3.0, pywin32 312 (저장소 `.venv`) |
| PowerPoint | Microsoft 365 PowerPoint 16.0 build 20430, 한국어 UI |
| LibreOffice | 설치돼 있지 않음 |

시험 파일은 스크래치 폴더에 만들었고 저장소에는 넣지 않았다.

| 파일 | 만든 방법 | 내용 |
|---|---|---|
| `fixture_basic.pptx` (8장) | python-pptx | PNG, 잘라낸 JPEG, 2단 그룹 안 GIF·BMP·TIFF, 그림 자리표시자, 막대·분산형 도표, 배경 그림, 그림 채우기 타원, 연결 그림 |
| `fixture_com.pptx` (16장) | 위 파일 + PowerPoint COM | SVG·EMF·WMF 그림, Office 서식 `Pitchbook.potx`의 슬라이드 6장(SmartArt 2, 도표 5, 표 2) |
| `template_training.pptx` (19장) | Office 서식 `Training.potx`를 COM으로 저장 | 그림 11개(서로 다른 그림 8개), SmartArt 1, 도표 1 |
| `scale_30_50.pptx` (30장, 81.6MB) | python-pptx + Pillow | JPEG 1600×1200 15개, JPEG 4032×3024 10개, PNG 1280×800 20개, GIF 3, BMP 2, 도표 3. 잡음을 넣어 압축이 잘 안 되게 만든 최악 사례 |
| `sample/sample_presentation.pptx` | 저장소 예제 | 그림이 없다. 숨긴 슬라이드(4번) 내보내기 확인에만 썼다 |

PowerPoint COM 시험은 PowerPoint가 꺼져 있을 때만 시작했다. 시험 파일만 읽기 전용, 창 없이(`WithWindow=False`) 열고 닫았다. 끝날 때 열린 문서가 하나도 없을 때만 `Quit`했다.

## 1. 현재 구현에서 출발점

- `ppt_reader/slides.py`의 `load_deck`은 슬라이드마다 `_in_reading_order(s.shapes)`를 돌며 `_shape_texts`로 글만 모은다. 그룹은 재귀로 들어가고 표는 셀 글을 읽는다. 그림, 도표, SmartArt는 모두 `[]`로 버린다. 그래서 SmartArt의 글과 도표의 값은 지금 **대본에도 들어가지 않는다**.
- `ppt_reader/link.py`의 `_WinPowerPoint`는 `GetActiveObject("PowerPoint.Application")`로 실행 중인 PowerPoint에 붙고, 객체를 붙잡지 않고 매번 새로 얻는다. 바쁠 때 오는 `com_error`와 `AttributeError`는 무시하고 다음 확인으로 넘어간다. `win.Presentation`에서 `Slides(n)`으로 가는 경로가 이미 있으므로 `Slide.Export`를 더하기 쉽다. 다만 COM 개체는 이 스레드(`ppt-link`)에서만 써야 한다.
- `_MacPowerPoint`는 `osascript`로 쇼 상태를 읽고 슬라이드를 넘긴다. 슬라이드를 그림으로 내보내는 AppleScript는 아직 없다.

## 2. 그림 개체: python-pptx로 원본 바이트 꺼내기

### 2.1 꺼내는 코드(실행한 것)

```python
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.shapes.picture import Picture

def walk(shapes):
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from walk(sh.shapes)      # 그룹 안의 그룹까지
        else:
            yield sh

prs = Presentation(path)
for no, slide in enumerate(prs.slides, start=1):
    for sh in walk(slide.shapes):
        if not isinstance(sh, Picture):     # shape_type == PICTURE로 거르면 자리표시자 그림을 놓친다
            continue
        rid = sh._element.blip_rId          # r:embed. 없으면 None(연결 그림, 대체 그림 없는 SVG)
        if rid is None:
            continue
        part = sh.part.related_part(rid)
        blob, ctype = part.blob, part.content_type   # Image.content_type 말고 part의 것을 쓴다(2.3 참고)
        crop = (sh.crop_left, sh.crop_top, sh.crop_right, sh.crop_bottom)
```

`Picture.image`는 슬라이드 부분에서 `blip_rId`의 관계를 따라가 그림 부분을 돌려준다. `r:embed`가 없으면 `ValueError("no embedded image")`를 낸다([picture.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/shapes/picture.py), [oxml/shapes/picture.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/oxml/shapes/picture.py)).

### 2.2 형식과 위치별 결과(실측, `fixture_com.pptx`)

| 대상 | python-pptx에서 보인 모습 | 그림 얻기 |
|---|---|---|
| PNG, JPEG, GIF, BMP, TIFF | `Picture`. `part.content_type`이 각각 `image/png`·`image/jpeg`·`image/gif`·`image/bmp`·`image/tiff` | 됨 |
| 2단 그룹 안 그림 | `GroupShape.shapes`를 재귀로 돌면 셋 다 찾음 | 됨 |
| 그림 자리표시자 | 클래스는 `PlaceholderPicture`, `shape_type`은 `PLACEHOLDER (14)` | 됨. `isinstance(sh, Picture)`로 골라야 한다 |
| 잘라낸 그림 | 바이트는 **원본 전체**(1600×900). `crop_left=0.25, crop_top=0.2, crop_right=0.1, crop_bottom=0.05` | 됨. 잘라내기는 직접 적용한다(2.4) |
| 배경 그림 | `slide.background.fill`은 종류만 알려 주고 그림 API가 없다 | XML로 됨(2.5) |
| 그림으로 채운 도형 | 그림 API 없음 | XML로 됨(2.5) |
| 연결(link)만 된 그림 | `image`가 `ValueError: no embedded image`. 파일 안에 바이트가 없다 | 안 됨. PowerPoint 렌더도 "그림을 표시할 수 없습니다."로 나왔다 |
| EMF | 바이트 정상, `part.content_type`은 `image/x-emf`. 그런데 `Image.ext='wmf'`, `Image.content_type='image/x-wmf'`, `size=(8001, 4501)` | 바이트는 됨. 변환은 Windows만(5장) |
| WMF | 정상(`image/x-wmf`, 960×540) | 바이트는 됨. 변환은 Windows만 |
| SVG(이 PC의 PowerPoint `Shapes.AddPicture`로 넣음) | `a:blip`에 `r:embed`가 **없고** `asvg:svgBlip r:embed`만 있다. `image`가 `ValueError` | SVG 바이트만 XML로 됨(2.6). 그림으로 바꾸려면 렌더가 필요하다 |
| 동영상(`Movie`) | `Picture`가 아니다. `poster_frame`으로 표지 그림을 준다(소스 확인, 미실행) | 표지만 |

같은 그림이 여러 슬라이드에 다시 쓰이면 같은 부분을 가리킨다. `template_training.pptx`에서는 그림 11개가 서로 다른 그림 8개였다(`image6.png`를 3장, `image13.jpeg`를 2장에서 씀). `part.partname`과 잘라내기 값으로 중복을 지우면 캡션을 다시 만들지 않아도 된다.

슬라이드 레이아웃이나 마스터에 있는 그림(회사 로고 같은 것)은 `slide.shapes`에 나오지 않는다. 캡션 대상이 아니라고 보고 이번에는 다루지 않았다.

### 2.3 EMF가 WMF로 잘못 표시되는 문제

python-pptx의 `Image.ext`는 Pillow가 알려 준 형식 이름을 `ext_map`(`BMP, GIF, JPEG, PNG, TIFF, WMF`)으로 바꾼다([parts/image.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/parts/image.py)). Pillow는 EMF와 WMF를 같은 `WmfStubImageFile`(`format = "WMF"`)로 읽는다([WmfImagePlugin.py](https://github.com/python-pillow/Pillow/blob/main/src/PIL/WmfImagePlugin.py)). 그래서 EMF도 `ext='wmf'`, `content_type='image/x-wmf'`로 나온다(실측). 형식은 **그림 부분의 `content_type`**(`image/x-emf`)으로 판별해야 한다. 이 맵에 없는 형식이면 `Image.ext`와 `Image.content_type`이 `ValueError`를 낸다. 바이트(`blob`)는 Pillow를 거치지 않아 늘 읽힌다.

### 2.4 잘라내기(crop) 적용

`crop_*` 값은 원본 그림 크기에 대한 비율이다. 1.0이 100%이고, 음수는 그림 바깥으로 넓힌 것이다([python-pptx Picture 문서](https://python-pptx.readthedocs.io/en/latest/api/shapes.html#pptx.shapes.picture.Picture.crop_left)). 실제 서식 파일(`template_training.pptx` 13번)에도 음수 값이 있었다. 음수는 0으로 보고 자르면 된다.

```python
l, t, r, b = (max(0.0, c) for c in crop)
w, h = im.size
im = im.crop((round(w * l), round(h * t), round(w * (1 - r)), round(h * (1 - b))))
```

실측: 1600×900 JPEG → 1040×675, 27ms. 그림 자리표시자에 `insert_picture`로 넣은 그림도 자동으로 잘려 있었다(`crop_left=crop_right=0.125`).

### 2.5 배경 그림과 그림으로 채운 도형(XML)

```python
from lxml import etree
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
xp = lambda elm, q: etree._Element.xpath(elm, q, namespaces=NS)

bg = xp(slide._element, "./p:cSld/p:bg/p:bgPr/a:blipFill/a:blip/@r:embed")   # 배경 그림
fill = xp(shape._element, "./p:spPr/a:blipFill/a:blip/@r:embed")             # 그림 채우기 도형
part = slide.part.related_part(bg[0])
```

python-pptx의 `BaseOxmlElement.xpath`는 자기 네임스페이스 표만 쓴다. 그래서 `mc`, `asvg`, `dgm` 접두어가 있으면 `Undefined namespace prefix`가 난다(실측). 위처럼 `lxml`의 `xpath`를 직접 부르면 된다. 배경이 마스터나 레이아웃에서 물려받은 것이면 슬라이드 XML에는 `p:bg`가 없다. 시험 파일은 슬라이드에 직접 넣은 경우만 확인했다.

### 2.6 SVG

Office는 SVG를 `a:blip/a:extLst` 안의 `asvg:svgBlip` 요소(`r:embed`)로 저장한다. 이 요소는 Office 2019 이상에서 쓴다([Open XML SDK SVGBlip](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.office2019.drawing.svg.svgblip?view=openxml-3.0.1)). 이 PC에서 창 없이 `AddPicture`로 넣은 SVG는 바깥 `a:blip`에 `r:embed`가 없었다. 그래서 python-pptx가 줄 수 있는 대체 PNG가 없었다. 다른 PowerPoint 버전이나 화면에서 넣은 SVG에 대체 PNG가 붙는지는 확인하지 못했다(미확인). 대체 PNG가 없으면 `asvg:svgBlip/@r:embed`로 SVG 원문(`image/svg+xml`)만 얻는다. Pillow는 SVG를 읽지 못하므로(형식 목록에 없음) 그림으로 바꾸려면 슬라이드 렌더(4장)를 쓴다.

## 3. 그림이 아닌 시각 요소

### 3.1 도표: 데이터를 글로 꺼낼 수 있다

`GraphicFrame.has_chart`가 참이면 `chart.plots[*].categories`, `plot.series[*].name`, `.values`, `chart.chart_title`로 읽힌다. 실측 결과는 다음과 같다.

```
막대(python-pptx로 만듦): COLUMN_CLUSTERED, title '학기별 점수',
  categories ['1학기','2학기','3학기'], 수학 [80.0, 90.0, 85.5], 국어 [70.0, 85.0, None]
분산형: XY_SCATTER, values(Y) [45.0, 52.0, 63.0]  ← X값은 API에 없어 XML c:xVal에서 ['150','160','170']
Office 서식 막대: categories ['1분기'..'4분기'], 매출총이익 [7720.0, 8896.0, 8221.0, 8751.0], 순수익 [...]
Office 서식 꺾은선(Training): categories ['새 직원','1년','2년','3년'], Series 1 [2.0, 3.0, 5.0, 8.0]
Office 서식 3차원 원형: chart.chart_type → ValueError: unsupported plot type ...pie3DChart
```

python-pptx는 `area, area3D, bar, bubble, doughnut, line, pie, radar, scatter`만 안다([chart/plot.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/chart/plot.py) `PlotFactory`). 그 밖의 종류(`pie3DChart`, `bar3DChart`, `line3DChart`, `stockChart`, `surfaceChart` 등)는 `chart_type`부터 `ValueError`를 낸다. 하지만 값은 같은 XML 캐시에 있으므로 다음처럼 읽으면 종류와 상관없이 된다(실측: 3차원 원형에서 `['1분기'..]`, `['8215','10153','9175','9292']`).

```python
cs = chart._chartSpace
for ser in xp(cs, ".//c:ser"):       # NS에 c = http://schemas.openxmlformats.org/drawingml/2006/chart
    name = "".join(xp(ser, "./c:tx//c:v/text()"))
    cats = xp(ser, "./c:cat//c:pt/c:v/text()") or xp(ser, "./c:xVal//c:pt/c:v/text()")
    vals = xp(ser, "./c:val//c:pt/c:v/text()") or xp(ser, "./c:yVal//c:pt/c:v/text()")
```

캐시 값은 도표를 마지막으로 저장할 때의 값이다. 도표를 그림으로 캡션하는 것보다 숫자가 정확하고 LLM 호출이 필요 없다. 질의응답의 근거로는 이 글이 더 낫다고 본다.

### 3.2 SmartArt: 글은 꺼낼 수 있다

SmartArt는 `graphicData@uri`가 `.../drawingml/2006/diagram`인 `GraphicFrame`이다. python-pptx의 `shape_type`은 `None`이다(소스 주석에 "for example when the shape contains SmartArt", [graphfrm.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/shapes/graphfrm.py)). `dgm:relIds`의 `r:dm`이 Diagram Data 부분을 가리킨다([Open XML SDK RelationshipIds](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.diagrams.relationshipids?view=openxml-3.0.1)). 그 부분의 `a:t`를 모으면 글이 나온다.

```python
dm = xp(sh._element, ".//dgm:relIds/@r:dm")   # dgm = http://schemas.openxmlformats.org/drawingml/2006/diagram
root = etree.fromstring(sh.part.related_part(dm[0]).blob)
texts = [t for t in xp(root, "//a:t/text()") if t.strip()]
```

실측(Office 서식 3개)은 다음과 같다.

- 조직도: `['Contoso','제품 개발','디자인','품질 보증','인사','본사','자회사','제조','재무']`
- 순환형: `['운영','지원','최적화','변경']`
- Training 서식: `['1','2','새 환경 탐색','3','새 동료 만나기','새 업무에 익숙해지기']`

XML 순서는 화면에서 읽는 순서와 다를 수 있다(마지막 예). 관계(누가 누구의 하위인지)는 data 부분의 `dgm:cxn`에 있으나 이번에는 풀지 않았다.

### 3.3 python-pptx가 아예 보지 못하는 개체

python-pptx는 `p:spTree`의 자식 가운데 `p:sp, p:grpSp, p:graphicFrame, p:cxnSp, p:pic, p:contentPart`만 도형으로 돌린다([oxml/shapes/groupshape.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/oxml/shapes/groupshape.py) `_shape_tags`). 그래서 `mc:AlternateContent`로 싼 개체는 건너뛴다. Office 2016 이후의 새 도표(폭포, 히스토그램 등)를 시험 파일에 넣으려 했으나 창 없는 PowerPoint에서 `Shapes.AddChart2(-1, 119, ...)`가 `E_FAIL`로 실패했다. 실물로는 확인하지 못했다(미확인). 이런 개체가 있는지는 `xp(slide._element, "./p:cSld/p:spTree/mc:AlternateContent")`로 셀 수 있다.

### 3.4 도형으로 그린 그림

화살표, 자유형, 글상자를 모아 만든 도식은 그림 바이트가 없다. 글은 지금 `slides.py`처럼 꺼낼 수 있지만, 모양과 배치는 슬라이드 렌더로만 볼 수 있다.

## 4. 슬라이드 전체를 그림으로

### 4.1 Windows: PowerPoint COM `Slide.Export`

- 문서: `Slide.Export(FileName, FilterName, ScaleWidth, ScaleHeight)`. 필터는 레지스트리에 등록된 확장자나 필터 이름이고, 크기는 픽셀이다. 내보내도 `Saved`가 바뀌지 않는다. 다운로드가 끝나지 않은 슬라이드면 실패한다([Slide.Export](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.slide.export)).
- 한꺼번에: `Presentation.Export(Path, FilterName, ScaleWidth, ScaleHeight)`([문서](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.presentation.export)), `Presentation.SaveAs(path, ppSaveAsPNG=18)`([PpSaveAsFileType](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.ppsaveasfiletype)).
- 시험 파일 열기: `Presentations.Open(FileName, ReadOnly=msoTrue, Untitled=msoFalse, WithWindow=msoFalse)`([문서](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.presentations.open)).

```python
app = win32com.client.Dispatch("PowerPoint.Application")      # 연동 중이면 GetActiveObject로 이미 얻은 것
pres = app.Presentations.Open(path, True, False, False)       # 읽기 전용, 창 없이
pres.Slides(i).Export(out_png, "PNG", 1280, 720)
pres.Close()
if app.Presentations.Count == 0:                              # 다른 문서가 열려 있으면 끄지 않는다
    app.Quit()
```

실측(장당 시간은 전체 ÷ 장 수). "처음"은 파일을 연 뒤 처음 내보낸 것이고 "다시"는 같은 파일을 한 번 더 내보낸 것이다.

| 작업 | 시간 |
|---|---|
| 꺼진 PowerPoint 시작(`Dispatch`) | 2.37~2.80초 |
| `scale_30_50.pptx`(81.6MB) 창 없이 열기 | 0.78~1.07초 |
| `template_training.pptx`(1.2MB) 열기 / `fixture_com.pptx`(2.3MB) 열기 | 0.39초 / 0.36초 |
| 30장 PNG 1280×720 (처음) | 4.02~4.58초 (장당 134~153ms) |
| 30장 PNG 1568×882 (처음) | 5.30초 (장당 177ms) |
| 30장 PNG 1920×1080 (다시) | 4.18초 (장당 139ms) |
| 30장 PNG 640×360 (다시) | 1.22초 (장당 41ms) |
| Training 19장 PNG 1280×720 (처음 / 다시) | 2.27초 / 2.10초 (장당 110~119ms) |
| Training 19장 PNG 1568×882 | 2.81초 (장당 148ms) |
| SmartArt 슬라이드 1장 1280×720 | 175ms |
| `fixture_com.pptx` 16장(도표 5, SmartArt 2, SVG·EMF) 1280×720 | 6.17초 (장당 385ms) |
| 크기를 주지 않았을 때 | 1280×720(13.333in × 96dpi) 1장 90~116ms |
| `Presentation.Export` 30장 1280×720 | 3.65초 |
| `SaveAs(..., ppSaveAsPNG)` 30장 | 1.98초, 1280×720 |

확인한 점은 다음과 같다.

- 도표, SmartArt, SVG, EMF, WMF가 모두 화면과 같이 그려졌다. 숨긴 슬라이드(예제 4번)도 내보내졌다.
- `Presentation.Export`와 `SaveAs`의 파일 이름은 UI 언어를 따라 `슬라이드1.PNG`, `슬라이드10.PNG`…였다. 문서도 이름은 PowerPoint가 정한다고 한다. 장 번호와 파일을 맞추려면 `Slide.Export`에 이름을 직접 주는 편이 안전하다.
- `SaveAs`는 가장 빨랐지만 열린 문서의 저장 동작이다. 발표자가 열어 둔 문서에 쓰는 것은 피하고, `Saved`를 바꾸지 않는다고 문서에 적힌 `Export` 계열을 쓴다.
- 문서에 없는 `Shape.Export(path, 2)`도 동작했다(151ms). 문서가 없어 쓰지 않기를 권한다.

**PowerPoint는 프로세스 하나를 같이 쓴다(실측).** 시험하는 동안 다른 프로그램이 PowerPoint를 여러 번 띄웠다. 한 번은 창 제목이 `sample_presentation - 읽기 전용 - PowerPoint 발표자 도구`였다. 우리가 띄운 PowerPoint에 그 클라이언트가 붙어 문서를 열자 우리 호출이 pywin32에서 `AttributeError`(`<unknown>.Export`, `Open.PageSetup`)로 거절됐다. 그쪽이 PowerPoint를 끝내자 프로세스가 사라지면서 우리가 창 없이 열어 둔 시험 파일도 함께 닫혔다. 이렇게 끼어든 회차의 측정값은 표에서 뺐다. 그래서 다음을 지켜야 한다.

- 거절된 호출은 짧게 다시 시도한다. `link.py`처럼 `AttributeError`와 `com_error(RPC_E_CALL_REJECTED)`를 함께 잡는다.
- `Quit`는 열린 문서가 0개일 때만 한다.
- 숨겨 띄운 PowerPoint는 언제든 사라질 수 있다고 가정한다.

**연동 중일 때와 아닐 때.**

- 연동 중(발표자가 그 파일을 PowerPoint에 열어 둠)이면 시작과 열기가 필요 없다. 이미 열린 `Presentation`에서 `Slides(n).Export`만 부르면 장당 약 0.1~0.2초다. 저장하지 않은 고침도 반영된다. 로컬 파일 경로를 찾지 못하는 OneDrive 문서에도 쓸 수 있다(문서 근거. 다만 다운로드가 덜 된 슬라이드는 실패한다).
- 이 호출은 `ppt-link` 스레드의 명령 큐로 보내야 한다. 30장을 한 번에 내보내면 그동안(4~5초) 상태 확인이 멈추므로, 필요한 장만 내보내거나 한 장씩 나눠 처리한다.
- 쇼가 진행 중일 때 내보내면 화면이 깜빡이거나 쇼가 느려지는지는 확인하지 못했다(미확인). 발표자의 쇼를 건드릴 수 없어 시험하지 않았다.

### 4.2 macOS: PowerPoint AppleScript (문서 근거, 미실행)

- PowerPoint for Mac의 AppleScript 사전은 앱 안(`.sdef`)에만 있고, 웹에서 1차 문서를 찾지 못했다.
- 포럼에는 `save active presentation in <폴더> as save as PNG`가 오류 없이 끝나지만 그림이 하나도 생기지 않았다는 보고(2023)가 있다. 대안으로 `save as PDF` 뒤에 PDF를 그림으로 바꾸는 방법이 올라와 있다([MacScripter](https://macscripter.net/t/applescript-export-powerpoint-slides-to-png-not-working/74809)). 1차 출처가 아니므로 참고만 한다.
- Office 2016 이후 Mac 앱은 샌드박스 안에서 돌아, 바깥 파일에 접근할 때 발표자에게 권한을 묻는다([Office for Mac VBA](https://learn.microsoft.com/en-us/office/vba/api/overview/office-mac), [GrantAccessToMultipleFiles](https://learn.microsoft.com/en-us/office/vba/office-mac/grantaccesstomultiplefiles)). 내보낼 폴더를 어디로 둬야 묻지 않는지는 미확인이다.
- 결론: macOS의 슬라이드 렌더는 실제 Mac에서 확인하기 전까지 기능 목록에 넣지 않는다.

### 4.3 PowerPoint가 없을 때: LibreOffice (미설치, 미실행)

- `soffice --headless --convert-to <확장자>[:<필터>] --outdir <폴더> <파일>`로 변환한다([명령줄 인자 문서](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)). 그림 내보내기 필터는 `GRAPHICFILTER` 아래 `png`, `jpg`, `svg`로 있다([필터 이름 표](https://help.libreoffice.org/latest/en-US/text/shared/guide/convertfilters.html)). 프레젠테이션용 표에는 `impress_pdf_Export`만 있다.
- Impress의 PNG/JPG 내보내기가 한 장만 내보낸다는 버그(tdf#67614)가 검색 목록에 있다. 페이지는 봇 차단으로 열지 못했다. 그래서 흔히 PDF로 바꾼 뒤 별도 라이브러리로 쪽마다 그림을 만든다. 속도와 결과는 이 PC에 LibreOffice가 없어 재지 못했다(미확인).
- 수백 MB의 별도 설치가 필요하고 렌더가 PowerPoint와 다를 수 있다. 기본 경로로는 권하지 않는다.

## 5. 형식 변환: LLM이 받는 PNG/JPEG로

### 5.1 LLM이 받는 형식(1차 문서)

| | Claude | OpenAI | Gemini |
|---|---|---|---|
| 형식 | JPEG, PNG, GIF, WebP. 움직이는 그림은 첫 장면만 | PNG, JPEG, WEBP, 움직이지 않는 GIF | PNG, JPEG, WEBP, HEIC, HEIF |
| 크기 | 장당 최대 8000×8000. 표준 모델은 긴 변 1568px, 고해상도 모델(4.7 이후)은 2576px를 넘으면 줄여서 본다. 한 요청에 20장을 넘기면 2000px 이하로 줄이라고 권함. API 장당 10MB(base64) | 요청당 512MB, 1,500장 | 인라인은 요청 전체 20MB |
| 출처 | [Vision](https://platform.claude.com/docs/en/build-with-claude/vision) | [Images and vision](https://developers.openai.com/api/docs/guides/images-vision) | [Image understanding](https://ai.google.dev/gemini-api/docs/image-understanding) |

세 곳이 모두 받는 형식은 **PNG, JPEG, WebP**다. EMF, WMF, SVG, BMP, TIFF는 아무 곳도 받지 않는다. GIF는 Gemini 목록에 없다. 긴 변을 **1568px 이하**로 맞추면 Claude 표준 모델에서도 더 줄어들지 않고, 20장이 넘는 요청의 2000px 권고도 지킨다.

### 5.2 Pillow로 바꾸기(실행한 코드)

```python
import io
from PIL import Image

LONG_EDGE = 1568
METAFILE = {"image/x-emf", "image/x-wmf"}

def to_llm_image(blob, content_type, crop=(0, 0, 0, 0)):
    im = Image.open(io.BytesIO(blob))
    if content_type in {"image/png", "image/jpeg"} and not any(c > 0 for c in crop) \
            and max(im.size) <= LONG_EDGE:
        return blob, content_type                          # 그대로 보낸다
    if content_type in METAFILE:                           # Windows에서만 그릴 수 있다
        dpi = im.info.get("dpi", 72)
        dpi = dpi[0] if isinstance(dpi, tuple) else dpi
        im.load(dpi=dpi * LONG_EDGE / max(im.size))       # 원래 크기(8001×4501)로 그리지 않게
    l, t, r, b = (max(0.0, c) for c in crop)
    if any((l, t, r, b)):
        w, h = im.size
        im = im.crop((round(w * l), round(h * t), round(w * (1 - r)), round(h * (1 - b))))
    if max(im.size) > LONG_EDGE:
        im.thumbnail((LONG_EDGE, LONG_EDGE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    if content_type == "image/jpeg":
        im.convert("RGB").save(out, "JPEG", quality=85)
        return out.getvalue(), "image/jpeg"
    if im.mode not in ("RGB", "RGBA", "L", "LA"):
        im = im.convert("RGBA")
    im.save(out, "PNG")                                    # GIF(첫 장면), BMP, TIFF, EMF, WMF → PNG
    return out.getvalue(), "image/png"
```

- **의존성**: python-pptx가 이미 Pillow를 쓴다(`parts/image.py`가 `from PIL import Image`). 새 패키지가 필요 없다. 이 PC의 Pillow 12.3.0은 WebP도 쓸 수 있었다(`features.check("webp")`가 참).
- `Image.thumbnail`은 JPEG이면 `draft()`로 줄여 읽는다([Pillow Image 문서](https://pillow.readthedocs.io/en/stable/reference/Image.html)). 그래도 4032×3024 JPEG는 장당 0.33~0.43초가 들었다.
- **EMF/WMF**는 운영체제마다 다르다.
  - 문서: "Pillow can identify WMF and EMF files. On Windows, it can read WMF and EMF files. By default, it will load the image at 72 dpi."([형식 문서](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#wmf-emf)).
  - 그리는 코드(`drawwmf`)는 `#ifdef _WIN32` 안에 있다. GDI의 `PlayEnhMetaFileRecord`로 흰 바탕에 그린다([display.c](https://github.com/python-pillow/Pillow/blob/main/src/display.c)).
  - 처리기를 뺀 상태(macOS·Linux와 같은 상태)를 흉내 내면 `Image.open`은 되지만(`WMF (8001, 4501)`) `load()`는 `OSError: cannot find loader for this WMF file`을 냈다(실측).
  - PowerPoint가 내보낸 EMF에는 EMF+ 기록이 들어 있었다(EMF+ dual). GDI 대체 기록으로 제대로 그려졌다(눈으로 확인). EMF+ 기록만 있는 파일은 확인하지 못했다(미확인).
  - macOS에서 EMF/WMF를 그림으로 바꿀 방법은 찾지 못했다. 슬라이드 렌더나 건너뛰기로 처리한다.
- **SVG**: Pillow 형식 문서에 없다. 그림으로 바꾸려면 슬라이드 렌더를 쓴다. 별도 SVG 라이브러리는 조사하지 않았다(미확인).

### 5.3 변환 시간(실측, 한 장씩)

| 원본 | 결과 | 시간 |
|---|---|---|
| PNG 1280×800 (0.34MB) | 그대로(다시 인코딩하면 63~66ms) | 0ms |
| 작은 JPEG(≤1568px) | 그대로 | 0ms |
| JPEG 1600×1200 (0.8MB) | JPEG 1568×1176 | 84~137ms |
| JPEG 4032×3024 (6MB) | JPEG 1568×1176 (0.4MB) | 332~425ms |
| 잘라낸 JPEG 1600×900 | JPEG 1040×675 | 27ms |
| GIF 480×360 | PNG | 15~19ms |
| BMP 640×480 (0.9MB) | PNG (0.1MB) | 18~20ms |
| TIFF 400×300 | PNG | 123ms(첫 TIFF, 플러그인 적재 포함으로 보임) |
| EMF 1MB(원래 8001×4501) | PNG 1567×882 | 40ms |
| WMF 1MB | PNG 1568×882 | 44ms |

## 6. 규모: 30장, 그림 50개

| 경로 | 측정 |
|---|---|
| python-pptx `Presentation()` 열기(81.6MB, 모든 부분을 메모리로 읽음) | 0.46~0.51초 |
| 도형 돌기 + 그림 50개 바이트 얻기 + 결과 파일 쓰기 | 0.1초 이하(전체에서 열기와 변환을 뺀 값) |
| Pillow 변환 50개(모두 다시 인코딩) | 6.14~7.22초 |
| Pillow 변환 50개(한도 안의 PNG·JPEG는 그대로) | 4.96~5.17초. 이 가운데 약 3.8초가 4032×3024 JPEG 10개 |
| 실제 서식(Training 19장, 그림 11·고유 8) 열기+변환 | 0.23초 |
| PowerPoint 연동 중 30장 `Slide.Export` 1280×720 | 4.0~4.6초 |
| PowerPoint를 숨겨 띄워 같은 일 | 위에 시작 2.4~2.8초 + 열기 0.8~1.1초 |

시험 자료는 잡음을 넣어 사진보다 압축이 안 되게 만든 최악 사례다(4032×3024 JPEG 하나가 6MB). 보통 사진은 더 빨리 풀릴 것으로 보지만 재지는 않았다. 어느 경로든 발표 시작 전, 또는 파일을 연 직후 백그라운드에서 한 번 하면 되는 크기다. 캡션 결과는 `part.partname`과 잘라내기 값(또는 바이트의 SHA-1)으로 저장해 두면 다음에 열 때 다시 만들지 않아도 된다.

## 7. 권하는 조합

1. **늘(Windows, macOS)**: `load_deck`과 같은 순회에서 다음을 모은다.
   - `isinstance(sh, Picture)`로 그림을 찾는다(그룹 재귀, 자리표시자 포함).
   - 배경 그림과 그림 채우기 도형은 XML로 찾는다.
   - 그림은 부분 이름으로 중복을 지우고, 잘라내기를 적용하고, 긴 변 1568px 이하의 PNG/JPEG로 바꾼다. EMF/WMF는 Windows에서만 바꾼다.
   - 도표는 계열·항목·값을 글로, SmartArt는 글로 꺼낸다. 이것은 캡션 없이 바로 PPT 근거에 넣는다.
2. **"렌더 필요" 표시**: 다음이 있는 슬라이드는 그림을 얻지 못했다고 표시한다.
   - `r:embed`가 없는 그림(연결 그림, 대체 PNG 없는 SVG)
   - macOS의 EMF/WMF
   - `mc:AlternateContent`
3. **Windows에서 PowerPoint 연동 중**이면 2의 슬라이드만 `ppt-link` 스레드에서 `Slides(n).Export(이름, "PNG", 1280, 720)`으로 보충한다. 원하면 모든 슬라이드를 렌더해 슬라이드 단위 캡션을 만들 수도 있다(30장 4~5초).
4. **Windows에서 PowerPoint가 설치돼 있으나 연동하지 않음**: 숨겨 띄우기는 선택 기능으로만 둔다. 4.1의 공유 프로세스 규칙을 지킨다.
5. **macOS**: 1만 한다. 2의 슬라이드는 캡션을 건너뛰고 글만 근거로 쓴다. AppleScript 렌더는 실제 Mac에서 확인한 뒤 더한다.
6. LibreOffice는 쓰지 않는다.

## 곁가지 발견

- python-pptx는 프레젠테이션 부분의 content type이 `.pptx`나 `.pptm`일 때만 연다([api.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/api.py) `_is_pptx_package`). `.potx`를 열면 `ValueError: ... is not a PowerPoint file`이 났다(실측). 같은 코드로 보아 `.ppsx`(쇼 파일)도 `load_deck`에서 실패할 것이다(소스 근거, 미실행).
- 지금 대본에는 SmartArt 글과 도표 값이 빠진다(1장). 3.1·3.2의 코드를 `_shape_texts`에 더하면 대본과 질의응답 근거가 함께 좋아진다.

## 확인하지 못한 것

- macOS: PowerPoint AppleScript로 슬라이드를 PNG/PDF로 내보내는 동작과 속도, 샌드박스 권한 질문. macOS에서 EMF/WMF를 그림으로 바꾸는 방법.
- LibreOffice: 설치하지 않아 변환 결과, 속도, 한 장만 내보내는 문제를 직접 보지 못했다.
- 슬라이드 쇼가 진행 중인 PowerPoint에서 `Slide.Export`를 불렀을 때 쇼에 주는 영향.
- 다른 PowerPoint 버전이나 화면 조작으로 넣은 SVG에 대체 PNG가 붙는지.
- Office 2016 이후 새 도표(폭포 등)와 그 밖의 `mc:AlternateContent` 개체를 실물 파일로 확인하는 것(창 없는 `AddChart2` 실패).
- EMF+ 기록만 있는 EMF를 Pillow가 그리는 결과.
- 마스터·레이아웃에서 물려받은 배경 그림을 찾는 코드.
- 잡음 없는 실제 사진으로 잰 변환 시간. 여러 스레드로 나눴을 때의 속도.
- `Movie.poster_frame`, OLE 개체 미리보기 그림.

## 출처

- python-pptx 1.0.2 소스: [shapes/picture.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/shapes/picture.py), [oxml/shapes/picture.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/oxml/shapes/picture.py), [parts/image.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/parts/image.py), [shapes/graphfrm.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/shapes/graphfrm.py), [shapes/shapetree.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/shapes/shapetree.py), [oxml/shapes/groupshape.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/oxml/shapes/groupshape.py), [chart/plot.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/chart/plot.py), [chart/series.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/chart/series.py), [dml/fill.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/dml/fill.py), [api.py](https://github.com/scanny/python-pptx/blob/v1.0.2/src/pptx/api.py)
- python-pptx 문서: [Shapes(Picture.crop_*, image)](https://python-pptx.readthedocs.io/en/latest/api/shapes.html), [Image](https://python-pptx.readthedocs.io/en/latest/api/image.html)
- Microsoft PowerPoint VBA: [Slide.Export](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.slide.export), [Presentation.Export](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.presentation.export), [Presentations.Open](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.presentations.open), [PpSaveAsFileType](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.ppsaveasfiletype)
- Microsoft Office for Mac: [Office for Mac VBA 개요(샌드박스)](https://learn.microsoft.com/en-us/office/vba/api/overview/office-mac), [GrantAccessToMultipleFiles](https://learn.microsoft.com/en-us/office/vba/office-mac/grantaccesstomultiplefiles)
- Open XML SDK: [SVGBlip](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.office2019.drawing.svg.svgblip?view=openxml-3.0.1), [RelationshipIds(dgm:relIds)](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.diagrams.relationshipids?view=openxml-3.0.1)
- Pillow: [Image file formats(WMF/EMF)](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#wmf-emf), [Image 모듈(thumbnail, draft, seek)](https://pillow.readthedocs.io/en/stable/reference/Image.html), [WmfImagePlugin.py](https://github.com/python-pillow/Pillow/blob/main/src/PIL/WmfImagePlugin.py), [display.c](https://github.com/python-pillow/Pillow/blob/main/src/display.c)
- LibreOffice: [Starting LibreOffice with parameters](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html), [File conversion filter names](https://help.libreoffice.org/latest/en-US/text/shared/guide/convertfilters.html), [tdf#67614](https://bugs.documentfoundation.org/show_bug.cgi?id=67614)(봇 차단으로 본문 미열람)
- LLM 이미지 입력: [Claude Vision](https://platform.claude.com/docs/en/build-with-claude/vision), [OpenAI Images and vision](https://developers.openai.com/api/docs/guides/images-vision), [Gemini Image understanding](https://ai.google.dev/gemini-api/docs/image-understanding)
- 1차 출처가 아닌 참고: [MacScripter: AppleScript export PowerPoint slides to PNG - not working](https://macscripter.net/t/applescript-export-powerpoint-slides-to-png-not-working/74809)
