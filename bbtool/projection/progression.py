
"""Level-up roll ranges and deterministic level-11 projections."""
from __future__ import annotations


from ..models import Brother

def gain_range(stat: str, stars: int) -> tuple[int, int]:
    """
    Vanilla normal-level roll range used by the projection model.

    Base ranges:
      Initiative: 3-5
      MAtk/MDef: 1-3
      HP/Fatigue/Resolve/RAtk/RDef: 2-4

    Talent stars shift the range:
      0*: base
      1*: +1 minimum
      2*: +2 minimum
      3*: +2 minimum and +1 maximum
    """
    if stat == "Initiative":
        lo, hi = 3, 5
    elif stat in ("MAtk", "MDef"):
        lo, hi = 1, 3
    else:
        lo, hi = 2, 4

    lo += min(stars, 2)
    hi += stars // 3
    return lo, hi

def average_gain(stat: str, stars: int) -> float:
    lo, hi = gain_range(stat, stars)
    return (lo + hi) / 2.0


def development_rounds_to_11(bro: Brother) -> int:
    """
    Number of stat-allocation rounds still available through level 11.

    Reaching a level increments Brother.Level before the player necessarily
    spends that level's stat points. Therefore pending LevelPoints must count
    as still-available development rounds.

    Example:
      Level 2 + LevelPoints 1 -> 10 rounds remain:
      the pending level-2 allocation + levels 3..11.
    """
    level_points = getattr(bro, "LevelPoints", None)
    pending_rounds = 0 if level_points is None else max(0, int(level_points))
    return max(0, 11 - int(bro.Level)) + pending_rounds

