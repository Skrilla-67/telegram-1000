from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import TelegramUser, get_current_user
from .config import settings
from .game.engine import GameEngine, create_game, join_game, start_game
from .game.models import GameState, GameStatus
from .store import store

logger = logging.getLogger("server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task: asyncio.Task | None = None
    if settings.bot_token:
        from bot.main import run_bot

        bot_task = asyncio.create_task(run_bot(), name="telegram-bot-polling")
        logger.info("Started Telegram bot polling in background")
    else:
        logger.warning("BOT_TOKEN empty; bot polling not started")
    try:
        yield
    finally:
        if bot_task is not None:
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped Telegram bot polling")


app = FastAPI(title="Telegram 1000", version="1.1.0", lifespan=lifespan)

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
    bots: int = Field(default=1, ge=0, le=3)
    max_humans: int = Field(default=1, ge=1, le=4)


class JoinGameRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class ActionRequest(BaseModel):
    type: str  # roll | bank


def _require_member(state: GameState, user: TelegramUser) -> None:
    if state.has_player(user.id):
        return
    if settings.dev_mode and state.owner_user_id == user.id:
        return
    raise HTTPException(status_code=403, detail="Р’С‹ РЅРµ РІ СЌС‚РѕР№ РёРіСЂРµ")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "dev_mode": settings.dev_mode}


@app.post("/api/games", response_model=GameState)
def create_game_endpoint(
    body: CreateGameRequest,
    user: TelegramUser = Depends(get_current_user),
) -> GameState:
    # Solo vs bots if max_humans==1; otherwise lobby for friends (+ optional bots).
    if body.max_humans == 1 and body.bots < 1:
        raise HTTPException(status_code=400, detail="Р”Р»СЏ РѕРґРёРЅРѕС‡РЅРѕР№ РёРіСЂС‹ РЅСѓР¶РµРЅ С…РѕС‚СЏ Р±С‹ 1 Р±РѕС‚")
    if body.bots + body.max_humans < 2:
        raise HTTPException(status_code=400, detail="РќСѓР¶РЅРѕ РјРёРЅРёРјСѓРј 2 СѓС‡Р°СЃС‚РЅРёРєР° СЃСѓРјРјР°СЂРЅРѕ")

    state = create_game(
        human_id=user.id,
        human_name=user.display_name,
        bot_count=body.bots,
        max_humans=body.max_humans,
    )
    store.save(state)
    return state


@app.post("/api/games/join", response_model=GameState)
def join_game_endpoint(
    body: JoinGameRequest,
    user: TelegramUser = Depends(get_current_user),
) -> GameState:
    state = store.find_by_invite_code(body.code)
    if state is None:
        raise HTTPException(status_code=404, detail="РљРѕРјРЅР°С‚Р° РЅРµ РЅР°Р№РґРµРЅР°")
    try:
        state = join_game(state, user_id=user.id, user_name=user.display_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save(state)
    return state


@app.post("/api/games/{game_id}/start", response_model=GameState)
def start_game_endpoint(
    game_id: str,
    user: TelegramUser = Depends(get_current_user),
) -> GameState:
    state = store.get(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="РРіСЂР° РЅРµ РЅР°Р№РґРµРЅР°")
    try:
        state = start_game(state, user_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save(state)
    return state


@app.get("/api/games/{game_id}", response_model=GameState)
def get_game(
    game_id: str,
    user: TelegramUser = Depends(get_current_user),
) -> GameState:
    state = store.get(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="РРіСЂР° РЅРµ РЅР°Р№РґРµРЅР°")
    _require_member(state, user)
    return state


@app.post("/api/games/{game_id}/actions", response_model=GameState)
def game_action(
    game_id: str,
    body: ActionRequest,
    user: TelegramUser = Depends(get_current_user),
) -> GameState:
    state = store.get(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="РРіСЂР° РЅРµ РЅР°Р№РґРµРЅР°")
    _require_member(state, user)

    if state.status != GameStatus.PLAYING:
        raise HTTPException(status_code=400, detail="РРіСЂР° РµС‰С‘ РЅРµ РёРґС‘С‚")

    engine = GameEngine(state)
    try:
        new_state = engine.apply_action(user.id, body.type)
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
    import sys

    import uvicorn

    port = int(os.environ.get("PORT", settings.api_port))
    host = os.environ.get("API_HOST", settings.api_host) or "0.0.0.0"
    print(f"Starting uvicorn on {host}:{port}", flush=True)
    sys.stdout.flush()
    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
