from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

from app.platform.accounts.repository import AccountError, AccountRepository

logger = logging.getLogger(__name__)


class TelegramAccountBot:
    def __init__(self, repository: AccountRepository, token: str | None = None) -> None:
        self.repository = repository
        self.token = (token or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        self.poll_seconds = float(os.getenv("TELEGRAM_BOT_POLL_SECONDS") or "2")
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._offset = 0

    def start(self) -> None:
        if not self.token:
            logger.warning("Telegram account bot disabled: TELEGRAM_BOT_TOKEN is empty")
            return
        if self._task is None or self._task.done():
            self._stop = asyncio.Event()
            self._task = asyncio.create_task(self._run())
            logger.info("Telegram account bot started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        base_url = f"https://api.telegram.org/bot{self.token}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            while not self._stop.is_set():
                try:
                    response = await client.get(
                        f"{base_url}/getUpdates",
                        params={"offset": self._offset, "timeout": 15, "allowed_updates": '["message"]'},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if not payload.get("ok"):
                        logger.warning("Telegram bot getUpdates returned not ok: %s", payload)
                        await self._sleep()
                        continue

                    for update in payload.get("result") or []:
                        self._offset = max(self._offset, int(update.get("update_id") or 0) + 1)
                        await self._handle_update(client, base_url, update)
                except Exception as exc:
                    logger.exception("Telegram account bot polling failed: %s", exc)
                    await self._sleep(5)

    async def _handle_update(self, client: httpx.AsyncClient, base_url: str, update: dict[str, Any]) -> None:
        message = update.get("message") if isinstance(update.get("message"), dict) else {}
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        sender = message.get("from") if isinstance(message.get("from"), dict) else {}
        chat_id = int(chat.get("id") or 0)
        telegram_user_id = int(sender.get("id") or 0)
        text = str(message.get("text") or "").strip()

        if not chat_id or not telegram_user_id or not text.startswith("/"):
            return

        reply = self._dispatch(telegram_user_id, chat_id, text)
        await self._send_message(client, base_url, chat_id, reply)

    def _dispatch(self, telegram_user_id: int, chat_id: int, text: str) -> str:
        parts = text.split(maxsplit=1)
        command = parts[0].split("@", 1)[0].lower()
        payload = parts[1].strip().lower() if len(parts) > 1 else ""

        try:
            if command == "/start":
                if payload in {"register", "registration", "reg"}:
                    return self._registration_code(telegram_user_id, chat_id)
                if payload in {"login", "code", "auth"}:
                    return self._login_code(telegram_user_id)
                return _help_text()
            if command == "/help":
                return _help_text()
            if command == "/register":
                return self._registration_code(telegram_user_id, chat_id)
            if command == "/code":
                return self._login_code(telegram_user_id)
            if command == "/activate":
                rest = payload.split()
                if not rest:
                    return "Формат: /activate TWAP-..."
                user = self.repository.redeem_activation_key_for_telegram(telegram_user_id, rest[0])
                return (
                    "Ключ активирован.\n"
                    f"Логин: {user.get('login')}\n"
                    f"Доступ до: {user.get('access_until') or 'нет'}"
                )
            if command == "/status":
                user = self.repository.get_user_by_telegram(telegram_user_id)
                if not user:
                    return "Telegram не привязан. Зарегистрируйтесь через сайт и получите код через кнопку Telegram-бота."
                public = self.repository.get_user_by_id(int(user["id"])) or user
                return (
                    f"Логин: {public.get('login')}\n"
                    f"Доступ до: {public.get('access_until') or 'нет'}"
                )
            if command == "/logout":
                user = self.repository.get_user_by_telegram(telegram_user_id)
                if not user:
                    return "Telegram не привязан."
                count = self.repository.close_sessions_for_user(int(user["id"]), "telegram_logout")
                return f"Активные сессии закрыты: {count}"
        except AccountError as exc:
            return str(exc)
        except Exception as exc:
            logger.exception("Telegram bot command failed: %s", text)
            return f"Ошибка: {exc}"

        return "Неизвестная команда. Используйте /help"

    def _registration_code(self, telegram_user_id: int, chat_id: int) -> str:
        code = self.repository.create_registration_code_for_telegram(telegram_user_id, chat_id)
        return (
            "Код регистрации для сайта:\n"
            f"{code}\n\n"
            "Вернитесь на страницу регистрации, введите логин, пароль и этот код. Код действует 10 минут."
        )

    def _login_code(self, telegram_user_id: int) -> str:
        code = self.repository.create_login_code_for_telegram(telegram_user_id)
        return (
            "Код входа:\n"
            f"{code}\n\n"
            "Код действует 5 минут. Для каждого входа нужен новый код."
        )

    async def _send_message(self, client: httpx.AsyncClient, base_url: str, chat_id: int, text: str) -> None:
        await client.post(
            f"{base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text[:3900], "disable_web_page_preview": True},
        )

    async def _sleep(self, seconds: float | None = None) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds or self.poll_seconds)
        except asyncio.TimeoutError:
            pass


def _help_text() -> str:
    site = (os.getenv("PUBLIC_BASE_URL") or "https://beta.twaps.ru").rstrip("/")
    return (
        "TWAP бот кодов входа и активации.\n\n"
        f"Сайт / ЛК: {site}\n\n"
        "Команды:\n"
        "/register — получить код регистрации для сайта\n"
        "/code — получить одноразовый код входа\n"
        "/activate TWAP-... — активировать ключ и добавить время работы\n"
        "/status — проверить доступ\n"
        "/logout — закрыть активную сессию софта\n\n"
        "Регистрация и вход выполняются на сайте; бот только выдаёт одноразовые коды."
    )
