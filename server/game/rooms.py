from __future__ import annotations

import secrets
from enum import Enum

from pydantic import BaseModel, Field


class RoomStatus(str, Enum):
    LOBBY = "lobby"
    PLAYING = "playing"
    FINISHED = "finished"


class RoomSeat(BaseModel):
    user_id: str
    name: str


class Room(BaseModel):
    code: str
    status: RoomStatus = RoomStatus.LOBBY
    host_id: str
    max_humans: int = Field(default=2, ge=2, le=4)
    bots: int = Field(default=0, ge=0, le=3)
    seats: list[RoomSeat] = Field(default_factory=list)
    game_id: str | None = None

    @property
    def participant_count(self) -> int:
        return len(self.seats) + self.bots

    def is_seated(self, user_id: str) -> bool:
        return any(s.user_id == user_id for s in self.seats)

    def seat_for(self, user_id: str) -> RoomSeat | None:
        return next((s for s in self.seats if s.user_id == user_id), None)


def generate_room_code(length: int = 6) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))
