from __future__ import annotations

from typing import Any

from app.shared.types import ParseResult, SourceGroupConfig


def format_forward(result: ParseResult, config: SourceGroupConfig) -> str:
    payload = result.payload
    side = "Покупка" if payload.get("side") == "buy" else "Продажа"
    return "\n".join(
        line
        for line in [
            "✅ TWAPx принят",
            "",
            f"Монета: {payload.get('asset', 'n/a')}",
            f"Сторона: {side}",
            f"Объём TWAP: {_usd(payload.get('amount_usd'))}",
            f"Время исполнения: {_minutes(payload.get('duration_minutes'))}",
            f"Market volume: {_usd(payload.get('market_volume_usd'))}",
            f"TWAP share: {_pct(payload.get('twap_share_percent'))}",
            f"Цена: {_price(payload.get('price'))}",
            f"Score: {_value(payload.get('score'))}",
            f"User: {payload.get('user_address', 'n/a')}",
            f"CreatedAt: {payload.get('created_at_text', 'n/a')}",
            "",
            "Фильтр:",
            f"• объём ≥ {_usd(config.filters.min_usd)}",
            f"• время ≤ {config.filters.max_duration_minutes:g} минут",
            f"• market volume < {_usd(config.filters.max_market_volume_usd)}",
            f"• TWAP share > {config.filters.min_twap_share_percent:g}%",
        ]
        if line is not None
    )


def format_result(result: ParseResult, original: dict[str, Any]) -> str:
    payload = result.payload
    original_payload = original.get("payload") or {}

    result_type = payload.get("result_type")
    title = "❌ TWAPx отменён" if result_type == "cancelled" else "✅ TWAPx завершён"
    side = _side(original_payload.get("side"))

    return "\n".join(
        line
        for line in [
            title,
            "",
            f"Монета: {payload.get('asset') or original_payload.get('asset') or 'n/a'}",
            f"Сторона исходного сигнала: {side}",
            f"Исполнено: {_pct(payload.get('executed_percent'))}",
            f"Результат: {_signed_pct(payload.get('result_percent'))}",
            f"Цена входа: {_price(payload.get('price_start') or original_payload.get('price'))}",
            f"Цена выхода: {_price(payload.get('price_end'))}",
            f"Размер: {_amount(payload.get('executed_amount_asset'))} / {_amount(payload.get('total_amount_asset'))}",
            f"TwapId: {payload.get('twap_id', 'n/a')}",
            f"Статус: {payload.get('status', 'n/a')}",
            f"User: {payload.get('user_address') or original_payload.get('user_address') or 'n/a'}",
        ]
        if line is not None
    )


def _side(value: object) -> str:
    if value == "buy":
        return "Покупка"
    if value == "sell":
        return "Продажа"
    return "n/a"


def _usd(value: object) -> str:
    if value is None:
        return "n/a"
    number = float(value)
    if abs(number) >= 1_000_000_000:
        return f"${number / 1_000_000_000:.2f}B"
    if abs(number) >= 1_000_000:
        return f"${number / 1_000_000:.2f}M"
    if abs(number) >= 1_000:
        return f"${number / 1_000:.2f}K"
    return f"${number:.2f}"


def _minutes(value: object) -> str:
    if value is None:
        return "n/a"
    minutes = float(value)
    if minutes >= 60 and minutes % 60 == 0:
        return f"{minutes / 60:.0f} ч"
    return f"{minutes:g} мин"


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value):g}%"


def _signed_pct(value: object) -> str:
    if value is None:
        return "n/a"
    number = float(value)
    return f"{number:+g}%"


def _price(value: object) -> str:
    return "n/a" if value is None else f"${float(value):g}"


def _amount(value: object) -> str:
    return "n/a" if value is None else f"{float(value):g}"


def _value(value: object) -> str:
    return "n/a" if value is None else str(value)
