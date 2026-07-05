from __future__ import annotations

from os import getenv

from app.core.env import env_bool, env_float, env_int, env_int_list
from app.shared.types import FilterConfig, SourceGroupConfig

PARSER_KEY = "twapx"


def load_config() -> SourceGroupConfig:
    source_chat_ids = env_int_list("TWAPX_SOURCE_CHAT_IDS", [-1003663170785])
    return SourceGroupConfig(
        name="twapx",
        source_chat_ids=source_chat_ids,
        source_threads_by_chat_id=_source_threads_by_chat_id(source_chat_ids),
        target_chat_id=env_int("TWAPX_TARGET_CHAT_ID", -1003918218733),
        target_thread_id=env_int("TWAPX_TARGET_THREAD_ID", 4),
        enabled=env_bool("TWAPX_ENABLED", True),
        filters=FilterConfig(
            min_usd=env_float("TWAPX_MIN_USD", 300_000),
            max_duration_minutes=env_float("TWAPX_MAX_DURATION_MINUTES", 30),
            max_market_volume_usd=env_float("TWAPX_MAX_MARKET_VOLUME_USD", 100_000_000),
            min_twap_share_percent=env_float("TWAPX_MIN_TWAP_SHARE_PERCENT", 0.5),
        ),
    )


def _source_threads_by_chat_id(source_chat_ids: list[int]) -> dict[int, set[int]]:
    mapped = _parse_chat_thread_map("TWAPX_SOURCE_CHAT_THREADS")
    if mapped:
        return mapped

    shared_thread_ids = set(env_int_list("TWAPX_SOURCE_THREAD_IDS", []))
    if not shared_thread_ids:
        return {}

    return {chat_id: set(shared_thread_ids) for chat_id in source_chat_ids}


def _parse_chat_thread_map(env_name: str) -> dict[int, set[int]]:
    raw = getenv(env_name, "").strip()
    if not raw:
        return {}

    result: dict[int, set[int]] = {}
    current_chat_id: int | None = None

    for item in raw.split(","):
        chunk = item.strip()
        if not chunk:
            continue

        if ":" in chunk:
            chat_raw, _, threads_raw = chunk.partition(":")
            if not chat_raw.strip() or not threads_raw.strip():
                raise ValueError(f"Invalid {env_name} item: {chunk}")
            current_chat_id = int(chat_raw.strip())
            result.setdefault(current_chat_id, set()).update(_parse_thread_ids(threads_raw))
            continue

        if current_chat_id is None:
            raise ValueError(f"Invalid {env_name} item: {chunk}")
        result.setdefault(current_chat_id, set()).update(_parse_thread_ids(chunk))

    return result


def _parse_thread_ids(value: str) -> set[int]:
    return {
        int(item.strip())
        for item in value.replace("|", ";").replace(",", ";").split(";")
        if item.strip()
    }
