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
from .game.models import GameState, Phase, PlayerKind
from .game.rooms import Room, RoomSeat, RoomStatus, generate_room_code
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


class CreateRoomRequest(BaseModel):
    bots: int = Field(default=0, ge=0, le=3)
    max_humans: int = Field(default=2, ge=2, le=4)


class JoinRoomRequest(BaseModel):
    code: str | None = None


class ActionRequest(BaseModel):
    type: str  # roll | bank


class RoomView(BaseModel):
    code: str
    status: RoomStatus
    host_id: str
    max_humans: int
    bots: int
    seats: list[RoomSeat]
    game_id: str | None = None
    game: GameState | None = None
    you_are_host: bool = False


def _room_view(room: Room, user: TelegramUser, include_game: bool = True) -> RoomView:
    game: GameState | None = None
    if include_game and room.game_id:
        game = store.get(room.game_id)
        if game and game.phase == Phase.FINISHED and room.status == RoomStatus.PLAYING:
            room.status = RoomStatus.FINISHED
            store.save_room(room)
    return RoomView(
        code=room.code,
        status=room.status,
        host_id=room.host_id,
        max_humans=room.max_humans,
        bots=room.bots,
        seats=room.seats,
        game_id=room.game_id,
        game=game,
        you_are_host=room.host_id == user.id,
    )


def _assert_game_access(state: GameState, user: TelegramUser) -> None:
    seated = {p.id for p in state.players if p.kind == PlayerKind.HUMAN}
    if user.id in seated:
        return
    if settings.dev_mode and not seated:
        return
    if state.owner_user_id and state.owner_user_id == user.id:
        return
    raise HTTPException(status_code=403, detail="Not your game")


def _human_seat(state: GameState, user: TelegramUser) -> str:
    for p in state.players:
        if p.kind == PlayerKind.HUMAN and p.id == user.id:
            return p.id
    if settings.dev_mode:
        # Legacy solo tests sometimes use a single human seat.
        humans = [p for p in state.players if p.kind == PlayerKind.HUMAN]
        if len(humans) == 1 and (
            not state.owner_user_id or state.owner_user_id == user.id or user.id == "dev-user"
        ):
            return humans[0].id
    raise HTTPException(status_code=403, detail="Not your seat")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "dev_mode": settings.dev_mode}


@app.post("/api/games", response_model=GameState)
def create_game_endpoint(
    body: CreateGameRequest,
    user: TelegramUser = Depends(get_current_user),
) -> GameState:
    state = create_game(
        humans=[(user.id, user.display_name)],
        bot_count=body.bots,
        owner_user_id=user.id,
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
    _assert_game_access(state, user)
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
    _assert_game_access(state, user)
    seat_id = _human_seat(state, user)

    engine = GameEngine(state)
    try:
        new_state = engine.apply_action(seat_id, body.type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store.save(new_state)

    if new_state.phase == Phase.FINISHED and new_state.room_code:
        room = store.get_room(new_state.room_code)
        if room and room.status == RoomStatus.PLAYING:
            room.status = RoomStatus.FINISHED
            store.save_room(room)

    return new_state


@app.post("/api/rooms", response_model=RoomView)
def create_room(
    body: CreateRoomRequest,
    user: TelegramUser = Depends(get_current_user),
) -> RoomView:
    if body.bots == 0 and body.max_humans < 2:
        raise HTTPException(status_code=400, detail="Нужны боты или место ещё для людей")

    code = generate_room_code()
    # Extremely unlikely collision; regenerate a few times.
    for _ in range(8):
        if store.get_room(code) is None:
            break
        code = generate_room_code()

    room = Room(
        code=code,
        status=RoomStatus.LOBBY,
        host_id=user.id,
        max_humans=body.max_humans,
        bots=body.bots,
        seats=[RoomSeat(user_id=user.id, name=user.display_name)],
    )
    store.save_room(room)
    return _room_view(room, user)


@app.post("/api/rooms/{code}/join", response_model=RoomView)
def join_room(
    code: str,
    user: TelegramUser = Depends(get_current_user),
) -> RoomView:
    room = store.get_room(code.strip().upper())
    if room is None:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if room.status != RoomStatus.LOBBY:
        if room.is_seated(user.id):
            return _room_view(room, user)
        raise HTTPException(status_code=400, detail="Игра уже началась")
    if room.is_seated(user.id):
        return _room_view(room, user)
    if len(room.seats) >= room.max_humans:
        raise HTTPException(status_code=400, detail="Нет свободных мест")

    room.seats.append(RoomSeat(user_id=user.id, name=user.display_name))
    store.save_room(room)
    return _room_view(room, user)


@app.post("/api/rooms/{code}/start", response_model=RoomView)
def start_room(
    code: str,
    user: TelegramUser = Depends(get_current_user),
) -> RoomView:
    room = store.get_room(code.strip().upper())
    if room is None:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if room.host_id != user.id:
        raise HTTPException(status_code=403, detail="Только хост может начать")
    if room.status != RoomStatus.LOBBY:
        raise HTTPException(status_code=400, detail="Игра уже началась")
    if room.participant_count < 2:
        raise HTTPException(status_code=400, detail="Нужно минимум 2 участника")

    state = create_game(
        humans=[(s.user_id, s.name) for s in room.seats],
        bot_count=room.bots,
        owner_user_id=room.host_id,
        room_code=room.code,
    )
    store.save(state)
    room.game_id = state.id
    room.status = RoomStatus.PLAYING
    store.save_room(room)
    return _room_view(room, user)


@app.get("/api/rooms/{code}", response_model=RoomView)
def get_room(
    code: str,
    user: TelegramUser = Depends(get_current_user),
) -> RoomView:
    room = store.get_room(code.strip().upper())
    if room is None:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if not room.is_seated(user.id) and room.status == RoomStatus.LOBBY:
        # Allow peek so join UI can show seats before joining? Prefer require join.
        # Spec: polling for seated players — only seated (or allow public lobby peek).
        # Allow unseated to see lobby so invite link can show "join" screen.
        pass
    elif not room.is_seated(user.id) and room.status != RoomStatus.LOBBY:
        raise HTTPException(status_code=403, detail="Вы не в этой комнате")
    return _room_view(room, user)


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
