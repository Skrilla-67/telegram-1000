from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

from .config import settings


@dataclass
class TelegramUser:
    id: str
    first_name: str
    last_name: str | None = None
    username: str | None = None

    @property
    def display_name(self) -> str:
        if self.username:
            return self.username
        parts = [self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) or f"User {self.id}"


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
    user = json.loads(user_raw)
    return TelegramUser(
        id=str(user["id"]),
        first_name=user.get("first_name") or "Игрок",
        last_name=user.get("last_name"),
        username=user.get("username"),
    )


def get_current_user(
    x_telegram_init_data: str | None = Header(default=None),
    x_dev_user: str | None = Header(default=None),
    x_dev_user_id: str | None = Header(default=None),
) -> TelegramUser:
    if x_telegram_init_data:
        if not settings.bot_token and not settings.dev_mode:
            raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")
        try:
            if settings.bot_token:
                return validate_init_data(x_telegram_init_data, settings.bot_token)
            # Dev: accept without verification if no token
            if settings.dev_mode:
                pairs = dict(parse_qsl(x_telegram_init_data, keep_blank_values=True))
                user = json.loads(pairs.get("user") or "{}")
                return TelegramUser(
                    id=str(user.get("id") or x_dev_user_id or "dev"),
                    first_name=user.get("first_name") or "Dev",
                    last_name=user.get("last_name"),
                    username=user.get("username"),
                )
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    if settings.dev_mode:
        name = x_dev_user or "Dev Player"
        return TelegramUser(id=x_dev_user_id or "dev-user", first_name=name)

    raise HTTPException(status_code=401, detail="Telegram authorization required")
