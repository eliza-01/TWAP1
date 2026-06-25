from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

from app.shared.types import FilterConfig, ParseResult

DEBUG_PREFIX = "🛠 TWAPx debug"


@dataclass(frozen=True)
class DebugContext:
    group_name: str
    parser_key: str
    chat_id: int
    thread_id: int | None
    message_id: int
    reply_to_message_id: int | None
    message_text: str = ""
    filters: FilterConfig | None = None
    incoming_id: int | None = None
    parsed_id: int | None = None
    forwarded_message_id: int | None = None
    related_message_found: bool | None = None
    target_error: str | None = None
    action: str = "processed"


def should_send_debug(status: str, send_skipped: bool) -> bool:
    if status == "skipped" and not send_skipped:
        return False
    return status in {"accepted", "rejected", "error", "skipped"}


def is_debug_message(text: str) -> bool:
    return text.strip().startswith(DEBUG_PREFIX)


def format_debug_result(result: ParseResult, ctx: DebugContext) -> str:
    payload = result.payload
    lines = [
        f"<b>{escape(DEBUG_PREFIX)}</b>",
        "",
        "<b>Цитата сигнала:</b>",
        _quote(ctx.message_text),
        "",
        f"<b>Реакция:</b> {_reaction(result.status)}",
        f"<b>{escape(_group_title(ctx.group_name))}</b> · <b>{escape(_asset(payload))}</b> · <i>{escape(_side(payload.get('side')))}</i> · <code>{escape(_price(payload.get('price')))}</code>",
    ]

    if result.kind == "twap_created":
        lines.extend(["", "<b>Результат фильтрации:</b>", *_filter_lines(payload, ctx.filters)])
    elif result.kind == "twap_result":
        lines.extend(["", "<b>Результат TWAP:</b>", *_result_lines(payload, ctx)])
    else:
        lines.extend(["", f"<b>Тип:</b> <code>{escape(result.kind)}</code>"])

    details = _details(result, ctx)
    if details:
        lines.extend(["", *details])

    return "\n".join(lines)


def format_debug_runtime_error(ctx: DebugContext, error: Exception) -> str:
    return "\n".join(
        [
            f"<b>{escape(DEBUG_PREFIX)}</b>",
            "",
            "<b>Цитата сигнала:</b>",
            _quote(ctx.message_text),
            "",
            "<b>Реакция:</b> ⚠️ <b>error</b>",
            f"<b>{escape(_group_title(ctx.group_name))}</b> · <b>n/a</b> · <i>n/a</i> · <code>n/a</code>",
            "",
            "<b>Ошибка обработки:</b>",
            f"<code>{escape(type(error).__name__)}: {escape(str(error))}</code>",
            "",
            _source_line(ctx),
        ]
    )


def _filter_lines(payload: dict[str, Any], filters: FilterConfig | None) -> list[str]:
    return [
        _filter_line(
            "Объем TWAP",
            payload.get("amount_usd"),
            lambda value: filters is not None and value >= filters.min_usd,
            _usd,
        ),
        _filter_line(
            "Время исполнения",
            payload.get("duration_minutes"),
            lambda value: filters is not None and value <= filters.max_duration_minutes,
            _duration,
        ),
        _filter_line(
            "Объем рынка",
            payload.get("market_volume_usd"),
            lambda value: filters is not None and value < filters.max_market_volume_usd,
            _usd,
        ),
        _filter_line(
            "Доля TWAP в рынке",
            payload.get("twap_share_percent"),
            lambda value: filters is not None and value > filters.min_twap_share_percent,
            _percent,
        ),
    ]


def _filter_line(title: str, value: object, check, formatter) -> str:
    if value is None:
        return f"{escape(title)} — <b>n/a</b> ❌"
    number = float(value)
    return f"{escape(title)} — <b>{escape(formatter(number))}</b> {'✅' if check(number) else '❌'}"


def _result_lines(payload: dict[str, Any], ctx: DebugContext) -> list[str]:
    result_type = payload.get("result_type")
    title = "Отмена" if result_type == "cancelled" else "Завершение"
    lines = [
        f"Событие — <b>{escape(title)}</b>",
        f"Исполнено — <b>{escape(_percent(payload.get('executed_percent')))}</b>",
        f"Результат — <b>{escape(_signed_percent(payload.get('result_percent')))}</b>",
        f"Цена входа — <code>{escape(_price(payload.get('price_start')))}</code>",
        f"Цена выхода — <code>{escape(_price(payload.get('price_end')))}</code>",
    ]
    if payload.get("twap_id") is not None:
        lines.append(f"TwapId — <code>{escape(str(payload['twap_id']))}</code>")
    if ctx.related_message_found is not None:
        lines.append(f"Связан с принятым сигналом — <b>{'да' if ctx.related_message_found else 'нет'}</b>")
    return lines


def _details(result: ParseResult, ctx: DebugContext) -> list[str]:
    lines: list[str] = []
    if result.reason and result.reason not in {"parsed", "filter_passed"}:
        lines.extend(["<b>Причина:</b>", *_reason_lines(result.reason)])
    lines.append(_target_line(result, ctx))
    lines.append(_source_line(ctx))
    return lines


def _target_line(result: ParseResult, ctx: DebugContext) -> str:
    if ctx.target_error:
        return f"<b>Target:</b> ❌ ошибка отправки — <code>{escape(ctx.target_error)}</code>"
    if ctx.forwarded_message_id is not None:
        return f"<b>Target:</b> ✅ отправлено, msg <code>{ctx.forwarded_message_id}</code>"
    if result.kind == "twap_created" and result.status == "rejected":
        return "<b>Target:</b> не отправлено — не прошёл фильтр"
    if result.kind == "twap_result" and ctx.related_message_found is False:
        return "<b>Target:</b> не отправлено — не найден принятый исходный сигнал"
    if result.status in {"error", "skipped"}:
        return "<b>Target:</b> не отправлено"
    return "<b>Target:</b> не отправлено"


def _source_line(ctx: DebugContext) -> str:
    return (
        "<b>Источник:</b> "
        f"chat <code>{ctx.chat_id}</code>, "
        f"thread <code>{escape(_empty(ctx.thread_id))}</code>, "
        f"msg <code>{ctx.message_id}</code>"
    )


def _reason_lines(reason: str) -> list[str]:
    return [f"- {escape(item)}" for item in _human_reasons(reason)]


def _human_reasons(reason: str) -> list[str]:
    mapping = {
        "missing_amount_usd": "не найден объем TWAP",
        "missing_duration_minutes": "не найдено время исполнения",
        "missing_market_volume_usd": "не найден объем рынка",
        "missing_twap_share_percent": "не найдена доля TWAP в рынке",
        "unsupported_message": "сообщение не похоже на TWAP-сигнал",
        "empty_message": "пустое сообщение",
        "parse_exception": "ошибка парсинга",
    }
    parts: list[str] = []
    for item in reason.split(";"):
        item = item.strip()
        if item.startswith("amount_usd_lt_"):
            parts.append(f"объем TWAP меньше {_usd(_tail_float(item))}")
        elif item.startswith("duration_gt_"):
            parts.append(f"время исполнения больше {_duration(_tail_float(item))}")
        elif item.startswith("market_volume_gte_"):
            parts.append(f"объем рынка не меньше {_usd(_tail_float(item))}")
        elif item.startswith("twap_share_lte_"):
            parts.append(f"доля TWAP не больше {_percent(_tail_float(item))}")
        else:
            parts.append(mapping.get(item, item))
    return parts


def _tail_float(value: str) -> float:
    for part in reversed(value.split("_")):
        try:
            return float(part)
        except ValueError:
            continue
    return 0.0


def _quote(text: str) -> str:
    clean = "\n".join(line.strip() for line in text.strip().splitlines() if line.strip())
    if not clean:
        return "<blockquote>n/a</blockquote>"
    if len(clean) > 420:
        clean = clean[:417].rstrip() + "..."
    quoted = "\n".join(escape(line) for line in clean.splitlines()[:8])
    return f"<blockquote>{quoted}</blockquote>"


def _reaction(status: str) -> str:
    return {
        "accepted": "✅ <b>accepted</b>",
        "rejected": "❌ <b>rejected</b>",
        "error": "⚠️ <b>error</b>",
        "skipped": "⏭ <b>skipped</b>",
    }.get(status, escape(status))


def _group_title(value: str) -> str:
    return value.upper() if value else "n/a"


def _asset(payload: dict[str, Any]) -> str:
    return str(payload.get("asset") or "n/a")


def _side(value: object) -> str:
    if value == "buy":
        return "покупка"
    if value == "sell":
        return "продажа"
    return "n/a"


def _usd(value: object) -> str:
    if value is None:
        return "n/a"
    number = float(value)
    abs_number = abs(number)
    if abs_number >= 1_000_000_000:
        return f"${number / 1_000_000_000:.2f}B"
    if abs_number >= 1_000_000:
        return f"${number / 1_000_000:.2f}M"
    if abs_number >= 1_000:
        return f"${number / 1_000:.2f}K"
    return f"${number:.2f}"


def _duration(value: object) -> str:
    if value is None:
        return "n/a"
    minutes = float(value)
    if minutes >= 60:
        hours = minutes / 60
        if hours == 1:
            return "1 час"
        return f"{hours:g} часа"
    return f"{minutes:g} минут"


def _percent(value: object) -> str:
    return "n/a" if value is None else f"{float(value):g}%"


def _signed_percent(value: object) -> str:
    return "n/a" if value is None else f"{float(value):+g}%"


def _price(value: object) -> str:
    return "n/a" if value is None else f"${float(value):g}"


def _empty(value: object) -> str:
    return "n/a" if value is None else str(value)
