from __future__ import annotations

from app.exchanges.core.base import ExchangeAdapter
from app.exchanges.core.errors import ExchangeError
from app.exchanges.core.types import ExchangeConfig, ExchangeCredentials
from app.exchanges.mexc.adapter import MexcAdapter
from app.local.settings.model import LocalSettings

_ADAPTERS = {
    MexcAdapter.name: MexcAdapter,
}


def available_exchanges() -> list[dict[str, str]]:
    return [{"name": cls.name, "title": cls.title} for cls in _ADAPTERS.values()]


def get_exchange(settings: LocalSettings, name: str | None = None) -> ExchangeAdapter:
    exchange_name = name or settings.selected_exchange
    cls = _ADAPTERS.get(exchange_name)
    if cls is None:
        raise ExchangeError(f"Биржа не поддерживается: {exchange_name}")

    raw = settings.exchanges.get(exchange_name)
    config = ExchangeConfig(
        name=exchange_name,
        enabled=bool(raw.enabled) if raw else False,
        credentials=ExchangeCredentials(auth_token=raw.auth_token if raw else ""),
    )
    return cls(config)
