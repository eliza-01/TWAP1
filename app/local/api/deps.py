from __future__ import annotations

from app.exchanges.registry import get_exchange
from app.local.settings.store import LocalSettingsStore
from app.local.signal_client.client import LocalSignalClient
from app.local.signal_client.store import LocalSignalStore
from app.local.trading.auto_trader import LocalAutoTrader
from app.local.trading.fallback_reports import FallbackCloseReportRepository
from app.local.trading.log_store import LocalTradeStore

settings_store = LocalSettingsStore()

signal_store = LocalSignalStore()

trade_store = LocalTradeStore()

fallback_report_store = FallbackCloseReportRepository()

auto_trader = LocalAutoTrader(settings_store, trade_store, fallback_report_store)

signal_client = LocalSignalClient(settings_store, signal_store, auto_trader)


def selected_exchange(name: str | None = None):
    settings = settings_store.load()
    return get_exchange(settings, name)
