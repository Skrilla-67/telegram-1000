from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from server.config import settings
from server.game.engine import create_game
from server.game.models import PlayerKind
from server.main import app
from server.store import GameStore


def _client(tmp_path: Path) -> TestClient:
    settings.data_dir = str(tmp_path)
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
    settings.dev_mode = True
    client = _client(tmp_path)

    r = client.post(
        "/api/rooms",
        json={"bots": 1, "max_humans": 2},
        headers=_headers("host1", "Host"),
    )
    assert r.status_code == 200
    room = r.json()
    code = room["code"]
    assert room["status"] == "lobby"
    assert room["you_are_host"] is True
    assert len(room["seats"]) == 1

    r2 = client.post(
        f"/api/rooms/{code}/join",
        headers=_headers("guest1", "Guest"),
    )
    assert r2.status_code == 200
    joined = r2.json()
    assert len(joined["seats"]) == 2
    assert joined["you_are_host"] is False

    bad = client.post(
        f"/api/rooms/{code}/start",
        headers=_headers("guest1", "Guest"),
    )
    assert bad.status_code == 403

    started = client.post(
        f"/api/rooms/{code}/start",
        headers=_headers("host1", "Host"),
    )
    assert started.status_code == 200
    body = started.json()
    assert body["status"] == "playing"
    assert body["game"] is not None
    humans = [p for p in body["game"]["players"] if p["kind"] == "human"]
    bots = [p for p in body["game"]["players"] if p["kind"] == "bot"]
    assert len(humans) == 2
    assert len(bots) == 1


def test_non_owner_human_can_act(tmp_path: Path):
    settings.dev_mode = True
    client = _client(tmp_path)

    r = client.post(
        "/api/rooms",
        json={"bots": 0, "max_humans": 2},
        headers=_headers("host1", "Host"),
    )
    code = r.json()["code"]
    client.post(f"/api/rooms/{code}/join", headers=_headers("guest1", "Guest"))
    started = client.post(
        f"/api/rooms/{code}/start",
        headers=_headers("host1", "Host"),
    )
    game = started.json()["game"]
    game_id = game["id"]
    assert game["players"][0]["id"] == "host1"

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
    assert resp.json()["players"][1]["id"] == "guest1"

    # Ownership must not block host with 403; wrong-turn is 400.
    host_try = client.post(
        f"/api/games/{game_id}/actions",
        json={"type": "bank"},
        headers=_headers("host1", "Host"),
    )
    assert host_try.status_code in (200, 400)
    assert host_try.status_code != 403


def test_create_game_multi_humans_zero_bots():
    state = create_game(
        humans=[("a", "A"), ("b", "B")],
        bot_count=0,
        owner_user_id="a",
    )
    assert len(state.players) == 2
    assert all(p.kind == PlayerKind.HUMAN for p in state.players)
    assert state.owner_user_id == "a"


def test_solo_still_requires_bots(tmp_path: Path):
    settings.dev_mode = True
    client = _client(tmp_path)
    r = client.post("/api/games", json={"bots": 2}, headers=_headers("solo", "Solo"))
    assert r.status_code == 200
    players = r.json()["players"]
    assert sum(1 for p in players if p["kind"] == "human") == 1
    assert sum(1 for p in players if p["kind"] == "bot") == 2
