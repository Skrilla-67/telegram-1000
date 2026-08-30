from __future__ import annotations

import secrets
import uuid
from typing import Callable

from . import rules
from .bot_ai import decide_action
from .models import (
    GameConfig,
    GameEvent,
    GameState,
    Phase,
    PlayerKind,
    PlayerState,
    TurnState,
)
from .scoring import score_dice


RollFn = Callable[[int], list[int]]


def _default_roll(n: int) -> list[int]:
    return [secrets.randbelow(6) + 1 for _ in range(n)]


def create_game(
    *,
    human_id: str,
    human_name: str,
    bot_count: int = 1,
    config: GameConfig | None = None,
) -> GameState:
    bot_count = max(1, min(3, bot_count))
    cfg = config or GameConfig()
    players: list[PlayerState] = [
        PlayerState(id=human_id, name=human_name or "Игрок", kind=PlayerKind.HUMAN)
    ]
    bot_names = ["Бот Алекс", "Бот Маша", "Бот Игорь"]
    for i in range(bot_count):
        players.append(
            PlayerState(
                id=f"bot-{i + 1}",
                name=bot_names[i],
                kind=PlayerKind.BOT,
            )
        )

    state = GameState(
        id=str(uuid.uuid4()),
        config=cfg,
        players=players,
        owner_user_id=human_id,
        turn=TurnState(remaining_dice=cfg.dice_count, must_roll=True),
        events=[
            GameEvent(
                type="game_start",
                message=f"Игра началась! Игроков: {len(players)}",
                data={"bot_count": bot_count},
            )
        ],
    )
    return state


class GameEngine:
    def __init__(self, state: GameState, roll_fn: RollFn | None = None) -> None:
        self.state = state
        self.roll_fn = roll_fn or _default_roll

    def public_state(self) -> GameState:
        return self.state

    def apply_action(self, player_id: str, action: str) -> GameState:
        if self.state.phase == Phase.FINISHED:
            raise ValueError("Игра уже окончена")

        current = self.state.current_player()
        if current.id != player_id:
            raise ValueError("Сейчас ход другого игрока")

        if action == "roll":
            self._roll()
        elif action == "bank":
            self._bank()
        else:
            raise ValueError(f"Неизвестное действие: {action}")

        # After human action, auto-play bots until human turn or finish.
        self._play_bots()
        return self.state

    def _play_bots(self) -> None:
        guard = 0
        while (
            self.state.phase != Phase.FINISHED
            and self.state.current_player().kind == PlayerKind.BOT
            and guard < 200
        ):
            guard += 1
            action = decide_action(self.state)
            if action == "roll":
                self._roll()
            else:
                self._bank()

    def _roll(self) -> None:
        if self.state.phase not in (Phase.WAITING_ROLL, Phase.WAITING_DECISION):
            raise ValueError("Сейчас нельзя бросать")

        # After a scoring roll, player may roll again only if they choose not to bank
        # (must_roll True after hot dice or start).
        if self.state.phase == Phase.WAITING_DECISION and not self.state.turn.must_roll:
            # Voluntary re-roll of remaining non-scoring dice.
            pass
        elif self.state.phase == Phase.WAITING_DECISION and self.state.turn.must_roll:
            pass
        elif self.state.phase == Phase.WAITING_ROLL:
            pass
        else:
            raise ValueError("Сейчас нельзя бросать")

        n = self.state.turn.remaining_dice
        if n <= 0:
            n = self.state.config.dice_count

        dice = self.roll_fn(n)
        result = score_dice(dice)
        player = self.state.current_player()

        self.state.turn.last_roll = dice
        self.state.turn.last_scoring_dice = result.scoring_dice
        self.state.turn.last_roll_points = result.points

        self.state.events.append(
            GameEvent(
                type="roll",
                message=f"{player.name} бросил: {', '.join(map(str, dice))} → {result.points}",
                data={
                    "player_id": player.id,
                    "dice": dice,
                    "points": result.points,
                    "scoring": result.scoring_dice,
                },
            )
        )

        if result.is_bust:
            self._handle_bust()
            return

        self.state.turn.score += result.points
        non = len(result.non_scoring)

        if non == 0:
            # Hot dice — must roll all five again.
            self.state.turn.remaining_dice = self.state.config.dice_count
            self.state.turn.must_roll = True
            self.state.phase = Phase.WAITING_ROLL
            self.state.events.append(
                GameEvent(
                    type="hot_dice",
                    message=f"{player.name}: все кости в игре — обязательный бросок всех пяти!",
                    data={"player_id": player.id, "turn_score": self.state.turn.score},
                )
            )
        else:
            self.state.turn.remaining_dice = non
            self.state.turn.must_roll = False
            self.state.phase = Phase.WAITING_DECISION

        self.state.turn.can_bank = rules.can_bank(
            player, self.state.turn.score, self.state.config
        )

    def _handle_bust(self) -> None:
        player = self.state.current_player()
        if player.on_barrel:
            # Bust on barrel counts as failed attempt.
            rules.register_failed_barrel_attempt(player, self.state.config, self.state.events)
        else:
            rules.register_bolt(player, self.state.config, self.state.events)

        self.state.events.append(
            GameEvent(
                type="bust",
                message=f"{player.name}: очки хода сгорели",
                data={"player_id": player.id, "lost": self.state.turn.score},
            )
        )
        self._advance_player()

    def _bank(self) -> None:
        if self.state.phase != Phase.WAITING_DECISION:
            raise ValueError("Нельзя сказать «хватит» сейчас")
        if self.state.turn.must_roll:
            raise ValueError("Обязательный бросок — нельзя банкуть")

        player = self.state.current_player()
        turn_score = self.state.turn.score

        if not rules.can_bank(player, turn_score, self.state.config):
            need = rules.min_bank_points(player, self.state.config)
            raise ValueError(f"Нужно минимум {need} очков, чтобы записать")

        others = [p for p in self.state.players if p.id != player.id]

        if player.on_barrel:
            won = rules.apply_bank(player, turn_score, others, self.state.config, self.state.events)
            if won:
                self.state.winner_id = player.id
                self.state.phase = Phase.FINISHED
                return
            # Banked but didn't reach 1000 — failed attempt.
            rules.register_failed_barrel_attempt(player, self.state.config, self.state.events)
            self._advance_player()
            return

        won = rules.apply_bank(player, turn_score, others, self.state.config, self.state.events)
        if won:
            self.state.winner_id = player.id
            self.state.phase = Phase.FINISHED
            return

        self.state.events.append(
            GameEvent(
                type="bank",
                message=f"{player.name} записал {turn_score} (счёт {player.score})",
                data={"player_id": player.id, "points": turn_score, "score": player.score},
            )
        )
        self._advance_player()

    def _advance_player(self) -> None:
        self.state.current_player_index = (self.state.current_player_index + 1) % len(
            self.state.players
        )
        cfg = self.state.config
        self.state.turn = TurnState(
            remaining_dice=cfg.dice_count,
            must_roll=True,
            can_bank=False,
        )
        self.state.phase = Phase.WAITING_ROLL
        nxt = self.state.current_player()
        self.state.events.append(
            GameEvent(
                type="turn",
                message=f"Ход: {nxt.name}",
                data={"player_id": nxt.id},
            )
        )


# Convenience for tests / API
def create_game_engine(
    *,
    human_id: str,
    human_name: str,
    bot_count: int = 1,
    config: GameConfig | None = None,
    roll_fn: RollFn | None = None,
) -> GameEngine:
    return GameEngine(
        create_game(
            human_id=human_id,
            human_name=human_name,
            bot_count=bot_count,
            config=config,
        ),
        roll_fn=roll_fn,
    )
