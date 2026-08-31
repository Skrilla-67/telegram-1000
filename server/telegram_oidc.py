from __future__ import annotations

import threading
import time
from typing import Any

import jwt
from jwt import PyJWKClient

from .config import settings

TELEGRAM_ISSUER = "https://oauth.telegram.org"
JWKS_URL = "https://oauth.telegram.org/.well-known/jwks.json"

_lock = threading.Lock()
_jwk_client: PyJWKClient | None = None
_jwk_loaded_at = 0.0
JWKS_TTL = 3600


def bot_client_id() -> str:
    if settings.bot_client_id:
        return str(settings.bot_client_id).strip()
    if settings.bot_token and ":" in settings.bot_token:
        return settings.bot_token.split(":", 1)[0]
    return ""


def _get_jwk_client() -> PyJWKClient:
    global _jwk_client, _jwk_loaded_at
    now = time.time()
    with _lock:
        if _jwk_client is None or now - _jwk_loaded_at > JWKS_TTL:
            _jwk_client = PyJWKClient(JWKS_URL, cache_keys=True, lifespan=JWKS_TTL)
            _jwk_loaded_at = now
        return _jwk_client


def validate_id_token(id_token: str, client_id: str | None = None) -> dict[str, Any]:
    """Verify Telegram Login OIDC id_token (iOS/Android/native SDK)."""
    if not id_token or not id_token.strip():
        raise ValueError("empty id_token")
    aud = (client_id or bot_client_id()).strip()
    if not aud:
        raise ValueError("BOT_CLIENT_ID not configured")

    client = _get_jwk_client()
    signing_key = client.get_signing_key_from_jwt(id_token)
    payload = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=aud,
        issuer=TELEGRAM_ISSUER,
        options={"require": ["exp", "iat", "sub"]},
    )
    return payload
