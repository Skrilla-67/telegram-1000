from __future__ import annotations

from . import rules
from .models import GameState, Phase


def decide_action(state: GameState) -> str:
    """Heuristic: bank when safe enough; else risk another roll."""
    if state.phase == Phase.WAITING_ROLL or state.turn.must_roll:
        return "roll"

    if state.phase != Phase.WAITING_DECISION:
        return "roll"

    player = state.current_player()
    turn = state.turn
    cfg = state.config

    if not turn.can_bank:
        # Must keep rolling until threshold met (or bust).
        return "roll"

    remaining = turn.remaining_dice
    score = turn.score
    need = rules.min_bank_points(player, cfg)

    # On barrel — bank as soon as we have enough.
    if player.on_barrel and score >= need:
        return "bank"

    # Just opened / got out of pit — bank sooner when dice are low.
    if remaining == 1 and score >= need:
        # One die left: ~40% chance of 1 or 5 — often bank if already above need+15.
        if score >= need + 20:
            return "bank"
        return "roll"

    if remaining == 2 and score >= need + 30:
        return "bank"

    if remaining >= 3 and score >= max(need, 50) + 25:
        return "bank"

    # Large haul — take it.
    if score >= 150:
        return "bank"

    # Default: risk a bit more if below comfortable cushion.
    if score >= need + 40:
        return "bank"

    return "roll"
