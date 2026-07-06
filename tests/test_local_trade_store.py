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



def test_ignore_open_trades_on_startup_marks_only_open_trades(tmp_path):
    store = LocalTradeStore(str(tmp_path / "trades.json"))
    store.add_open_trade({"trade_key": "signal:1", "symbol": "ENAUSDT", "status": "open"})
    store.add_open_trade({"trade_key": "signal:2", "symbol": "ZECUSDT", "status": "open"})
    store.close_trade("signal:2", {"close_reason": "test"})

    count = store.ignore_open_trades_on_startup("2026-07-06T16:00:00+00:00")

    assert count == 1
    assert store.list_open_trades() == []
    trades = store._trades()
    ignored = next(trade for trade in trades if trade["trade_key"] == "signal:1")
    closed = next(trade for trade in trades if trade["trade_key"] == "signal:2")
    assert ignored["status"] == "ignored_on_startup"
    assert ignored["ignore_reason"] == "software_started_fresh"
    assert closed["status"] == "closed"
