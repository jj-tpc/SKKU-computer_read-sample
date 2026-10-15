#!/bin/bash
# PPT 읽어주기 - macOS 실행 스크립트.  터미널에서:  bash run_mac.sh
# 처음 실행할 때 .venv 를 만들고 필요한 패키지를 설치한다(인터넷 필요).
cd "$(dirname "$0")" || exit 1

PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "python3가 없습니다. https://www.python.org/downloads/ 에서 macOS용 Python을 설치하세요."
    exit 1
fi
if ! "$PY" -c "import tkinter; tkinter.Tk().destroy()" >/dev/null 2>&1; then
    echo "이 Python에는 화면 라이브러리(tkinter)가 없습니다."
    echo " - python.org 설치 파일로 Python을 설치하거나"
    echo " - Homebrew를 쓴다면: brew install python-tk"
    exit 1
fi

if [ ! -f .venv/installed.ok ]; then
    echo "처음 실행: 필요한 패키지를 설치합니다..."
    "$PY" -m venv .venv || exit 1
    .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt || {
        echo "패키지 설치에 실패했습니다. 인터넷 연결을 확인하고 다시 실행하세요."
        exit 1
    }
    touch .venv/installed.ok
fi

exec .venv/bin/python main.py "$@"
