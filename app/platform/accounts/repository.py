from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.connection import db_cursor
from app.platform.accounts.security import (
    hash_password,
    hash_secret,
    new_activation_key,
    new_login_code,
    new_token,
    verify_password,
)


class AccountError(Exception):
    pass


class AccountRepository:
    def create_registration_code_for_telegram(self, telegram_user_id: int, telegram_chat_id: int, ttl_minutes: int = 10) -> str:
        """Create a short code that lets the website bind a new account to this Telegram user."""
        if not telegram_user_id or not telegram_chat_id:
            raise AccountError("Не удалось определить Telegram-пользователя")
        existing = self.get_user_by_telegram(telegram_user_id)
        if existing:
            raise AccountError("Этот Telegram уже привязан к аккаунту. Для входа используйте код /code")

        code = new_login_code()
        expires_at = _now() + timedelta(minutes=max(1, int(ttl_minutes or 10)))
        with db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO telegram_registration_codes
                    (telegram_user_id, telegram_chat_id, code_hash, expires_at)
                VALUES (%s, %s, %s, %s)
                """,
                (telegram_user_id, telegram_chat_id, hash_secret(code), _mysql_dt(expires_at)),
            )
        return code

    def create_user_with_registration_code(self, login: str, password: str, code: str) -> dict[str, Any]:
        safe_login = _login(login)
        if len(str(password or "")) < 6:
            raise AccountError("Пароль должен быть не короче 6 символов")
        code_hash = hash_secret(str(code or "").strip())
        now = _now()

        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM telegram_registration_codes
                WHERE code_hash = %s
                  AND used_at IS NULL
                  AND expires_at >= %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (code_hash, _mysql_dt(now)),
            )
            registration = cursor.fetchone()
            if not registration:
                raise AccountError("Неверный или просроченный код регистрации из Telegram-бота")

            telegram_user_id = int(registration["telegram_user_id"])
            telegram_chat_id = int(registration["telegram_chat_id"])

            cursor.execute(
                "SELECT id, login FROM software_users WHERE login = %s OR telegram_user_id = %s LIMIT 1",
                (safe_login, telegram_user_id),
            )
            existing = cursor.fetchone()
            if existing:
                raise AccountError("Логин или Telegram-аккаунт уже зарегистрирован")

            cursor.execute(
                """
                INSERT INTO software_users
                    (login, password_hash, telegram_user_id, telegram_chat_id, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                """,
                (safe_login, hash_password(password), telegram_user_id, telegram_chat_id),
            )
            user_id = int(cursor.lastrowid)
            cursor.execute(
                "UPDATE telegram_registration_codes SET used_at = %s WHERE id = %s",
                (_mysql_dt(now), registration["id"]),
            )

        return public_user(self.get_user_by_id(user_id) or {})

    def create_user_from_telegram(self, telegram_user_id: int, telegram_chat_id: int, login: str, password: str) -> dict[str, Any]:
        # Backward compatible helper for old scripts. The public flow should use
        # create_registration_code_for_telegram() + create_user_with_registration_code().
        safe_login = _login(login)
        if len(str(password or "")) < 6:
            raise AccountError("Пароль должен быть не короче 6 символов")
        password_hash = hash_password(password)
        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT id, login FROM software_users WHERE login = %s OR telegram_user_id = %s LIMIT 1",
                (safe_login, telegram_user_id),
            )
            existing = cursor.fetchone()
            if existing:
                raise AccountError("Логин или Telegram-аккаунт уже зарегистрирован")

            cursor.execute(
                """
                INSERT INTO software_users
                    (login, password_hash, telegram_user_id, telegram_chat_id, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                """,
                (safe_login, password_hash, telegram_user_id, telegram_chat_id),
            )
            user_id = int(cursor.lastrowid)
        return self.get_user_by_id(user_id) or {}

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM software_users WHERE id = %s LIMIT 1", (user_id,))
            row = cursor.fetchone()
        return _normalize_user(row)

    def get_user_by_login(self, login: str) -> dict[str, Any] | None:
        with db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM software_users WHERE login = %s LIMIT 1", (_login(login),))
            row = cursor.fetchone()
        return _normalize_user(row)

    def get_user_by_telegram(self, telegram_user_id: int) -> dict[str, Any] | None:
        with db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM software_users WHERE telegram_user_id = %s LIMIT 1", (telegram_user_id,))
            row = cursor.fetchone()
        return _normalize_user(row)

    def create_login_code_for_telegram(self, telegram_user_id: int, ttl_minutes: int = 5) -> str:
        user = self.get_user_by_telegram(telegram_user_id)
        if not user:
            raise AccountError("Telegram-аккаунт не привязан. Зарегистрируйтесь через сайт и получите код регистрации в боте.")

        code = new_login_code()
        expires_at = _now() + timedelta(minutes=max(1, int(ttl_minutes or 5)))
        with db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO login_codes (user_id, code_hash, purpose, expires_at)
                VALUES (%s, %s, 'login', %s)
                """,
                (user["id"], hash_secret(code), _mysql_dt(expires_at)),
            )
        return code

    def login_with_code(self, login: str, password: str, code: str, device_id: str, device_name: str = "") -> dict[str, Any]:
        user = self.get_user_by_login(login)
        if not user or not verify_password(password, str(user.get("password_hash") or "")):
            raise AccountError("Неверный логин или пароль")
        if not user.get("is_active"):
            raise AccountError("Аккаунт отключен")
        if not self._consume_login_code(int(user["id"]), code):
            raise AccountError("Неверный или просроченный код Telegram-бота")

        self.cleanup_stale_sessions()
        active = self.active_session_for_user(int(user["id"]))
        if active:
            raise AccountError("Софт уже запущен на другом устройстве. Сначала выйдите там или дождитесь истечения сессии.")

        raw_token = new_token("twap_session")
        token_hash = hash_secret(raw_token)
        now = _now()
        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                INSERT INTO user_sessions
                    (user_id, token_hash, device_id, device_name, started_at, last_seen_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user["id"],
                    token_hash,
                    str(device_id or "")[:128],
                    str(device_name or "")[:255],
                    _mysql_dt(now),
                    _mysql_dt(now),
                ),
            )
            session_id = int(cursor.lastrowid)

        fresh_user = self.get_user_by_id(int(user["id"])) or user
        return {
            "token": raw_token,
            "session_id": session_id,
            "user": public_user(fresh_user),
        }

    def validate_session_token(self, token: str, touch: bool = True, require_active_access: bool = True) -> dict[str, Any] | None:
        token_hash = hash_secret(token)
        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT
                    s.id AS session_id,
                    s.user_id,
                    s.device_id,
                    s.device_name,
                    s.started_at,
                    s.last_seen_at,
                    u.login,
                    u.telegram_user_id,
                    u.telegram_chat_id,
                    u.access_until,
                    u.is_active
                FROM user_sessions s
                JOIN software_users u ON u.id = s.user_id
                WHERE s.token_hash = %s
                  AND s.closed_at IS NULL
                LIMIT 1
                """,
                (token_hash,),
            )
            row = cursor.fetchone()

        if not row or not row.get("is_active"):
            return None
        if require_active_access and not _has_active_access(row):
            return None

        if touch:
            self.touch_session(int(row["session_id"]))
        return _normalize_session(row)

    def touch_session(self, session_id: int) -> None:
        with db_cursor() as cursor:
            cursor.execute(
                "UPDATE user_sessions SET last_seen_at = %s WHERE id = %s AND closed_at IS NULL",
                (_mysql_dt(_now()), session_id),
            )

    def close_session_by_token(self, token: str) -> bool:
        with db_cursor() as cursor:
            cursor.execute(
                "UPDATE user_sessions SET closed_at = %s WHERE token_hash = %s AND closed_at IS NULL",
                (_mysql_dt(_now()), hash_secret(token)),
            )
            return cursor.rowcount > 0

    def close_sessions_for_user(self, user_id: int, reason: str = "manual") -> int:
        with db_cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_sessions
                SET closed_at = %s, close_reason = %s
                WHERE user_id = %s AND closed_at IS NULL
                """,
                (_mysql_dt(_now()), reason[:64], user_id),
            )
            return int(cursor.rowcount or 0)

    def active_session_for_user(self, user_id: int) -> dict[str, Any] | None:
        stale_before = _now() - timedelta(seconds=_session_ttl_seconds())
        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM user_sessions
                WHERE user_id = %s
                  AND closed_at IS NULL
                  AND last_seen_at >= %s
                ORDER BY last_seen_at DESC
                LIMIT 1
                """,
                (user_id, _mysql_dt(stale_before)),
            )
            row = cursor.fetchone()
        return row if isinstance(row, dict) else None

    def cleanup_stale_sessions(self) -> int:
        stale_before = _now() - timedelta(seconds=_session_ttl_seconds())
        with db_cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_sessions
                SET closed_at = %s, close_reason = 'stale'
                WHERE closed_at IS NULL
                  AND last_seen_at < %s
                """,
                (_mysql_dt(_now()), _mysql_dt(stale_before)),
            )
            return int(cursor.rowcount or 0)

    def create_activation_key(self, duration_seconds: int, expires_at: datetime | None = None, note: str = "") -> dict[str, Any]:
        duration = max(60, int(duration_seconds or 0))
        raw_key = new_activation_key()
        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                INSERT INTO activation_keys
                    (key_hash, duration_seconds, expires_at, note)
                VALUES (%s, %s, %s, %s)
                """,
                (hash_secret(raw_key), duration, _mysql_dt(expires_at) if expires_at else None, note[:255]),
            )
            key_id = int(cursor.lastrowid)
        return {"id": key_id, "key": raw_key, "duration_seconds": duration, "expires_at": _iso(expires_at), "note": note}

    def redeem_activation_key_for_telegram(self, telegram_user_id: int, raw_key: str) -> dict[str, Any]:
        user = self.get_user_by_telegram(telegram_user_id)
        if not user:
            raise AccountError("Telegram-аккаунт не привязан. Зарегистрируйтесь через сайт.")
        return self.redeem_activation_key(int(user["id"]), raw_key)

    def redeem_activation_key(self, user_id: int, raw_key: str) -> dict[str, Any]:
        now = _now()
        key_hash = hash_secret(str(raw_key or "").strip())
        with db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM activation_keys WHERE key_hash = %s LIMIT 1", (key_hash,))
            key = cursor.fetchone()
            if not key:
                raise AccountError("Ключ активации не найден")
            if key.get("used_at") is not None:
                raise AccountError("Ключ активации уже использован")
            if key.get("expires_at") and _as_utc(key["expires_at"]) < now:
                raise AccountError("Ключ активации истёк")

            cursor.execute("SELECT * FROM software_users WHERE id = %s LIMIT 1", (user_id,))
            user = cursor.fetchone()
            if not user:
                raise AccountError("Пользователь не найден")

            current_until = _as_utc(user.get("access_until")) if user.get("access_until") else None
            base_time = current_until if current_until and current_until > now else now
            new_until = base_time + timedelta(seconds=int(key["duration_seconds"]))

            cursor.execute(
                "UPDATE software_users SET access_until = %s WHERE id = %s",
                (_mysql_dt(new_until), user_id),
            )
            cursor.execute(
                """
                UPDATE activation_keys
                SET used_by_user_id = %s, used_at = %s
                WHERE id = %s
                """,
                (user_id, _mysql_dt(now), key["id"]),
            )
        fresh_user = self.get_user_by_id(user_id) or {}
        return public_user(fresh_user)

    def _consume_login_code(self, user_id: int, code: str) -> bool:
        code_hash = hash_secret(str(code or "").strip())
        with db_cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT id
                FROM login_codes
                WHERE user_id = %s
                  AND code_hash = %s
                  AND purpose = 'login'
                  AND used_at IS NULL
                  AND expires_at >= %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id, code_hash, _mysql_dt(_now())),
            )
            row = cursor.fetchone()
            if not row:
                return False
            cursor.execute(
                "UPDATE login_codes SET used_at = %s WHERE id = %s",
                (_mysql_dt(_now()), row["id"]),
            )
            return True


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(user.get("id") or 0),
        "login": user.get("login") or "",
        "telegram_user_id": user.get("telegram_user_id"),
        "access_until": _iso(user.get("access_until")),
        "is_active": bool(user.get("is_active")),
        "has_active_access": _has_active_access(user),
    }


def _normalize_user(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    out = dict(row)
    out["is_active"] = bool(out.get("is_active"))
    return out


def _normalize_session(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["session_id"] = int(out.get("session_id") or 0)
    out["user_id"] = int(out.get("user_id") or 0)
    out["user"] = public_user(
        {
            "id": out["user_id"],
            "login": out.get("login"),
            "telegram_user_id": out.get("telegram_user_id"),
            "telegram_chat_id": out.get("telegram_chat_id"),
            "access_until": out.get("access_until"),
            "is_active": out.get("is_active"),
        }
    )
    return out


def _login(value: str) -> str:
    clean = str(value or "").strip().lower()
    if len(clean) < 3:
        raise AccountError("Логин должен быть не короче 3 символов")
    if len(clean) > 64:
        raise AccountError("Логин слишком длинный")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_.-")
    if any(ch not in allowed for ch in clean):
        raise AccountError("Логин может содержать только латиницу, цифры, точку, дефис и подчёркивание")
    return clean


def _has_active_access(user: dict[str, Any]) -> bool:
    access_until = user.get("access_until")
    if not access_until:
        return False
    return _as_utc(access_until) > _now()


def _session_ttl_seconds() -> int:
    import os

    try:
        return max(60, int(os.getenv("SIGNAL_SERVER_SESSION_STALE_SECONDS") or "120"))
    except ValueError:
        return 120


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _mysql_dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def _iso(value: Any) -> str | None:
    if not value:
        return None
    try:
        return _as_utc(value).isoformat(timespec="seconds")
    except Exception:
        return None
