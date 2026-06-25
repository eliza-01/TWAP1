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
class AppSettings:
    db: DbSettings
    telegram: TelegramSettings
    groups: list[str]
    history_limit: int


def load_settings() -> AppSettings:
    load_dotenv()

    return AppSettings(
        db=DbSettings(
            host=env_str("MYSQL_HOST", "mysql"),
            port=env_int("MYSQL_PORT", 3306),
            database=env_str("MYSQL_DATABASE", "twap_parser"),
            user=env_str("MYSQL_USER", "twap_user"),
            password=env_str("MYSQL_PASSWORD", "twap_password"),
        ),
        telegram=TelegramSettings(
            api_id=env_int("TELEGRAM_API_ID"),
            api_hash=env_str("TELEGRAM_API_HASH"),
            phone=env_str("TELEGRAM_PHONE"),
            session_path=env_str("TELEGRAM_SESSION_PATH", "sessions/twap_user.session"),
        ),
        groups=_split_csv(env_str("GROUPS", "twapx")),
        history_limit=env_int("HISTORY_LIMIT", 1000),
    )


def ensure_runtime_dirs(settings: AppSettings) -> None:
    session_dir = Path(settings.telegram.session_path).parent
    session_dir.mkdir(parents=True, exist_ok=True)
