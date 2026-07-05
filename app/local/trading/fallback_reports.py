from __future__ import annotations

import json
from datetime import datetime
from typing import Any


class FallbackCloseReportRepository:
    def save(self, report: dict[str, Any]) -> int | None:
        try:
            from app.db.connection import db_cursor, json_dump
        except ModuleNotFoundError:
            return None

        try:
            with db_cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    INSERT INTO fallback_close_reports
                        (trade_key, open_signal_id, twap_id, symbol, direction,
                         opened_at, twap_started_at, twap_deadline_at, grace_seconds,
                         triggered_at, close_order_id, status, message, report_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON))
                    """,
                    (
                        str(report.get("trade_key") or ""),
                        _int_or_none(report.get("open_signal_id")),
                        _int_or_none(report.get("twap_id")),
                        str(report.get("symbol") or ""),
                        str(report.get("direction") or ""),
                        _dt(report.get("opened_at")),
                        _dt(report.get("twap_started_at")),
                        _dt(report.get("twap_deadline_at")),
                        float(report.get("grace_seconds") or 0),
                        _dt(report.get("triggered_at")) or _dt(datetime.utcnow()),
                        str(report.get("close_order_id") or "") or None,
                        str(report.get("status") or ""),
                        str(report.get("message") or ""),
                        json_dump(report),
                    ),
                )
                return int(cursor.lastrowid)
        except RuntimeError:
            return None

    def list_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        try:
            from app.db.connection import db_cursor
        except ModuleNotFoundError:
            return []

        try:
            with db_cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        trade_key,
                        open_signal_id,
                        twap_id,
                        symbol,
                        direction,
                        opened_at,
                        twap_started_at,
                        twap_deadline_at,
                        grace_seconds,
                        triggered_at,
                        close_order_id,
                        status,
                        message,
                        report_json,
                        created_at
                    FROM fallback_close_reports
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (max(1, min(int(limit or 100), 500)),),
                )
                rows = cursor.fetchall()
        except RuntimeError:
            return []

        return [_normalize(row) for row in rows]


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in ("opened_at", "twap_started_at", "twap_deadline_at", "triggered_at", "created_at"):
        value = out.get(key)
        if isinstance(value, datetime):
            out[key] = value.isoformat()
    out["report"] = _json_load(out.pop("report_json", None))
    return out


def _dt(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


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
