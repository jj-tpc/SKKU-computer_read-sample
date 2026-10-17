"""설정 파일, 옛 설정 옮기기, 고친 대본 저장 시험."""
from __future__ import annotations

import json

import pytest

import ppt_reader.settings as settings_mod
from ppt_reader.settings import Edits, Settings, app_folder, defaults, nearest_speed


def test_defaults_and_first_save(app_home):
    s = Settings()
    assert app_folder() == app_home and s.path == app_home / "settings.json"
    assert s.data == defaults() and s.first_run
    assert not s.path.exists()  # 바꾸기 전에는 파일을 만들지 않는다
    s.set(first_run_done=True)
    raw = s.path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["version"] == 2 and data["first_run_done"] is True
    assert '"provider": "claude"' in raw and "\n  " in raw  # indent 2
    assert not Settings().first_run
    assert [p.name for p in app_home.iterdir()] == ["settings.json"]  # 임시 파일이 남지 않는다


def test_set_saves_immediately_and_cleans(app_home):
    s = Settings()
    s.set(speed=7, dog="cat", monitor="DISPLAY2", persona="존댓말로 짧게")
    again = Settings()
    assert again["speed"] == 5.0 and again["dog"] == "shiba"
    assert again["monitor"] == "DISPLAY2" and again["persona"] == "존댓말로 짧게"
    assert "존댓말로 짧게" in s.path.read_text(encoding="utf-8")  # ensure_ascii=False


def test_keys_are_kept_per_provider(app_home):
    s = Settings()
    s.set_for("keys", "claude", "claude-key")
    s.set(provider="openai")
    s.set_for("keys", "openai", "openai-key")
    s.set_for("key_ok", "openai", True)
    again = Settings()
    assert again["keys"] == {"claude": "claude-key", "openai": "openai-key", "gemini": "", "elevenlabs": ""}
    assert again["key_ok"] == {"claude": False, "openai": True, "gemini": False, "elevenlabs": False}
    assert again["models"]["claude"] == "claude-haiku-5-5"


def test_voice_engine_settings(app_home):
    s = Settings()
    assert s["voice_engine"] == "os"
    assert s["cloud_voice"]["elevenlabs"]["model"] == "eleven_multilingual_v2"
    assert s["cloud_voice"]["gemini"] == {"model": "gemini-3.8-flash-tts", "voice": "Kore"}
    s.set(voice_engine="openai")  # 없는 엔진은 받지 않는다
    assert Settings()["voice_engine"] == "os"
    s.set(voice_engine="elevenlabs", cloud_voice={"elevenlabs": {"voice_id": "abc", "voice_name": "Anna", "model": ""},
                                                  "gemini": {"voice": ""}})
    again = Settings()
    assert again["voice_engine"] == "elevenlabs"
    assert again["cloud_voice"]["elevenlabs"] == {"model": "eleven_multilingual_v2", "voice_id": "abc", "voice_name": "Anna"}
    assert again["cloud_voice"]["gemini"]["voice"] == "Kore"  # 빈 값은 기본값으로
    s.set_for("keys", "elevenlabs", "el-key")
    s.set_for("keys", "gemini", "gm-key")  # Gemini 음성과 Gemini 질의응답은 키 하나
    assert Settings()["keys"]["elevenlabs"] == "el-key" and Settings()["keys"]["gemini"] == "gm-key"


def test_thinking_depth_is_not_saved(app_home):
    s = Settings()
    s.set(effort="high", thinking="high")
    data = json.loads(s.path.read_text(encoding="utf-8"))
    assert "effort" not in data and "thinking" not in data


@pytest.mark.parametrize("old, new", [(0.5, 1.0), (1.0, 1.0), (1.24, 1.0), (1.25, 1.5), (1.6, 1.5),
                                      (1.75, 2.0), (2.0, 2.0), (3.4, 2.0), (3.5, 5.0), ("x", 1.0)])
def test_nearest_speed(old, new):
    assert nearest_speed(old) == new


def test_migrate_old_settings(app_home, tmp_path):
    old = {"source": "body", "voice": "Microsoft Heami Desktop - Korean  [ko_KR]",
           "output": {"id": "dev-1", "name": "헤드폰(Shokz)"}, "speed": 1.24,
           "auto_next": True, "read_on_change": False, "topmost": True}
    old_path = tmp_path / "old_settings.json"
    old_path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    before = old_path.read_bytes()
    s = Settings()
    assert s["source"] == "body" and s["voice"] == "Microsoft Heami Desktop - Korean"
    assert s["output"] == {"id": "dev-1", "name": "헤드폰(Shokz)"} and s["speed"] == 1.0
    assert s["auto_next"] is True and s["read_on_change"] is False and "topmost" not in s.data
    assert s.first_run  # 옮겨 와도 새 프로그램은 처음 실행이다
    s.set(first_run_done=True)
    assert old_path.read_bytes() == before  # 옛 파일은 건드리지 않는다

    old_path.write_text(json.dumps({"source": "notes"}), encoding="utf-8")
    assert Settings()["source"] == "body"  # 새 파일이 있으면 옛 파일은 보지 않는다


def test_broken_file_uses_defaults(app_home):
    app_home.mkdir(parents=True)
    (app_home / "settings.json").write_text("{깨진 파일", encoding="utf-8")
    assert Settings().data == defaults()


def test_folder_by_platform(monkeypatch, tmp_path):
    monkeypatch.delenv("PPT_READER_HOME")
    monkeypatch.setattr(settings_mod.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert app_folder() == tmp_path / "Roaming" / "PPT읽어주기"
    monkeypatch.setattr(settings_mod.sys, "platform", "darwin")
    monkeypatch.setattr(settings_mod.Path, "home", lambda: tmp_path)
    assert app_folder() == tmp_path / "Library" / "Application Support" / "PPT읽어주기"


def test_edits_store(app_home, tmp_path):
    deck = tmp_path / "발표.pptx"
    e = Edits()
    e.put(deck, 2, "고친 대본", "원래 대본")
    again = Edits()
    got = again.for_deck(deck)
    assert list(got) == [2] and got[2]["text"] == "고친 대본"
    assert not Edits.source_changed(got[2], "원래 대본")
    assert Edits.source_changed(got[2], "원래 대본이 바뀜")
    assert again.for_deck(tmp_path / "다른.pptx") == {}
    again.remove(deck, 2)
    assert Edits().for_deck(deck) == {} and Edits().data == {}
