from __future__ import annotations

from ..models import STATS
from .fingerprint import stable_hash


def progression_evidence(bro) -> dict:
    '''Opaque-safe continuity evidence. Not an active cache identity contract.'''
    future = getattr(bro, "FutureRolls", {}) or {}
    return {
        "background_id": str(getattr(bro, "BackgroundID", "") or ""),
        "stars": {s: int(getattr(bro, s + "Stars")) for s in STATS},
        "trait_ids": sorted(getattr(bro, "TraitIDs", []) or []),
        "future_roll_lengths": {s: len(future.get(s, ()) or ()) for s in STATS},
        "future_roll_digest": stable_hash({
            s: list(future.get(s, ()) or ()) for s in STATS
        }),
    }


def future_roll_suffix_shift(previous_bro, current_bro) -> int | None:
    '''Diagnostic-only check for a common consumed prefix across all stats.'''
    prev = getattr(previous_bro, "FutureRolls", {}) or {}
    cur = getattr(current_bro, "FutureRolls", {}) or {}
    shifts = set()
    for stat in STATS:
        a = list(prev.get(stat, ()) or ())
        b = list(cur.get(stat, ()) or ())
        if not a and not b:
            continue
        if len(b) > len(a):
            return None
        shift = len(a) - len(b)
        if a[shift:] != b:
            return None
        shifts.add(shift)
    if not shifts:
        return None
    return shifts.pop() if len(shifts) == 1 else None
