from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

MessageKind = Literal["twap_created", "twap_result", "unknown"]
ParseStatus = Literal["accepted", "rejected", "skipped", "error"]
Side = Literal["buy", "sell"]


@dataclass(frozen=True)
class FilterConfig:
    min_usd: float
    max_duration_minutes: float
    max_market_volume_usd: float
    min_twap_share_percent: float


@dataclass(frozen=True)
class SourceGroupConfig:
    name: str
    source_chat_ids: list[int]
    source_threads_by_chat_id: dict[int, set[int]]
    target_chat_id: int
    target_thread_id: int | None
    filters: FilterConfig
    enabled: bool = True

    def source_thread_ids(self, chat_id: int) -> set[int]:
        return self.source_threads_by_chat_id.get(chat_id, set())

    def allows_source_thread(self, chat_id: int, thread_id: int | None) -> bool:
        allowed = self.source_thread_ids(chat_id)
        return not allowed or thread_id in allowed


@dataclass(frozen=True)
class IncomingMessage:
    group_name: str
    chat_id: int
    thread_id: int | None
    reply_to_message_id: int | None
    message_id: int
    text: str
    message_date: datetime | None
    raw_json: dict[str, Any]


@dataclass(frozen=True)
class ParseResult:
    kind: MessageKind
    status: ParseStatus
    reason: str
    payload: dict[str, Any]

    @staticmethod
    def skipped(reason: str = "message_not_supported") -> "ParseResult":
        return ParseResult("unknown", "skipped", reason, {})

    @staticmethod
    def error(reason: str, payload: dict[str, Any] | None = None) -> "ParseResult":
        return ParseResult("unknown", "error", reason, payload or {})
