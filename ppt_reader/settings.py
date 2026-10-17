"""설정 파일(settings.json), 고친 대본(edits.json), 옛 설정 옮기기.

Qt 없이 시험할 수 있게 QStandardPaths를 쓰지 않고 폴더를 직접 정한다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from .slides import SOURCES

APP_FOLDER = "PPT읽어주기"
OLD_SETTINGS = Path.home() / ".ppt_reader_settings.json"
VERSION = 2
SPEEDS = (1.0, 1.5, 2.0, 5.0)
PROVIDERS = ("claude", "openai", "gemini")  # 질의응답 LLM
KEY_OWNERS = PROVIDERS + ("elevenlabs",)  # 키는 회사마다 하나. Gemini 음성은 질의응답의 Gemini 키를 함께 쓴다
DEFAULT_MODELS = {"claude": "claude-haiku-5-5", "openai": "gpt-6-luna", "gemini": "gemini-3.5-flash-lite"}
VOICE_ENGINES = ("os", "elevenlabs", "gemini")
ELEVENLABS_MODELS = ("eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_v4")
GEMINI_TTS_MODELS = ("gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts")
DOGS = ("shiba", "bichon", "beagle")
_SOURCE_KEYS = tuple(k for k, _ in SOURCES)


def app_folder() -> Path:
    """운영체제 표준 앱 폴더. 시험에서는 PPT_READER_HOME으로 바꾼다."""
    env = os.environ.get("PPT_READER_HOME")
    if env:
        return Path(env)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / APP_FOLDER
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_FOLDER
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / APP_FOLDER


def defaults() -> dict:
    return {
        "version": VERSION,
        "first_run_done": False,
        "source": "notes_first",
        "voice": "",
        "output": None,  # None = 운영체제의 기본 출력 장치
        "speed": 1.0,
        "voice_engine": "os",
        "cloud_voice": {
            "elevenlabs": {"model": ELEVENLABS_MODELS[0], "voice_id": "", "voice_name": ""},
            "gemini": {"model": GEMINI_TTS_MODELS[0], "voice": "Kore"},
        },
        "auto_next": False,
        "read_on_change": True,
        "provider": "claude",
        "models": dict(DEFAULT_MODELS),
        "keys": {p: "" for p in KEY_OWNERS},
        "key_ok": {p: False for p in KEY_OWNERS},
        "persona": "",
        "captions": False,
        "dog": "shiba",
        "dog_visible": True,
        "monitor": "follow",
        "x5_factor": {},
    }


def nearest_speed(value) -> float:
    """1.0, 1.5, 2.0, 5.0 중 가장 가까운 값. 한가운데면 빠른 쪽(1.25 → 1.5)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 1.0
    return min(SPEEDS, key=lambda s: (abs(s - v), -s))


def _clean(raw: dict) -> dict:
    """읽은 값 중 형식이 맞는 것만 기본값 위에 얹는다. 잘못된 값 하나 때문에 전체를 버리지 않는다."""
    d = defaults()
    for key in ("first_run_done", "auto_next", "read_on_change", "captions", "dog_visible"):
        if isinstance(raw.get(key), bool):
            d[key] = raw[key]
    for key in ("voice", "persona"):
        if isinstance(raw.get(key), str):
            d[key] = raw[key]
    if raw.get("source") in _SOURCE_KEYS:
        d["source"] = raw["source"]
    out = raw.get("output")
    if isinstance(out, dict) and isinstance(out.get("id"), str) and out["id"]:
        d["output"] = {"id": out["id"], "name": out.get("name") if isinstance(out.get("name"), str) else out["id"]}
    if "speed" in raw:
        d["speed"] = nearest_speed(raw["speed"])
    if raw.get("provider") in PROVIDERS:
        d["provider"] = raw["provider"]
    for key, kind, empty_ok in (("models", str, False), ("keys", str, True), ("key_ok", bool, True)):
        given = raw.get(key)
        if isinstance(given, dict):
            for p in d[key]:
                if isinstance(given.get(p), kind) and (empty_ok or given[p]):
                    d[key][p] = given[p]
    if raw.get("voice_engine") in VOICE_ENGINES:
        d["voice_engine"] = raw["voice_engine"]
    cloud = raw.get("cloud_voice")
    if isinstance(cloud, dict):
        for engine, fields in d["cloud_voice"].items():
            given = cloud.get(engine)
            if isinstance(given, dict):
                for field in fields:
                    if isinstance(given.get(field), str):
                        fields[field] = given[field]
            base = defaults()["cloud_voice"][engine]
            for field in ("model", "voice"):
                if field in fields and not fields[field]:
                    fields[field] = base[field]
    if raw.get("dog") in DOGS:
        d["dog"] = raw["dog"]
    if isinstance(raw.get("monitor"), str) and raw["monitor"]:
        d["monitor"] = raw["monitor"]
    x5 = raw.get("x5_factor")
    if isinstance(x5, dict):
        d["x5_factor"] = {k: float(v) for k, v in x5.items()
                          if isinstance(k, str) and isinstance(v, (int, float)) and v > 0}
    return d


def migrate_old(old: dict) -> dict:
    """v1(tkinter) 설정에서 쓸 수 있는 값만 옮긴다. 옛 파일은 건드리지 않는다."""
    raw = {k: old[k] for k in ("source", "output", "auto_next", "read_on_change") if k in old}
    if isinstance(old.get("voice"), str):
        # v1은 목록 글자("이름  [ko_KR]")를 저장했다. 새 파일에는 음성 이름만 둔다.
        raw["voice"] = re.sub(r"\s+\[[^\]]*\]$", "", old["voice"])
    if "speed" in old:
        raw["speed"] = old["speed"]
    return raw


def _write_atomic(path: Path, data) -> bool:
    """임시 파일에 다 쓴 뒤 바꿔치기한다. 쓰는 도중에 꺼져도 앞 파일이 깨지지 않는다."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise
        return True
    except OSError:
        return False


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class Settings:
    """settings.json. 값을 바꾸면 바로 파일 전체를 다시 쓴다."""

    def __init__(self, folder: Path | str | None = None):
        self.folder = Path(folder) if folder else app_folder()
        self.path = self.folder / "settings.json"
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            raw = _read_json(self.path)
        else:
            old = _read_json(OLD_SETTINGS)
            raw = migrate_old(old) if isinstance(old, dict) else {}
        return _clean(raw if isinstance(raw, dict) else {})

    @property
    def first_run(self) -> bool:
        return not self.data["first_run_done"]

    def __getitem__(self, key: str):
        return self.data[key]

    def set(self, **values) -> None:
        self.data = _clean({**self.data, **values})
        self.save()

    def set_for(self, field: str, provider: str, value) -> None:
        """제공자마다 따로 두는 값(models, keys, key_ok)을 바꾼다."""
        merged = {**self.data[field], provider: value}
        self.set(**{field: merged})

    def save(self) -> bool:
        return _write_atomic(self.path, self.data)


# ---------------------------------------------------------------- 고친 대본

def norm_path(path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Edits:
    """edits.json: {발표 파일 경로: {장 번호: {"text": 고친 대본, "orig": 고칠 때 원래 대본의 sha256}}}"""

    def __init__(self, folder: Path | str | None = None):
        self.path = Path(folder or app_folder()) / "edits.json"
        data = _read_json(self.path)
        self.data: dict = data if isinstance(data, dict) else {}

    def for_deck(self, deck_path) -> dict[int, dict]:
        entry = self.data.get(norm_path(deck_path))
        out: dict[int, dict] = {}
        if not isinstance(entry, dict):
            return out
        for key, e in entry.items():
            if (key.isdigit() and isinstance(e, dict) and isinstance(e.get("text"), str)
                    and isinstance(e.get("orig"), str)):
                out[int(key)] = {"text": e["text"], "orig": e["orig"]}
        return out

    def put(self, deck_path, number: int, text: str, original: str) -> None:
        self.data.setdefault(norm_path(deck_path), {})[str(number)] = {"text": text, "orig": text_hash(original)}
        _write_atomic(self.path, self.data)

    def remove(self, deck_path, number: int) -> None:
        key = norm_path(deck_path)
        entry = self.data.get(key)
        if isinstance(entry, dict) and entry.pop(str(number), None) is not None:
            if not entry:
                del self.data[key]
            _write_atomic(self.path, self.data)

    @staticmethod
    def source_changed(edit: dict, original: str) -> bool:
        """고친 뒤에 원래 대본(슬라이드 글)이 바뀌었나."""
        return edit["orig"] != text_hash(original)
