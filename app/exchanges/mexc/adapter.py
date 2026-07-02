from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP, ROUND_UP
from typing import Any

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
from app.exchanges.mexc.client import MexcFuturesClient
from app.exchanges.mexc.constants import ACCOUNT_ASSET, CONTRACT_DETAIL, OPEN_POSITIONS, SUBMIT_ORDER, TICKER


class MexcAdapter(ExchangeAdapter):
    name = "mexc"
    title = "MEXC Futures"

    def __init__(self, config: ExchangeConfig) -> None:
        self.config = config
        self.client = MexcFuturesClient(config.credentials.auth_token)

    async def status(self) -> ConnectionStatus:
        if not self.config.enabled:
            return ConnectionStatus("disabled", "Биржа отключена в локальных настройках")
        if not self.config.credentials.auth_token:
            return ConnectionStatus("not_configured", "Не указан MEXC WEB token")
        try:
            await self.client.get(TICKER, {"symbol": "BTC_USDT"})
            await self.client.get(f"{ACCOUNT_ASSET}/USDT")
            return ConnectionStatus("connected", "Подключение к MEXC активно")
        except Exception as exc:
            return ConnectionStatus("error", str(exc))

    async def balance(self, currency: str = "USDT") -> Balance:
        self._ensure_ready()
        data = await self.client.get(f"{ACCOUNT_ASSET}/{currency}")
        raw = _data(data)
        return Balance(
            currency=currency,
            available=_float(raw.get("availableBalance")),
            equity=_float(raw.get("equity")),
            raw=raw,
        )

    async def futures_assets(self) -> list[FuturesAsset]:
        data = await self.client.get(CONTRACT_DETAIL)
        items = _list_data(data)
        assets: list[FuturesAsset] = []
        for item in items:
            symbol = str(item.get("symbol") or "")
            if not symbol:
                continue
            assets.append(
                FuturesAsset(
                    symbol=symbol,
                    display_name=symbol.replace("_", "/"),
                    base_coin=item.get("baseCoinName") or item.get("baseCoin"),
                    quote_coin=item.get("quoteCoinName") or item.get("quoteCoin"),
                    min_vol=_maybe_float(item.get("minVol")),
                    max_vol=_maybe_float(item.get("maxVol")),
                    vol_unit=_maybe_float(item.get("volUnit")),
                    contract_size=_maybe_float(item.get("contractSize")),
                    min_leverage=_maybe_int(item.get("minLeverage")),
                    max_leverage=_maybe_int(item.get("maxLeverage")),
                    raw=item,
                )
            )
        return sorted(assets, key=lambda asset: asset.symbol)

    async def trading_rules(self, symbol: str) -> TradingRules:
        self._ensure_ready()
        normalized = _normalize_symbol(symbol)
        contract = await self._contract_detail(normalized)
        ticker = await self.client.get(TICKER, {"symbol": normalized})
        price = _ticker_price(ticker, "buy")
        min_volume = _maybe_float(contract.get("minVol")) or 0.0
        max_volume = _maybe_float(contract.get("maxVol"))
        volume_step = _maybe_float(contract.get("volUnit"))
        contract_size = _maybe_float(contract.get("contractSize"))
        min_leverage = _maybe_int(contract.get("minLeverage")) or 1
        max_leverage = _maybe_int(contract.get("maxLeverage")) or min_leverage

        return TradingRules(
            symbol=normalized,
            min_volume=min_volume,
            max_volume=max_volume,
            volume_step=volume_step,
            contract_size=contract_size,
            min_leverage=min_leverage,
            max_leverage=max_leverage,
            price=price,
            min_notional_usdt=_min_notional(min_volume, contract_size, price),
            raw={"contract": contract, "ticker": _data(ticker)},
        )

    async def positions(self, symbol: str | None = None) -> list[Position]:
        self._ensure_ready()
        params = {"symbol": _normalize_symbol(symbol)} if symbol else None
        data = await self.client.get(OPEN_POSITIONS, params)
        positions: list[Position] = []
        for item in _list_data(data):
            volume = _float(item.get("holdVol"))
            if volume <= 0:
                continue
            position_type = int(item.get("positionType") or 0)
            positions.append(
                Position(
                    symbol=str(item.get("symbol") or ""),
                    direction="long" if position_type == 1 else "short",
                    volume=volume,
                    entry_price=_maybe_float(item.get("holdAvgPrice")),
                    pnl=_maybe_float(item.get("realised")),
                    position_id=_maybe_int(item.get("positionId")),
                    raw=item,
                )
            )
        return positions

    async def open_position(self, request: OpenOrderRequest) -> OrderResult:
        self._ensure_ready()
        symbol = _normalize_symbol(request.symbol)
        contract = await self._contract_detail(symbol)
        ticker = await self.client.get(TICKER, {"symbol": symbol})

        raw_price = _ticker_price(ticker, _trade_price_side(request.direction, is_close=False))
        price = _normalize_price(raw_price, contract)
        volume = _order_volume(request.volume, request.amount_usdt, request.notional_rounding, contract, symbol, raw_price)
        leverage = _normalize_leverage(request.leverage, contract, symbol)

        payload = {
            "symbol": symbol,
            "price": price,
            "vol": volume,
            "side": 1 if request.direction == "long" else 3,
            "type": 5,
            "openType": request.open_type,  # 1 = isolated margin for MEXC Futures.
            "leverage": leverage,
            "externalOid": f"local_{int(time.time() * 1000)}",
        }
        data = await self.client.post(SUBMIT_ORDER, payload)
        order_id = str(data.get("data") or "") or None
        return OrderResult(True, "Ордер открытия отправлен", order_id, {"request": payload, "meta": _order_meta(request.amount_usdt, request.notional_rounding, volume, contract, raw_price), "response": data})

    async def close_position(self, request: CloseOrderRequest) -> OrderResult:
        self._ensure_ready()
        symbol = _normalize_symbol(request.symbol)
        positions = await self.positions(symbol)
        target = _find_close_target(positions, request)
        contract = await self._contract_detail(symbol)
        ticker = await self.client.get(TICKER, {"symbol": symbol})
        raw_price = _ticker_price(ticker, _trade_price_side(request.direction, is_close=True))
        price = _normalize_price(raw_price, contract)
        volume = _close_order_volume(request, target, contract, symbol, raw_price)

        payload: dict[str, Any] = {
            "symbol": symbol,
            "price": price,
            "vol": volume,
            "side": 4 if request.direction == "long" else 2,
            "type": 5,
            "openType": request.open_type,  # 1 = isolated margin for MEXC Futures.
        }
        if request.position_id or target.position_id:
            payload["positionId"] = request.position_id or target.position_id
        data = await self.client.post(SUBMIT_ORDER, payload)
        order_id = str(data.get("data") or "") or None
        return OrderResult(True, "Ордер закрытия отправлен", order_id, {"request": payload, "meta": _order_meta(request.amount_usdt, request.notional_rounding, volume, contract, raw_price), "response": data})

    async def _contract_detail(self, symbol: str) -> dict[str, Any]:
        data = await self.client.get(CONTRACT_DETAIL, {"symbol": symbol})
        items = _list_data(data)
        for item in items:
            if str(item.get("symbol") or "").upper() == symbol:
                return item
        if items:
            return items[0]
        raise ExchangeRequestError(f"MEXC не вернула параметры контракта {symbol}")

    def _ensure_ready(self) -> None:
        if not self.config.enabled:
            raise ExchangeDisabledError("MEXC отключена")
        if not self.config.credentials.auth_token:
            raise ExchangeNotConfiguredError("Не указан MEXC WEB token")


def _data(data: dict[str, Any]) -> dict[str, Any]:
    value = data.get("data")
    return value if isinstance(value, dict) else {}


def _list_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    value = data.get("data")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


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


def _maybe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_symbol(symbol: str | None) -> str:
    clean = (symbol or "").strip().upper()
    if not clean:
        raise ExchangeRequestError("Не указан futures-символ")
    return clean


def _trade_price_side(direction: str, is_close: bool) -> str:
    # buy price is used for open long / close short; sell price for open short / close long.
    if (direction == "long" and not is_close) or (direction == "short" and is_close):
        return "buy"
    return "sell"


def _ticker_price(data: dict[str, Any], side: str) -> float:
    raw = _data(data)
    priority = ["ask1", "lastPrice", "fairPrice", "indexPrice"] if side == "buy" else ["bid1", "lastPrice", "fairPrice", "indexPrice"]
    for key in priority:
        price = _maybe_float(raw.get(key))
        if price and price > 0:
            return price
    raise ExchangeRequestError("Не удалось получить текущую цену MEXC")


def _normalize_price(price: float, contract: dict[str, Any]) -> float | int:
    scale = _scale(contract.get("priceScale"), fallback=8)
    step = _step(contract.get("priceUnit"), scale)
    value = _round_to_step(_decimal(price), step, ROUND_HALF_UP)
    if value <= 0:
        raise ExchangeRequestError("MEXC вернула некорректную цену контракта")
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

    min_vol = _decimal(contract.get("minVol") or 0)
    max_vol = _decimal(contract.get("maxVol") or 0)
    scale = _scale(contract.get("volScale"), fallback=8)
    step = _step(contract.get("volUnit"), scale)

    if min_vol > 0 and raw < min_vol:
        if not clamp_to_min:
            raise ExchangeRequestError(f"Минимальный объем для {symbol}: {_plain(min_vol)}")
        raw = min_vol
    if max_vol > 0 and raw > max_vol:
        raise ExchangeRequestError(f"Максимальный объем для {symbol}: {_plain(max_vol)}")

    value = _round_to_step(raw, step, ROUND_UP if rounding == "up" else ROUND_DOWN)
    if value <= 0 or (min_vol > 0 and value < min_vol):
        raise ExchangeRequestError(f"Объем должен быть кратен {_plain(step)} и не меньше {_plain(min_vol)}")
    if max_vol > 0 and value > max_vol:
        raise ExchangeRequestError(f"Максимальный объем для {symbol}: {_plain(max_vol)}")
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
) -> dict[str, Any]:
    rounded_amount = _decimal(volume) * _decimal(price) * _contract_size(contract)
    return {
        "requested_amount_usdt": amount_usdt,
        "notional_rounding": notional_rounding,
        "rounded_amount_usdt": _json_number(rounded_amount, 8),
        "contract_size": _json_number(_contract_size(contract), 12),
    }


def _normalize_leverage(leverage: int, contract: dict[str, Any], symbol: str) -> int:
    min_leverage = _maybe_int(contract.get("minLeverage")) or 1
    max_leverage = _maybe_int(contract.get("maxLeverage")) or min_leverage
    value = int(leverage or min_leverage)
    if value < min_leverage or value > max_leverage:
        raise ExchangeRequestError(f"Плечо для {symbol}: от {min_leverage}x до {max_leverage}x")
    return value


def _contract_size(contract: dict[str, Any]) -> Decimal:
    value = _decimal(contract.get("contractSize") or 1)
    return value if value > 0 else Decimal("1")


def _scale(value: Any, fallback: int) -> int:
    parsed = _maybe_int(value)
    if parsed is None or parsed < 0:
        return fallback
    return min(parsed, 12)


def _step(value: Any, scale: int) -> Decimal:
    raw = _decimal(value)
    if raw > 0:
        return raw
    return Decimal(1).scaleb(-scale)


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _round_to_step(value: Decimal, step: Decimal, rounding: str) -> Decimal:
    if step <= 0:
        return value
    return (value / step).to_integral_value(rounding=rounding) * step


def _json_number(value: Decimal, scale: int) -> float | int:
    quantized = value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_DOWN)
    if scale == 0:
        return int(quantized)
    return float(quantized)


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _find_close_target(positions: list[Position], request: CloseOrderRequest) -> Position:
    symbol = _normalize_symbol(request.symbol)
    for position in positions:
        if position.symbol == symbol and position.direction == request.direction:
            if request.position_id is None or position.position_id == request.position_id:
                return position
    raise ExchangeRequestError(f"Не найдена открытая {request.direction} позиция по {symbol}")


def _min_notional(min_volume: float, contract_size: float | None, price: float | None) -> float | None:
    if not min_volume or not price:
        return None
    multiplier = contract_size if contract_size and contract_size > 0 else 1
    return min_volume * multiplier * price
