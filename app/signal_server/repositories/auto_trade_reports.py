from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.db.connection import db_cursor, json_dump


class AutoTradeReportRepository:
    def save_skip_report(self, session: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        report = _report_payload(session, payload)
        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                INSERT INTO auto_trade_skip_reports
                    (user_id, session_id, device_id, device_name, reason_code,
                     symbol, asset, side, signal_id, twap_id, message,
                     signal_created_at, report_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON))
                """,
                (
                    _int_or_none(session.get("user_id")),
                    _int_or_none(session.get("session_id")),
                    str(session.get("device_id") or "")[:128],
                    str(session.get("device_name") or "")[:255],
                    str(report.get("reason_code") or "")[:64],
                    str(report.get("symbol") or "")[:32],
                    str(report.get("asset") or "")[:32] or None,
                    str(report.get("side") or "")[:16] or None,
                    _int_or_none(report.get("signal_id")),
                    _int_or_none(report.get("twap_id")),
                    str(report.get("message") or ""),
                    _dt(report.get("signal_created_at")),
                    json_dump(report),
                ),
            )
            report_id = int(cursor.lastrowid)
        return {"success": True, "id": report_id, "report": report}

    def list_skip_reports(self, session: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        user_id = _int_or_none(session.get("user_id"))
        if user_id is None:
            return []
        safe_limit = max(1, min(int(limit or 100), 500))
        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    user_id,
                    session_id,
                    device_id,
                    device_name,
                    reason_code,
                    symbol,
                    asset,
                    side,
                    signal_id,
                    twap_id,
                    message,
                    signal_created_at,
                    report_json,
                    created_at
                FROM auto_trade_skip_reports
                WHERE user_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (user_id, safe_limit),
            )
            rows = cursor.fetchall()
        return [_normalize_row(row) for row in rows]


def _report_payload(session: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    signal = payload.get("signal") if isinstance(payload.get("signal"), dict) else {}
    symbol = _normalize_symbol(payload.get("symbol") or signal.get("symbol") or signal.get("asset"))
    return {
        "reason_code": str(payload.get("reason_code") or payload.get("reason") or "auto_trade_skipped")[:64],
        "symbol": symbol,
        "asset": str(payload.get("asset") or signal.get("asset") or "").strip().upper(),
        "side": str(payload.get("side") or signal.get("side") or "").strip().lower(),
        "signal_id": _first_present(payload.get("signal_id"), signal.get("signal_id"), signal.get("id")),
        "twap_id": _first_present(payload.get("twap_id"), signal.get("twap_id")),
        "message": str(payload.get("message") or "Сигнал автоторговли пропущен"),
        "signal_created_at": _first_present(payload.get("signal_created_at"), signal.get("created_at"), signal.get("message_date")),
        "client": {
            "user_id": session.get("user_id"),
            "session_id": session.get("session_id"),
            "device_id": session.get("device_id"),
            "device_name": session.get("device_name"),
            "login": session.get("login") or (session.get("user") or {}).get("login"),
        },
        "details": payload.get("details") if isinstance(payload.get("details"), dict) else {},
        "signal": signal,
    }


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in ("signal_created_at", "created_at"):
        value = out.get(key)
        if isinstance(value, datetime):
            out[key] = value.isoformat()
    out["report"] = _json_load(out.pop("report_json", None))
    return out


def _normalize_symbol(value: Any) -> str:
    clean = str(value or "").strip().upper().replace("/", "").replace("_", "").replace("-", "")
    if not clean:
        return ""
    return clean if clean.endswith("USDT") else f"{clean}USDT"


def _dt(value: Any) -> str | None:
    if value in (None, ""):
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


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
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
