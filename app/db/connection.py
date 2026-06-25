from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator

import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.pooling import MySQLConnectionPool

from app.core.env import DbSettings

_pool: MySQLConnectionPool | None = None


def init_pool(settings: DbSettings, retries: int = 20, delay_seconds: float = 2.0) -> None:
    global _pool
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            _pool = MySQLConnectionPool(
                pool_name="twap_parser_pool",
                pool_size=5,
                host=settings.host,
                port=settings.port,
                database=settings.database,
                user=settings.user,
                password=settings.password,
                autocommit=False,
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
            )
            return
        except mysql.connector.Error as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(delay_seconds)

    raise RuntimeError(f"MySQL is not available after {retries} attempts: {last_error}") from last_error


@contextmanager
def db_cursor(dictionary: bool = False) -> Iterator[mysql.connector.cursor.MySQLCursor]:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    conn: MySQLConnection = _pool.get_connection()
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=_json_default)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return str(value)
