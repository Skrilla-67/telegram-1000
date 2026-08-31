from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

from .config import settings
from .users import users


@dataclass
class TelegramUser:
    id: str
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_premium: bool | None = None
    photo_url: str | None = None
    allows_write_to_pm: bool | None = None
    phone_number: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        if self.username:
            return self.username
        parts = [self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) or f"User {self.id}"

    def to_profile_patch(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "username": self.username,
            "language_code": self.language_code,
            "is_premium": self.is_premium,
            "photo_url": self.photo_url,
            "allows_write_to_pm": self.allows_write_to_pm,
            "phone_number": self.phone_number,
            "extra": self.extra,
        }


def _user_from_telegram_dict(user: dict[str, Any]) -> TelegramUser:
    known = {
        "id",
        "first_name",
        "last_name",
        "username",
        "language_code",
        "is_premium",
        "photo_url",
        "allows_write_to_pm",
    }
    extra = {k: v for k, v in user.items() if k not in known}
    return TelegramUser(
        id=str(user["id"]),
        first_name=user.get("first_name") or "Player",
        last_name=user.get("last_name"),
        username=user.get("username"),
        language_code=user.get("language_code"),
        is_premium=user.get("is_premium"),
        photo_url=user.get("photo_url"),
        allows_write_to_pm=user.get("allows_write_to_pm"),
        extra=extra,
    )


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> TelegramUser:
    if not init_data:
        raise ValueError("empty initData")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise ValueError("missing hash")

    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise ValueError("invalid hash")

    auth_date = int(pairs.get("auth_date", "0"))
    if auth_date and time.time() - auth_date > max_age_seconds:
        raise ValueError("initData expired")

    user_raw = pairs.get("user")
    if not user_raw:
        raise ValueError("missing user")
    return _user_from_telegram_dict(json.loads(user_raw))



def user_from_id_token_claims(claims: dict[str, Any]) -> TelegramUser:
    user_id = claims.get("id") or claims.get("sub")
    if user_id is None:
        raise ValueError("missing user id in id_token")
    given = claims.get("given_name")
    family = claims.get("family_name")
    full_name = claims.get("name")
    if not given and full_name:
        parts = str(full_name).split(" ", 1)
        given = parts[0]
        family = parts[1] if len(parts) > 1 else None
    extra = {
        k: v
        for k, v in claims.items()
        if k
        not in {
            "id",
            "sub",
            "iss",
            "aud",
            "exp",
            "iat",
            "given_name",
            "family_name",
            "name",
            "preferred_username",
            "picture",
            "phone_number",
            "phone_number_verified",
        }
    }
    return TelegramUser(
        id=str(user_id),
        first_name=str(given or "Player"),
        last_name=family,
        username=claims.get("preferred_username"),
        photo_url=claims.get("picture"),
        phone_number=claims.get("phone_number"),
        extra=extra,
    )


def validate_native_id_token(id_token: str, platform: str | None = None) -> TelegramUser:
    from .telegram_oidc import validate_id_token

    claims = validate_id_token(id_token)
    user = user_from_id_token_claims(claims)
    if platform:
        user.extra["native_platform"] = platform
    return user


def validate_login_widget(data: dict[str, Any], bot_token: str, max_age_seconds: int = 86400) -> TelegramUser:
    """Validate Telegram Login Widget callback payload."""
    payload = {k: str(v) for k, v in data.items() if v is not None and k != "hash"}
    received_hash = data.get("hash")
    if not received_hash:
        raise ValueError("missing hash")

    data_check = "\n".join(f"{k}={payload[k]}" for k in sorted(payload.keys()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, str(received_hash)):
        raise ValueError("invalid login hash")

    auth_date = int(payload.get("auth_date", "0"))
    if auth_date and time.time() - auth_date > max_age_seconds:
        raise ValueError("login data expired")

    user = _user_from_telegram_dict(
        {
            "id": payload["id"],
            "first_name": payload.get("first_name") or "Player",
            "last_name": payload.get("last_name"),
            "username": payload.get("username"),
            "photo_url": payload.get("photo_url"),
        }
    )
    return user


def _session_secret() -> bytes:
    raw = settings.session_secret or settings.bot_token or "dev-session-secret"
    return hashlib.sha256(raw.encode()).digest()


def issue_session_token(user: TelegramUser, ttl_seconds: int = 60 * 60 * 24 * 30) -> str:
    payload = {
        "uid": user.id,
        "name": user.first_name,
        "username": user.username,
        "exp": int(time.time()) + ttl_seconds,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_session_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def parse_session_token(token: str) -> TelegramUser:
    try:
        body, sig = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("bad session token") from exc
    expected = hmac.new(_session_secret(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("bad session signature")
    pad = "=" * (-len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(body + pad))
    if int(payload.get("exp", 0)) < time.time():
        raise ValueError("session expired")
    return TelegramUser(
        id=str(payload["uid"]),
        first_name=payload.get("name") or "Player",
        username=payload.get("username"),
    )


def persist_user(user: TelegramUser, source: str, client_meta: dict[str, Any] | None = None) -> None:
    patch = user.to_profile_patch()
    if client_meta:
        for key in ("platform", "tg_version", "color_scheme", "phone_number"):
            if client_meta.get(key) is not None:
                patch[key] = client_meta[key]
        extras = {k: v for k, v in client_meta.items() if k not in patch}
        if extras:
            patch.setdefault("extra", {}).update(extras)
    users.upsert(patch, source=source)


def get_current_user(
    x_telegram_init_data: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    x_dev_user: str | None = Header(default=None),
    x_dev_user_id: str | None = Header(default=None),
    x_client_meta: str | None = Header(default=None),
) -> TelegramUser:
    client_meta: dict[str, Any] = {}
    if x_client_meta:
        try:
            client_meta = json.loads(x_client_meta)
        except json.JSONDecodeError:
            client_meta = {}

    if x_telegram_init_data:
        if not settings.bot_token and not settings.dev_mode:
            raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")
        try:
            if settings.bot_token:
                user = validate_init_data(x_telegram_init_data, settings.bot_token)
            elif settings.dev_mode:
                pairs = dict(parse_qsl(x_telegram_init_data, keep_blank_values=True))
                raw = json.loads(pairs.get("user") or "{}")
                user = _user_from_telegram_dict(
                    {
                        "id": raw.get("id") or x_dev_user_id or "dev",
                        "first_name": raw.get("first_name") or "Dev",
                        "last_name": raw.get("last_name"),
                        "username": raw.get("username"),
                        "language_code": raw.get("language_code"),
                        "is_premium": raw.get("is_premium"),
                        "photo_url": raw.get("photo_url"),
                        "allows_write_to_pm": raw.get("allows_write_to_pm"),
                    }
                )
            else:
                raise ValueError("no bot token")
            persist_user(user, source="webapp", client_meta=client_meta)
            return user
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    token = x_session_token
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if token:
        try:
            user = parse_session_token(token)
            persist_user(user, source="session", client_meta=client_meta)
            return user
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    if settings.dev_mode:
        name = x_dev_user or "Dev Player"
        user = TelegramUser(id=x_dev_user_id or "dev-user", first_name=name)
        persist_user(user, source="dev", client_meta=client_meta)
        return user

    raise HTTPException(status_code=401, detail="Telegram authorization required")
