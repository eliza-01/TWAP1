from __future__ import annotations

import re
from typing import Any

from app.shared.types import ParseResult

_START_EN_RE = re.compile(
    r"^\$(?P<usd>[\d.,]+)\s*(?P<suffix>[KMB])?\s+"
    r"(?P<side>buying|selling)\s+"
    r"(?P<asset>[A-Z0-9]+)\s+in\s+"
    r"(?P<duration>[\d.]+)\s+(?P<unit>minutes?|hours?)\s+(?P<emoji>[🟩🟥])",
    re.IGNORECASE,
)

_START_RU_RE = re.compile(
    r"^(?P<emoji>[🟩🟥])\s+\$(?P<usd>[\d.,]+)\s*(?P<suffix>[KMB])?\s+"
    r"(?P<side>покупка|продажа)\s+"
    r"(?P<asset>[A-Z0-9]+).*?в\s+течени[еи]\s+"
    r"(?P<duration>[\d.]+)\s+(?P<unit>минут[аы]?|час(?:а|ов)?)",
    re.IGNORECASE | re.DOTALL,
)

_RESULT_RU_RE = re.compile(r"^(✅|❌)\s+TWAP\s+(?P<label>заверш[её]н|отмен[её]н)", re.IGNORECASE)

_MONEY_RE = re.compile(r"\$\s*(?P<num>[\d.,]+)\s*(?P<suffix>[KMB])?", re.IGNORECASE)
_VOLUME_RE = re.compile(r"(?:Volume|Объем):\s*\$\s*(?P<volume>[\d.,]+)\s*(?P<suffix>[KMB])?\s*\((?P<share>[\d.,]+)%\)", re.IGNORECASE)
_SCORE_RE = re.compile(r"Score:\s*(?P<score>[\d.]+)", re.IGNORECASE)
_PRICE_RE = re.compile(r"(?:Price|Цена):\s*\$\s*(?P<price>[\d.,]+)", re.IGNORECASE)
_USER_RE = re.compile(r"(?:User|Субъект):\s*(?P<user>0x[a-fA-F0-9]+)")
_AMOUNT_RE = re.compile(r"Amount:\s*(?P<amount>[\d.,]+)\s+(?P<asset>[A-Z0-9]+)", re.IGNORECASE)
_CREATED_RE = re.compile(r"CreatedAt:\s*(?P<value>.+)", re.IGNORECASE)
_FINISHED_RE = re.compile(r"FinishedAt:\s*(?P<value>.+)", re.IGNORECASE)
_FUTURES_RE = re.compile(r"Futures:\s*(?P<value>.+)", re.IGNORECASE)
_FREQ_RE = re.compile(r"Frequency:\s*(?P<value>.+)", re.IGNORECASE)

_STATUS_RE = re.compile(r"Статус:\s*(?P<value>\w+)", re.IGNORECASE)
_EXECUTED_RE = re.compile(r"Исполнено:\s*(?P<value>[\d.,]+)%", re.IGNORECASE)
_SIZE_RE = re.compile(r"Размер:\s*(?P<done>[\d.,]+)\s*/\s*(?P<total>[\d.,]+)\s+(?P<asset>[A-Z0-9]+)", re.IGNORECASE)
_TWAP_ID_RE = re.compile(r"TwapId:\s*(?P<value>\d+)", re.IGNORECASE)
_PRICE_START_RE = re.compile(r"Цена\s+в\s+начале:\s*\$\s*(?P<value>[\d.,]+)", re.IGNORECASE)
_PRICE_END_RE = re.compile(r"Цена\s+в\s+конце:\s*\$\s*(?P<price>[\d.,]+)\s*(?P<emoji>[🟢🔴])?\s*\((?P<result>[+-]?[\d.,]+)%\)", re.IGNORECASE)


def parse(text: str) -> ParseResult:
    clean = text.strip()
    if not clean:
        return ParseResult.skipped("empty_message")

    try:
        created = _parse_created(clean)
        if created is not None:
            return created

        finished = _parse_result(clean)
        if finished is not None:
            return finished
    except Exception as exc:
        return ParseResult.error("parse_exception", {"error": str(exc), "text": clean})

    return ParseResult.skipped("unsupported_message")


def _parse_created(text: str) -> ParseResult | None:
    match = _START_EN_RE.search(text)
    lang = "en"
    if match is None:
        match = _START_RU_RE.search(text)
        lang = "ru"
    if match is None:
        return None

    side_raw = match.group("side").lower()
    payload: dict[str, Any] = {
        "language": lang,
        "asset": match.group("asset").upper(),
        "side": "buy" if side_raw in {"buying", "покупка"} else "sell",
        "direction_emoji": match.group("emoji"),
        "amount_usd": _money(match.group("usd"), match.group("suffix")),
        "duration_minutes": _duration_minutes(match.group("duration"), match.group("unit")),
    }

    volume = _VOLUME_RE.search(text)
    if volume:
        payload["market_volume_usd"] = _money(volume.group("volume"), volume.group("suffix"))
        payload["twap_share_percent"] = _num(volume.group("share"))

    for key, regex, cast in (
        ("score", _SCORE_RE, _num),
        ("price", _PRICE_RE, _num),
        ("user_address", _USER_RE, str),
    ):
        found = regex.search(text)
        if found:
            payload[key] = cast(found.group(list(found.groupdict().keys())[0]))

    amount = _AMOUNT_RE.search(text)
    if amount:
        payload["amount_asset"] = _num(amount.group("amount"))
        payload["amount_asset_symbol"] = amount.group("asset").upper()

    for key, regex in (
        ("created_at_text", _CREATED_RE),
        ("finished_at_text", _FINISHED_RE),
        ("futures", _FUTURES_RE),
        ("frequency", _FREQ_RE),
    ):
        found = regex.search(text)
        if found:
            payload[key] = found.group("value").strip()

    return ParseResult("twap_created", "accepted", "parsed", payload)


def _parse_result(text: str) -> ParseResult | None:
    result_header = _RESULT_RU_RE.search(text)
    if result_header is None:
        return None

    label = result_header.group("label").lower().replace("ё", "е")
    result_type = "cancelled" if label.startswith("отмен") else "finished"

    end = _PRICE_END_RE.search(text)
    result_percent = None
    result_emoji = None
    price_end = None
    if end:
        result_emoji = end.group("emoji")
        raw_result = abs(_num(end.group("result")))
        result_percent = raw_result if result_emoji == "🟢" else -raw_result
        price_end = _num(end.group("price"))

    size = _SIZE_RE.search(text)
    payload: dict[str, Any] = {
        "result_type": result_type,
        "status": _optional_group(_STATUS_RE, text),
        "executed_percent": _optional_num(_EXECUTED_RE, text),
        "twap_id": _optional_int(_TWAP_ID_RE, text),
        "user_address": _optional_group(_USER_RE, text),
        "price_start": _optional_num(_PRICE_START_RE, text),
        "price_end": price_end,
        "result_percent": result_percent,
        "result_emoji": result_emoji,
    }
    if size:
        payload.update(
            {
                "executed_amount_asset": _num(size.group("done")),
                "total_amount_asset": _num(size.group("total")),
                "asset": size.group("asset").upper(),
            }
        )

    return ParseResult("twap_result", "accepted", "parsed", {k: v for k, v in payload.items() if v is not None})


def _money(raw: str, suffix: str | None) -> float:
    value = _num(raw)
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    return value * multipliers.get((suffix or "").upper(), 1)


def _num(raw: str) -> float:
    return float(raw.replace(",", ""))


def _duration_minutes(raw: str, unit: str) -> float:
    value = _num(raw)
    normalized = unit.lower()
    if normalized.startswith("hour") or normalized.startswith("час"):
        return value * 60
    return value


def _optional_group(regex: re.Pattern[str], text: str) -> str | None:
    found = regex.search(text)
    if not found:
        return None
    return found.group(list(found.groupdict().keys())[0]).strip()


def _optional_num(regex: re.Pattern[str], text: str) -> float | None:
    raw = _optional_group(regex, text)
    return _num(raw) if raw else None


def _optional_int(regex: re.Pattern[str], text: str) -> int | None:
    raw = _optional_group(regex, text)
    return int(raw) if raw else None
