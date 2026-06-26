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
