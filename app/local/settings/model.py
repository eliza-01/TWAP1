from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LocalExchangeSettings:
    enabled: bool = False
    api_key: str = ""
    secret_key: str = ""
    hedge_mode_enabled: bool = True


@dataclass
class LocalSignalSettings:
    server_ws_url: str = ""
    server_http_url: str = ""
    last_signal_id: int = 0


@dataclass
class LocalTradingSettings:
    default_volume: float = 10.0
    default_leverage: int = 1
    default_direction: str = "long"
    auto_trading_enabled: bool = False
    auto_trading_enabled_at: str = ""
    use_min_volume: bool = False
    auto_order_usdt: float = 10.0
    auto_leverage_enabled: bool = True
    max_auto_leverage: int = 20
    disable_signal_filters: bool = False
    ignore_min_usd_by_market_share: bool = False
    min_usd_override_twap_share_percent: float = 1.0
    fallback_close_enabled: bool = False
    fallback_close_grace_seconds: float = 5.0


@dataclass
class LocalSettings:
    selected_exchange: str = "binance"
    exchanges: dict[str, LocalExchangeSettings] = field(
        default_factory=lambda: {"binance": LocalExchangeSettings()}
    )
    trading: LocalTradingSettings = field(default_factory=LocalTradingSettings)
    signals: LocalSignalSettings = field(default_factory=LocalSignalSettings)

    def to_dict(self, hide_secrets: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if hide_secrets:
            for exchange in data.get("exchanges", {}).values():
                exchange["api_key"] = _mask(exchange.get("api_key") or "")
                exchange["secret_key"] = _mask(exchange.get("secret_key") or "")
        return data


def settings_from_dict(data: dict[str, Any]) -> LocalSettings:
    exchanges: dict[str, LocalExchangeSettings] = {}

    for name, raw in (data.get("exchanges") or {}).items():
        if name != "binance" or not isinstance(raw, dict):
            continue
        exchanges[name] = LocalExchangeSettings(
            enabled=bool(raw.get("enabled", False)),
            api_key=str(raw.get("api_key") or ""),
            secret_key=str(raw.get("secret_key") or ""),
            hedge_mode_enabled=_bool_value(raw.get("hedge_mode_enabled"), True),
        )

    if "binance" not in exchanges:
        exchanges["binance"] = LocalExchangeSettings()

    trading_raw = data.get("trading") or {}
    signals_raw = data.get("signals") or {}

    use_min_volume = _bool_value(trading_raw.get("use_min_volume"), False)
    max_auto_leverage = _positive_int(trading_raw.get("max_auto_leverage"), 20)
    auto_order_usdt = _positive_float(
        trading_raw.get("auto_order_usdt", trading_raw.get("auto_margin_usdt")),
        10,
    )

    selected_exchange = str(data.get("selected_exchange") or "binance")
    if selected_exchange not in exchanges:
        selected_exchange = "binance"

    return LocalSettings(
        selected_exchange=selected_exchange,
        exchanges=exchanges,
        trading=LocalTradingSettings(
            default_volume=_positive_float(trading_raw.get("default_volume"), 1),
            default_leverage=1 if use_min_volume else _positive_int(trading_raw.get("default_leverage"), 1),
            default_direction=str(trading_raw.get("default_direction") or "long"),
            auto_trading_enabled=_bool_value(trading_raw.get("auto_trading_enabled"), False),
            auto_trading_enabled_at=str(trading_raw.get("auto_trading_enabled_at") or ""),
            use_min_volume=use_min_volume,
            auto_order_usdt=auto_order_usdt,
            auto_leverage_enabled=False if use_min_volume else _bool_value(trading_raw.get("auto_leverage_enabled"), True),
            max_auto_leverage=1 if use_min_volume else max_auto_leverage,
            disable_signal_filters=_bool_value(trading_raw.get("disable_signal_filters"), False),
            ignore_min_usd_by_market_share=_bool_value(trading_raw.get("ignore_min_usd_by_market_share"), False),
            min_usd_override_twap_share_percent=_positive_float(
                trading_raw.get("min_usd_override_twap_share_percent"),
                1.0,
            ),
            fallback_close_enabled=_bool_value(trading_raw.get("fallback_close_enabled"), False),
            fallback_close_grace_seconds=_non_negative_float(
                trading_raw.get("fallback_close_grace_seconds"),
                5.0,
            ),
        ),
        signals=LocalSignalSettings(
            server_ws_url=str(os.getenv("LOCAL_SIGNAL_WS_URL") or ""),
            server_http_url=str(os.getenv("LOCAL_SIGNAL_HTTP_URL") or ""),
            last_signal_id=int(signals_raw.get("last_signal_id") or 0),
        ),
    )


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _bool_value(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default

