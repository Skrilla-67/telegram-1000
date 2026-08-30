from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


TRIPLE_BASE = {1: 100, 2: 20, 3: 30, 4: 40, 5: 50, 6: 60}
# 3 → base, 4 → base*2, 5 → special for 1/2 else base*10
QUAD_MULT = 2


@dataclass(frozen=True)
class ScoreResult:
    points: int
    scoring_dice: list[int]
    non_scoring: list[int]

    @property
    def is_bust(self) -> bool:
        return self.points <= 0


def _of_a_kind_score(face: int, count: int) -> int:
    if count < 3:
        return 0
    base = TRIPLE_BASE[face]
    if count == 3:
        return base
    if count == 4:
        return base * QUAD_MULT
    # five of a kind
    if face == 1:
        return 1000
    if face == 2:
        return 200
    return base * 10


def score_dice(dice: list[int]) -> ScoreResult:
    """Return the maximum classic scoring combination for a roll."""
    if not dice:
        return ScoreResult(0, [], [])

    n = len(dice)
    best_points = 0
    best_mask = 0

    # Enumerate all non-empty subsets of dice indices (n <= 5).
    for mask in range(1, 1 << n):
        chosen = [dice[i] for i in range(n) if mask & (1 << i)]
        points = _score_exact_set(chosen)
        if points > best_points:
            best_points = points
            best_mask = mask

    if best_points == 0:
        return ScoreResult(0, [], list(dice))

    scoring = [dice[i] for i in range(n) if best_mask & (1 << i)]
    non_scoring = [dice[i] for i in range(n) if not (best_mask & (1 << i))]
    return ScoreResult(best_points, scoring, non_scoring)


def _score_exact_set(dice: list[int]) -> int:
    """Score a set only if EVERY die is used in the combination; else 0."""
    if not dice:
        return 0

    counts = Counter(dice)

    # Straights only with exactly 5 dice.
    if len(dice) == 5 and sorted(dice) == [1, 2, 3, 4, 5]:
        return 125
    if len(dice) == 5 and sorted(dice) == [2, 3, 4, 5, 6]:
        return 250

    remaining = counts.copy()
    points = 0

    for face in sorted(remaining):
        c = remaining[face]
        if c >= 3:
            points += _of_a_kind_score(face, c)
            remaining[face] = 0

    for face, c in list(remaining.items()):
        if c == 0:
            continue
        if face == 1:
            points += 10 * c
            remaining[face] = 0
        elif face == 5:
            points += 5 * c
            remaining[face] = 0

    if any(v > 0 for v in remaining.values()):
        return 0
    return points


def must_keep_all(dice: list[int]) -> bool:
    result = score_dice(dice)
    return result.points > 0 and len(result.non_scoring) == 0
