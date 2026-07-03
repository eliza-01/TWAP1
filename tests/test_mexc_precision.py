from app.exchanges.mexc.adapter import _normalize_price, _normalize_volume, _volume_from_notional


def test_mexc_price_uses_contract_precision() -> None:
    contract = {"priceScale": 2, "priceUnit": 0.01}
    assert _normalize_price(123.456789, contract) == 123.46


def test_mexc_volume_uses_contract_step() -> None:
    contract = {"volScale": 0, "volUnit": 1, "minVol": 1, "maxVol": 1000}
    assert _normalize_volume(3.9, contract, "BTC_USDT") == 3


def test_mexc_notional_volume_rounds_down_by_default() -> None:
    contract = {"contractSize": 1, "volScale": 0, "volUnit": 1, "minVol": 1, "maxVol": 1000}
    assert _volume_from_notional(2, contract, "ZRO_USDT", 0.8914) == 2


def test_mexc_notional_volume_can_round_up() -> None:
    contract = {"contractSize": 1, "volScale": 0, "volUnit": 1, "minVol": 1, "maxVol": 1000}
    assert _volume_from_notional(2, contract, "ZRO_USDT", 0.8914, "up") == 3


def test_mexc_notional_volume_clamps_to_min_contract() -> None:
    contract = {"contractSize": 1, "volScale": 0, "volUnit": 1, "minVol": 1, "maxVol": 1000}
    assert _volume_from_notional(0.1, contract, "ZRO_USDT", 0.8914) == 1
