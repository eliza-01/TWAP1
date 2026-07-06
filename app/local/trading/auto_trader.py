from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.exchanges.core.errors import ExchangeError
from app.exchanges.core.types import CloseOrderRequest, OpenOrderRequest, TradingRules
from app.exchanges.registry import get_exchange
from app.local.settings.model import LocalSettings
from app.local.settings.store import LocalSettingsStore
from app.local.trading.fallback_reports import FallbackCloseReportRepository
from app.local.trading.log_store import LocalTradeStore

logger = logging.getLogger(__name__)

_MARGIN_SAFETY = 0.98
_FALLBACK_RETRY_SECONDS = 15.0


@dataclass(frozen=True)
class OpenPlan:
    volume: float
    leverage: int
    target_order_usdt: float
    estimated_margin_usdt: float
    notional_usdt: float
    price: float
    contract_size: float
    auto_leverage_used: bool
    min_volume_used: bool
    available_margin_usdt: float


class LocalAutoTrader:
    def __init__(
        self,
        settings_store: LocalSettingsStore,
        trade_store: LocalTradeStore,
        fallback_reports: FallbackCloseReportRepository | None = None,
    ) -> None:
        self.settings_store = settings_store
        self.trade_store = trade_store
        self.fallback_reports = fallback_reports or FallbackCloseReportRepository()
        self._lock = asyncio.Lock()
        self._started_at = datetime.now(timezone.utc)
        self._startup_old_signal_log_written = False
        self._duplicate_signal_log_ids: set[int] = set()

    def reset_signal_runtime_state_on_startup(
        self,
        started_at: datetime | None = None,
        local_recent_signals_cleared: int = 0,
    ) -> dict[str, Any]:
        startup_at = (started_at or self._started_at).astimezone(timezone.utc)
        self._started_at = startup_at
        self._startup_old_signal_log_written = False
        self._duplicate_signal_log_ids.clear()
        started_at_iso = startup_at.isoformat()

        reset_method = getattr(self.trade_store, "reset_signal_state_on_startup", None)
        reset_summary = (
            reset_method(started_at_iso, clear_logs=True)
            if callable(reset_method)
            else {"processed_signals_cleared": 0, "logs_cleared": 0, "started_at": started_at_iso}
        )
        reset_summary["local_recent_signals_cleared"] = local_recent_signals_cleared

        self.trade_store.add_log(
            "warning",
            "startup_signal_state_reset",
            "Софт запущен с чистого листа: локальная память сигналов очищена, старые signal_id больше не влияют на новый запуск",
            raw=reset_summary,
        )
        logger.warning(
            "Startup fresh state: cleared local signal memory processed=%s recent=%s logs=%s",
            reset_summary.get("processed_signals_cleared"),
            local_recent_signals_cleared,
            reset_summary.get("logs_cleared"),
        )
        return reset_summary

    def ignore_existing_open_trades_on_startup(self, started_at: datetime | None = None) -> int:
        startup_at = (started_at or self._started_at).astimezone(timezone.utc)
        self._started_at = startup_at
        started_at_iso = startup_at.isoformat()

        ignore_method = getattr(self.trade_store, "ignore_open_trades_on_startup", None)
        if not callable(ignore_method):
            return 0

        ignored_count = int(ignore_method(started_at_iso))
        if ignored_count <= 0:
            return 0

        self.trade_store.add_log(
            "warning",
            "startup_fresh_state",
            f"Софт запущен с чистого листа: старые open-сделки ({ignored_count}) помечены как ignored_on_startup и не будут обслуживаться страховкой.",
            raw={"ignored_count": ignored_count, "started_at": started_at_iso},
        )
        logger.warning("Startup fresh state: ignored old open trades=%s", ignored_count)
        return ignored_count

    def log_signal_skipped_before_startup(self, signal: dict[str, Any]) -> None:
        signal_id = _signal_id(signal)
        if self.trade_store.is_signal_processed(signal_id):
            return
        self.trade_store.mark_signal_processed(signal_id)
        self.trade_store.add_log(
            "info",
            "skip_signal_before_startup",
            "Сигнал получен, но создан до запуска local-клиента: старт с чистого листа, сделка не открыта",
            signal,
        )

    async def handle_signal(self, signal: dict[str, Any]) -> None:
        async with self._lock:
            await self._handle_signal_locked(signal)

    async def check_fallback_closures(self) -> None:
        async with self._lock:
            await self._check_fallback_closures_locked()

    async def _handle_signal_locked(self, signal: dict[str, Any]) -> None:
        signal_id = _signal_id(signal)

        if self.trade_store.is_signal_processed(signal_id):
            if signal_id and signal_id not in self._duplicate_signal_log_ids:
                self._duplicate_signal_log_ids.add(signal_id)
                self.trade_store.add_log(
                    "info",
                    "skip_duplicate_signal",
                    "Повторный сигнал уже был обработан ранее, сделка повторно не открывается",
                    signal,
                )
            return

        settings = self.settings_store.load()

        if not settings.trading.auto_trading_enabled:
            self.trade_store.mark_signal_processed(signal_id)
            self.trade_store.add_log(
                "warning",
                "auto_trading_disabled",
                "Сигнал получен, но автоторговля выключена в локальных настройках: сделка не открыта",
                signal,
            )
            return

        if _is_before_dt(signal, self._started_at):
            self.trade_store.mark_signal_processed(signal_id)
            if not self._startup_old_signal_log_written:
                self._startup_old_signal_log_written = True
                self.trade_store.add_log(
                    "info",
                    "skip_signal_before_startup",
                    "Сигналы, созданные до запуска софта, пропускаются: старт с чистого листа",
                    signal,
                )
            return

        if _is_before_enabled_at(signal, settings.trading.auto_trading_enabled_at):
            self.trade_store.mark_signal_processed(signal_id)
            self.trade_store.add_log("info", "skip_old_signal", "Старый сигнал пропущен после включения автоторговли", signal)
            return

        kind = str(signal.get("kind") or "twap_created")
        status = str(signal.get("status") or "accepted")

        if kind == "twap_created" and status != "accepted":
            if settings.trading.disable_signal_filters:
                self.trade_store.add_log(
                    "warning",
                    "server_filter_ignored",
                    f"Серверный status/reason проигнорирован: вход по status={status}, reason={signal.get('reason') or 'n/a'}",
                    signal,
                )
            elif _should_bypass_min_usd_by_share(settings, signal):
                share = _signal_share_percent(signal)
                threshold = settings.trading.min_usd_override_twap_share_percent
                self.trade_store.add_log(
                    "warning",
                    "min_usd_bypassed_by_share",
                    f"Минимальный USD проигнорирован: TWAP share={_fmt(share)}% > {_fmt(threshold)}%",
                    signal,
                )
            else:
                self.trade_store.add_log(
                    "info",
                    "skip_server_filtered_signal",
                    f"Сигнал пропущен серверным статусом: status={status}, reason={signal.get('reason') or 'n/a'}",
                    signal,
                )
                self.trade_store.mark_signal_processed(signal_id)
                return

        if kind == "twap_created":
            local_filter_errors = _local_filter_errors(settings, signal)
            if local_filter_errors:
                if _should_bypass_local_min_usd_by_share(settings, signal, local_filter_errors):
                    share = _signal_share_percent(signal)
                    threshold = settings.trading.min_usd_override_twap_share_percent
                    self.trade_store.add_log(
                        "warning",
                        "local_min_usd_bypassed_by_share",
                        f"Локальный min USD проигнорирован: TWAP share={_fmt(share)}% > {_fmt(threshold)}%",
                        signal,
                        raw={"local_filter_errors": local_filter_errors},
                    )
                else:
                    self.trade_store.add_log(
                        "info",
                        "skip_local_filtered_signal",
                        "Сигнал пропущен локальными фильтрами: " + ";".join(local_filter_errors),
                        signal,
                        raw={"local_filter_errors": local_filter_errors},
                    )
                    self.trade_store.mark_signal_processed(signal_id)
                    return

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

        try:
            plan = await _build_open_plan(settings, adapter, symbol, rules)
        except ExchangeError as exc:
            self.trade_store.add_log("warning", "open_skipped", f"Сделка {symbol} не открыта: {exc}", signal)
            logger.warning("Auto open skipped: signal=%s symbol=%s error=%s", signal.get("signal_id"), symbol, exc)
            return

        request = OpenOrderRequest(
            symbol=symbol,
            direction=direction,
            volume=plan.volume,
            leverage=plan.leverage,
            amount_usdt=plan.target_order_usdt,
            notional_rounding="up" if plan.min_volume_used else "down",
            open_type=1,
        )

        try:
            result = await adapter.open_position(request)
        except ExchangeError as exc:
            self.trade_store.add_log("error", "open_failed", f"Не удалось открыть {symbol}: {exc}", signal)
            logger.warning("Auto open failed: signal=%s symbol=%s error=%s", signal.get("signal_id"), symbol, exc)
            return

        timing = _fallback_timing(signal, settings.trading.fallback_close_grace_seconds)
        trade = {
            "trade_key": _trade_key(signal),
            "open_signal_id": signal.get("signal_id"),
            "twap_id": signal.get("twap_id"),
            "user_address": signal.get("user_address"),
            "exchange": settings.selected_exchange,
            "symbol": symbol,
            "direction": direction,
            "volume": plan.volume,
            "leverage": plan.leverage,
            "open_type": 1,
            "margin_mode": "isolated",
            "target_order_usdt": plan.target_order_usdt,
            "estimated_margin_usdt": plan.estimated_margin_usdt,
            "notional_usdt": plan.notional_usdt,
            "price": plan.price,
            "contract_size": plan.contract_size,
            "auto_leverage_used": plan.auto_leverage_used,
            "min_volume_used": plan.min_volume_used,
            "duration_minutes": _float_or_none(signal.get("duration_minutes")),
            "twap_started_at": timing.get("twap_started_at"),
            "twap_deadline_at": timing.get("twap_deadline_at"),
            "fallback_close_grace_seconds": settings.trading.fallback_close_grace_seconds,
            "fallback_close_enabled_at_open": settings.trading.fallback_close_enabled,
            "open_order_id": result.order_id,
            "open_raw": result.raw,
        }
        saved = self.trade_store.add_open_trade(trade)
        self.trade_store.add_log(
            "success",
            "opened",
            _open_message(direction, symbol, plan),
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
            open_type=1,
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
                "close_reason": "twap_result",
                "close_order_id": result.order_id,
                "close_raw": result.raw,
            },
        )
        self.trade_store.add_log(
            "success",
            "closed",
            f"Закрыта {trade.get('direction')} сделка {trade.get('symbol')}, volume={trade.get('volume')}, margin≈{_fmt(trade.get('estimated_margin_usdt'))} USDT",
            signal,
            closed or trade,
            result.raw,
        )

    async def _check_fallback_closures_locked(self) -> None:
        settings = self.settings_store.load()
        if not settings.trading.fallback_close_enabled:
            return

        now = datetime.now(timezone.utc)
        grace_seconds = float(settings.trading.fallback_close_grace_seconds or 0)

        for trade in self.trade_store.list_open_trades():
            due_at = _fallback_due_at(trade, grace_seconds)
            trade_key = str(trade.get("trade_key") or "")
            if not trade_key or due_at is None:
                self._log_missing_fallback_timing_once(trade)
                continue
            if now < due_at:
                continue
            if not _can_retry_fallback(trade, now):
                continue
            await self._fallback_close_trade(settings, trade, due_at, grace_seconds)

    def _log_missing_fallback_timing_once(self, trade: dict[str, Any]) -> None:
        trade_key = str(trade.get("trade_key") or "")
        if not trade_key or trade.get("fallback_timing_warning_logged"):
            return
        updated = self.trade_store.update_open_trade(trade_key, {"fallback_timing_warning_logged": True})
        self.trade_store.add_log(
            "warning",
            "fallback_no_duration",
            "Страховка не может рассчитать дедлайн: у сделки нет duration_minutes / twap_deadline_at",
            trade=updated or trade,
        )

    async def _fallback_close_trade(
        self,
        settings: LocalSettings,
        trade: dict[str, Any],
        due_at: datetime,
        grace_seconds: float,
    ) -> None:
        adapter = get_exchange(settings, settings.selected_exchange)
        trade_key = str(trade.get("trade_key") or "")
        triggered_at = datetime.now(timezone.utc)
        self.trade_store.update_open_trade(
            trade_key,
            {
                "fallback_last_attempt_at": triggered_at.isoformat(),
                "fallback_attempt_count": int(trade.get("fallback_attempt_count") or 0) + 1,
            },
        )

        request = CloseOrderRequest(
            symbol=str(trade.get("symbol") or ""),
            direction="short" if trade.get("direction") == "short" else "long",
            volume=float(trade.get("volume") or 0),
            open_type=int(trade.get("open_type") or 1),
        )

        report_base = _fallback_report_base(trade, due_at, triggered_at, grace_seconds)

        try:
            result = await adapter.close_position(request)
        except ExchangeError as exc:
            message = f"Страховка не смогла закрыть {trade.get('symbol')}: {exc}"
            report = {**report_base, "status": "error", "message": message, "error": str(exc)}
            report_id = self.fallback_reports.save(report)
            self.trade_store.add_log("error", "fallback_close_failed", message, trade=trade, raw={"report_id": report_id})
            logger.warning("Fallback close failed: trade=%s error=%s", trade_key, exc)
            return

        closed = self.trade_store.close_trade(
            trade_key,
            {
                "close_reason": "fallback_twap_timeout",
                "fallback_closed_at": triggered_at.isoformat(),
                "fallback_due_at": due_at.isoformat(),
                "fallback_grace_seconds": grace_seconds,
                "close_order_id": result.order_id,
                "close_raw": result.raw,
            },
        )
        message = (
            f"Страховка закрыла {trade.get('direction')} сделку {trade.get('symbol')}: "
            f"TWAP duration истёк, уведомления о закрытии не было {grace_seconds:g} сек."
        )
        report = {
            **report_base,
            "status": "success",
            "message": message,
            "close_order_id": result.order_id,
            "response": result.raw,
        }
        report_id = self.fallback_reports.save(report)
        self.trade_store.add_log(
            "success",
            "fallback_closed",
            message,
            trade=closed or trade,
            raw={"report_id": report_id, "response": result.raw},
        )


async def _build_open_plan(settings: LocalSettings, adapter: Any, symbol: str, rules: TradingRules) -> OpenPlan:
    price = float(rules.price or 0)
    if price <= 0:
        raise ExchangeError(f"Нет текущей цены для {symbol}")

    contract_size = float(rules.contract_size or 1)
    if contract_size <= 0:
        contract_size = 1

    min_volume = float(rules.min_volume or 0)
    if min_volume <= 0:
        raise ExchangeError(f"Binance не вернула минимальный объем для {symbol}")

    balance = await adapter.balance("USDT")
    available = float(balance.available or 0)
    spendable = available * _MARGIN_SAFETY
    if spendable <= 0:
        raise ExchangeError("Нет доступной USDT-маржи")

    if settings.trading.use_min_volume:
        notional = _min_notional(rules, min_volume, price, contract_size)
        margin = notional
        if margin > spendable:
            raise ExchangeError(f"Недостаточно маржи для min volume: нужно ≈{_fmt(margin)} USDT, доступно ≈{_fmt(available)} USDT")
        return OpenPlan(
            volume=notional / (price * contract_size),
            leverage=1,
            target_order_usdt=notional,
            estimated_margin_usdt=margin,
            notional_usdt=notional,
            price=price,
            contract_size=contract_size,
            auto_leverage_used=False,
            min_volume_used=True,
            available_margin_usdt=available,
        )

    base_leverage = _clamp_int(settings.trading.default_leverage, rules.min_leverage, rules.max_leverage)
    max_auto_leverage = _clamp_int(settings.trading.max_auto_leverage, rules.min_leverage, rules.max_leverage)
    target_notional = float(settings.trading.auto_order_usdt or 0)
    if target_notional <= 0:
        raise ExchangeError("Объем сделки должен быть больше 0 USDT")

    min_notional = _min_notional(rules, min_volume, price, contract_size)
    min_volume_used = False
    if target_notional <= min_notional:
        target_notional = min_notional
        min_volume_used = True

    leverage = base_leverage
    margin_required = target_notional / leverage
    auto_used = False

    if margin_required > spendable:
        if not settings.trading.auto_leverage_enabled:
            raise ExchangeError(f"Недостаточно маржи: нужно ≈{_fmt(margin_required)} USDT, доступно ≈{_fmt(available)} USDT")
        required = math.ceil(target_notional / spendable)
        leverage = max(base_leverage, required, int(rules.min_leverage or 1))
        max_allowed = max_auto_leverage or int(rules.max_leverage or leverage)
        if leverage > max_allowed:
            raise ExchangeError(
                f"Недостаточно маржи даже с авто-плечом: нужно {leverage}x, максимум {max_allowed}x"
            )
        margin_required = target_notional / leverage
        auto_used = leverage != base_leverage

    if margin_required > spendable:
        raise ExchangeError(f"Недостаточно маржи: нужно ≈{_fmt(margin_required)} USDT, доступно ≈{_fmt(available)} USDT")

    volume = target_notional / (price * contract_size)
    if min_volume_used and volume < min_volume:
        volume = min_volume
    if rules.max_volume and volume > rules.max_volume:
        raise ExchangeError(f"Расчетный объем {volume:g} выше максимального {rules.max_volume:g} для {symbol}")

    return OpenPlan(
        volume=volume,
        leverage=leverage,
        target_order_usdt=target_notional,
        estimated_margin_usdt=margin_required,
        notional_usdt=target_notional,
        price=price,
        contract_size=contract_size,
        auto_leverage_used=auto_used,
        min_volume_used=min_volume_used,
        available_margin_usdt=available,
    )




def _local_filter_errors(settings: LocalSettings, signal: dict[str, Any]) -> list[str]:
    filters = getattr(settings.trading, "signal_filters", None)
    if filters is None or not getattr(filters, "enabled", True):
        return []

    errors: list[str] = []
    amount_usd = _signal_float(signal, "amount_usd")
    duration_minutes = _signal_float(signal, "duration_minutes")
    market_volume_usd = _signal_float(signal, "market_volume_usd")
    share = _signal_share_percent(signal)

    min_usd = float(getattr(filters, "min_usd", 0) or 0)
    max_duration = float(getattr(filters, "max_duration_minutes", 0) or 0)
    max_market_volume = float(getattr(filters, "max_market_volume_usd", 0) or 0)
    min_share = float(getattr(filters, "min_twap_share_percent", 0) or 0)

    if amount_usd is None:
        errors.append("missing_amount_usd")
    elif min_usd > 0 and amount_usd < min_usd:
        errors.append(f"amount_usd_lt_{min_usd:g}")

    if duration_minutes is None:
        errors.append("missing_duration_minutes")
    elif max_duration > 0 and duration_minutes > max_duration:
        errors.append(f"duration_gt_{max_duration:g}_minutes")

    if market_volume_usd is None:
        errors.append("missing_market_volume_usd")
    elif max_market_volume > 0 and market_volume_usd >= max_market_volume:
        errors.append(f"market_volume_gte_{max_market_volume:g}")

    if share is None:
        errors.append("missing_twap_share_percent")
    elif min_share > 0 and share <= min_share:
        errors.append(f"twap_share_lte_{min_share:g}_percent")

    return errors


def _should_bypass_local_min_usd_by_share(
    settings: LocalSettings,
    signal: dict[str, Any],
    errors: list[str],
) -> bool:
    if not settings.trading.ignore_min_usd_by_market_share:
        return False
    if not errors or not any(error.startswith("amount_usd_lt_") for error in errors):
        return False
    hard_errors = [error for error in errors if not error.startswith("amount_usd_lt_")]
    if hard_errors:
        return False
    threshold = float(settings.trading.min_usd_override_twap_share_percent or 0)
    if threshold <= 0:
        return False
    share = _signal_share_percent(signal)
    return share is not None and share > threshold


def _signal_float(signal: dict[str, Any], key: str) -> float | None:
    value = signal.get(key)
    if value is None and isinstance(signal.get("payload"), dict):
        value = signal["payload"].get(key)
    return _float_or_none(value)

def _should_bypass_min_usd_by_share(settings: LocalSettings, signal: dict[str, Any]) -> bool:
    if not settings.trading.ignore_min_usd_by_market_share:
        return False

    reasons = _signal_reasons(signal)
    if not reasons or not any(reason.startswith("amount_usd_lt_") for reason in reasons):
        return False

    hard_reasons = [reason for reason in reasons if not reason.startswith("amount_usd_lt_")]
    if hard_reasons:
        return False

    threshold = float(settings.trading.min_usd_override_twap_share_percent or 0)
    if threshold <= 0:
        return False

    share = _signal_share_percent(signal)
    return share is not None and share > threshold


def _signal_reasons(signal: dict[str, Any]) -> list[str]:
    reason = str(signal.get("reason") or "")
    return [item.strip() for item in reason.split(";") if item.strip()]


def _signal_share_percent(signal: dict[str, Any]) -> float | None:
    value = signal.get("twap_share_percent")
    if value is None and isinstance(signal.get("payload"), dict):
        value = signal["payload"].get("twap_share_percent")
    return _float_or_none(value)


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


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
    clean = str(symbol).upper().replace("/", "").replace("_", "").replace("-", "")
    return clean


def _symbol(asset: Any) -> str | None:
    if not asset:
        return None
    text = str(asset).upper()
    clean = text.replace("/", "").replace("_", "").replace("-", "")
    return clean if clean.endswith("USDT") else f"{clean}USDT"


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

    enabled_dt = _parse_dt(enabled_at)
    if enabled_dt is None:
        return False

    return _is_before_dt(signal, enabled_dt)


def _is_before_dt(signal: dict[str, Any], boundary: datetime) -> bool:
    signal_time = signal.get("created_at") or signal.get("message_date")
    signal_dt = _parse_dt(signal_time)
    if signal_dt is None:
        return False

    return signal_dt < boundary.astimezone(timezone.utc)


def _fallback_timing(signal: dict[str, Any], grace_seconds: float) -> dict[str, str | None]:
    started_at = _signal_started_at(signal)
    duration_minutes = _float_or_none(signal.get("duration_minutes"))
    if duration_minutes is None and isinstance(signal.get("payload"), dict):
        duration_minutes = _float_or_none(signal["payload"].get("duration_minutes"))
    if started_at is None or duration_minutes is None or duration_minutes <= 0:
        return {"twap_started_at": _iso(started_at), "twap_deadline_at": None, "fallback_due_at": None}

    deadline = started_at + timedelta(minutes=duration_minutes)
    due_at = deadline + timedelta(seconds=max(float(grace_seconds or 0), 0.0))
    return {
        "twap_started_at": _iso(started_at),
        "twap_deadline_at": _iso(deadline),
        "fallback_due_at": _iso(due_at),
    }


def _signal_started_at(signal: dict[str, Any]) -> datetime | None:
    for key in ("message_date", "created_at"):
        value = signal.get(key)
        parsed = _parse_dt(value)
        if parsed is not None:
            return parsed
    return None


def _fallback_due_at(trade: dict[str, Any], grace_seconds: float) -> datetime | None:
    explicit = _parse_dt(trade.get("twap_deadline_at"))
    if explicit is not None:
        return explicit + timedelta(seconds=max(float(grace_seconds or 0), 0.0))

    started_at = _parse_dt(trade.get("twap_started_at")) or _parse_dt(trade.get("opened_at"))
    duration_minutes = _float_or_none(trade.get("duration_minutes"))
    if started_at is None or duration_minutes is None or duration_minutes <= 0:
        return None
    return started_at + timedelta(minutes=duration_minutes, seconds=max(float(grace_seconds or 0), 0.0))


def _can_retry_fallback(trade: dict[str, Any], now: datetime) -> bool:
    last_attempt = _parse_dt(trade.get("fallback_last_attempt_at"))
    if last_attempt is None:
        return True
    return (now - last_attempt).total_seconds() >= _FALLBACK_RETRY_SECONDS


def _fallback_report_base(
    trade: dict[str, Any],
    due_at: datetime,
    triggered_at: datetime,
    grace_seconds: float,
) -> dict[str, Any]:
    return {
        "trade_key": trade.get("trade_key"),
        "open_signal_id": trade.get("open_signal_id"),
        "twap_id": trade.get("twap_id"),
        "symbol": trade.get("symbol"),
        "direction": trade.get("direction"),
        "opened_at": trade.get("opened_at"),
        "twap_started_at": trade.get("twap_started_at"),
        "twap_deadline_at": trade.get("twap_deadline_at"),
        "fallback_due_at": due_at.isoformat(),
        "grace_seconds": grace_seconds,
        "triggered_at": triggered_at.isoformat(),
        "duration_minutes": trade.get("duration_minutes"),
        "volume": trade.get("volume"),
        "leverage": trade.get("leverage"),
        "notional_usdt": trade.get("notional_usdt"),
        "estimated_margin_usdt": trade.get("estimated_margin_usdt"),
    }


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _notional(volume: float, price: float, contract_size: float) -> float:
    return volume * price * contract_size


def _min_notional(rules: TradingRules, min_volume: float, price: float, contract_size: float) -> float:
    return max(
        _notional(min_volume, price, contract_size),
        float(rules.min_notional_usdt or 0),
    )


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    low = int(minimum or 1)
    high = int(maximum or low)
    parsed = int(value or low)
    return max(low, min(parsed, high))


def _open_message(direction: str, symbol: str, plan: OpenPlan) -> str:
    suffix: list[str] = []
    if plan.auto_leverage_used:
        suffix.append("авто-плечо")
    if plan.min_volume_used:
        suffix.append("min volume")
    tail = f" ({', '.join(suffix)})" if suffix else ""
    return (
        f"Открыта {direction} сделка {symbol}: volume≈{_fmt(plan.notional_usdt)} USDT, "
        f"margin≈{_fmt(plan.estimated_margin_usdt)} USDT, quantity={plan.volume:g}, "
        f"leverage={plan.leverage}x, isolated{tail}"
    )


def _fmt(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0.00"
