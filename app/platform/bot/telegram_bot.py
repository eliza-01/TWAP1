from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from app.platform.accounts.repository import AccountError, AccountRepository

logger = logging.getLogger(__name__)

GET_CODE_BUTTON = "Получить код"
CHECK_BALANCE_BUTTON = "Проверить баланс"


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

        if not chat_id or not telegram_user_id or not text:
            return

        reply = self._dispatch(telegram_user_id, chat_id, text)
        await self._send_message(
            client,
            base_url,
            chat_id,
            reply,
            attach_keyboard=_should_attach_keyboard(text),
        )

    def _dispatch(self, telegram_user_id: int, chat_id: int, text: str) -> str:
        clean_text = str(text or "").strip()
        normalized_text = clean_text.casefold()

        try:
            if normalized_text in {"получить код", "код", "get code"}:
                return self._smart_code(telegram_user_id, chat_id)
            if normalized_text in {"проверить баланс", "баланс", "balance", "status"}:
                return self._balance_text(telegram_user_id)

            if not clean_text.startswith("/"):
                return _help_text()

            parts = clean_text.split(maxsplit=1)
            command = parts[0].split("@", 1)[0].lower()
            payload = parts[1].strip() if len(parts) > 1 else ""
            payload_normalized = payload.casefold()

            if command == "/start":
                if payload_normalized in {"register", "registration", "reg"}:
                    return self._registration_code(telegram_user_id, chat_id)
                if payload_normalized in {"login", "code", "auth"}:
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
                    f"Доступ до: {user.get('access_until') or 'нет'}\n"
                    f"Осталось: {_remaining_access_text(user.get('access_until'))}"
                )
            if command == "/status":
                return self._balance_text(telegram_user_id)
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

    def _smart_code(self, telegram_user_id: int, chat_id: int) -> str:
        user = self.repository.get_user_by_telegram(telegram_user_id)
        if user:
            return self._login_code(telegram_user_id)
        return self._registration_code(telegram_user_id, chat_id)

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

    def _balance_text(self, telegram_user_id: int) -> str:
        user = self.repository.get_user_by_telegram(telegram_user_id)
        if not user:
            return (
                "Telegram пока не привязан к аккаунту.\n\n"
                "Нажмите «Получить код», затем зарегистрируйтесь на сайте и введите этот код."
            )

        public = self.repository.get_user_by_id(int(user["id"])) or user
        access_until = public.get("access_until")
        return (
            "Баланс времени использования:\n"
            f"Логин: {public.get('login')}\n"
            f"Осталось: {_remaining_access_text(access_until)}\n"
            f"Доступ до: {_format_access_until(access_until)}"
        )

    async def _send_message(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        chat_id: int,
        text: str,
        *,
        attach_keyboard: bool = False,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text[:3900],
            "disable_web_page_preview": True,
        }
        # Нижняя клавиатура Telegram — это persistent ReplyKeyboard.
        # Ее достаточно отправить при /start или /help: после этого Telegram-клиент
        # держит кнопки внизу у поля ввода, а не добавляет кнопки под каждый ответ бота.
        if attach_keyboard:
            payload["reply_markup"] = _persistent_keyboard()

        await client.post(f"{base_url}/sendMessage", json=payload)

    async def _sleep(self, seconds: float | None = None) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds or self.poll_seconds)
        except asyncio.TimeoutError:
            pass


def _should_attach_keyboard(text: str) -> bool:
    clean_text = str(text or "").strip()
    if not clean_text.startswith("/"):
        return False

    command = clean_text.split(maxsplit=1)[0].split("@", 1)[0].lower()
    return command in {"/start", "/help"}

def _persistent_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [[{"text": GET_CODE_BUTTON}, {"text": CHECK_BALANCE_BUTTON}]],
        "resize_keyboard": True,
        "one_time_keyboard": False,
        "is_persistent": True,
    }


def _help_text() -> str:
    site = (os.getenv("PUBLIC_BASE_URL") or "https://beta.twaps.ru").rstrip("/")
    return (
        "TWAP бот кодов входа и баланса.\n\n"
        f"Сайт: {site}\n\n"
        "Внизу есть две основные кнопки:\n"
        f"• {GET_CODE_BUTTON} — получить код регистрации или входа\n"
        f"• {CHECK_BALANCE_BUTTON} — узнать, сколько времени использования осталось\n\n"
        "Дополнительные команды:\n"
        "/activate TWAP-... — активировать ключ и добавить время работы\n"
        "/logout — закрыть активную сессию софта"
    )


def _remaining_access_text(access_until: Any) -> str:
    until = _parse_access_until(access_until)
    if until is None:
        return "время не добавлено"

    seconds = int((until - datetime.now(timezone.utc)).total_seconds())
    if seconds <= 0:
        return "время закончилось"

    days, remainder = divmod(seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, _ = divmod(remainder, 60)

    parts: list[str] = []
    if days:
        parts.append(_plural(days, "день", "дня", "дней"))
    if hours:
        parts.append(_plural(hours, "час", "часа", "часов"))
    if minutes or not parts:
        parts.append(_plural(minutes, "минута", "минуты", "минут"))
    return " ".join(parts[:3])


def _format_access_until(access_until: Any) -> str:
    until = _parse_access_until(access_until)
    if until is None:
        return "нет активированного времени"
    return until.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _parse_access_until(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _plural(value: int, one: str, few: str, many: str) -> str:
    value = abs(int(value))
    if value % 10 == 1 and value % 100 != 11:
        word = one
    elif 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14:
        word = few
    else:
        word = many
    return f"{value} {word}"
