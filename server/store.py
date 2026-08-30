from __future__ import annotations

import json
import threading
from pathlib import Path

from .config import settings
from .game.models import GameState


class GameStore:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, game_id: str) -> Path:
        return self.root / f"{game_id}.json"

    def save(self, state: GameState) -> None:
        with self._lock:
            path = self._path(state.id)
            path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def get(self, game_id: str) -> GameState | None:
        path = self._path(game_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return GameState.model_validate(data)

    def delete(self, game_id: str) -> None:
        path = self._path(game_id)
        if path.exists():
            path.unlink()


store = GameStore()
