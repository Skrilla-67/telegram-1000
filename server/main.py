from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import TelegramUser, get_current_user, issue_session_token, validate_login_widget, validate_native_id_token, persist_user
from .config import settings
from .game.engine import GameEngine, create_game, join_game, start_game
from .game.models import GameState, GameStatus
from .store import store
from .history import history
from .users import users
from .telegram_oidc import bot_client_id

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



def _maybe_archive(state: GameState) -> None:
    if state.status != GameStatus.FINISHED:
        return
    if history.exists(state.id):
        return
    history.archive(state)
    for p in state.players:
        if p.kind.value == "human":
            users.record_game_result(p.id, won=(p.id == state.winner_id))

@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "dev_mode": settings.dev_mode,
        "bot_username": settings.bot_username or None,
        "webapp_url": settings.webapp_url,
        "web_dist": WEB_DIST.is_dir(),
        "web_index": (WEB_DIST / "index.html").is_file(),
    }



class NativeLoginPayload(BaseModel):
    id_token: str = Field(min_length=20)
    platform: str | None = Field(default=None, description="ios | android")


class OidcLoginPayload(BaseModel):
    id_token: str = Field(min_length=20)


class LoginWidgetPayload(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class ClientMetaPayload(BaseModel):
    platform: str | None = None
    tg_version: str | None = None
    color_scheme: str | None = None
    phone_number: str | None = None
    allows_write_to_pm: bool | None = None
    extra: dict | None = None


@app.get("/api/config")
def public_config() -> dict:
    return {
        "bot_username": settings.bot_username or "",
        "bot_client_id": bot_client_id(),
        "webapp_url": settings.webapp_url,
        "dev_mode": settings.dev_mode,
        "native_login": {
            "ios": "https://github.com/TelegramMessenger/telegram-login-ios",
            "android": "https://github.com/TelegramMessenger/telegram-login-android",
            "token_endpoint": "/api/auth/native",
        },
    }



@app.post("/api/auth/native")
def auth_native_login(body: NativeLoginPayload) -> dict:
    """Exchange idToken from telegram-login-ios / telegram-login-android SDK."""
    try:
        user = validate_native_id_token(body.id_token, platform=body.platform)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    source = f"native_{body.platform}" if body.platform else "native"
    persist_user(user, source=source)
    token = issue_session_token(user)
    profile = users.get(user.id)
    return {"token": token, "user": profile.model_dump() if profile else user.to_profile_patch()}


@app.post("/api/auth/oidc")
def auth_oidc_login(body: OidcLoginPayload) -> dict:
    """Verify OIDC id_token (new oauth.telegram.org Login Widget)."""
    try:
        user = validate_native_id_token(body.id_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    persist_user(user, source="oidc_widget")
    token = issue_session_token(user)
    profile = users.get(user.id)
    return {"token": token, "user": profile.model_dump() if profile else user.to_profile_patch()}


@app.post("/api/auth/telegram")
def auth_telegram_login(body: LoginWidgetPayload) -> dict:
    if not settings.bot_token:
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")
    try:
        user = validate_login_widget(body.model_dump(), settings.bot_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    persist_user(user, source="login_widget")
    token = issue_session_token(user)
    profile = users.get(user.id)
    return {"token": token, "user": profile.model_dump() if profile else user.to_profile_patch()}


@app.post("/api/me/ping")
def me_ping(
    body: ClientMetaPayload | None = None,
    user: TelegramUser = Depends(get_current_user),
) -> dict:
    meta = body.model_dump(exclude_none=True) if body else {}
    persist_user(user, source="ping", client_meta=meta)
    profile = users.get(user.id)
    return profile.model_dump() if profile else user.to_profile_patch()


@app.get("/api/me")
def me(user: TelegramUser = Depends(get_current_user)) -> dict:
    profile = users.get(user.id)
    if profile is None:
        persist_user(user, source="me")
        profile = users.get(user.id)
    assert profile is not None
    return profile.model_dump()


@app.get("/api/me/history")
def me_history(user: TelegramUser = Depends(get_current_user)) -> dict:
    return {"items": [h.model_dump() for h in history.list_for_user(user.id)]}

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
    _maybe_archive(state)
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
    _maybe_archive(state)
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
    _maybe_archive(state)
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
    _maybe_archive(new_state)
    return new_state


assets_dir = WEB_DIST / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
def spa_index():
    index = WEB_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><title>Build missing</title>"
        "<body style='font-family:sans-serif;background:#132820;color:#f3efe6;padding:2rem'>"
        "<h1>Frontend not built</h1>"
        "<p>On Render set Build Command to:</p>"
        "<pre>pip install -r requirements.txt\n"
        "cd web &amp;&amp; npm install &amp;&amp; npm run build\n"
        "test -f dist/index.html</pre>"
        "<p>Then Manual Deploy. Check <code>/api/health</code> → web_index:true</p>"
        "</body>",
        status_code=503,
    )


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="Not found")
    index = WEB_DIST / "index.html"
    if index.is_file():
        # Prefer real static file if present (e.g. favicon), else SPA shell
        candidate = WEB_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend not built")


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
