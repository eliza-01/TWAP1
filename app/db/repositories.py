from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from app.db.connection import db_cursor, json_dump
from app.shared.types import IncomingMessage, ParseResult, SourceGroupConfig

class SourceGroupRepository:
    def upsert(self, config: SourceGroupConfig, parser_key: str) -> None:
        with db_cursor() as cursor:
            for chat_id in config.source_chat_ids:
                source_thread_ids = config.source_thread_ids(chat_id) or {0}
                for source_thread_id in source_thread_ids:
                    cursor.execute(
                        """                        INSERT INTO source_groups                            (name, source_chat_id, source_thread_id, target_chat_id, target_thread_id, parser_key, filters_json, enabled)                        VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS JSON), %s)                        ON DUPLICATE KEY UPDATE                            target_chat_id = VALUES(target_chat_id),                            target_thread_id = VALUES(target_thread_id),                            parser_key = VALUES(parser_key),                            filters_json = VALUES(filters_json),                            enabled = VALUES(enabled)                        """,
                        (
                            config.name,
                            chat_id,
                            source_thread_id,
                            config.target_chat_id,
                            config.target_thread_id,
                            parser_key,
                            json_dump(config.filters.__dict__),
                            config.enabled,
                        ),
                    )

class MessageRepository:
    def save_incoming(self, message: IncomingMessage) -> tuple[int, bool]:
        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """                INSERT INTO incoming_messages                    (group_name, telegram_chat_id, telegram_thread_id, telegram_message_id,                     telegram_reply_to_message_id, message_date, raw_text, raw_json)                VALUES (%s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON))                ON DUPLICATE KEY UPDATE                    id = LAST_INSERT_ID(id),                    telegram_thread_id = VALUES(telegram_thread_id),                    telegram_reply_to_message_id = VALUES(telegram_reply_to_message_id),                    raw_text = VALUES(raw_text),                    raw_json = VALUES(raw_json)                """,
                (
                    message.group_name,
                    message.chat_id,
                    message.thread_id,
                    message.message_id,
                    message.reply_to_message_id,
                    _dt(message.message_date),
                    message.text,
                    json_dump(message.raw_json),
                ),
            )
            incoming_id = int(cursor.lastrowid)
            created = cursor.rowcount == 1
            return incoming_id, created
    def save_parsed(self, incoming_id: int, parser_key: str, result: ParseResult) -> int:
        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """                INSERT INTO parsed_messages                    (incoming_message_id, parser_key, kind, status, reason, payload_json)                VALUES (%s, %s, %s, %s, %s, CAST(%s AS JSON))                ON DUPLICATE KEY UPDATE                    id = LAST_INSERT_ID(id),
                    kind = VALUES(kind),
                    status = VALUES(status),
                    reason = VALUES(reason),
                    payload_json = VALUES(payload_json)
                """,

                (

                    incoming_id,

                    parser_key,

                    result.kind,

                    result.status,

                    result.reason,

                    json_dump(result.payload),

                ),

            )

            return int(cursor.lastrowid)


    def link_result_to_created(self, parsed_id: int, original: dict[str, Any]) -> None:

        with db_cursor() as cursor:

            cursor.execute(

                """
                UPDATE parsed_messages
                SET related_incoming_message_id = %s,
                    related_parsed_message_id = %s
                WHERE id = %s
                """,

                (original.get("incoming_id"), original.get("parsed_id"), parsed_id),

            )


    def find_forwarded_created_by_reply(

        self,

        group_name: str,

        parser_key: str,

        chat_id: int,

        reply_to_message_id: int | None,

    ) -> dict[str, Any] | None:

        if reply_to_message_id is None:

            return None


        with db_cursor(dictionary=True) as cursor:

            cursor.execute(

                """
                SELECT
                    im.id AS incoming_id,
                    pm.id AS parsed_id,
                    pm.forwarded_message_id,
                    ts.asset,
                    ts.side,
                    ts.amount_usd,
                    ts.duration_minutes,
                    ts.price,
                    ts.market_volume_usd,
                    ts.twap_share_percent,
                    ts.score,
                    ts.user_address,
                    ts.payload_json
                FROM incoming_messages im
                JOIN parsed_messages pm ON pm.incoming_message_id = im.id
                LEFT JOIN twap_signals ts ON ts.parsed_message_id = pm.id
                WHERE im.group_name = %s
                  AND im.telegram_chat_id = %s
                  AND im.telegram_message_id = %s
                  AND pm.parser_key = %s
                  AND pm.kind = 'twap_created'
                  AND pm.status = 'accepted'
                ORDER BY pm.id DESC
                LIMIT 1
                """,

                (group_name, chat_id, reply_to_message_id, parser_key),

            )

            row = cursor.fetchone()

            if not row:

                return None


        row["payload"] = _json_load(row.get("payload_json"))

        return row


    def save_twap_signal(self, parsed_id: int, group_name: str, result: ParseResult) -> None:

        payload = result.payload

        with db_cursor() as cursor:

            cursor.execute(

                """
                INSERT INTO twap_signals
                    (parsed_message_id, group_name, kind, asset, side, amount_usd, duration_minutes,
                     price, market_volume_usd, twap_share_percent, score, user_address, twap_id,
                     executed_percent, result_percent, payload_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON))
                ON DUPLICATE KEY UPDATE
                    kind = VALUES(kind),
                    asset = VALUES(asset),
                    side = VALUES(side),
                    amount_usd = VALUES(amount_usd),
                    duration_minutes = VALUES(duration_minutes),
                    price = VALUES(price),
                    market_volume_usd = VALUES(market_volume_usd),
                    twap_share_percent = VALUES(twap_share_percent),
                    score = VALUES(score),
                    user_address = VALUES(user_address),
                    twap_id = VALUES(twap_id),
                    executed_percent = VALUES(executed_percent),
                    result_percent = VALUES(result_percent),
                    payload_json = VALUES(payload_json)
                """,

                (

                    parsed_id,

                    group_name,

                    result.kind,

                    payload.get("asset"),

                    payload.get("side"),

                    payload.get("amount_usd"),

                    payload.get("duration_minutes"),

                    payload.get("price"),

                    payload.get("market_volume_usd"),

                    payload.get("twap_share_percent"),

                    payload.get("score"),

                    payload.get("user_address"),

                    payload.get("twap_id"),

                    payload.get("executed_percent"),

                    payload.get("result_percent"),

                    json_dump(payload),

                ),

            )


    def mark_forwarded(self, parsed_id: int, forwarded_message_id: int | None) -> None:

        with db_cursor() as cursor:

            cursor.execute(

                "UPDATE parsed_messages SET forwarded_message_id = %s WHERE id = %s",

                (forwarded_message_id, parsed_id),

            )


def _dt(value: datetime | None) -> str | None:

    if value is None:

        return None

    return value.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def _json_load(value: Any) -> dict[str, Any]:

    if isinstance(value, dict):

        return value

    if not value:

        return {}

    try:

        return json.loads(value)

    except Exception:

        return {}
