from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from server.config import settings
from server.game.engine import create_game, join_game, start_game
from server.game.models import GameStatus, PlayerKind
from server.main import app
from server.store import GameStore


def _client(tmp_path: Path) -> TestClient:
    settings.data_dir = str(tmp_path)
    settings.dev_mode = True
    import server.main as main_mod
    import server.store as store_mod

    store_mod.store = GameStore(str(tmp_path))
    main_mod.store = store_mod.store
    return TestClient(app)


def _headers(user_id: str, name: str) -> dict[str, str]:
    return {
        "X-Dev-User-Id": user_id,
        "X-Dev-User": name,
        "Content-Type": "application/json",
    }


def test_create_join_start_room(tmp_path: Path):
    client = _client(tmp_path)

    r = client.post(
        "/api/games",
        json={"bots": 1, "max_humans": 2},
        headers=_headers("host1", "Host"),
    )
    assert r.status_code == 200, r.text
    room = r.json()
    code = room["invite_code"]
    assert room["status"] == "lobby"
    assert room["owner_user_id"] == "host1"
    assert len(room["players"]) == 2  # host + 1 bot

    r2 = client.post(
        "/api/games/join",
        json={"code": code},
        headers=_headers("guest1", "Guest"),
    )
    assert r2.status_code == 200, r2.text
    joined = r2.json()
    humans = [p for p in joined["players"] if p["kind"] == "human"]
    assert len(humans) == 2

    bad = client.post(
        f"/api/games/{joined['id']}/start",
        headers=_headers("guest1", "Guest"),
    )
    assert bad.status_code == 400

    started = client.post(
        f"/api/games/{joined['id']}/start",
        headers=_headers("host1", "Host"),
    )
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["status"] == "playing"
    assert sum(1 for p in body["players"] if p["kind"] == "human") == 2
    assert sum(1 for p in body["players"] if p["kind"] == "bot") == 1


def test_guest_can_act_on_their_turn(tmp_path: Path):
    client = _client(tmp_path)

    r = client.post(
        "/api/games",
        json={"bots": 0, "max_humans": 2},
        headers=_headers("host1", "Host"),
    )
    code = r.json()["invite_code"]
    game_id = r.json()["id"]
    client.post("/api/games/join", json={"code": code}, headers=_headers("guest1", "Guest"))
    client.post(f"/api/games/{game_id}/start", headers=_headers("host1", "Host"))

    import server.main as main_mod
    from server.game.models import Phase, TurnState

    state = main_mod.store.get(game_id)
    assert state is not None
    state.current_player_index = 1
    state.phase = Phase.WAITING_ROLL
    state.turn = TurnState(remaining_dice=5, must_roll=True)
    main_mod.store.save(state)

    resp = client.post(
        f"/api/games/{game_id}/actions",
        json={"type": "roll"},
        headers=_headers("guest1", "Guest"),
    )
    assert resp.status_code == 200, resp.text

    host_try = client.post(
        f"/api/games/{game_id}/actions",
        json={"type": "bank"},
        headers=_headers("host1", "Host"),
    )
    assert host_try.status_code in (200, 400)
    assert host_try.status_code != 403


def test_create_game_lobby_zero_bots():
    state = create_game(
        human_id="a",
        human_name="A",
        bot_count=0,
        max_humans=2,
    )
    assert state.status == GameStatus.LOBBY
    assert len(state.players) == 1
    join_game(state, user_id="b", user_name="B")
    assert state.human_count() == 2
    start_game(state, user_id="a")
    assert state.status == GameStatus.PLAYING
    assert all(p.kind == PlayerKind.HUMAN for p in state.players)


def test_solo_still_works(tmp_path: Path):
    client = _client(tmp_path)
    r = client.post("/api/games", json={"bots": 2}, headers=_headers("solo", "Solo"))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "playing"
    assert sum(1 for p in body["players"] if p["kind"] == "human") == 1
    assert sum(1 for p in body["players"] if p["kind"] == "bot") == 2
