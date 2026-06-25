from app.shared.types import FilterConfig, ParseResult
from app.telegram.debug import DebugContext, format_debug_result, should_send_debug


def test_debug_report_is_human_readable_for_rejected_created_signal():
    result = ParseResult(
        kind="twap_created",
        status="rejected",
        reason="duration_gt_30_minutes",
        payload={
            "asset": "HYPE",
            "side": "buy",
            "price": 62.13,
            "amount_usd": 803120,
            "duration_minutes": 90,
            "market_volume_usd": 3440000,
            "twap_share_percent": 23.34,
        },
    )
    text = format_debug_result(
        result,
        DebugContext(
            group_name="twapx",
            parser_key="twapx",
            chat_id=-1003918218733,
            thread_id=48,
            message_id=36,
            reply_to_message_id=None,
            message_text="🟩 $803.12K покупка HYPE в течении 1.5 часа\nЦена: $62.13",
            filters=FilterConfig(
                min_usd=300_000,
                max_duration_minutes=30,
                max_market_volume_usd=100_000_000,
                min_twap_share_percent=0.5,
            ),
            action="not_forwarded",
        ),
    )

    assert "<b>Цитата сигнала:</b>" in text
    assert "<blockquote>🟩 $803.12K покупка HYPE" in text
    assert "<b>Реакция:</b> ❌ <b>rejected</b>" in text
    assert "<b>TWAPX</b> · <b>HYPE</b> · <i>покупка</i> · <code>$62.13</code>" in text
    assert "Объем TWAP — <b>$803.12K</b> ✅" in text
    assert "Время исполнения — <b>1.5 часа</b> ❌" in text
    assert "Объем рынка — <b>$3.44M</b> ✅" in text
    assert "Доля TWAP в рынке — <b>23.34%</b> ✅" in text
    assert "- время исполнения больше 30 минут" in text
    assert "<b>Target:</b> не отправлено — не прошёл фильтр" in text


def test_debug_report_shows_target_error():
    result = ParseResult(
        kind="twap_created",
        status="accepted",
        reason="filter_passed",
        payload={"asset": "HYPE", "side": "buy", "price": 62.13},
    )
    text = format_debug_result(
        result,
        DebugContext(
            group_name="twapx",
            parser_key="twapx",
            chat_id=-1003918218733,
            thread_id=48,
            message_id=36,
            reply_to_message_id=None,
            target_error="BadRequestError: invalid reply_to",
        ),
    )

    assert "<b>Target:</b> ❌ ошибка отправки" in text
    assert "BadRequestError" in text


def test_debug_skipped_is_configurable():
    assert not should_send_debug("skipped", send_skipped=False)
    assert should_send_debug("skipped", send_skipped=True)
