"""더블클릭/실행 파일 빌드용 시작점.  사용법: python main.py [파일.pptx]"""
import sys

from ppt_reader.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
