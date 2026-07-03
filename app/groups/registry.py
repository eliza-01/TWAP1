from __future__ import annotations

from typing import Any, Protocol

from app.groups.twapx.config import PARSER_KEY as TWAPX_PARSER_KEY
from app.groups.twapx.config import load_config as load_twapx_config
from app.groups.twapx.processor import TwapxProcessor
from app.shared.types import ParseResult, SourceGroupConfig


class GroupProcessor(Protocol):
    parser_key: str
    config: SourceGroupConfig

    def process(self, text: str) -> ParseResult: ...

    def should_forward(self, result: ParseResult) -> bool: ...

    def should_forward_result(self, result: ParseResult, original: dict[str, Any] | None) -> bool: ...

    def format_forward(self, result: ParseResult) -> str: ...

    def format_result(self, result: ParseResult, original: dict[str, Any]) -> str: ...


def load_processors(group_names: list[str]) -> list[GroupProcessor]:
    processors: list[GroupProcessor] = []
    for group_name in group_names:
        normalized = group_name.strip().lower()
        if normalized == TWAPX_PARSER_KEY:
            config = load_twapx_config()
            if config.enabled:
                processors.append(TwapxProcessor(config))
            continue
        raise ValueError(f"Unknown group parser: {group_name}")
    return processors

