from __future__ import annotationsimport loggingimport mathfrom dataclasses import dataclassfrom datetime import datetime, timezonefrom typing import Anyfrom app.exchanges.core.errors import ExchangeErrorfrom app.exchanges.core.types import CloseOrderRequest, OpenOrderRequest, TradingRulesfrom app.exchanges.registry import get_exchangefrom app.local.settings.model import LocalSettingsfrom app.local.settings.store import LocalSettingsStorefrom app.local.trading.log_store import LocalTradeStorelogger = logging.getLogger(__name__)_MARGIN_SAFETY = 0.98@dataclass(frozen=True)class OpenPlan:    volume: float    leverage: int    target_order_usdt: float    estimated_margin_usdt: float    notional_usdt: float    price: float    contract_size: float    auto_leverage_used: bool    min_volume_used: bool    available_margin_usdt: float

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
        status = str(signal.get("status") or "accepted")
        if kind == "twap_created" and status != "accepted":
            if settings.trading.disable_signal_filters:
                self.trade_store.add_log(
                    "warning",
                    "filter_disabled",
                    f"Фильтр сигналов отключен: вход по status={status}, reason={signal.get('reason') or 'n/a'}",
                    signal,
                )
            elif _should_bypass_min_usd_by_share(settings, signal):
                share = _signal_share_percent(signal)
                threshold = settings.trading.min_usd_override_twap_share_percent
                self.trade_store.add_log(
                    "warning",
                    "min_usd_bypassed_by_share",
                    f"TWAPX_MIN_USD проигнорирован: TWAP share={_fmt(share)}% > {_fmt(threshold)}%",
                    signal,
                )
            else:
                self.trade_store.add_log(
                    "info",
                    "skip_filtered_signal",
                    f"Сигнал пропущен фильтром: status={status}, reason={signal.get('reason') or 'n/a'}",
                    signal,
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
            f"Закрыта {trade.get('direction')} сделка {trade.get('symbol')}, volume={trade.get('volume')}, margin≈{_fmt(trade.get('estimated_margin_usdt'))} USDT",
            signal,
            closed or trade,
            result.raw,
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

