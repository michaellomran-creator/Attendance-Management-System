from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import time
from typing import Any, Dict, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
import jwt
from jwt.exceptions import PyJWTError

from app.core.config import settings

# Argon2id with explicit secure parameters
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_secret(plain_text: str) -> str:
    """Hash a password or PIN using Argon2id."""
    return _password_hasher.hash(plain_text)


def verify_secret(plain_text: str, hashed_text: str) -> bool:
    """Verify a password or PIN against an Argon2id hash."""
    if not hashed_text:
        return False
    try:
        return _password_hasher.verify(hashed_text, plain_text)
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_token(raw_token: str) -> str:
    """Deterministic SHA-256 hash for refresh tokens and terminal API keys."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_terminal_token() -> str:
    """Generate a cryptographically random terminal authentication secret."""
    return f"ntk_{secrets.token_urlsafe(32)}"


def create_access_token(
    subject: str,
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(12),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    subject: str,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except PyJWTError:
        return None


class InMemoryRateLimiter:
    """Simple sliding-window rate limiter for login and PIN attempts."""

    def __init__(self) -> None:
        self._attempts: Dict[str, list[float]] = defaultdict(list)

    def check_and_record(
        self, key: str, max_attempts: int, window_seconds: int
    ) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        recent = [ts for ts in self._attempts[key] if ts > cutoff]
        if len(recent) >= max_attempts:
            self._attempts[key] = recent
            return False
        recent.append(now)
        self._attempts[key] = recent
        return True

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)


rate_limiter = InMemoryRateLimiter()
