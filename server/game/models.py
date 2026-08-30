from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PlayerKind(str, Enum):
    HUMAN = "human"
    BOT = "bot"


class GameStatus(str, Enum):
    LOBBY = "lobby"
    PLAYING = "playing"
    FINISHED = "finished"


class Phase(str, Enum):
    WAITING_ROLL = "waiting_roll"
    WAITING_DECISION = "waiting_decision"
    FINISHED = "finished"


class GameConfig(BaseModel):
    open_threshold: int = 50
    pits: list[tuple[int, int]] = Field(default_factory=lambda: [(200, 300), (600, 700)])
    barrel_threshold: int = 880
    win_score: int = 1000
    bolt_limit: int = 3
    bolt_penalty: int = 100
    overtake_penalty: int = 50
    dump_truck_score: int = 555
    barrel_attempts: int = 3
    barrel_falls_limit: int = 3
    barrel_fall_penalty: int = 100
    dice_count: int = 5


class PlayerState(BaseModel):
    id: str
    name: str
    kind: PlayerKind
    score: int = 0
    opened: bool = False
    bolts: int = 0
    on_barrel: bool = False
    barrel_attempts: int = 0
    barrel_falls: int = 0


class TurnState(BaseModel):
    score: int = 0
    remaining_dice: int = 5
    last_roll: list[int] = Field(default_factory=list)
    last_scoring_dice: list[int] = Field(default_factory=list)
    last_roll_points: int = 0
    can_bank: bool = False
    must_roll: bool = True


class GameEvent(BaseModel):
    type: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class GameState(BaseModel):
    id: str
    invite_code: str = ""
    status: GameStatus = GameStatus.PLAYING
    config: GameConfig = Field(default_factory=GameConfig)
    players: list[PlayerState]
    max_humans: int = 1
    current_player_index: int = 0
    phase: Phase = Phase.WAITING_ROLL
    turn: TurnState = Field(default_factory=TurnState)
    events: list[GameEvent] = Field(default_factory=list)
    winner_id: str | None = None
    owner_user_id: str | None = None

    def current_player(self) -> PlayerState:
        return self.players[self.current_player_index]

    def human_count(self) -> int:
        return sum(1 for p in self.players if p.kind == PlayerKind.HUMAN)

    def has_player(self, player_id: str) -> bool:
        return any(p.id == player_id for p in self.players)
