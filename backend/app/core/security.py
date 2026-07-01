from datetime import timedelta
from typing import Any, Literal

import bcrypt
from jose import jwt

from app.core.config import get_settings
from app.core.time import utcnow


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def _create_token(subject: str, role: str, token_type: Literal["access", "refresh"], expires_delta: timedelta) -> str:
    settings = get_settings()
    now = utcnow()
    payload = {"sub": subject, "role": role, "type": token_type, "iat": now, "exp": now + expires_delta}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, role: str) -> str:
    settings = get_settings()
    return _create_token(subject, role, "access", timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(subject: str, role: str) -> str:
    settings = get_settings()
    return _create_token(subject, role, "refresh", timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str) -> dict[str, Any]:
    """Raises `jose.JWTError` (base class of `ExpiredSignatureError` etc.) on any invalid,
    tampered, or expired token — callers catch that one type.
    """
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
