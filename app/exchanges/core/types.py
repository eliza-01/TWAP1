from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ExchangeStatus = Literal["connected", "error", "disabled", "not_configured"]
OrderDirection = Literal["long", "short"]
NotionalRounding = Literal["down", "up"]


@dataclass(frozen=True)
class ExchangeCredentials:
    auth_token: str = ""
    api_key: str = ""
    secret_key: str = ""


@dataclass(frozen=True)
class ExchangeConfig:
    name: str
    enabled: bool
    credentials: ExchangeCredentials = field(default_factory=ExchangeCredentials)


@dataclass(frozen=True)
class ConnectionStatus:
    status: ExchangeStatus
    message: str


@dataclass(frozen=True)
class FuturesAsset:
    symbol: str
    display_name: str
    base_coin: str | None = None
    quote_coin: str | None = None
    min_vol: float | None = None
    max_vol: float | None = None
    vol_unit: float | None = None
    contract_size: float | None = None
    min_leverage: int | None = None
    max_leverage: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradingRules:
    symbol: str
    min_volume: float
    max_volume: float | None = None
    volume_step: float | None = None
    contract_size: float | None = None
    min_leverage: int = 1
    max_leverage: int = 1
    price: float | None = None
    min_notional_usdt: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Balance:
    currency: str
    available: float
    equity: float
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Position:
    symbol: str
    direction: OrderDirection
    volume: float
    entry_price: float | None = None
    pnl: float | None = None
    position_id: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenOrderRequest:
    symbol: str
    direction: OrderDirection
    volume: float
    leverage: int
    amount_usdt: float | None = None
    notional_rounding: NotionalRounding = "down"
    open_type: int = 1


@dataclass(frozen=True)
class CloseOrderRequest:
    symbol: str
    direction: OrderDirection
    volume: float | None = None
    amount_usdt: float | None = None
    notional_rounding: NotionalRounding = "down"
    position_id: int | None = None
    open_type: int = 1


@dataclass(frozen=True)
class OrderResult:
    success: bool
    message: str
    order_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
