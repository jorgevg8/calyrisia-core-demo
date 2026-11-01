import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import jwt
except Exception:  # pragma: no cover - stdlib HS256 fallback if PyJWT is absent
    import base64 as _b64
    import hashlib as _hashlib
    import hmac as _hmac
    import json as _json
    import time as _time

    class _StdlibJWT:
        class PyJWTError(Exception):
            pass

        @staticmethod
        def _b64url_encode(data: bytes) -> str:
            return _b64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

        @staticmethod
        def _b64url_decode(data: str) -> bytes:
            pad = "=" * (-len(data) % 4)
            return _b64.urlsafe_b64decode(data + pad)

        def encode(self, payload: dict, key: str, algorithm: str = "HS256") -> str:
            clean_payload = {}
            for k, v in payload.items():
                if hasattr(v, "timestamp"):
                    clean_payload[k] = int(v.timestamp())
                else:
                    clean_payload[k] = v
            header_b64 = self._b64url_encode(_json.dumps({"alg": algorithm, "typ": "JWT"}).encode("utf-8"))
            payload_b64 = self._b64url_encode(_json.dumps(clean_payload).encode("utf-8"))
            signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
            sig = _hmac.new(key.encode("utf-8"), signing_input, _hashlib.sha256).digest()
            return f"{header_b64}.{payload_b64}.{self._b64url_encode(sig)}"

        def decode(self, token: str, key: str, algorithms=None, issuer=None) -> dict:
            try:
                parts = str(token).split(".")
                if len(parts) != 3:
                    raise self.PyJWTError("Invalid token format")
                signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
                expected_sig = _hmac.new(key.encode("utf-8"), signing_input, _hashlib.sha256).digest()
                actual_sig = self._b64url_decode(parts[2])
                if not _hmac.compare_digest(expected_sig, actual_sig):
                    raise self.PyJWTError("Invalid signature")
                payload = _json.loads(self._b64url_decode(parts[1]).decode("utf-8"))
                if "exp" in payload and int(payload["exp"]) < int(_time.time()):
                    raise self.PyJWTError("Token expired")
                if issuer and payload.get("iss") != issuer:
                    raise self.PyJWTError("Invalid issuer")
                return payload
            except self.PyJWTError:
                raise
            except Exception as exc:
                raise self.PyJWTError(str(exc)) from exc

    jwt = _StdlibJWT()  # type: ignore

from app.core.config import get_settings

ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    """Return a valid >=32-char JWT secret from .env/environment, deriving a deterministic 64-char key if needed."""
    settings = get_settings()
    secret = (
        settings.galaxy_jwt_secret.strip()
        or os.getenv("GALAXY_JWT_SECRET", "").strip()
        or os.getenv("JWT_SECRET", "").strip()
    )
    if len(secret) >= 32 and secret != "GENERATE_WITH_scripts/paso39_security_setup.py":
        return secret
    seed = f"calyrisia-jwt-seed::{secret}::{settings.pg_host}::{settings.pg_user}::{settings.app_name}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def get_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    pwdhash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex() + ":" + pwdhash.hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        stored = str(hashed_password).strip()
        if ":" not in stored:
            return hmac.compare_digest(plain_password, stored)
        salt_hex, hash_hex = stored.split(":", 1)
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
    )
