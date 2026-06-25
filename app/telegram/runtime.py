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
from app.telegram.debug import (
    DebugContext,
    format_debug_result,
    format_debug_runtime_error,
    is_debug_message,
    should_send_debug,
)

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

            text = event.message.raw_text or ""
            if is_debug_message(text):
                logger.debug("Own debug message ignored: chat=%s msg=%s", chat_id, event.message.id)
                return

            matched = False
            for processor in processors:
                if processor.config.allows_source_thread(chat_id, thread_id):
                    matched = True
                    try:
                        await self._handle_message(processor, chat_id, event.message, thread_id)
                    except Exception as exc:
                        logger.exception(
                            "Unhandled message processing error: group=%s chat=%s msg=%s",
                            processor.config.name,
                            chat_id,
                            event.message.id,
                        )
                        await self._send_debug_runtime_error(processor, chat_id, event.message, thread_id, exc)

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
                forwarded_id: int | None = None
                target_error: str | None = None
                try:
                    forwarded_id = await self._forward_result(processor, result, original)
                except Exception as exc:
                    target_error = f"{type(exc).__name__}: {exc}"
                    logger.exception(
                        "Failed to forward TWAP result: group=%s source_chat=%s source_msg=%s target_chat=%s target_thread=%s",
                        processor.config.name,
                        chat_id,
                        message.id,
                        processor.config.target_chat_id,
                        processor.config.target_thread_id,
                    )

                await asyncio.to_thread(self.message_repo.mark_forwarded, parsed_id, forwarded_id)
                await self._send_debug_result(
                    processor,
                    result,
                    chat_id,
                    message,
                    thread_id,
                    incoming_id,
                    parsed_id,
                    forwarded_id,
                    related_message_found=True,
                    target_error=target_error,
                    action="twap_result_forward_failed" if target_error else "twap_result_forwarded",
                )
                if target_error:
                    return
                logger.info(
                    "Forwarded TWAP result: group=%s msg=%s related_source_msg=%s forwarded=%s",
                    processor.config.name,
                    message.id,
                    _message_reply_to_id(message),
                    forwarded_id,
                )
                return

            await self._send_debug_result(
                processor,
                result,
                chat_id,
                message,
                thread_id,
                incoming_id,
                parsed_id,
                related_message_found=bool(original),
                action="twap_result_stored_without_forward",
            )
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
            await self._send_debug_result(
                processor,
                result,
                chat_id,
                message,
                thread_id,
                incoming_id,
                parsed_id,
                action="not_forwarded",
            )
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

        forwarded_id: int | None = None
        target_error: str | None = None
        try:
            forwarded_id = await self._forward_created(processor, result)
        except Exception as exc:
            target_error = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "Failed to forward accepted TWAP: group=%s source_chat=%s source_msg=%s target_chat=%s target_thread=%s",
                processor.config.name,
                chat_id,
                message.id,
                processor.config.target_chat_id,
                processor.config.target_thread_id,
            )

        await asyncio.to_thread(self.message_repo.mark_forwarded, parsed_id, forwarded_id)
        await self._send_debug_result(
            processor,
            result,
            chat_id,
            message,
            thread_id,
            incoming_id,
            parsed_id,
            forwarded_id,
            target_error=target_error,
            action="twap_created_forward_failed" if target_error else "twap_created_forwarded",
        )
        if target_error:
            return
        logger.info("Forwarded accepted TWAP: group=%s msg=%s forwarded=%s", processor.config.name, message.id, forwarded_id)

    async def _send_debug_result(
        self,
        processor: GroupProcessor,
        result,
        chat_id: int,
        message: Message,
        thread_id: int | None,
        incoming_id: int | None,
        parsed_id: int | None,
        forwarded_message_id: int | None = None,
        related_message_found: bool | None = None,
        target_error: str | None = None,
        action: str = "processed",
    ) -> None:
        debug = self.settings.debug
        if not debug.enabled or debug.chat_id is None:
            return
        if not should_send_debug(result.status, debug.send_skipped):
            return

        ctx = DebugContext(
            group_name=processor.config.name,
            parser_key=processor.parser_key,
            chat_id=chat_id,
            thread_id=thread_id,
            message_id=int(message.id),
            reply_to_message_id=_message_reply_to_id(message),
            message_text=message.raw_text or "",
            filters=processor.config.filters,
            incoming_id=incoming_id,
            parsed_id=parsed_id,
            forwarded_message_id=forwarded_message_id,
            related_message_found=related_message_found,
            target_error=target_error,
            action=action,
        )
        await self._send_debug_message(chat_id, thread_id, int(message.id), format_debug_result(result, ctx))

    async def _send_debug_runtime_error(
        self,
        processor: GroupProcessor,
        chat_id: int,
        message: Message,
        thread_id: int | None,
        error: Exception,
    ) -> None:
        debug = self.settings.debug
        if not debug.enabled or debug.chat_id is None:
            return

        ctx = DebugContext(
            group_name=processor.config.name,
            parser_key=processor.parser_key,
            chat_id=chat_id,
            thread_id=thread_id,
            message_id=int(message.id),
            reply_to_message_id=_message_reply_to_id(message),
            message_text=message.raw_text or "",
            filters=processor.config.filters,
            action="runtime_exception",
        )
        await self._send_debug_message(chat_id, thread_id, int(message.id), format_debug_runtime_error(ctx, error))

    async def _send_debug_message(self, source_chat_id: int, source_thread_id: int | None, source_message_id: int, text: str) -> None:
        debug = self.settings.debug
        if not debug.enabled or debug.chat_id is None:
            return

        reply_to = self._debug_reply_to(source_chat_id, source_thread_id, source_message_id)
        kwargs: dict[str, Any] = {}
        if reply_to:
            kwargs["reply_to"] = reply_to

        try:
            await self.client.send_message(debug.chat_id, text, parse_mode="html", link_preview=False, **kwargs)
        except Exception:
            logger.exception("Failed to send debug message: debug_chat=%s reply_to=%s", debug.chat_id, reply_to)

    def _debug_reply_to(self, source_chat_id: int, source_thread_id: int | None, source_message_id: int) -> int | None:
        debug = self.settings.debug
        if debug.chat_id is None:
            return None

        if debug.chat_id == source_chat_id and (debug.thread_id is None or debug.thread_id == source_thread_id):
            return source_message_id

        return debug.thread_id

    async def _forward_created(self, processor: GroupProcessor, result) -> int | None:
        kwargs: dict[str, Any] = {}
        if processor.config.target_thread_id:
            kwargs["reply_to"] = processor.config.target_thread_id

        logger.info(
            "Sending accepted TWAP to target: group=%s target_chat=%s target_thread=%s asset=%s",
            processor.config.name,
            processor.config.target_chat_id,
            processor.config.target_thread_id,
            result.payload.get("asset"),
        )
        sent = await self.client.send_message(
            processor.config.target_chat_id,
            processor.format_forward(result),
            link_preview=False,
            **kwargs,
        )
        logger.info(
            "Target accepted TWAP sent: group=%s target_chat=%s target_thread=%s sent_msg=%s",
            processor.config.name,
            processor.config.target_chat_id,
            processor.config.target_thread_id,
            getattr(sent, "id", None),
        )
        return int(sent.id) if sent else None

    async def _forward_result(self, processor: GroupProcessor, result, original: dict[str, Any]) -> int | None:
        reply_to = original.get("forwarded_message_id") or processor.config.target_thread_id
        kwargs: dict[str, Any] = {}
        if reply_to:
            kwargs["reply_to"] = int(reply_to)

        logger.info(
            "Sending TWAP result to target: group=%s target_chat=%s reply_to=%s asset=%s",
            processor.config.name,
            processor.config.target_chat_id,
            reply_to,
            result.payload.get("asset"),
        )
        sent = await self.client.send_message(
            processor.config.target_chat_id,
            processor.format_result(result, original),
            link_preview=False,
            **kwargs,
        )
        logger.info(
            "Target TWAP result sent: group=%s target_chat=%s sent_msg=%s",
            processor.config.name,
            processor.config.target_chat_id,
            getattr(sent, "id", None),
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
