# 실행 파일 빌드와 넘기기 정하기

Type: grilling
Status: resolved
Blocked by: 10, 12

## Question

Windows판과 macOS판(Apple Silicon)을 어떻게 빌드해서 받는 사람에게 넘기나? [Mac 없이 macOS판을 만들고 확인하는 방법](13-research-mac-without-mac.md)의 결과를 바탕으로 정한다.

정할 것:
- **판 고정**: Python 버전, PySide6 버전(바인딩 최소 macOS: 6.10·6.11은 15.0, 6.12.0은 26.0. Windows 10 지원), Qt 추가 모듈(음성·소리 쪽 결정에 따름).
- **macOS 빌드 자리**: GitHub Actions `macos-15` 러너에 수동 실행 워크플로를 두나. 저장소를 비공개로 두고 무료 분(약 200~300분) 안에서 쓰나, 공개해서 무료로 쓰나.
- **러너에서 확인할 것**: 서명 검사, arm64 확인, import, 가짜 전체 화면 위 화면 찍기 중 무엇을 넣나.
- **넘기는 꾸러미**: `ditto` zip, 받는 사람용 안내(응용 프로그램 폴더로 옮기기, "그래도 열기", PowerPoint 자동화 허용, 새 판마다 반복), 받는 사람에게 부탁할 확인표(실제 PowerPoint 쇼 위에 보이는지, 레티나에서 크기와 위치, macOS 판).
- **Windows판**: PyInstaller 묶음 방식(onedir), LGPL 문구와 Qt를 바꿔 끼울 수 있는 형태, 스프라이트 등 자원 넣기.
- **설정 파일 위치**: 두 운영체제에서 설정 파일(API 키 포함)을 어디에 두나.

## Answer

- **판 고정**: 빌드는 Python 3.14로 한다(최소 3.10). PySide6-Essentials와 PySide6-Addons를 **6.11.x**로 `requirements.txt`에 고정한다.
  - 6.11.x를 고른 까닭: 음높이 유지 배속(6.10 이상), Python 3.14(6.10.1 이상), Windows 10 지원(6.12까지), 바인딩 최소 macOS 15를 모두 맞춘다.
  - 받는 사람 Mac은 macOS 15(Sequoia) 이상이어야 한다. M1 Pro는 무료 업데이트로 올릴 수 있다.
  - Addons에 딸려 오는 가상 키보드 플러그인(약 16MB)은 빼 본다.
- **빌드 자리**: 발표자는 GitHub Actions 비공개 쿼타가 없다고 했다. 그래서 **저장소를 공개로 바꾸고** 무료 표준 러너를 쓴다.
  - 손으로 누를 때만 도는 빌드(`workflow_dispatch`) 하나에서 Windows판(`windows-latest`)과 macOS판(`macos-15`, Apple Silicon)을 함께 만든다.
  - 버린 대안: 받는 사람 Mac에서 소스로 돌리기, 다른 무료 macOS 빌드 서비스, Mac 빌리기.
- **공개하기 전에 확인할 것**(구현 때, 공개는 되돌리기 어렵다):
  - 기록 전체에 API 키 같은 비밀이 없는지 검사한다.
  - 커밋 작성자 이메일이 공개된다. 그대로 둘지 정한다.
  - `sample/`의 발표 자료를 공개해도 되는지 본다.
  - 원격에 올릴 브랜치를 정한다(`research/*`, `prototype/*`는 지금 로컬에만 있다).
- **러너에서 확인할 것**:
  - 두 운영체제 공통: 숨은 옵션 `--self-check`로 실행 파일을 띄운다. Qt 화면을 화면 밖에 한 번 만들고, 한 문장을 합성하고, 스프라이트를 읽은 뒤 끝난다.
  - macOS만:
    - `codesign --verify --deep --strict`로 서명이 망가지지 않았는지 본다.
    - `lipo -archs`로 arm64만 담겼는지 본다.
    - 가짜 전체 화면 앱 위에 강아지와 원 버튼을 띄우고, cliclick으로 커서를 움직이며 `screencapture`로 찍어 결과물로 올린다. 사람이 그 사진을 본다.
- **넘기는 꾸러미**: 운영체제마다 zip 하나다.
  - Windows: onedir `PPTReader/` 폴더를 zip으로 묶는다. 안에 "먼저 읽어 주세요.txt"를 넣는다(서명이 없어 "Windows의 PC 보호"가 뜨면 "추가 정보 → 실행").
  - macOS: `ditto -c -k --keepParent`로 `PPTReader.app`을 묶는다(그냥 올리면 "손상됨"이 뜬다). "먼저 읽어 주세요.txt"에 적을 것:
    - macOS 15 이상인지 확인하기
    - 응용 프로그램 폴더로 옮기기
    - 열려고 한 뒤 시스템 설정 › 개인정보 보호 및 보안에서 "그래도 열기"(약 1시간만 보임)
    - PowerPoint 제어 허용
    - 새 판마다 위 과정을 반복하기
  - 받는 사람 확인표(macOS): 실제 PowerPoint 쇼 위에 강아지와 원 버튼이 보이는지, 레티나 화면에서 크기와 위치가 맞는지, 읽기와 질의응답이 되는지. 사진으로 돌려받는다.
- **라이선스**: onedir라서 Qt와 FFmpeg는 따로 된 라이브러리로 들어가 바꿔 끼울 수 있다(LGPL). 꾸러미에 `licenses/` 폴더를 두고 Qt, PySide6, FFmpeg, 세 LLM SDK와 그 밖의 의존성 라이선스 원문을 넣는다. 설정 창 맨 아래에 "오픈 소스 라이선스" 링크를 둔다.
- **설정 파일 위치**: [Qt로 바꾼 뒤의 프로그램 구조 정하기](16-grilling-program-structure.md)대로 운영체제 표준 앱 폴더다. 실행 파일에서도 그 폴더를 쓰는지 `--self-check`로 확인한다.

## Comments

- 2026-10-16 [파동과 강아지 입이 목소리를 따라가는 방식 결정](10-grilling-voice-reactive-motion.md)에 따라 PySide6-Addons(QtMultimedia)가 들어간다. 음높이 유지 배속에는 PySide6 6.10 이상이 필요하다. 가상 키보드 플러그인(15.9MB)을 뺄 수 있는지, FFmpeg DLL의 LGPL 문구도 함께 본다.
- 2026-10-16 설정 파일 위치는 [Qt로 바꾼 뒤의 프로그램 구조 정하기](16-grilling-program-structure.md)에서 정했다(운영체제 표준 앱 폴더). 이 일에서는 묶음에 넣을 자원(`assets/` 스프라이트)과 실행 파일에서 그 폴더를 쓰는지만 확인한다.
