from __future__ import annotations

from app.groups.twapx.filters import apply_filters
from app.groups.twapx.formatter import format_forward
from app.groups.twapx.parser import parse
from app.shared.types import ParseResult, SourceGroupConfig


class TwapxProcessor:
    parser_key = "twapx"

    def __init__(self, config: SourceGroupConfig) -> None:
        self.config = config

    def process(self, text: str) -> ParseResult:
        result = parse(text)
        return apply_filters(result, self.config.filters)

    def should_forward(self, result: ParseResult) -> bool:
        return result.kind == "twap_created" and result.status == "accepted"

    def format_forward(self, result: ParseResult) -> str:
        return format_forward(result, self.config)
