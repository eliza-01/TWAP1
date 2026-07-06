from __future__ import annotations

from app.shared.types import FilterConfig, ParseResult


def apply_filters(result: ParseResult, filters: FilterConfig | None = None) -> ParseResult:
    """Server-side TWAP filters are disabled.

    The server must not decide whether a user enters a deal. Each local client has
    its own filter settings in local_data/settings.json and applies them before
    opening a position.
    """
    return result
