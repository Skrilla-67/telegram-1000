from __future__ import annotations

from .models import GameConfig, GameEvent, PlayerState


def pit_for_score(score: int, config: GameConfig) -> tuple[int, int] | None:
    for low, high in config.pits:
        if low <= score < high:
            return low, high
    return None


def in_pit(player: PlayerState, config: GameConfig) -> bool:
    return pit_for_score(player.score, config) is not None


def min_bank_points(player: PlayerState, config: GameConfig) -> int:
    """Minimum turn score required to bank."""
    if player.on_barrel:
        return max(1, config.win_score - player.score)

    if not player.opened:
        return config.open_threshold

    pit = pit_for_score(player.score, config)
    if pit is not None:
        _low, high = pit
        return high - player.score

    return 1


def can_bank(player: PlayerState, turn_score: int, config: GameConfig) -> bool:
    return turn_score >= min_bank_points(player, config)


def bolts_count_on_bust(player: PlayerState, config: GameConfig) -> bool:
    """Bolts do not accumulate in pit / on barrel / before opening."""
    if not player.opened:
        return False
    if player.on_barrel:
        return False
    if in_pit(player, config):
        return False
    return True


def apply_score_delta(player: PlayerState, delta: int, events: list[GameEvent]) -> None:
    player.score = max(0, player.score + delta)
    events.append(
        GameEvent(
            type="score_change",
            message=f"{player.name}: {'+' if delta >= 0 else ''}{delta} → {player.score}",
            data={"player_id": player.id, "delta": delta, "score": player.score},
        )
    )


def apply_bank(
    player: PlayerState,
    turn_score: int,
    others: list[PlayerState],
    config: GameConfig,
    events: list[GameEvent],
) -> bool:
    """
    Apply banking turn_score for player.
    Returns True if the player won.
    """
    old_score = player.score
    was_on_barrel = player.on_barrel

    if player.on_barrel:
        # Must reach win_score in one go.
        new_score = player.score + turn_score
        if new_score >= config.win_score:
            player.score = new_score
            player.on_barrel = False
            events.append(
                GameEvent(
                    type="win",
                    message=f"{player.name} набрал {new_score} и победил!",
                    data={"player_id": player.id, "score": new_score},
                )
            )
            return True
        # Failed barrel attempt handled by caller via barrel_attempts.
        return False

    new_score = old_score + turn_score

    if not player.opened:
        player.opened = True
        events.append(
            GameEvent(
                type="opened",
                message=f"{player.name} открыл игру ({turn_score})",
                data={"player_id": player.id, "points": turn_score},
            )
        )

    # Cap at barrel threshold when climbing onto barrel.
    if new_score > config.barrel_threshold:
        # Point barrel: must sit at threshold before finishing (even if turn overshoots 1000).
        player.score = config.barrel_threshold
        player.on_barrel = True
        player.barrel_attempts = 0
        events.append(
            GameEvent(
                type="barrel",
                message=f"{player.name} сел на бочку ({config.barrel_threshold})",
                data={"player_id": player.id},
            )
        )
        for other in others:
            if other.on_barrel and other.id != player.id:
                knock_off_barrel(other, config, events, reason="opponent_barrel")
    else:
        player.score = new_score

    # Dump truck
    if player.score == config.dump_truck_score:
        player.score = 0
        player.on_barrel = False
        player.barrel_attempts = 0
        events.append(
            GameEvent(
                type="dump_truck",
                message=f"{player.name} попал на самосвал ({config.dump_truck_score}) — счёт обнулён!",
                data={"player_id": player.id},
            )
        )
        return False

    # Overtake: before < other < after (strict), −50 each overtaken player.
    if not was_on_barrel and player.score > 0:
        _apply_overtakes(player, others, old_score, config, events)

    return False


def _apply_overtakes(
    player: PlayerState,
    others: list[PlayerState],
    old_score: int,
    config: GameConfig,
    events: list[GameEvent],
) -> None:
    for other in others:
        if other.id == player.id:
            continue
        if old_score < other.score < player.score:
            apply_score_delta(other, -config.overtake_penalty, events)
            events.append(
                GameEvent(
                    type="overtake",
                    message=f"{player.name} обогнал {other.name} (−{config.overtake_penalty})",
                    data={
                        "player_id": player.id,
                        "target_id": other.id,
                        "penalty": config.overtake_penalty,
                    },
                )
            )
            if other.score == config.dump_truck_score:
                other.score = 0
                events.append(
                    GameEvent(
                        type="dump_truck",
                        message=f"{other.name} попал на самосвал ({config.dump_truck_score}) — счёт обнулён!",
                        data={"player_id": other.id},
                    )
                )


def knock_off_barrel(
    player: PlayerState,
    config: GameConfig,
    events: list[GameEvent],
    reason: str,
) -> None:
    player.on_barrel = False
    player.barrel_attempts = 0
    player.barrel_falls += 1

    if player.barrel_falls >= config.barrel_falls_limit:
        player.score = 0
        events.append(
            GameEvent(
                type="barrel_fall_zero",
                message=f"{player.name} упал с бочки в третий раз — счёт обнулён!",
                data={"player_id": player.id, "reason": reason},
            )
        )
    else:
        apply_score_delta(player, -config.barrel_fall_penalty, events)
        events.append(
            GameEvent(
                type="barrel_fall",
                message=f"{player.name} упал с бочки (−{config.barrel_fall_penalty})",
                data={"player_id": player.id, "reason": reason, "falls": player.barrel_falls},
            )
        )


def register_failed_barrel_attempt(
    player: PlayerState,
    config: GameConfig,
    events: list[GameEvent],
) -> None:
    player.barrel_attempts += 1
    events.append(
        GameEvent(
            type="barrel_attempt",
            message=f"{player.name}: попытка с бочки {player.barrel_attempts}/{config.barrel_attempts}",
            data={"player_id": player.id, "attempts": player.barrel_attempts},
        )
    )
    if player.barrel_attempts >= config.barrel_attempts:
        knock_off_barrel(player, config, events, reason="attempts_exhausted")


def register_bolt(player: PlayerState, config: GameConfig, events: list[GameEvent]) -> None:
    if not bolts_count_on_bust(player, config):
        events.append(
            GameEvent(
                type="bust",
                message=f"{player.name}: нулевая комбинация (болт не засчитывается)",
                data={"player_id": player.id},
            )
        )
        return

    player.bolts += 1
    events.append(
        GameEvent(
            type="bolt",
            message=f"{player.name}: болт ({player.bolts}/{config.bolt_limit})",
            data={"player_id": player.id, "bolts": player.bolts},
        )
    )
    if player.bolts >= config.bolt_limit:
        player.bolts = 0
        apply_score_delta(player, -config.bolt_penalty, events)
        if player.score == config.dump_truck_score:
            player.score = 0
            events.append(
                GameEvent(
                    type="dump_truck",
                    message=f"{player.name} попал на самосвал ({config.dump_truck_score}) — счёт обнулён!",
                    data={"player_id": player.id},
                )
            )
        events.append(
            GameEvent(
                type="bolt_penalty",
                message=f"{player.name}: 3 болта (−{config.bolt_penalty})",
                data={"player_id": player.id},
            )
        )
