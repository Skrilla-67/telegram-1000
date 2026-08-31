from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .config import settings


class UserProfile(BaseModel):
    id: str
    first_name: str = ""
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_premium: bool | None = None
    photo_url: str | None = None
    allows_write_to_pm: bool | None = None
    phone_number: str | None = None
    platform: str | None = None
    tg_version: str | None = None
    color_scheme: str | None = None
    auth_sources: list[str] = Field(default_factory=list)
    first_seen_at: float = Field(default_factory=lambda: time.time())
    last_seen_at: float = Field(default_factory=lambda: time.time())
    games_played: int = 0
    games_won: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def display_name(self) -> str:
        if self.username:
            return self.username
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) or f"User {self.id}"


class UserStore:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.data_dir) / "users"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, user_id: str) -> Path:
        safe = "".join(c for c in user_id if c.isalnum() or c in "-_")
        return self.root / f"{safe}.json"

    def get(self, user_id: str) -> UserProfile | None:
        path = self._path(user_id)
        if not path.exists():
            return None
        return UserProfile.model_validate_json(path.read_text(encoding="utf-8"))

    def upsert(self, patch: dict[str, Any], source: str | None = None) -> UserProfile:
        user_id = str(patch["id"])
        with self._lock:
            existing = self.get(user_id)
            data = existing.model_dump() if existing else {"id": user_id}
            for key, value in patch.items():
                if value is None:
                    continue
                if key == "extra" and isinstance(value, dict):
                    data.setdefault("extra", {}).update(value)
                elif key == "auth_sources":
                    continue
                else:
                    data[key] = value
            sources = list(data.get("auth_sources") or [])
            if source and source not in sources:
                sources.append(source)
            data["auth_sources"] = sources
            data["last_seen_at"] = time.time()
            if not existing:
                data["first_seen_at"] = time.time()
            profile = UserProfile.model_validate(data)
            self._path(user_id).write_text(profile.model_dump_json(indent=2), encoding="utf-8")
            return profile

    def record_game_result(self, user_id: str, won: bool) -> None:
        with self._lock:
            profile = self.get(user_id)
            if profile is None:
                profile = UserProfile(id=user_id)
            profile.games_played += 1
            if won:
                profile.games_won += 1
            profile.last_seen_at = time.time()
            self._path(user_id).write_text(profile.model_dump_json(indent=2), encoding="utf-8")


users = UserStore()
