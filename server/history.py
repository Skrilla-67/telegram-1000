from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from pydantic import BaseModel, Field

from .config import settings
from .game.models import GameState, PlayerKind


class HistoryPlayer(BaseModel):
    id: str
    name: str
    kind: str
    score: int


class GameHistoryRecord(BaseModel):
    game_id: str
    finished_at: float = Field(default_factory=lambda: time.time())
    invite_code: str = ""
    winner_id: str | None = None
    winner_name: str | None = None
    players: list[HistoryPlayer]
    human_ids: list[str]
    max_humans: int = 1
    status: str = "finished"


class HistoryStore:
    def __init__(self, root: str | None = None) -> None:
        base = Path(root or settings.data_dir)
        self.root = base / "history"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.jsonl"
        self._lock = threading.Lock()

    def _game_path(self, game_id: str) -> Path:
        return self.root / f"{game_id}.json"

    def exists(self, game_id: str) -> bool:
        return self._game_path(game_id).exists()

    def archive(self, state: GameState) -> GameHistoryRecord:
        humans = [p for p in state.players if p.kind == PlayerKind.HUMAN]
        winner = next((p for p in state.players if p.id == state.winner_id), None)
        record = GameHistoryRecord(
            game_id=state.id,
            invite_code=state.invite_code,
            winner_id=state.winner_id,
            winner_name=winner.name if winner else None,
            players=[
                HistoryPlayer(id=p.id, name=p.name, kind=p.kind.value, score=p.score)
                for p in state.players
            ],
            human_ids=[p.id for p in humans],
            max_humans=state.max_humans,
            status=state.status.value,
        )
        with self._lock:
            self._game_path(state.id).write_text(record.model_dump_json(indent=2), encoding="utf-8")
            with self.index_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"game_id": state.id, "human_ids": record.human_ids, "finished_at": record.finished_at}, ensure_ascii=False) + "\n")
        return record

    def list_for_user(self, user_id: str, limit: int = 30) -> list[GameHistoryRecord]:
        uid = str(user_id)
        out: list[GameHistoryRecord] = []
        with self._lock:
            if not self.index_path.exists():
                return []
            lines = self.index_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            if len(out) >= limit:
                break
            try:
                meta = json.loads(line)
            except json.JSONDecodeError:
                continue
            if uid not in meta.get("human_ids", []):
                continue
            path = self._game_path(meta["game_id"])
            if not path.exists():
                continue
            out.append(GameHistoryRecord.model_validate_json(path.read_text(encoding="utf-8")))
        return out


history = HistoryStore()
