from __future__ import annotations

from app.shared.types import FilterConfig, ParseResult


def apply_filters(result: ParseResult, filters: FilterConfig) -> ParseResult:
    if result.status != "accepted" or result.kind != "twap_created":
        return result

    payload = result.payload
    errors: list[str] = []

    if _missing(payload, "amount_usd"):
        errors.append("missing_amount_usd")
    elif float(payload["amount_usd"]) < filters.min_usd:
        errors.append(f"amount_usd_lt_{filters.min_usd:g}")

    if _missing(payload, "duration_minutes"):
        errors.append("missing_duration_minutes")
    elif float(payload["duration_minutes"]) > filters.max_duration_minutes:
        errors.append(f"duration_gt_{filters.max_duration_minutes:g}_minutes")

    if _missing(payload, "market_volume_usd"):
        errors.append("missing_market_volume_usd")
    elif float(payload["market_volume_usd"]) >= filters.max_market_volume_usd:
        errors.append(f"market_volume_gte_{filters.max_market_volume_usd:g}")

    if _missing(payload, "twap_share_percent"):
        errors.append("missing_twap_share_percent")
    elif float(payload["twap_share_percent"]) <= filters.min_twap_share_percent:
        errors.append(f"twap_share_lte_{filters.min_twap_share_percent:g}_percent")

    if errors:
        return ParseResult(result.kind, "rejected", ";".join(errors), payload)

    return ParseResult(result.kind, "accepted", "filter_passed", payload)


def _missing(payload: dict, key: str) -> bool:
    return key not in payload or payload[key] is None
