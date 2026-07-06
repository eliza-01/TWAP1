from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any

_PASSWORD_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    clean = str(password or "")
    if len(clean) < 6:
        raise ValueError("Пароль должен быть не короче 6 символов")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", clean.encode("utf-8"), bytes.fromhex(salt), _PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${_PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iterations_raw, salt_hex, digest_hex = str(stored_hash or "").split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            str(password or "").encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        ).hex()
        return hmac.compare_digest(digest, digest_hex)
    except Exception:
        return False


def hash_secret(value: str) -> str:
    return hashlib.sha256(str(value or "").strip().encode("utf-8")).hexdigest()


def new_token(prefix: str = "twap") -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def new_activation_key() -> str:
    return f"TWAP-{secrets.token_urlsafe(18).replace('_', '').replace('-', '').upper()[:24]}"


def new_login_code() -> str:
    # 6 digits, easier to type from Telegram.
    return f"{secrets.randbelow(1_000_000):06d}"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
