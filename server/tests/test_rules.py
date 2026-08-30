from server.game.engine import GameEngine, create_game
from server.game.models import GameConfig, Phase
from server.game import rules


def test_min_bank_open():
    state = create_game(human_id="h", human_name="H", bot_count=1)
    p = state.players[0]
    assert rules.min_bank_points(p, state.config) == 50
    assert rules.can_bank(p, 45, state.config) is False
    assert rules.can_bank(p, 50, state.config) is True


def test_pit_requirement():
    cfg = GameConfig()
    state = create_game(human_id="h", human_name="H", bot_count=1, config=cfg)
    p = state.players[0]
    p.opened = True
    p.score = 225
    assert rules.min_bank_points(p, cfg) == 75


def test_overtake_and_dump_truck():
    cfg = GameConfig()
    state = create_game(human_id="h", human_name="H", bot_count=1, config=cfg)
    human = state.players[0]
    bot = state.players[1]
    human.opened = True
    bot.opened = True
    human.score = 100
    bot.score = 140
    events = []
    rules.apply_bank(human, 50, [bot], cfg, events)
    # 100+50=150 > 140 → overtake −50 → bot 90
    assert human.score == 150
    assert bot.score == 90
    assert any(e.type == "overtake" for e in events)


def test_dump_truck_exact():
    cfg = GameConfig()
    state = create_game(human_id="h", human_name="H", bot_count=1, config=cfg)
    human = state.players[0]
    human.opened = True
    human.score = 500
    events = []
    rules.apply_bank(human, 55, state.players[1:], cfg, events)
    assert human.score == 0
    assert any(e.type == "dump_truck" for e in events)


def test_barrel_sit():
    cfg = GameConfig()
    state = create_game(human_id="h", human_name="H", bot_count=1, config=cfg)
    human = state.players[0]
    human.opened = True
    human.score = 850
    events = []
    rules.apply_bank(human, 40, state.players[1:], cfg, events)
    assert human.on_barrel
    assert human.score == 880


def test_engine_roll_bust(monkeypatch):
    state = create_game(human_id="h", human_name="H", bot_count=1)
    # Prevent bot from playing after bust by making next player human-only:
    # After bust, advances to bot — stub bot to bank immediately won't work if waiting_roll.
    # Use roll_fn that returns bust for human, then for bot returns scoring and we... 
    # Simpler: only test scoring path with controlled rolls.

    rolls = iter(
        [
            [2, 3, 4, 6, 6],  # bust
        ]
    )

    def roll_fn(n: int) -> list[int]:
        return list(next(rolls))[:n]

    engine = GameEngine(state, roll_fn=roll_fn)
    # Remove bots so turn stays testable
    state.players = [state.players[0]]
    engine.apply_action("h", "roll")
    assert state.turn.score == 0
    assert state.phase == Phase.WAITING_ROLL


def test_hot_dice():
    state = create_game(human_id="h", human_name="H", bot_count=1)
    state.players = [state.players[0]]

    def roll_fn(n: int) -> list[int]:
        return [1, 1, 1, 5, 5][:n]

    engine = GameEngine(state, roll_fn=roll_fn)
    engine.apply_action("h", "roll")
    assert state.turn.score == 110  # 100 + 10
    assert state.turn.remaining_dice == 5
    assert state.turn.must_roll is True
    assert state.phase == Phase.WAITING_ROLL
