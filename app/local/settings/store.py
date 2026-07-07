from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from app.local.settings.model import LocalSettings, settings_from_dict

DEFAULT_SETTINGS_PATH = "local_data/settings.json"

class LocalSettingsStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.getenv("LOCAL_SETTINGS_PATH") or DEFAULT_SETTINGS_PATH)
    def load(self) -> LocalSettings:
        if not self.path.exists():
            settings = LocalSettings()
            self.save(settings)
            return settings
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        return settings_from_dict(data if isinstance(data, dict) else {})
    def save(self, settings: LocalSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(settings.to_dict(), ensure_ascii=False, indent=2)
        with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(self.path.parent)) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        tmp_path.replace(self.path)
    def update(self, patch: dict[str, Any]) -> LocalSettings:
        current = self.load().to_dict()
        merged = _deep_merge(current, patch)

        settings = settings_from_dict(merged)

        self.save(settings)

        return settings


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:

    out = dict(base)

    for key, value in patch.items():

        if isinstance(value, dict) and isinstance(out.get(key), dict):

            out[key] = _deep_merge(out[key], value)

        else:

            out[key] = value

    return out
