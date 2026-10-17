슬라이독 — 오픈 소스 라이선스
=================================

이 프로그램은 아래 오픈 소스 소프트웨어를 함께 묶어 배포합니다. 각 라이선스 원문은 이 폴더에 있습니다.

| 소프트웨어                | 판           | 라이선스                         | 원문 파일                 |
|---------------------------|--------------|----------------------------------|---------------------------|
| Qt for Python (PySide6)   | 6.11         | LGPL-3.0                         | LGPL-3.0.txt, GPL-3.0.txt |
| Qt 6 (Core, Gui, Widgets, Multimedia 등) | 6.11 | LGPL-3.0                    | LGPL-3.0.txt, GPL-3.0.txt |
| FFmpeg (Qt Multimedia가 씀) | Qt 6.11에 딸림 | LGPL-2.1 이상                  | LGPL-2.1.txt              |
| Python                    | 3.14         | PSF License                      | Python-LICENSE.txt        |
| anthropic                 | 1.15         | MIT                              | anthropic-LICENSE.txt     |
| openai                    | 3.33         | Apache-2.0                       | openai-LICENSE.txt        |
| google-genai              | 2.31         | Apache-2.0                       | google-genai-LICENSE.txt  |
| python-pptx               | 1.0          | MIT                              | python-pptx-LICENSE.txt   |
| Pillow                    | 12           | MIT-CMU                          | Pillow-LICENSE.txt        |
| pywin32 (Windows판)       | 312          | PSF                              | pywin32-LICENSE.txt       |
| pyobjc (macOS판)          | 12           | MIT                              | pyobjc-LICENSE.txt        |
| lxml                      | 6.1          | BSD-3-Clause                     | lxml-LICENSE.txt          |
| httpx, httpx2             | 0.28, 2.13   | BSD-3-Clause                     | httpx-LICENSE.md, httpx2-LICENSE.md |
| certifi                   | 2026.7       | MPL-2.0                          | certifi-LICENSE.txt       |
| pydantic                  | 2.14         | MIT                              | pydantic-LICENSE.txt      |

Qt와 FFmpeg(LGPL)에 대하여
---------------------------
- 이 프로그램은 Qt, PySide6, FFmpeg를 고치지 않고 그대로 씁니다.
- 실행 파일은 한 파일로 묶지 않고 폴더째 배포합니다(PyInstaller onedir). Qt와 FFmpeg는 그 폴더 안에 따로 된 라이브러리 파일로 들어 있습니다.
  - Windows: Slidog\_internal\PySide6 폴더의 Qt6*.dll, avcodec-*.dll 등
  - macOS: Slidog.app/Contents/Frameworks 안의 Qt와 FFmpeg 라이브러리
- 사용자는 이 라이브러리들을 같은 판의 다른 빌드(직접 고쳐 빌드한 것 포함)로 바꿔 끼워 쓸 수 있습니다.
- 소스 코드:
  - Qt: https://download.qt.io/official_releases/qt/6.11/
  - PySide6: https://code.qt.io/cgit/pyside/pyside-setup.git/
  - FFmpeg: https://ffmpeg.org/download.html (Qt Multimedia가 쓰는 FFmpeg 빌드 방법은 Qt 문서 "Qt Multimedia FFmpeg"에 있습니다)
- 이 프로그램 자체의 소스: https://github.com/jj-tpc/SKKU-computer_read-sample
