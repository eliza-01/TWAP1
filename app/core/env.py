from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from dotenv import load_dotenv


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_int(name: str, default: int = 0) -> int:
    raw = env_str(name)
    return int(raw) if raw else default


def env_float(name: str, default: float = 0.0) -> float:
    raw = env_str(name)
    return float(raw) if raw else default


def env_bool(name: str, default: bool = False) -> bool:
    raw = env_str(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "y", "on"}


def env_int_list(name: str, default: Iterable[int] | None = None) -> list[int]:
    raw = env_str(name)
    if not raw:
        return list(default or [])
    return [int(item) for item in _split_csv(raw)]


def env_stage_str(name: str, default: str = "", stage: bool | None = None) -> str:
    """Read STAGE_<name> or PROD_<name>, with fallback to common <name>."""
    stage = env_bool("STAGE", False) if stage is None else stage
    prefixed_name = f"{'STAGE' if stage else 'PROD'}_{name}"
    raw = env_str(prefixed_name)
    if raw:
        return raw
    return env_str(name, default)


def env_stage_int(name: str, default: int = 0, stage: bool | None = None) -> int:
    raw = env_stage_str(name, "", stage)
    return int(raw) if raw else default


def env_stage_float(name: str, default: float = 0.0, stage: bool | None = None) -> float:
    raw = env_stage_str(name, "", stage)
    return float(raw) if raw else default


def env_stage_bool(name: str, default: bool = False, stage: bool | None = None) -> bool:
    raw = env_stage_str(name, "", stage)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "y", "on"}


def env_stage_int_list(name: str, default: Iterable[int] | None = None, stage: bool | None = None) -> list[int]:
    raw = env_stage_str(name, "", stage)
    if not raw:
        return list(default or [])
    return [int(item) for item in _split_csv(raw)]


def _optional_env_int(name: str) -> int | None:
    raw = env_str(name)
    return int(raw) if raw else None


def _stage_port(name: str, stage_name: str, prod_name: str, stage_default: int, prod_default: int, stage: bool) -> int:
    raw = env_str(name)
    if raw:
        return int(raw)
    if stage:
        return env_int(stage_name, stage_default)
    return env_int(prod_name, prod_default)


@dataclass(frozen=True)
class DeploymentSettings:
    stage: bool
    env_name: str
    domain: str
    public_base_url: str
    public_signal_ws_url: str
    local_ui_port: int
    signal_server_port: int
    phpmyadmin_port: int
    mysql_host_port: int


@dataclass(frozen=True)
class DbSettings:
    host: str
    port: int
    database: str
    user: str
    password: str


@dataclass(frozen=True)
class TelegramSettings:
    api_id: int
    api_hash: str
    phone: str
    session_path: str


@dataclass(frozen=True)
class DebugSettings:
    enabled: bool
    chat_id: int | None
    thread_id: int | None
    send_skipped: bool


@dataclass(frozen=True)
class AppSettings:
    deploy: DeploymentSettings
    db: DbSettings
    telegram: TelegramSettings
    debug: DebugSettings
    groups: list[str]
    history_limit: int


def load_deployment_settings() -> DeploymentSettings:
    stage = env_bool("STAGE", False)
    env_name = "stage" if stage else "prod"
    domain = env_str("PUBLIC_DOMAIN") or env_str("STAGE_DOMAIN" if stage else "PROD_DOMAIN", "beta.twaps.ru" if stage else "twaps.ru")
    protocol = env_str("PUBLIC_PROTOCOL", "https") or "https"
    public_base_url = env_str("PUBLIC_BASE_URL") or f"{protocol}://{domain}"
    ws_protocol = "wss" if protocol == "https" else "ws"
    public_signal_ws_url = env_str("PUBLIC_SIGNAL_WS_URL") or f"{ws_protocol}://{domain}/ws/signals"

    return DeploymentSettings(
        stage=stage,
        env_name=env_name,
        domain=domain,
        public_base_url=public_base_url,
        public_signal_ws_url=public_signal_ws_url,
        local_ui_port=_stage_port("LOCAL_UI_PORT", "STAGE_LOCAL_UI_PORT", "PROD_LOCAL_UI_PORT", 18080, 8080, stage),
        signal_server_port=_stage_port("SIGNAL_SERVER_PORT", "STAGE_SIGNAL_SERVER_PORT", "PROD_SIGNAL_SERVER_PORT", 18090, 8090, stage),
        phpmyadmin_port=_stage_port("PHPMYADMIN_PORT", "STAGE_PHPMYADMIN_PORT", "PROD_PHPMYADMIN_PORT", 18081, 8081, stage),
        mysql_host_port=_stage_port("MYSQL_HOST_PORT", "STAGE_MYSQL_HOST_PORT", "PROD_MYSQL_HOST_PORT", 13306, 3306, stage),
    )


def load_settings() -> AppSettings:
    load_dotenv()
    deploy = load_deployment_settings()
    default_session_path = "sessions/twap_stage_user.session" if deploy.stage else "sessions/twap_prod_user.session"
    return AppSettings(
        deploy=deploy,
        db=DbSettings(
            host=env_str("MYSQL_HOST", "mysql"),
            port=env_int("MYSQL_PORT", 3306),
            database=env_str("MYSQL_DATABASE", "twap_parser"),
            user=env_str("MYSQL_USER", "twap_user"),
            password=env_str("MYSQL_PASSWORD", "twap_password"),
        ),
        telegram=TelegramSettings(
            api_id=env_stage_int("TELEGRAM_API_ID", 0, deploy.stage),
            api_hash=env_stage_str("TELEGRAM_API_HASH", "", deploy.stage),
            phone=env_stage_str("TELEGRAM_PHONE", "", deploy.stage),
            session_path=env_stage_str("TELEGRAM_SESSION_PATH", default_session_path, deploy.stage),
        ),
        debug=DebugSettings(
            enabled=env_bool("DEBUG_ENABLED", False),
            chat_id=_optional_env_int("DEBUG_CHAT_ID"),
            thread_id=_optional_env_int("DEBUG_THREAD_ID"),
            send_skipped=env_bool("DEBUG_SEND_SKIPPED", False),
        ),
        groups=_split_csv(env_str("GROUPS", "twapx")),
        history_limit=env_int("HISTORY_LIMIT", 1000),
    )


def ensure_runtime_dirs(settings: AppSettings) -> None:
    session_dir = Path(settings.telegram.session_path).parent
    session_dir.mkdir(parents=True, exist_ok=True)
