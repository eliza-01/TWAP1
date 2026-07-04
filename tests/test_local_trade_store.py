from __future__ import annotations

from app.local.trading.log_store import LocalTradeStore


def test_find_open_trade_matches_binance_symbol_without_related_id(tmp_path):
    store = LocalTradeStore(str(tmp_path / "trades.json"))
    store.add_open_trade(
        {
            "trade_key": "signal:42",
            "open_signal_id": 42,
            "symbol": "PENDLEUSDT",
            "direction": "short",
            "user_address": "0x1a852d88f87ddc57edb57552019d2ec94f68c5",
            "status": "open",
        }
    )

    found = store.find_open_for_signal(
        {
            "signal_id": 43,
            "kind": "twap_result",
            "symbol": "PENDLE_USDT",
            "asset": "PENDLE",
            "user_address": "0x1a852d88f87ddc57edb57552019d2ec94f68c5",
        }
    )

    assert found is not None
    assert found["trade_key"] == "signal:42"
