from __future__ import annotations

import asyncio
import logging
from typing import Any

from telethon import TelegramClient, events, functions, helpers
from telethon.tl.custom.message import Message

from app.core.env import AppSettings, ensure_runtime_dirs
from app.db.repositories import MessageRepository, SourceGroupRepository
from app.groups.registry import GroupProcessor
from app.shared.types import IncomingMessage
from app.telegram.debug import (
    DebugContext,
    format_debug_result,
    format_debug_runtime_error,
    format_target_result,
    format_target_runtime_error,
    format_target_status,
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
        self._handlers_registered = False

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

        # Register the Telethon handler before connecting. Otherwise updates that arrive
        # during TelegramClient.start() can be consumed before our NewMessage handler exists.
        self._register_handlers()
        await self.client.start(phone=self.settings.telegram.phone or None)
        await self._log_source_chats_state()
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
        if self._handlers_registered:
            return
        self._handlers_registered = True
        chats = sorted(self._processors_by_chat_id.keys())
        logger.info("Registering Telegram NewMessage handler for source chats: %s", chats)

        # Do not pass chats=... here. With user sessions and channel/forum entities,
        # Telethon can miss updates when an entity is not resolved exactly as the raw
        # numeric -100... id. We accept all updates and immediately filter by chat_id
        # ourselves, so the processing rules stay the same but the listener is safer.
        @self.client.on(events.NewMessage)
        async def _handler(event: events.NewMessage.Event) -> None:
            chat_id = int(event.chat_id)
            processors = self._processors_by_chat_id.get(chat_id, [])
            if not processors:
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
                        await self._send_target_runtime_error(processor, chat_id, event.message, thread_id, exc)
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

        related_message_found: bool | None = None
        if result.kind == "twap_result" and result.status == "accepted":
            original = await asyncio.to_thread(
                self.message_repo.find_forwarded_created_by_reply,
                processor.config.name,
                processor.parser_key,
                chat_id,
                _message_reply_to_id(message),
            )
            related_message_found = bool(original)
            if original:
                await asyncio.to_thread(self.message_repo.link_result_to_created, parsed_id, original)

        if result.kind in {"twap_created", "twap_result"} and result.status in {"accepted", "rejected"}:
            await asyncio.to_thread(self.message_repo.save_twap_signal, parsed_id, processor.config.name, result)

        forwarded_id, target_error = await self._forward_processed_message(
            processor,
            result,
            chat_id,
            message,
            thread_id,
            incoming_id,
            parsed_id,
            related_message_found=related_message_found,
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
            related_message_found=related_message_found,
            target_error=target_error,
            action="target_forward_failed" if target_error else "target_forwarded",
        )

        logger.info(
            "Message processed and forwarded to target: group=%s chat=%s msg=%s kind=%s status=%s reason=%s forwarded=%s",
            processor.config.name,
            chat_id,
            message.id,
            result.kind,
            result.status,
            result.reason,
            forwarded_id,
        )

    async def _log_source_chats_state(self) -> None:
        for chat_id in sorted(self._processors_by_chat_id.keys()):
            try:
                entity = await self.client.get_entity(chat_id)
                logger.info(
                    "Source chat resolved: chat=%s title=%s username=%s",
                    chat_id,
                    getattr(entity, "title", None),
                    getattr(entity, "username", None),
                )
            except Exception:
                logger.exception(
                    "Failed to resolve source chat. Check TWAPX_SOURCE_CHAT_IDS and Telegram account access: chat=%s",
                    chat_id,
                )

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

    async def _send_target_runtime_error(
        self,
        processor: GroupProcessor,
        chat_id: int,
        message: Message,
        thread_id: int | None,
        error: Exception,
    ) -> None:
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
            show_target_line=False,
        )

        try:
            forwarded_id = await self._forward_source_message_to_target(processor, chat_id, message)
            await self._send_target_status(processor, "error", forwarded_id)
        except Exception as forward_exc:
            logger.exception(
                "Failed to forward runtime error source message to target: target_chat=%s target_thread=%s",
                processor.config.target_chat_id,
                processor.config.target_thread_id,
            )
            await self._send_target_fallback_report(
                processor,
                format_target_runtime_error(ctx, error),
                f"{type(forward_exc).__name__}: {forward_exc}",
            )

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

    async def _forward_processed_message(
        self,
        processor: GroupProcessor,
        result,
        chat_id: int,
        message: Message,
        thread_id: int | None,
        incoming_id: int | None,
        parsed_id: int | None,
        related_message_found: bool | None = None,
    ) -> tuple[int | None, str | None]:
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
            related_message_found=related_message_found,
            action="target_forward",
            show_target_line=False,
        )

        try:
            forwarded_id = await self._forward_source_message_to_target(processor, chat_id, message)
        except Exception as exc:
            target_error = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "Failed to forward source message to target: group=%s source_chat=%s source_msg=%s target_chat=%s target_thread=%s",
                processor.config.name,
                chat_id,
                message.id,
                processor.config.target_chat_id,
                processor.config.target_thread_id,
            )
            await self._send_target_fallback_report(processor, format_target_result(result, ctx), target_error)
            return None, target_error

        try:
            await self._send_target_status(processor, result.status, forwarded_id)
            return forwarded_id, None
        except Exception as exc:
            target_error = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "Failed to send target status reply: group=%s forwarded_msg=%s target_chat=%s",
                processor.config.name,
                forwarded_id,
                processor.config.target_chat_id,
            )
            return forwarded_id, target_error

    async def _forward_source_message_to_target(self, processor: GroupProcessor, source_chat_id: int, message: Message) -> int | None:
        logger.info(
            "Forwarding source message to target: group=%s source_chat=%s source_msg=%s target_chat=%s target_thread=%s",
            processor.config.name,
            source_chat_id,
            message.id,
            processor.config.target_chat_id,
            processor.config.target_thread_id,
        )

        try:
            sent = await self._forward_source_message_to_topic(processor, source_chat_id, int(message.id))
        except TypeError:
            logger.warning("Topic-aware forward is not supported by current Telethon build; using forward_messages fallback")
            sent = await self.client.forward_messages(
                processor.config.target_chat_id,
                int(message.id),
                from_peer=source_chat_id,
            )

        forwarded_id = _sent_message_id(sent)
        logger.info(
            "Source message forwarded: group=%s target_chat=%s target_thread=%s forwarded_msg=%s",
            processor.config.name,
            processor.config.target_chat_id,
            processor.config.target_thread_id,
            forwarded_id,
        )
        return forwarded_id

    async def _forward_source_message_to_topic(self, processor: GroupProcessor, source_chat_id: int, source_message_id: int):
        source_peer = await self.client.get_input_entity(source_chat_id)
        target_peer = await self.client.get_input_entity(processor.config.target_chat_id)
        request = functions.messages.ForwardMessagesRequest(
            from_peer=source_peer,
            id=[source_message_id],
            random_id=[helpers.generate_random_long()],
            to_peer=target_peer,
            top_msg_id=processor.config.target_thread_id or None,
        )
        result = await self.client(request)
        return _forward_response_message(result)

    async def _send_target_status(self, processor: GroupProcessor, status: str, forwarded_message_id: int | None) -> int | None:
        kwargs: dict[str, Any] = {}
        if forwarded_message_id:
            kwargs["reply_to"] = forwarded_message_id
        elif processor.config.target_thread_id:
            kwargs["reply_to"] = processor.config.target_thread_id

        sent = await self.client.send_message(
            processor.config.target_chat_id,
            format_target_status(status),
            link_preview=False,
            **kwargs,
        )
        return int(sent.id) if sent else None

    async def _send_target_fallback_report(self, processor: GroupProcessor, text: str, target_error: str) -> None:
        kwargs: dict[str, Any] = {}
        if processor.config.target_thread_id:
            kwargs["reply_to"] = processor.config.target_thread_id

        try:
            await self.client.send_message(
                processor.config.target_chat_id,
                f"{text}\n\n<b>Ошибка пересылки:</b> <code>{target_error}</code>",
                parse_mode="html",
                link_preview=False,
                **kwargs,
            )
        except Exception:
            logger.exception(
                "Failed to send fallback target report: target_chat=%s target_thread=%s",
                processor.config.target_chat_id,
                processor.config.target_thread_id,
            )

    def _validate_settings(self) -> None:
        if not self.settings.telegram.api_id or not self.settings.telegram.api_hash:
            raise ValueError("Fill TELEGRAM_API_ID and TELEGRAM_API_HASH in .env")



def _forward_response_message(result):
    if result is None:
        return None
    updates = getattr(result, "updates", None) or []
    for update in updates:
        message = getattr(update, "message", None)
        if message is not None and getattr(message, "id", None) is not None:
            return message
    return result


def _sent_message_id(sent) -> int | None:
    if sent is None:
        return None
    if isinstance(sent, list):
        return _sent_message_id(sent[0]) if sent else None
    if getattr(sent, "id", None) is not None:
        return int(sent.id)
    return None

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
