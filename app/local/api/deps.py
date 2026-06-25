from __future__ import annotations

from app.exchanges.registry import get_exchange
from app.local.settings.store import LocalSettingsStore
from app.local.signal_client.store import LocalSignalStore

settings_store = LocalSettingsStore()
signal_store = LocalSignalStore()


def selected_exchange(name: str | None = None):
    settings = settings_store.load()
    return get_exchange(settings, name)
