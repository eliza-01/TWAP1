from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LocalExchangeSettings:
    enabled: bool = False
    auth_token: str = ""


@dataclass
class LocalSignalSettings:
    enabled: bool = False
    server_ws_url: str = ""
    server_http_url: str = ""
    device_token: str = ""
    last_signal_id: int = 0


@dataclass
class LocalTradingSettings:
    default_volume: float = 1.0
    default_leverage: int = 1
    default_direction: str = "long"
    auto_trading_enabled: bool = False
    auto_trading_enabled_at: str = ""
    use_min_volume: bool = False


@dataclass
class LocalSettings:
    selected_exchange: str = "mexc"
    exchanges: dict[str, LocalExchangeSettings] = field(
        default_factory=lambda: {"mexc": LocalExchangeSettings()}
    )
    trading: LocalTradingSettings = field(default_factory=LocalTradingSettings)
    signals: LocalSignalSettings = field(default_factory=LocalSignalSettings)

    def to_dict(self, hide_secrets: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if hide_secrets:
            for exchange in data.get("exchanges", {}).values():
                token = exchange.get("auth_token") or ""
                exchange["auth_token"] = _mask(token)
            token = data.get("signals", {}).get("device_token") or ""
            data["signals"]["device_token"] = _mask(token)
        return data


def settings_from_dict(data: dict[str, Any]) -> LocalSettings:
    exchanges: dict[str, LocalExchangeSettings] = {}
    for name, raw in (data.get("exchanges") or {}).items():
        if isinstance(raw, dict):
            exchanges[name] = LocalExchangeSettings(
                enabled=bool(raw.get("enabled", False)),
                auth_token=str(raw.get("auth_token") or ""),
            )
    if "mexc" not in exchanges:
        exchanges["mexc"] = LocalExchangeSettings()

    trading_raw = data.get("trading") or {}
    signals_raw = data.get("signals") or {}
    use_min_volume = _bool_value(trading_raw.get("use_min_volume"), False)

    return LocalSettings(
        selected_exchange=str(data.get("selected_exchange") or "mexc"),
        exchanges=exchanges,
        trading=LocalTradingSettings(
            default_volume=float(trading_raw.get("default_volume") or 1),
            default_leverage=1 if use_min_volume else int(trading_raw.get("default_leverage") or 1),
            default_direction=str(trading_raw.get("default_direction") or "long"),
            auto_trading_enabled=_bool_value(trading_raw.get("auto_trading_enabled"), False),
            auto_trading_enabled_at=str(trading_raw.get("auto_trading_enabled_at") or ""),
            use_min_volume=use_min_volume,
        ),
        signals=LocalSignalSettings(
            enabled=_bool_value(signals_raw.get("enabled"), _env_bool("LOCAL_SIGNAL_CLIENT_ENABLED", False)),
            server_ws_url=str(signals_raw.get("server_ws_url") or os.getenv("LOCAL_SIGNAL_WS_URL") or ""),
            server_http_url=str(signals_raw.get("server_http_url") or os.getenv("LOCAL_SIGNAL_HTTP_URL") or ""),
            device_token=str(signals_raw.get("device_token") or os.getenv("LOCAL_SIGNAL_DEVICE_TOKEN") or ""),
            last_signal_id=int(signals_raw.get("last_signal_id") or 0),
        ),
    )


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _bool_value(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)
