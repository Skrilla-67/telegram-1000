from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import TelegramUser, get_current_user
from .config import settings
from .game.engine import GameEngine, create_game
from .game.models import GameState
from .store import store

app = FastAPI(title="Telegram 1000", version="1.0.0")

origins = (
    ["*"]
    if settings.cors_origins.strip() == "*"
    else [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"


class CreateGameRequest(BaseModel):
    bots: int = Field(default=1, ge=1, le=3)


class ActionRequest(BaseModel):
    type: str  # roll | bank


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "dev_mode": settings.dev_mode}


@app.post("/api/games", response_model=GameState)
def create_game_endpoint(
    body: CreateGameRequest,
    user: TelegramUser = Depends(get_current_user),
) -> GameState:
    state = create_game(
        human_id=user.id,
        human_name=user.display_name,
        bot_count=body.bots,
    )
    store.save(state)
    return state


@app.get("/api/games/{game_id}", response_model=GameState)
def get_game(
    game_id: str,
    user: TelegramUser = Depends(get_current_user),
) -> GameState:
    state = store.get(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if state.owner_user_id and state.owner_user_id != user.id and not settings.dev_mode:
        raise HTTPException(status_code=403, detail="Not your game")
    return state


@app.post("/api/games/{game_id}/actions", response_model=GameState)
def game_action(
    game_id: str,
    body: ActionRequest,
    user: TelegramUser = Depends(get_current_user),
) -> GameState:
    state = store.get(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if state.owner_user_id and state.owner_user_id != user.id and not settings.dev_mode:
        raise HTTPException(status_code=403, detail="Not your game")

    engine = GameEngine(state)
    try:
        # Human actions are always under the human player id (= owner).
        human = next(p for p in state.players if p.kind.value == "human")
        if human.id != user.id and not settings.dev_mode:
            raise HTTPException(status_code=403, detail="Not your seat")
        new_state = engine.apply_action(human.id, body.type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store.save(new_state)
    return new_state


if WEB_DIST.is_dir():
    assets = WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    def spa_index() -> FileResponse:
        return FileResponse(WEB_DIST / "index.html")


def run() -> None:
    import os

    import uvicorn

    port = int(os.environ.get("PORT", settings.api_port))
    uvicorn.run(
        "server.main:app",
        host=settings.api_host,
        port=port,
        reload=settings.dev_mode and "PORT" not in os.environ,
    )


if __name__ == "__main__":
    run()
