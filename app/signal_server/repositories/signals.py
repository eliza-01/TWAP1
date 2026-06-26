from __future__ import annotations

import json
from typing import Any

from app.db.connection import db_cursor


class SignalRepository:
    def list_pending(self, after_id: int = 0, limit: int = 100, include_rejected: bool = False) -> list[dict[str, Any]]:
        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT
                    ts.id AS signal_id,
                    ts.kind,
                    ts.group_name,
                    ts.asset,
                    ts.side,
                    ts.amount_usd,
                    ts.duration_minutes,
                    ts.price,
                    ts.market_volume_usd,
                    ts.twap_share_percent,
                    ts.score,
                    ts.user_address,
                    ts.twap_id,
                    ts.payload_json,
                    pm.status,
                    pm.reason,
                    pm.related_parsed_message_id,
                    orig_ts.id AS related_signal_id,
                    orig_ts.asset AS original_asset,
                    orig_ts.side AS original_side,
                    orig_ts.twap_id AS original_twap_id,
                    orig_ts.payload_json AS original_payload_json,
                    im.telegram_chat_id,
                    im.telegram_thread_id,
                    im.telegram_message_id,
                    im.message_date,
                    ts.created_at
                FROM twap_signals ts
                JOIN parsed_messages pm ON pm.id = ts.parsed_message_id
                JOIN incoming_messages im ON im.id = pm.incoming_message_id
                LEFT JOIN twap_signals orig_ts ON orig_ts.parsed_message_id = pm.related_parsed_message_id
                WHERE ts.id > %s
                  AND ts.kind IN ('twap_created', 'twap_result')
                  AND (pm.status = 'accepted' OR (%s AND pm.status = 'rejected' AND ts.kind = 'twap_created'))
                ORDER BY ts.id ASC
                LIMIT %s
                """,
                (after_id, include_rejected, limit),
            )
            rows = cursor.fetchall()
        return [_normalize(row) for row in rows]


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    payload = _json_load(row.pop("payload_json", None))
    original_payload = _json_load(row.pop("original_payload_json", None))
    kind = row.get("kind")
    asset = row.get("asset") or row.get("original_asset") or original_payload.get("asset")
    side = row.get("side") or row.get("original_side") or original_payload.get("side")

    out = {
        "signal_id": int(row.get("signal_id") or 0),
        "kind": kind,
        "source": row.get("group_name"),
        "group_name": row.get("group_name"),
        "status": row.get("status"),
        "reason": row.get("reason"),
        "asset": asset,
        "symbol": _symbol(asset),
        "side": side,
        "amount_usd": _float_or_none(row.get("amount_usd") or original_payload.get("amount_usd")),
        "duration_minutes": _float_or_none(row.get("duration_minutes") or original_payload.get("duration_minutes")),
        "price": _float_or_none(row.get("price") or payload.get("price") or original_payload.get("price")),
        "market_volume_usd": _float_or_none(row.get("market_volume_usd") or original_payload.get("market_volume_usd")),
        "twap_share_percent": _float_or_none(row.get("twap_share_percent") or original_payload.get("twap_share_percent")),
        "score": _float_or_none(row.get("score") or original_payload.get("score")),
        "user_address": row.get("user_address") or original_payload.get("user_address"),
        "twap_id": row.get("twap_id") or payload.get("twap_id") or row.get("original_twap_id"),
        "related_signal_id": row.get("related_signal_id"),
        "related_parsed_message_id": row.get("related_parsed_message_id"),
        "original": {
            "asset": row.get("original_asset") or original_payload.get("asset"),
            "symbol": _symbol(row.get("original_asset") or original_payload.get("asset")),
            "side": row.get("original_side") or original_payload.get("side"),
            "twap_id": row.get("original_twap_id") or original_payload.get("twap_id"),
            "payload": original_payload,
        },
        "telegram": {
            "chat_id": row.get("telegram_chat_id"),
            "thread_id": row.get("telegram_thread_id"),
            "message_id": row.get("telegram_message_id"),
        },
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        "message_date": row.get("message_date").isoformat() if row.get("message_date") else None,
        "payload": payload,
    }
    return out


def _json_load(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _symbol(asset: Any) -> str | None:
    if not asset:
        return None
    text = str(asset).upper()
    return text if text.endswith("_USDT") else f"{text}_USDT"
