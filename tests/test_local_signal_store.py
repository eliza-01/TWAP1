from __future__ import annotations

from app.local.signal_client.store import LocalSignalStore


def test_clear_removes_recent_local_signals(tmp_path):
    store = LocalSignalStore(str(tmp_path / "signals.json"))
    store.add({"signal_id": 1, "asset": "ENA"})
    store.add({"signal_id": 2, "asset": "HYPE"})

    cleared = store.clear()

    assert cleared == 2
    assert store.list_recent() == []
