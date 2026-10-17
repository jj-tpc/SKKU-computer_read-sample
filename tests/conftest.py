"""모든 시험은 화면, 인터넷, 소리 없이 돈다. 사용자의 설정 폴더는 건드리지 않는다."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def app_home(tmp_path, monkeypatch):
    """설정 폴더를 임시 폴더로 두고, 옛 설정 파일도 임시 위치를 보게 한다."""
    import ppt_reader.settings as settings

    home = tmp_path / "home"
    monkeypatch.setenv("PPT_READER_HOME", str(home))
    monkeypatch.setattr(settings, "OLD_SETTINGS", tmp_path / "old_settings.json")
    return home
