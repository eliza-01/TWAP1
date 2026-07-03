from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP
from typing import Any

from app.exchanges.binance.client import BinanceApiError, BinanceFuturesClient
from app.exchanges.binance.constants import (
    ACCOUNT_BALANCE,
    BOOK_TICKER,
    CHANGE_LEVERAGE,
    CHANGE_MARGIN_TYPE,
    EXCHANGE_INFO,
    LEVERAGE_BRACKET,
    NEW_ORDER,
    POSITION_MODE,
    POSITION_RISK,
)
from app.exchanges.core.base import ExchangeAdapter
from app.exchanges.core.errors import ExchangeDisabledError, ExchangeNotConfiguredError, ExchangeRequestError
from app.exchanges.core.types import (
    Balance,
    CloseOrderRequest,
    ConnectionStatus,
    ExchangeConfig,
    FuturesAsset,
    NotionalRounding,
    OpenOrderRequest,
    OrderResult,
    Position,
    TradingRules,
)


class BinanceAdapter(ExchangeAdapter):
    name = "binance"
    title = "Binance USDⓈ-M Futures"

    def __init__(self, config: ExchangeConfig) -> None:
        self.config = config
        self.client = BinanceFuturesClient(config.credentials.api_key, config.credentials.secret_key)

    async def status(self) -> ConnectionStatus:
        if not self.config.enabled:
            return ConnectionStatus("disabled", "Биржа отключена в локальных настройках")
        if not self.config.credentials.api_key or not self.config.credentials.secret_key:
            return ConnectionStatus("not_configured", "Не указаны Binance API key и Secret key")
        try:
            await self.client.public_get(BOOK_TICKER, {"symbol": "BTCUSDT"})
            await self.client.signed_get(ACCOUNT_BALANCE)
            return ConnectionStatus("connected", "Подключение к Binance Futures активно")
        except Exception as exc:
            return ConnectionStatus("error", str(exc))

    async def balance(self, currency: str = "USDT") -> Balance:
        self._ensure_ready()
        items = await self.client.signed_get(ACCOUNT_BALANCE)
        for item in _list(items):
            if str(item.get("asset") or "").upper() == currency.upper():
                wallet = _float(item.get("balance"))
                cross_unpnl = _float(item.get("crossUnPnl"))
                return Balance(
                    currency=currency.upper(),
                    available=_float(item.get("availableBalance")),
                    equity=wallet + cross_unpnl,
                    raw=item,
                )
        return Balance(currency=currency.upper(), available=0.0, equity=0.0, raw={"items": items})

    async def futures_assets(self) -> list[FuturesAsset]:
        data = await self.client.public_get(EXCHANGE_INFO)
        assets: list[FuturesAsset] = []
        for item in _list(data.get("symbols") if isinstance(data, dict) else []):
            if str(item.get("status") or "") != "TRADING":
                continue
            if str(item.get("contractType") or "") != "PERPETUAL":
                continue
            if str(item.get("marginAsset") or "").upper() != "USDT":
                continue
            symbol = str(item.get("symbol") or "")
            if not symbol:
                continue
            lot = _filter(item, "MARKET_LOT_SIZE") or _filter(item, "LOT_SIZE")
            min_leverage, max_leverage = 1, 125
            assets.append(
                FuturesAsset(
                    symbol=symbol,
                    display_name=f"{item.get('baseAsset')}/{item.get('quoteAsset')}",
                    base_coin=item.get("baseAsset"),
                    quote_coin=item.get("quoteAsset"),
                    min_vol=_maybe_float(lot.get("minQty") if lot else None),
                    max_vol=_maybe_float(lot.get("maxQty") if lot else None),
                    vol_unit=_maybe_float(lot.get("stepSize") if lot else None),
                    contract_size=1.0,
                    min_leverage=min_leverage,
                    max_leverage=max_leverage,
                    raw=item,
                )
            )
        return sorted(assets, key=lambda asset: asset.symbol)

    async def trading_rules(self, symbol: str) -> TradingRules:
        self._ensure_ready()
        normalized = _normalize_symbol(symbol)
        contract = await self._symbol_info(normalized)
        ticker = await self.client.public_get(BOOK_TICKER, {"symbol": normalized})
        price = _ticker_price(ticker, "buy")
        lot = _filter(contract, "MARKET_LOT_SIZE") or _filter(contract, "LOT_SIZE")
        price_filter = _filter(contract, "PRICE_FILTER")
        min_notional_filter = _filter(contract, "MIN_NOTIONAL")
        bracket = await self._leverage_bracket(normalized)
        min_leverage, max_leverage = _leverage_range(bracket)

        min_volume = _maybe_float(lot.get("minQty") if lot else None) or 0.0
        max_volume = _maybe_float(lot.get("maxQty") if lot else None)
        volume_step = _maybe_float(lot.get("stepSize") if lot else None)
        min_notional = _maybe_float(min_notional_filter.get("notional") if min_notional_filter else None)
        calculated_min_notional = _min_notional(min_volume, 1.0, price)

        return TradingRules(
            symbol=normalized,
            min_volume=min_volume,
            max_volume=max_volume,
            volume_step=volume_step,
            contract_size=1.0,
            min_leverage=min_leverage,
            max_leverage=max_leverage,
            price=price,
            min_notional_usdt=max(_not_none(min_notional), _not_none(calculated_min_notional)) or None,
            raw={"contract": contract, "ticker": ticker, "price_filter": price_filter, "leverage_bracket": bracket},
        )

    async def positions(self, symbol: str | None = None) -> list[Position]:
        self._ensure_ready()
        params = {"symbol": _normalize_symbol(symbol)} if symbol else None
        data = await self.client.signed_get(POSITION_RISK, params)
        positions: list[Position] = []
        for item in _list(data):
            amount = _float(item.get("positionAmt"))
            if amount == 0:
                continue
            position_side = str(item.get("positionSide") or "BOTH").upper()
            direction = "long" if position_side == "LONG" or (position_side == "BOTH" and amount > 0) else "short"
            positions.append(
                Position(
                    symbol=str(item.get("symbol") or ""),
                    direction=direction,
                    volume=abs(amount),
                    entry_price=_maybe_float(item.get("entryPrice")),
                    pnl=_maybe_float(item.get("unRealizedProfit")),
                    position_id=None,
                    raw=item,
                )
            )
        return positions

    async def open_position(self, request: OpenOrderRequest) -> OrderResult:
        self._ensure_ready()
        symbol = _normalize_symbol(request.symbol)
        contract = await self._symbol_info(symbol)
        ticker = await self.client.public_get(BOOK_TICKER, {"symbol": symbol})
        raw_price = _ticker_price(ticker, _trade_price_side(request.direction, is_close=False))
        volume = _order_volume(request.volume, request.amount_usdt, request.notional_rounding, contract, symbol, raw_price)
        leverage = await self._prepare_symbol(symbol, request.leverage)
        hedge_mode = await self._hedge_mode()

        payload: dict[str, Any] = {
            "symbol": symbol,
            "side": "BUY" if request.direction == "long" else "SELL",
            "type": "MARKET",
            "quantity": _plain_decimal(_decimal(volume)),
            "newClientOrderId": f"local_{int(time.time() * 1000)}",
            "newOrderRespType": "RESULT",
        }
        if hedge_mode:
            payload["positionSide"] = "LONG" if request.direction == "long" else "SHORT"

        data = await self.client.signed_post(NEW_ORDER, payload)
        order_id = str(data.get("orderId") or "") if isinstance(data, dict) else ""
        return OrderResult(
            True,
            "Ордер открытия отправлен",
            order_id or None,
            {"request": payload, "meta": _order_meta(request.amount_usdt, request.notional_rounding, volume, contract, raw_price, leverage), "response": data},
        )

    async def close_position(self, request: CloseOrderRequest) -> OrderResult:
        self._ensure_ready()
        symbol = _normalize_symbol(request.symbol)
        positions = await self.positions(symbol)
        target = _find_close_target(positions, request)
        contract = await self._symbol_info(symbol)
        ticker = await self.client.public_get(BOOK_TICKER, {"symbol": symbol})
        raw_price = _ticker_price(ticker, _trade_price_side(request.direction, is_close=True))
        volume = _close_order_volume(request, target, contract, symbol, raw_price)
        hedge_mode = await self._hedge_mode()

        payload: dict[str, Any] = {
            "symbol": symbol,
            "side": "SELL" if request.direction == "long" else "BUY",
            "type": "MARKET",
            "quantity": _plain_decimal(_decimal(volume)),
            "newClientOrderId": f"local_close_{int(time.time() * 1000)}",
            "newOrderRespType": "RESULT",
        }
        if hedge_mode:
            payload["positionSide"] = "LONG" if request.direction == "long" else "SHORT"
        else:
            payload["reduceOnly"] = "true"

        data = await self.client.signed_post(NEW_ORDER, payload)
        order_id = str(data.get("orderId") or "") if isinstance(data, dict) else ""
        return OrderResult(
            True,
            "Ордер закрытия отправлен",
            order_id or None,
            {"request": payload, "meta": _order_meta(request.amount_usdt, request.notional_rounding, volume, contract, raw_price, None), "response": data},
        )

    async def _symbol_info(self, symbol: str) -> dict[str, Any]:
        data = await self.client.public_get(EXCHANGE_INFO)
        for item in _list(data.get("symbols") if isinstance(data, dict) else []):
            if str(item.get("symbol") or "").upper() == symbol:
                return item
        raise ExchangeRequestError(f"Binance не вернула параметры контракта {symbol}")

    async def _leverage_bracket(self, symbol: str) -> dict[str, Any]:
        data = await self.client.signed_get(LEVERAGE_BRACKET, {"symbol": symbol})
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        raise ExchangeRequestError(f"Binance не вернула лимиты плеча для {symbol}")


    async def _hedge_mode(self) -> bool:
        data = await self.client.signed_get(POSITION_MODE)
        if not isinstance(data, dict):
            raise ExchangeRequestError("Binance не вернула режим позиций")
        return bool(data.get("dualSidePosition"))

    async def _prepare_symbol(self, symbol: str, leverage: int) -> int:
        contract = await self._symbol_info(symbol)
        bracket = await self._leverage_bracket(symbol)
        min_leverage, max_leverage = _leverage_range(bracket)
        normalized_leverage = _normalize_leverage(leverage, min_leverage, max_leverage, symbol)
        await self._ensure_isolated(symbol)
        await self.client.signed_post(CHANGE_LEVERAGE, {"symbol": symbol, "leverage": normalized_leverage})
        return normalized_leverage

    async def _ensure_isolated(self, symbol: str) -> None:
        try:
            await self.client.signed_post(CHANGE_MARGIN_TYPE, {"symbol": symbol, "marginType": "ISOLATED"})
        except BinanceApiError as exc:
            if exc.code == -4046:
                return
            raise

    def _ensure_ready(self) -> None:
        if not self.config.enabled:
            raise ExchangeDisabledError("Binance отключена")
        if not self.config.credentials.api_key or not self.config.credentials.secret_key:
            raise ExchangeNotConfiguredError("Не указаны Binance API key и Secret key")


def _list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _filter(contract: dict[str, Any], filter_type: str) -> dict[str, Any]:
    for item in _list(contract.get("filters")):
        if str(item.get("filterType") or "") == filter_type:
            return item
    return {}


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _maybe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_symbol(symbol: str | None) -> str:
    clean = (symbol or "").strip().upper().replace("/", "").replace("_", "").replace("-", "")
    if not clean:
        raise ExchangeRequestError("Не указан futures-символ")
    return clean


def _trade_price_side(direction: str, is_close: bool) -> str:
    if (direction == "long" and not is_close) or (direction == "short" and is_close):
        return "buy"
    return "sell"


def _ticker_price(data: dict[str, Any], side: str) -> float:
    priority = ["askPrice", "lastPrice", "markPrice", "indexPrice"] if side == "buy" else ["bidPrice", "lastPrice", "markPrice", "indexPrice"]
    for key in priority:
        price = _maybe_float(data.get(key))
        if price and price > 0:
            return price
    raise ExchangeRequestError("Не удалось получить текущую цену Binance")


def _normalize_price(price: float, contract: dict[str, Any]) -> float | int:
    price_filter = _filter(contract, "PRICE_FILTER")
    step = _decimal(price_filter.get("tickSize") or 0)
    scale = _scale_from_step(step, fallback=8)
    value = _round_to_step(_decimal(price), step, ROUND_DOWN)
    if value <= 0:
        raise ExchangeRequestError("Binance вернула некорректную цену контракта")
    return _json_number(value, scale)


def _normalize_volume(
    volume: float | Decimal,
    contract: dict[str, Any],
    symbol: str,
    rounding: NotionalRounding = "down",
    clamp_to_min: bool = False,
) -> float | int:
    raw = _decimal(volume)
    if raw <= 0:
        raise ExchangeRequestError("Объем должен быть больше 0")

    lot = _filter(contract, "MARKET_LOT_SIZE") or _filter(contract, "LOT_SIZE")
    min_qty = _decimal(lot.get("minQty") or 0)
    max_qty = _decimal(lot.get("maxQty") or 0)
    step = _decimal(lot.get("stepSize") or 0)
    scale = _scale_from_step(step, fallback=8)

    if min_qty > 0 and raw < min_qty:
        if not clamp_to_min:
            raise ExchangeRequestError(f"Минимальный объем для {symbol}: {_plain_decimal(min_qty)}")
        raw = min_qty
    if max_qty > 0 and raw > max_qty:
        raise ExchangeRequestError(f"Максимальный объем для {symbol}: {_plain_decimal(max_qty)}")

    value = _round_to_step(raw, step, ROUND_UP if rounding == "up" else ROUND_DOWN)
    if value <= 0 or (min_qty > 0 and value < min_qty):
        raise ExchangeRequestError(f"Объем должен быть кратен {_plain_decimal(step)} и не меньше {_plain_decimal(min_qty)}")
    if max_qty > 0 and value > max_qty:
        raise ExchangeRequestError(f"Максимальный объем для {symbol}: {_plain_decimal(max_qty)}")
    return _json_number(value, scale)


def _order_volume(
    volume: float | None,
    amount_usdt: float | None,
    notional_rounding: NotionalRounding,
    contract: dict[str, Any],
    symbol: str,
    price: float,
) -> float | int:
    if amount_usdt is not None and amount_usdt > 0:
        return _volume_from_notional(amount_usdt, contract, symbol, price, notional_rounding)
    return _normalize_volume(volume or 0, contract, symbol)


def _close_order_volume(
    request: CloseOrderRequest,
    target: Position,
    contract: dict[str, Any],
    symbol: str,
    price: float,
) -> float | int:
    if request.amount_usdt is not None and request.amount_usdt > 0:
        requested = _decimal(_volume_from_notional(request.amount_usdt, contract, symbol, price, request.notional_rounding))
        held = _decimal(target.volume)
        if held > 0 and requested > held:
            requested = held
        return _normalize_volume(requested, contract, symbol)
    return _normalize_volume(request.volume or target.volume, contract, symbol)


def _volume_from_notional(
    amount_usdt: float,
    contract: dict[str, Any],
    symbol: str,
    price: float,
    rounding: NotionalRounding = "down",
) -> float | int:
    notional = _decimal(amount_usdt)
    if notional <= 0:
        raise ExchangeRequestError("Объем сделки должен быть больше 0 USDT")

    price_value = _decimal(price)
    if price_value <= 0:
        raise ExchangeRequestError(f"Нет текущей цены для {symbol}")

    raw_volume = notional / (price_value * _contract_size(contract))
    return _normalize_volume(raw_volume, contract, symbol, rounding, clamp_to_min=True)


def _order_meta(
    amount_usdt: float | None,
    notional_rounding: NotionalRounding,
    volume: float | int,
    contract: dict[str, Any],
    price: float,
    leverage: int | None,
) -> dict[str, Any]:
    rounded_amount = _decimal(volume) * _decimal(price) * _contract_size(contract)
    return {
        "requested_amount_usdt": amount_usdt,
        "notional_rounding": notional_rounding,
        "rounded_amount_usdt": _json_number(rounded_amount, 8),
        "contract_size": _json_number(_contract_size(contract), 12),
        "leverage": leverage,
    }


def _leverage_range(bracket: dict[str, Any] | None) -> tuple[int, int]:
    values: list[int] = []
    if isinstance(bracket, dict):
        for item in _list(bracket.get("brackets")):
            try:
                value = int(item.get("initialLeverage"))
            except (TypeError, ValueError):
                continue
            if value > 0:
                values.append(value)
    return 1, max(values) if values else 125


def _normalize_leverage(leverage: int, min_leverage: int, max_leverage: int, symbol: str) -> int:
    value = int(leverage or min_leverage)
    if value < min_leverage or value > max_leverage:
        raise ExchangeRequestError(f"Плечо для {symbol}: от {min_leverage}x до {max_leverage}x")
    return value


def _contract_size(contract: dict[str, Any]) -> Decimal:
    return Decimal("1")


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _round_to_step(value: Decimal, step: Decimal, rounding: str) -> Decimal:
    if step <= 0:
        return value
    return (value / step).to_integral_value(rounding=rounding) * step


def _scale_from_step(step: Decimal, fallback: int) -> int:
    if step <= 0:
        return fallback
    return max(0, -step.normalize().as_tuple().exponent)


def _json_number(value: Decimal, scale: int) -> float | int:
    if scale == 0:
        return int(value.to_integral_value(rounding=ROUND_DOWN))
    quantized = value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_DOWN)
    return float(quantized)


def _plain_decimal(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


def _find_close_target(positions: list[Position], request: CloseOrderRequest) -> Position:
    symbol = _normalize_symbol(request.symbol)
    for position in positions:
        if _normalize_symbol(position.symbol) == symbol and position.direction == request.direction:
            return position
    raise ExchangeRequestError(f"Не найдена открытая {request.direction} позиция по {symbol}")


def _min_notional(min_volume: float, contract_size: float | None, price: float | None) -> float | None:
    if not min_volume or not price:
        return None
    multiplier = contract_size if contract_size and contract_size > 0 else 1
    return min_volume * multiplier * price


def _not_none(value: float | None) -> float:
    return value if value is not None else 0.0
