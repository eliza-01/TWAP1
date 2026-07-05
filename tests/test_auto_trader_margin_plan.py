from __future__ import annotations

import asyncio

from app.exchanges.core.types import Balance, TradingRules
from app.local.settings.model import LocalSettings, LocalTradingSettings
from app.local.trading.auto_trader import _build_open_plan, _should_bypass_min_usd_by_share


class FakeAdapter:
    def __init__(self, available: float) -> None:
        self.available = available

    async def balance(self, currency: str = "USDT") -> Balance:
        return Balance(currency=currency, available=self.available, equity=self.available)


def _rules() -> TradingRules:
    return TradingRules(
        symbol="HYPE_USDT",
        min_volume=0.1,
        max_volume=1000,
        volume_step=0.1,
        contract_size=1,
        min_leverage=1,
        max_leverage=20,
        price=10,
        min_notional_usdt=1,
    )


def test_order_plan_uses_configured_usdt_volume_and_base_leverage() -> None:
    settings = LocalSettings(
        trading=LocalTradingSettings(auto_order_usdt=20, default_leverage=2, max_auto_leverage=20)
    )

    plan = asyncio.run(_build_open_plan(settings, FakeAdapter(available=100), "HYPE_USDT", _rules()))

    assert plan.leverage == 2
    assert plan.volume == 2
    assert plan.notional_usdt == 20
    assert plan.estimated_margin_usdt == 10
    assert plan.auto_leverage_used is False


def test_order_plan_increases_leverage_when_available_margin_is_low() -> None:
    settings = LocalSettings(
        trading=LocalTradingSettings(
            auto_order_usdt=20,
            default_leverage=2,
            auto_leverage_enabled=True,
            max_auto_leverage=20,
        )
    )

    plan = asyncio.run(_build_open_plan(settings, FakeAdapter(available=5), "HYPE_USDT", _rules()))

    assert plan.leverage == 5
    assert plan.volume == 2
    assert plan.notional_usdt == 20
    assert plan.estimated_margin_usdt == 4
    assert plan.auto_leverage_used is True

def test_min_usd_share_override_allows_only_min_usd_rejection() -> None:
    settings = LocalSettings(
        trading=LocalTradingSettings(
            ignore_min_usd_by_market_share=True,
            min_usd_override_twap_share_percent=2.5,
        )
    )

    assert _should_bypass_min_usd_by_share(
        settings,
        {"status": "rejected", "reason": "amount_usd_lt_300000", "twap_share_percent": 2.51},
    )


def test_min_usd_share_override_keeps_other_rejections_blocked() -> None:
    settings = LocalSettings(
        trading=LocalTradingSettings(
            ignore_min_usd_by_market_share=True,
            min_usd_override_twap_share_percent=2.5,
        )
    )

    assert not _should_bypass_min_usd_by_share(
        settings,
        {
            "status": "rejected",
            "reason": "amount_usd_lt_300000;duration_gt_30_minutes",
            "twap_share_percent": 5,
        },
    )



def _binance_min_notional_rules() -> TradingRules:
    return TradingRules(
        symbol="LOWUSDT",
        min_volume=0.01,
        max_volume=1000,
        volume_step=0.01,
        contract_size=1,
        min_leverage=1,
        max_leverage=20,
        price=10,
        min_notional_usdt=5,
    )


def test_order_plan_uses_exchange_min_notional_when_it_is_higher_than_min_qty() -> None:
    settings = LocalSettings(
        trading=LocalTradingSettings(auto_order_usdt=1, default_leverage=1, max_auto_leverage=20)
    )

    plan = asyncio.run(_build_open_plan(settings, FakeAdapter(available=100), "LOWUSDT", _binance_min_notional_rules()))

    assert plan.notional_usdt == 5
    assert plan.target_order_usdt == 5
    assert plan.volume == 0.5
    assert plan.min_volume_used is True


def test_min_volume_plan_uses_exchange_min_notional_when_it_is_higher_than_min_qty() -> None:
    settings = LocalSettings(trading=LocalTradingSettings(use_min_volume=True))

    plan = asyncio.run(_build_open_plan(settings, FakeAdapter(available=100), "LOWUSDT", _binance_min_notional_rules()))

    assert plan.leverage == 1
    assert plan.notional_usdt == 5
    assert plan.target_order_usdt == 5
    assert plan.volume == 0.5
    assert plan.min_volume_used is True


class FakeSettingsStore:
    def __init__(self, settings: LocalSettings) -> None:
        self.settings = settings

    def load(self) -> LocalSettings:
        return self.settings


class FakeTradeStore:
    def __init__(self) -> None:
        self.logs = []
        self.trades = []

    def add_open_trade(self, trade: dict) -> dict:
        self.trades.append(trade)
        return trade

    def add_log(self, *args, **kwargs) -> None:
        self.logs.append((args, kwargs))


class FakeOpenAdapter(FakeAdapter):
    def __init__(self, available: float) -> None:
        super().__init__(available)
        self.request = None

    async def trading_rules(self, symbol: str) -> TradingRules:
        return _rules()

    async def open_position(self, request):
        from app.exchanges.core.types import OrderResult

        self.request = request
        return OrderResult(True, "ok", "123", {"request": request.__dict__})


def test_auto_trader_opens_signal_with_amount_usdt_like_manual_order(monkeypatch) -> None:
    from app.local.trading import auto_trader as module
    from app.local.trading.auto_trader import LocalAutoTrader

    settings = LocalSettings(
        trading=LocalTradingSettings(auto_order_usdt=20, default_leverage=2, max_auto_leverage=20)
    )
    adapter = FakeOpenAdapter(available=100)
    monkeypatch.setattr(module, "get_exchange", lambda *_args, **_kwargs: adapter)

    trader = LocalAutoTrader(FakeSettingsStore(settings), FakeTradeStore())
    asyncio.run(trader._open_from_signal({"signal_id": 1, "asset": "HYPE", "side": "buy", "kind": "twap_created"}))

    assert adapter.request is not None
    assert adapter.request.symbol == "HYPEUSDT"
    assert adapter.request.direction == "long"
    assert adapter.request.volume == 2
    assert adapter.request.amount_usdt == 20


def test_fallback_closes_open_trade_after_twap_deadline(monkeypatch, tmp_path) -> None:
    from datetime import datetime, timedelta, timezone

    from app.exchanges.core.types import OrderResult
    from app.local.trading import auto_trader as module
    from app.local.trading.auto_trader import LocalAutoTrader
    from app.local.trading.log_store import LocalTradeStore

    class FakeCloseAdapter:
        def __init__(self) -> None:
            self.closed = None

        async def close_position(self, request):
            self.closed = request
            return OrderResult(True, "closed", "close-1", {"ok": True})

    class FakeReportStore:
        def __init__(self) -> None:
            self.reports = []

        def save(self, report: dict) -> int:
            self.reports.append(report)
            return len(self.reports)

    settings = LocalSettings(
        trading=LocalTradingSettings(
            fallback_close_enabled=True,
            fallback_close_grace_seconds=5,
        )
    )
    store = LocalTradeStore(str(tmp_path / "trades.json"))
    started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    store.add_open_trade(
        {
            "trade_key": "signal:100",
            "open_signal_id": 100,
            "twap_id": 777,
            "symbol": "HYPEUSDT",
            "direction": "long",
            "volume": 1.5,
            "duration_minutes": 1,
            "twap_started_at": started_at.isoformat(),
            "twap_deadline_at": (started_at + timedelta(minutes=1)).isoformat(),
            "status": "open",
        }
    )
    adapter = FakeCloseAdapter()
    reports = FakeReportStore()
    monkeypatch.setattr(module, "get_exchange", lambda *_args, **_kwargs: adapter)

    trader = LocalAutoTrader(FakeSettingsStore(settings), store, reports)
    asyncio.run(trader.check_fallback_closures())

    assert adapter.closed is not None
    assert adapter.closed.symbol == "HYPEUSDT"
    assert adapter.closed.direction == "long"
    assert adapter.closed.volume == 1.5
    assert store.list_open_trades() == []
    assert reports.reports[0]["status"] == "success"
    assert reports.reports[0]["trade_key"] == "signal:100"


def test_fallback_does_not_close_when_disabled(monkeypatch, tmp_path) -> None:
    from datetime import datetime, timedelta, timezone

    from app.local.trading import auto_trader as module
    from app.local.trading.auto_trader import LocalAutoTrader
    from app.local.trading.log_store import LocalTradeStore

    class FakeCloseAdapter:
        def __init__(self) -> None:
            self.closed = None

        async def close_position(self, request):
            self.closed = request
            raise AssertionError("fallback should be disabled")

    settings = LocalSettings(trading=LocalTradingSettings(fallback_close_enabled=False))
    store = LocalTradeStore(str(tmp_path / "trades.json"))
    started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    store.add_open_trade(
        {
            "trade_key": "signal:101",
            "symbol": "HYPEUSDT",
            "direction": "short",
            "volume": 1,
            "duration_minutes": 1,
            "twap_started_at": started_at.isoformat(),
            "twap_deadline_at": (started_at + timedelta(minutes=1)).isoformat(),
            "status": "open",
        }
    )
    adapter = FakeCloseAdapter()
    monkeypatch.setattr(module, "get_exchange", lambda *_args, **_kwargs: adapter)

    trader = LocalAutoTrader(FakeSettingsStore(settings), store)
    asyncio.run(trader.check_fallback_closures())

    assert adapter.closed is None
    assert len(store.list_open_trades()) == 1
