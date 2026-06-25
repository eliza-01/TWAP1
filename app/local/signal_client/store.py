from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

DEFAULT_SIGNALS_PATH = "local_data/signals.json"


class LocalSignalStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.getenv("LOCAL_SIGNALS_PATH") or DEFAULT_SIGNALS_PATH)

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        items = self._read()
        return items[-limit:][::-1]

    def add(self, signal: dict[str, Any]) -> None:
        items = self._read()
        signal_id = signal.get("signal_id") or signal.get("id")
        if signal_id is not None and any((item.get("signal_id") or item.get("id")) == signal_id for item in items):
            return
        items.append(signal)
        self._write(items[-500:])

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(items, ensure_ascii=False, indent=2)
        with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(self.path.parent)) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        tmp_path.replace(self.path)
