from __future__ import annotations

from abc import ABC, abstractmethod

from app.exchanges.core.types import (
    Balance,
    CloseOrderRequest,
    ConnectionStatus,
    FuturesAsset,
    OpenOrderRequest,
    OrderResult,
    Position,
    TradingRules,
)


class ExchangeAdapter(ABC):
    name: str
    title: str

    @abstractmethod
    async def status(self) -> ConnectionStatus:
        raise NotImplementedError

    @abstractmethod
    async def balance(self, currency: str = "USDT") -> Balance:
        raise NotImplementedError

    @abstractmethod
    async def futures_assets(self) -> list[FuturesAsset]:
        raise NotImplementedError

    @abstractmethod
    async def trading_rules(self, symbol: str) -> TradingRules:
        raise NotImplementedError

    @abstractmethod
    async def positions(self, symbol: str | None = None) -> list[Position]:
        raise NotImplementedError

    @abstractmethod
    async def open_position(self, request: OpenOrderRequest) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    async def close_position(self, request: CloseOrderRequest) -> OrderResult:
        raise NotImplementedError
