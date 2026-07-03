from app.exchanges.binance.adapter import _normalize_price, _normalize_volume, _volume_from_notional


BINANCE_FILTERS = [
    {"filterType": "PRICE_FILTER", "tickSize": "0.01", "minPrice": "0.01", "maxPrice": "1000000"},
    {"filterType": "MARKET_LOT_SIZE", "stepSize": "1", "minQty": "1", "maxQty": "1000"},
]


def test_binance_price_uses_tick_size() -> None:
    contract = {"filters": BINANCE_FILTERS}
    assert _normalize_price(123.456789, contract) == 123.45


def test_binance_volume_uses_step_size() -> None:
    contract = {"filters": BINANCE_FILTERS}
    assert _normalize_volume(3.9, contract, "BTCUSDT") == 3


def test_binance_notional_volume_rounds_down_by_default() -> None:
    contract = {"filters": BINANCE_FILTERS}
    assert _volume_from_notional(2, contract, "ZROUSDT", 0.8914) == 2


def test_binance_notional_volume_can_round_up() -> None:
    contract = {"filters": BINANCE_FILTERS}
    assert _volume_from_notional(2, contract, "ZROUSDT", 0.8914, "up") == 3


def test_binance_notional_volume_clamps_to_min_quantity() -> None:
    contract = {"filters": BINANCE_FILTERS}
    assert _volume_from_notional(0.1, contract, "ZROUSDT", 0.8914) == 1
