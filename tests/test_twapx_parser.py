from app.groups.twapx.parser import parse


def test_parse_english_created():
    text = """$203.26K selling HYPE in 30 minutes 🟥

Score: 46 📈
Price: $40.65
Type: perpetual
Volume: $285.23M (0.07%)
User: 0x3bcae23e8c380dab4732e9a159c0456f12d866f3

Amount: 5000.00 HYPE
CreatedAt:  25.03.2026, 09:08:20 (UTC)
FinishedAt: 25.03.2026, 09:38:20 (UTC)
"""
    result = parse(text)
    assert result.kind == "twap_created"
    assert result.payload["asset"] == "HYPE"
    assert result.payload["side"] == "sell"
    assert result.payload["amount_usd"] == 203260
    assert result.payload["duration_minutes"] == 30
    assert result.payload["market_volume_usd"] == 285_230_000
    assert result.payload["twap_share_percent"] == 0.07


def test_parse_russian_created():
    text = """🟩 $370.32K покупка HYPE в течении 1 час

Цена: $61.72
Объем: $751.60M (0.05%)
Субъект: 0x628132322864e09b888f053cd32ea2634373e9fa
Создан в: 05:16:12 (UTC)
"""
    result = parse(text)
    assert result.kind == "twap_created"
    assert result.payload["asset"] == "HYPE"
    assert result.payload["side"] == "buy"
    assert result.payload["duration_minutes"] == 60


def test_parse_russian_result_sign_by_emoji():
    text = """❌ TWAP отменён (частично)
Статус: terminated
Исполнено: 88.86%
Размер: 2221.51 / 2500.00 HYPE
TwapId: 1965085
Субъект: 0xb676a78f19227ffe9a97db93263fce675e547dbf

Цена в начале:  $62.15
Цена в конце: $62.31 🔴 (+0.26%)
"""
    result = parse(text)
    assert result.kind == "twap_result"
    assert result.payload["asset"] == "HYPE"
    assert result.payload["result_percent"] == -0.26
