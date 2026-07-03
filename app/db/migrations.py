from __future__ import annotations

import logging

from mysql.connector import Error as MySQLError

from app.db.connection import db_cursor

logger = logging.getLogger(__name__)

_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS source_groups (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(64) NOT NULL,
        source_chat_id BIGINT NOT NULL,
        source_thread_id BIGINT NOT NULL DEFAULT 0,
        target_chat_id BIGINT NOT NULL,
        target_thread_id BIGINT NULL,
        parser_key VARCHAR(64) NOT NULL,
        filters_json JSON NOT NULL,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_source_group_chat_thread (name, source_chat_id, source_thread_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS incoming_messages (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        group_name VARCHAR(64) NOT NULL,
        telegram_chat_id BIGINT NOT NULL,
        telegram_thread_id BIGINT NULL,
        telegram_message_id BIGINT NOT NULL,
        telegram_reply_to_message_id BIGINT NULL,
        message_date DATETIME NULL,
        raw_text MEDIUMTEXT NOT NULL,
        raw_json JSON NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_chat_message (telegram_chat_id, telegram_message_id),
        KEY idx_group_date (group_name, message_date),
        KEY idx_chat_thread (telegram_chat_id, telegram_thread_id),
        KEY idx_reply_message (telegram_chat_id, telegram_reply_to_message_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS parsed_messages (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        incoming_message_id BIGINT UNSIGNED NOT NULL,
        related_incoming_message_id BIGINT UNSIGNED NULL,
        related_parsed_message_id BIGINT UNSIGNED NULL,
        parser_key VARCHAR(64) NOT NULL,
        kind VARCHAR(64) NOT NULL,
        status VARCHAR(32) NOT NULL,
        reason VARCHAR(255) NOT NULL,
        payload_json JSON NOT NULL,
        forwarded_message_id BIGINT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_incoming_parser (incoming_message_id, parser_key),
        KEY idx_status_kind (status, kind),
        KEY idx_related_incoming (related_incoming_message_id),
        KEY idx_related_parsed (related_parsed_message_id),
        CONSTRAINT fk_parsed_incoming FOREIGN KEY (incoming_message_id)
            REFERENCES incoming_messages(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS twap_signals (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        parsed_message_id BIGINT UNSIGNED NOT NULL,
        group_name VARCHAR(64) NOT NULL,
        kind VARCHAR(64) NOT NULL,
        asset VARCHAR(32) NULL,
        side VARCHAR(16) NULL,
        amount_usd DECIMAL(24, 8) NULL,
        duration_minutes DECIMAL(12, 4) NULL,
        price DECIMAL(24, 10) NULL,
        market_volume_usd DECIMAL(24, 8) NULL,
        twap_share_percent DECIMAL(12, 6) NULL,
        score DECIMAL(12, 4) NULL,
        user_address VARCHAR(96) NULL,
        twap_id BIGINT NULL,
        executed_percent DECIMAL(12, 6) NULL,
        result_percent DECIMAL(12, 6) NULL,
        payload_json JSON NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_twap_parsed (parsed_message_id),
        KEY idx_asset (asset),
        KEY idx_filters (amount_usd, duration_minutes, market_volume_usd, twap_share_percent),
        KEY idx_twap_id (twap_id),
        CONSTRAINT fk_twap_parsed FOREIGN KEY (parsed_message_id)
            REFERENCES parsed_messages(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]

_ALTERS = [
    "ALTER TABLE incoming_messages ADD COLUMN telegram_reply_to_message_id BIGINT NULL AFTER telegram_message_id",
    "ALTER TABLE incoming_messages ADD KEY idx_reply_message (telegram_chat_id, telegram_reply_to_message_id)",
    "ALTER TABLE parsed_messages ADD COLUMN related_incoming_message_id BIGINT UNSIGNED NULL AFTER incoming_message_id",
    "ALTER TABLE parsed_messages ADD COLUMN related_parsed_message_id BIGINT UNSIGNED NULL AFTER related_incoming_message_id",
    "ALTER TABLE parsed_messages ADD KEY idx_related_incoming (related_incoming_message_id)",
    "ALTER TABLE parsed_messages ADD KEY idx_related_parsed (related_parsed_message_id)",
]


def migrate() -> None:
    with db_cursor() as cursor:
        for query in _TABLES:
            cursor.execute(query)
        for query in _ALTERS:
            try:
                cursor.execute(query)
            except MySQLError as exc:
                if exc.errno not in {1060, 1061}:  # duplicate column/key
                    raise
                logger.debug("Migration skipped existing schema object: %s", query)

