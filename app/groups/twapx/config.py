from __future__ import annotations

from os import getenv

from app.core.env import (
    env_bool,
    env_float,
    env_int,
    env_int_list,
    env_stage_bool,
    env_stage_str,
)
from app.shared.types import FilterConfig, SourceGroupConfig

PARSER_KEY = "twapx"


def load_config() -> SourceGroupConfig:
    source_chat_ids, source_threads_by_chat_id = _load_sources()
    target_chat_id, target_thread_id = _load_target()
    return SourceGroupConfig(
        name="twapx",
        source_chat_ids=source_chat_ids,
        source_threads_by_chat_id=source_threads_by_chat_id,
        target_chat_id=target_chat_id,
        target_thread_id=target_thread_id,
        enabled=env_stage_bool("TWAPX_ENABLED", env_bool("TWAPX_ENABLED", True)),
        filters=FilterConfig(
            min_usd=env_float("TWAPX_MIN_USD", 300_000),
            max_duration_minutes=env_float("TWAPX_MAX_DURATION_MINUTES", 30),
            max_market_volume_usd=env_float("TWAPX_MAX_MARKET_VOLUME_USD", 100_000_000),
            min_twap_share_percent=env_float("TWAPX_MIN_TWAP_SHARE_PERCENT", 0.5),
        ),
    )


def _load_sources() -> tuple[list[int], dict[int, set[int]]]:
    # New format. Stage/prod-aware:
    #   PROD_TWAPX_SOURCES=-1003918218733:2,-1003918218734:3,-1003918218735
    #   STAGE_TWAPX_SOURCES=-1003918218733:2
    # Common TWAPX_SOURCES is still supported as fallback.
    raw = env_stage_str("TWAPX_SOURCES")
    if raw:
        return _parse_sources(raw, "TWAPX_SOURCES")

    # Backward compatibility with the old split variables.
    source_chat_ids = env_int_list("TWAPX_SOURCE_CHAT_IDS", [-1003663170785])
    return source_chat_ids, _source_threads_by_chat_id(source_chat_ids)


def _load_target() -> tuple[int, int | None]:
    # New format. Stage/prod-aware:
    #   PROD_TWAPX_TARGET=-1003918218733:4
    #   STAGE_TWAPX_TARGET=-1003918218733:4
    # Without ':' the target chat is used without a forum topic/thread.
    raw = env_stage_str("TWAPX_TARGET")
    if raw:
        return _parse_target(raw, "TWAPX_TARGET")

    # Backward compatibility with the old split variables.
    return env_int("TWAPX_TARGET_CHAT_ID", -1003918218733), env_int("TWAPX_TARGET_THREAD_ID", 4)


def _source_threads_by_chat_id(source_chat_ids: list[int]) -> dict[int, set[int]]:
    mapped = _parse_chat_thread_map("TWAPX_SOURCE_CHAT_THREADS")
    if mapped:
        return mapped

    shared_thread_ids = set(env_int_list("TWAPX_SOURCE_THREAD_IDS", []))
    if not shared_thread_ids:
        return {}

    return {chat_id: set(shared_thread_ids) for chat_id in source_chat_ids}


def _parse_sources(value: str, env_name: str = "TWAPX_SOURCES") -> tuple[list[int], dict[int, set[int]]]:
    source_chat_ids: list[int] = []
    source_threads_by_chat_id: dict[int, set[int]] = {}

    for item in value.split(","):
        chunk = item.strip()
        if not chunk:
            continue

        chat_id, thread_ids = _parse_chat_thread_item(chunk, env_name)
        if chat_id not in source_chat_ids:
            source_chat_ids.append(chat_id)
        if thread_ids:
            source_threads_by_chat_id.setdefault(chat_id, set()).update(thread_ids)

    if not source_chat_ids:
        raise ValueError(f"{env_name} не содержит ни одного source-чата")

    return source_chat_ids, source_threads_by_chat_id


def _parse_target(value: str, env_name: str = "TWAPX_TARGET") -> tuple[int, int | None]:
    raw_items = [item.strip() for item in value.split(",") if item.strip()]
    if len(raw_items) != 1:
        raise ValueError(f"{env_name} должен содержать ровно один target-чат")

    chat_id, thread_ids = _parse_chat_thread_item(raw_items[0], env_name)
    if not thread_ids:
        return chat_id, None
    if len(thread_ids) != 1:
        raise ValueError(f"{env_name} должен содержать максимум один thread/topic")
    return chat_id, next(iter(thread_ids))


def _parse_chat_thread_item(value: str, env_name: str) -> tuple[int, set[int]]:
    if ":" not in value:
        return int(value), set()

    chat_raw, _, threads_raw = value.partition(":")
    if not chat_raw.strip() or not threads_raw.strip():
        raise ValueError(f"Invalid {env_name} item: {value}")
    return int(chat_raw.strip()), _parse_thread_ids(threads_raw)


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
