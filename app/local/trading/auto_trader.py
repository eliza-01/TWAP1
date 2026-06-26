from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.exchanges.core.errors import ExchangeError
from app.exchanges.core.types import CloseOrderRequest, OpenOrderRequest
from app.exchanges.registry import get_exchange
from app.local.settings.store import LocalSettingsStore
from app.local.trading.log_store import LocalTradeStore

logger = logging.getLogger(__name__)


class LocalAutoTrader:
    def __init__(self, settings_store: LocalSettingsStore, trade_store: LocalTradeStore) -> None:
        self.settings_store = settings_store
        self.trade_store = trade_store

    async def handle_signal(self, signal: dict[str, Any]) -> None:
        signal_id = _signal_id(signal)
        if self.trade_store.is_signal_processed(signal_id):
            return

        settings = self.settings_store.load()
        if not settings.trading.auto_trading_enabled:
            return

        if _is_before_enabled_at(signal, settings.trading.auto_trading_enabled_at):
            self.trade_store.mark_signal_processed(signal_id)
            self.trade_store.add_log("info", "skip_old_signal", "Старый сигнал пропущен после включения автоторговли", signal)
            return

        kind = str(signal.get("kind") or "twap_created")
        try:
            if kind == "twap_created":
                await self._open_from_signal(signal)
            elif kind == "twap_result":
                await self._close_from_signal(signal)
            else:
                self.trade_store.add_log("info", "skip_signal_kind", f"Неподдержанный тип сигнала: {kind}", signal)
        except Exception as exc:
            self.trade_store.add_log("error", "auto_trade_error", f"Ошибка автоторговли: {exc}", signal)
            logger.exception("Auto trade failed: signal=%s", signal.get("signal_id"))
        finally:
            self.trade_store.mark_signal_processed(signal_id)

    async def _open_from_signal(self, signal: dict[str, Any]) -> None:
        settings = self.settings_store.load()
        adapter = get_exchange(settings, settings.selected_exchange)

        symbol = _signal_symbol(signal)
        direction = _direction_from_signal(signal)
        rules = await adapter.trading_rules(symbol)

        if settings.trading.use_min_volume:
            volume = rules.min_volume
            leverage = 1
        else:
            volume = settings.trading.default_volume
            leverage = settings.trading.default_leverage

        request = OpenOrderRequest(
            symbol=symbol,
            direction=direction,
            volume=volume,
            leverage=leverage,
            open_type=1,  # isolated margin
        )

        try:
            result = await adapter.open_position(request)
        except ExchangeError as exc:
            self.trade_store.add_log("error", "open_failed", f"Не удалось открыть {symbol}: {exc}", signal)
            logger.warning("Auto open failed: signal=%s symbol=%s error=%s", signal.get("signal_id"), symbol, exc)
            return

        trade = {
            "trade_key": _trade_key(signal),
            "open_signal_id": signal.get("signal_id"),
            "twap_id": signal.get("twap_id"),
            "user_address": signal.get("user_address"),
            "exchange": settings.selected_exchange,
            "symbol": symbol,
            "direction": direction,
            "volume": volume,
            "leverage": leverage,
            "open_type": 1,
            "open_order_id": result.order_id,
            "open_raw": result.raw,
        }
        saved = self.trade_store.add_open_trade(trade)
        self.trade_store.add_log(
            "success",
            "opened",
            f"Открыта {direction} сделка {symbol}, volume={volume}, leverage={leverage}x, isolated",
            signal,
            saved,
            result.raw,
        )

    async def _close_from_signal(self, signal: dict[str, Any]) -> None:
        settings = self.settings_store.load()
        adapter = get_exchange(settings, settings.selected_exchange)
        trade = self.trade_store.find_open_for_signal(signal)
        if not trade:
            self.trade_store.add_log("warning", "close_not_found", "Не найдена открытая сделка для закрывающего сигнала", signal)
            return

        request = CloseOrderRequest(
            symbol=str(trade.get("symbol") or ""),
            direction="short" if trade.get("direction") == "short" else "long",
            volume=float(trade.get("volume") or 0),
            open_type=1,  # isolated margin
        )

        try:
            result = await adapter.close_position(request)
        except ExchangeError as exc:
            self.trade_store.add_log("error", "close_failed", f"Не удалось закрыть {trade.get('symbol')}: {exc}", signal, trade)
            logger.warning("Auto close failed: signal=%s trade=%s error=%s", signal.get("signal_id"), trade.get("trade_key"), exc)
            return

        closed = self.trade_store.close_trade(
            str(trade.get("trade_key")),
            {
                "close_signal_id": signal.get("signal_id"),
                "close_order_id": result.order_id,
                "close_raw": result.raw,
            },
        )
        self.trade_store.add_log(
            "success",
            "closed",
            f"Закрыта {trade.get('direction')} сделка {trade.get('symbol')}, volume={trade.get('volume')}",
            signal,
            closed or trade,
            result.raw,
        )


def _signal_id(signal: dict[str, Any]) -> int | None:
    value = signal.get("signal_id") or signal.get("id")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _signal_symbol(signal: dict[str, Any]) -> str:
    symbol = signal.get("symbol") or _symbol(signal.get("asset"))
    if not symbol:
        raise ExchangeError("Сигнал без символа")
    return str(symbol).upper()


def _symbol(asset: Any) -> str | None:
    if not asset:
        return None
    text = str(asset).upper()
    return text if text.endswith("_USDT") else f"{text}_USDT"


def _direction_from_signal(signal: dict[str, Any]) -> str:
    side = str(signal.get("side") or signal.get("original_side") or "").lower()
    return "long" if side == "buy" else "short"


def _trade_key(signal: dict[str, Any]) -> str:
    signal_id = signal.get("signal_id") or signal.get("id")
    if signal_id:
        return f"signal:{signal_id}"

    twap_id = signal.get("twap_id")
    if twap_id:
        return f"twap:{twap_id}"

    telegram = signal.get("telegram") if isinstance(signal.get("telegram"), dict) else {}
    if telegram.get("chat_id") and telegram.get("message_id"):
        return f"tg:{telegram.get('chat_id')}:{telegram.get('message_id')}"

    return f"raw:{datetime.now(timezone.utc).timestamp()}"


def _is_before_enabled_at(signal: dict[str, Any], enabled_at: str) -> bool:
    if not enabled_at:
        return False
    signal_time = signal.get("created_at") or signal.get("message_date")
    if not signal_time:
        return False
    try:
        signal_dt = datetime.fromisoformat(str(signal_time).replace("Z", "+00:00"))
        enabled_dt = datetime.fromisoformat(enabled_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if signal_dt.tzinfo is None:
        signal_dt = signal_dt.replace(tzinfo=timezone.utc)
    if enabled_dt.tzinfo is None:
        enabled_dt = enabled_dt.replace(tzinfo=timezone.utc)
    return signal_dt < enabled_dt
