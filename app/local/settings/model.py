from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LocalExchangeSettings:
    enabled: bool = False
    api_key: str = ""
    secret_key: str = ""
    hedge_mode_enabled: bool = True


@dataclass
class LocalAccountSettings:
    login: str = ""
    session_token: str = ""
    user_id: int = 0
    access_until: str = ""
    device_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    device_name: str = ""


@dataclass
class LocalSignalSettings:
    server_ws_url: str = ""
    server_http_url: str = ""
    last_signal_id: int = 0


@dataclass
class LocalUiSettings:
    table_rows: dict[str, int] = field(
        default_factory=lambda: {
            "assets": 50,
            "positions": 25,
            "signals": 50,
            "trade_logs": 50,
            "open_trades": 25,
            "fallback_reports": 50,
        }
    )


@dataclass
class LocalSignalFilterSettings:
    enabled: bool = True
    min_usd: float = 300_000.0
    max_duration_minutes: float = 30.0
    max_market_volume_usd: float = 100_000_000.0
    min_twap_share_percent: float = 0.5


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
    # Backward compatible name: true means "ignore server status/reason".
    disable_signal_filters: bool = True
    signal_filters: LocalSignalFilterSettings = field(default_factory=LocalSignalFilterSettings)
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
    account: LocalAccountSettings = field(default_factory=LocalAccountSettings)
    trading: LocalTradingSettings = field(default_factory=LocalTradingSettings)
    signals: LocalSignalSettings = field(default_factory=LocalSignalSettings)
    ui: LocalUiSettings = field(default_factory=LocalUiSettings)

    def to_dict(self, hide_secrets: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if hide_secrets:
            for exchange in data.get("exchanges", {}).values():
                exchange["api_key"] = _mask(exchange.get("api_key") or "")
                exchange["secret_key"] = _mask(exchange.get("secret_key") or "")
            account = data.get("account") or {}
            if account.get("session_token"):
                account["session_token"] = _mask(account.get("session_token") or "")
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

    account_raw = data.get("account") if isinstance(data.get("account"), dict) else {}
    trading_raw = data.get("trading") if isinstance(data.get("trading"), dict) else {}
    signals_raw = data.get("signals") if isinstance(data.get("signals"), dict) else {}
    ui_raw = data.get("ui") if isinstance(data.get("ui"), dict) else {}
    filters_raw = trading_raw.get("signal_filters") if isinstance(trading_raw.get("signal_filters"), dict) else {}

    use_min_volume = _bool_value(trading_raw.get("use_min_volume"), False)
    max_auto_leverage = _positive_int(trading_raw.get("max_auto_leverage"), 20)
    auto_order_usdt = _positive_float(
        trading_raw.get("auto_order_usdt", trading_raw.get("auto_margin_usdt")),
        10,
    )

    selected_exchange = str(data.get("selected_exchange") or "binance")
    if selected_exchange not in exchanges:
        selected_exchange = "binance"

    device_id = str(account_raw.get("device_id") or "").strip() or uuid.uuid4().hex

    return LocalSettings(
        selected_exchange=selected_exchange,
        exchanges=exchanges,
        account=LocalAccountSettings(
            login=str(account_raw.get("login") or ""),
            session_token=str(account_raw.get("session_token") or ""),
            user_id=_non_negative_int(account_raw.get("user_id"), 0),
            access_until=str(account_raw.get("access_until") or ""),
            device_id=device_id,
            device_name=str(account_raw.get("device_name") or os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "local-client"),
        ),
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
            disable_signal_filters=_bool_value(trading_raw.get("disable_signal_filters"), True),
            signal_filters=LocalSignalFilterSettings(
                enabled=_bool_value(filters_raw.get("enabled"), True),
                min_usd=_non_negative_float(filters_raw.get("min_usd"), 300_000.0),
                max_duration_minutes=_positive_float(filters_raw.get("max_duration_minutes"), 30.0),
                max_market_volume_usd=_positive_float(filters_raw.get("max_market_volume_usd"), 100_000_000.0),
                min_twap_share_percent=_non_negative_float(filters_raw.get("min_twap_share_percent"), 0.5),
            ),
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
            server_ws_url=str(os.getenv("LOCAL_SIGNAL_WS_URL") or signals_raw.get("server_ws_url") or ""),
            server_http_url=str(os.getenv("LOCAL_SIGNAL_HTTP_URL") or signals_raw.get("server_http_url") or ""),
            last_signal_id=int(signals_raw.get("last_signal_id") or 0),
        ),
        ui=LocalUiSettings(
            table_rows=_table_rows_from_dict(
                ui_raw.get("table_rows") if isinstance(ui_raw.get("table_rows"), dict) else {}
            ),
        ),
    )


def _table_rows_from_dict(raw: dict[str, Any]) -> dict[str, int]:
    defaults = LocalUiSettings().table_rows
    return {
        key: _bounded_int(raw.get(key), default, 10, 500)
        for key, default in defaults.items()
    }


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return minimum
    if parsed > maximum:
        return maximum
    return parsed


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


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _non_negative_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError):
        return default


def _positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _non_negative_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError):
        return default

