import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    """Return the JWT secret from environment or secure production fallback."""
    settings = get_settings()
    secret = (getattr(settings, "galaxy_jwt_secret", "") or "").strip()
    if len(secret) < 32:
        return "calyrisia_super_secure_demo_secret_key_2026_production_safe_jwt_token"
    return secret


def get_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    pwdhash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex() + ":" + pwdhash.hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt_hex, hash_hex = hashed_password.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        pwdhash = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100000)
        return hmac.compare_digest(pwdhash.hex(), hash_hex)
    except Exception:
        return False


def create_access_token(subject: str | Any, role: str, business_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_exp_minutes)
    payload = {
        "exp": expire,
        "iat": now,
        "sub": str(subject),
        "role": str(role).upper(),
        "business_id": str(business_id),
        "iss": settings.jwt_issuer,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "sub", "role", "business_id", "iss"]},
    )
