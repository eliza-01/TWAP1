from __future__ import annotations

import asyncio
import logging
from typing import Any

from telethon import TelegramClient, events
from telethon.tl.custom.message import Message

from app.core.env import AppSettings, ensure_runtime_dirs
from app.db.repositories import MessageRepository, SourceGroupRepository
from app.groups.registry import GroupProcessor
from app.shared.types import IncomingMessage

logger = logging.getLogger(__name__)


class TelegramRuntime:
    def __init__(
        self,
        settings: AppSettings,
        processors: list[GroupProcessor],
        message_repo: MessageRepository,
        group_repo: SourceGroupRepository,
    ) -> None:
        self.settings = settings
        self.processors = processors
        self.message_repo = message_repo
        self.group_repo = group_repo
        self.client = TelegramClient(
            settings.telegram.session_path,
            settings.telegram.api_id,
            settings.telegram.api_hash,
        )
        self._processors_by_chat_id: dict[int, list[GroupProcessor]] = {}
        for processor in processors:
            for chat_id in processor.config.source_chat_ids:
                self._processors_by_chat_id.setdefault(chat_id, []).append(processor)

    async def login(self) -> None:
        ensure_runtime_dirs(self.settings)
        await self.client.start(phone=self.settings.telegram.phone or None)
        me = await self.client.get_me()
        logger.info("Telegram session is ready: %s", getattr(me, "username", None) or getattr(me, "id", "unknown"))
        await self.client.disconnect()

    async def listen(self) -> None:
        self._validate_settings()
        ensure_runtime_dirs(self.settings)
        for processor in self.processors:
            self.group_repo.upsert(processor.config, processor.parser_key)

        await self.client.start(phone=self.settings.telegram.phone or None)
        self._register_handlers()
        logger.info("Listening chats: %s", sorted(self._processors_by_chat_id.keys()))
        await self.client.run_until_disconnected()

    async def import_history(self, limit: int) -> None:
        self._validate_settings()
        ensure_runtime_dirs(self.settings)
        await self.client.start(phone=self.settings.telegram.phone or None)

        for processor in self.processors:
            for chat_id in processor.config.source_chat_ids:
                logger.info("Importing history: group=%s chat=%s limit=%s", processor.config.name, chat_id, limit)
                async for message in self.client.iter_messages(chat_id, limit=limit, reverse=True):
                    thread_id = _message_thread_id(message)
                    if not processor.config.allows_source_thread(chat_id, thread_id):
                        continue
                    await self._handle_message(processor, chat_id, message, thread_id)

        await self.client.disconnect()

    def _register_handlers(self) -> None:
        chats = list(self._processors_by_chat_id.keys())

        @self.client.on(events.NewMessage(chats=chats))
        async def _handler(event: events.NewMessage.Event) -> None:
            chat_id = int(event.chat_id)
            processors = self._processors_by_chat_id.get(chat_id, [])
            if not processors:
                logger.warning("No processor for chat_id=%s", event.chat_id)
                return

            thread_id = _message_thread_id(event.message)
            reply_to_message_id = _message_reply_to_id(event.message)
            logger.info(
                "Incoming Telegram message: chat=%s thread=%s reply_to=%s msg=%s sender=%s",
                chat_id,
                thread_id,
                reply_to_message_id,
                event.message.id,
                getattr(event.message, "sender_id", None),
            )

            matched = False
            for processor in processors:
                if processor.config.allows_source_thread(chat_id, thread_id):
                    matched = True
                    await self._handle_message(processor, chat_id, event.message, thread_id)

            if not matched:
                logger.info(
                    "Message ignored by source thread filter: chat=%s thread=%s msg=%s",
                    chat_id,
                    thread_id,
                    event.message.id,
                )

    async def _handle_message(self, processor: GroupProcessor, chat_id: int, message: Message, thread_id: int | None) -> None:
        text = message.raw_text or ""
        incoming = IncomingMessage(
            group_name=processor.config.name,
            chat_id=chat_id,
            thread_id=thread_id,
            message_id=int(message.id),
            reply_to_message_id=_message_reply_to_id(message),
            text=text,
            message_date=message.date,
            raw_json=_safe_message_json(message),
        )

        incoming_id, _ = await asyncio.to_thread(self.message_repo.save_incoming, incoming)
        result = processor.process(text)
        parsed_id = await asyncio.to_thread(self.message_repo.save_parsed, incoming_id, processor.parser_key, result)

        if result.kind in {"twap_created", "twap_result"} and result.status in {"accepted", "rejected"}:
            await asyncio.to_thread(self.message_repo.save_twap_signal, parsed_id, processor.config.name, result)

        if result.kind == "twap_result" and result.status == "accepted":
            original = await asyncio.to_thread(
                self.message_repo.find_forwarded_created_by_reply,
                processor.config.name,
                processor.parser_key,
                chat_id,
                _message_reply_to_id(message),
            )
            if original:
                await asyncio.to_thread(self.message_repo.link_result_to_created, parsed_id, original)

            if processor.should_forward_result(result, original):
                forwarded_id = await self._forward_result(processor, result, original)
                await asyncio.to_thread(self.message_repo.mark_forwarded, parsed_id, forwarded_id)
                logger.info(
                    "Forwarded TWAP result: group=%s msg=%s related_source_msg=%s forwarded=%s",
                    processor.config.name,
                    message.id,
                    _message_reply_to_id(message),
                    forwarded_id,
                )
                return

            logger.info(
                "TWAP result stored without forward: group=%s chat=%s msg=%s reply_to=%s matched_original=%s",
                processor.config.name,
                chat_id,
                message.id,
                _message_reply_to_id(message),
                bool(original),
            )
            return

        if not processor.should_forward(result):
            logger.info(
                "Message skipped: group=%s chat=%s msg=%s kind=%s status=%s reason=%s",
                processor.config.name,
                chat_id,
                message.id,
                result.kind,
                result.status,
                result.reason,
            )
            return

        forwarded_id = await self._forward_created(processor, result)
        await asyncio.to_thread(self.message_repo.mark_forwarded, parsed_id, forwarded_id)
        logger.info("Forwarded accepted TWAP: group=%s msg=%s forwarded=%s", processor.config.name, message.id, forwarded_id)

    async def _forward_created(self, processor: GroupProcessor, result) -> int | None:
        kwargs: dict[str, Any] = {}
        if processor.config.target_thread_id:
            kwargs["reply_to"] = processor.config.target_thread_id

        sent = await self.client.send_message(
            processor.config.target_chat_id,
            processor.format_forward(result),
            **kwargs,
        )
        return int(sent.id) if sent else None

    async def _forward_result(self, processor: GroupProcessor, result, original: dict[str, Any]) -> int | None:
        reply_to = original.get("forwarded_message_id") or processor.config.target_thread_id
        kwargs: dict[str, Any] = {}
        if reply_to:
            kwargs["reply_to"] = int(reply_to)

        sent = await self.client.send_message(
            processor.config.target_chat_id,
            processor.format_result(result, original),
            **kwargs,
        )
        return int(sent.id) if sent else None

    def _validate_settings(self) -> None:
        if not self.settings.telegram.api_id or not self.settings.telegram.api_hash:
            raise ValueError("Fill TELEGRAM_API_ID and TELEGRAM_API_HASH in .env")


def _safe_message_json(message: Message) -> dict[str, Any]:
    try:
        return message.to_dict()
    except Exception as exc:
        return {"serialization_error": str(exc), "id": getattr(message, "id", None)}


def _message_thread_id(message: Message) -> int | None:
    reply_to = getattr(message, "reply_to", None)
    if reply_to:
        top_id = getattr(reply_to, "reply_to_top_id", None)
        if top_id:
            return int(top_id)

        reply_to_id = getattr(reply_to, "reply_to_msg_id", None)
        if reply_to_id:
            return int(reply_to_id)

    reply_to_msg_id = getattr(message, "reply_to_msg_id", None)
    return int(reply_to_msg_id) if reply_to_msg_id else None


def _message_reply_to_id(message: Message) -> int | None:
    reply_to = getattr(message, "reply_to", None)
    if reply_to:
        reply_to_id = getattr(reply_to, "reply_to_msg_id", None)
        if reply_to_id:
            return int(reply_to_id)

    reply_to_msg_id = getattr(message, "reply_to_msg_id", None)
    return int(reply_to_msg_id) if reply_to_msg_id else None
