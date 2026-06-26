from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

DEFAULT_TRADES_PATH = "local_data/trades.json"


class LocalTradeStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.getenv("LOCAL_TRADES_PATH") or DEFAULT_TRADES_PATH)

    def list_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        data = self._read()
        logs = data.get("logs") if isinstance(data.get("logs"), list) else []
        return [item for item in logs if isinstance(item, dict)][-limit:][::-1]

    def list_open_trades(self) -> list[dict[str, Any]]:
        trades = self._trades()
        return [trade for trade in trades if trade.get("status") == "open"]

    def add_log(
        self,
        level: str,
        action: str,
        message: str,
        signal: dict[str, Any] | None = None,
        trade: dict[str, Any] | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        data = self._read()
        logs = data.setdefault("logs", [])
        logs.append(
            {
                "time": _now(),
                "level": level,
                "action": action,
                "message": message,
                "signal_id": _signal_id(signal),
                "signal_kind": (signal or {}).get("kind"),
                "symbol": (signal or {}).get("symbol") or (trade or {}).get("symbol"),
                "trade_key": (trade or {}).get("trade_key"),
                "raw": raw or {},
            }
        )
        data["logs"] = logs[-1000:]
        self._write(data)

    def is_signal_processed(self, signal_id: int | None) -> bool:
        if not signal_id:
            return False
        processed = self._read().get("processed_signals")
        return signal_id in processed if isinstance(processed, list) else False

    def mark_signal_processed(self, signal_id: int | None) -> None:
        if not signal_id:
            return
        data = self._read()
        processed = data.setdefault("processed_signals", [])
        if signal_id not in processed:
            processed.append(signal_id)
        data["processed_signals"] = processed[-2000:]
        self._write(data)

    def add_open_trade(self, trade: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        trades = data.setdefault("trades", [])
        key = trade.get("trade_key")
        if key:
            for existing in trades:
                if existing.get("trade_key") == key and existing.get("status") == "open":
                    return existing
        trade.setdefault("opened_at", _now())
        trade.setdefault("status", "open")
        trades.append(trade)
        data["trades"] = trades[-1000:]
        self._write(data)
        return trade

    def close_trade(self, trade_key: str, close_data: dict[str, Any]) -> dict[str, Any] | None:
        data = self._read()
        trades = data.setdefault("trades", [])
        closed: dict[str, Any] | None = None
        for trade in trades:
            if trade.get("trade_key") == trade_key and trade.get("status") == "open":
                trade.update(close_data)
                trade["status"] = "closed"
                trade.setdefault("closed_at", _now())
                closed = trade
                break
        self._write(data)
        return closed

    def find_open_for_signal(self, signal: dict[str, Any]) -> dict[str, Any] | None:
        candidates = self.list_open_trades()
        related_signal_id = signal.get("related_signal_id")
        if related_signal_id:
            for trade in candidates:
                if int(trade.get("open_signal_id") or 0) == int(related_signal_id):
                    return trade

        twap_id = signal.get("twap_id") or signal.get("original_twap_id") or (signal.get("payload") or {}).get("twap_id")
        if twap_id:
            for trade in candidates:
                if str(trade.get("twap_id") or "") == str(twap_id):
                    return trade

        symbol = signal.get("symbol") or _symbol(signal.get("asset"))
        user_address = signal.get("user_address")
        if symbol:
            for trade in candidates:
                if trade.get("symbol") != symbol:
                    continue
                if user_address and trade.get("user_address") and user_address != trade.get("user_address"):
                    continue
                return trade

        return None

    def _trades(self) -> list[dict[str, Any]]:
        data = self._read()
        trades = data.get("trades")
        return [item for item in trades if isinstance(item, dict)] if isinstance(trades, list) else []

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"trades": [], "logs": [], "processed_signals": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"trades": [], "logs": [], "processed_signals": []}
        return data if isinstance(data, dict) else {"trades": [], "logs": [], "processed_signals": []}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(self.path.parent)) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        tmp_path.replace(self.path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _signal_id(signal: dict[str, Any] | None) -> int | None:
    if not signal:
        return None
    value = signal.get("signal_id") or signal.get("id")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _symbol(asset: Any) -> str | None:
    if not asset:
        return None
    text = str(asset).upper()
    return text if text.endswith("_USDT") else f"{text}_USDT"
