"""Cached immutable projection inputs shared across archetypes (v3.18).

The brother's raw/current state, intrinsic permanent transforms, development
horizon and vanilla roll ranges are independent of the archetype. Building
them once per unique brother state avoids repeating identical setup work for
every role.
"""
from __future__ import annotations

from ..models import STATS, Brother
from .perks import effective_values, natural_projection_effects_by_stat
from .progression import average_gain, development_rounds_to_11, gain_range

_BRO_CONTEXT_CACHE: dict[tuple, tuple] = {}
_BRO_CONTEXT_CACHE_MAX = 256


def bro_fingerprint(bro: Brother) -> tuple:
    return (
        tuple(float(getattr(bro, stat)) for stat in STATS),
        tuple(int(getattr(bro, stat + "Stars")) for stat in STATS),
        tuple(sorted(getattr(bro, "Perks", []) or [])),
        int(getattr(bro, "Level", 0)),
        int(getattr(bro, "LevelPoints", 0)),
        tuple(sorted(getattr(bro, "TraitIDs", []) or [])),
        tuple(sorted(getattr(bro, "PermanentInjuryIDs", []) or [])),
    )


def reset_bro_context_cache() -> None:
    _BRO_CONTEXT_CACHE.clear()


def bro_projection_context(bro: Brother) -> tuple:
    """Return role-independent projection inputs for one immutable bro state.

    Returned mappings are treated as read-only by callers. callers and
    other mutating consumers copy raw_start before modification.
    """
    key = bro_fingerprint(bro)
    cached = _BRO_CONTEXT_CACHE.get(key)
    if cached is not None:
        return cached

    raw_start = {stat: float(getattr(bro, stat)) for stat in STATS}
    effects = natural_projection_effects_by_stat(bro)
    current = effective_values(bro, raw_start, effects)
    levels = development_rounds_to_11(bro)
    gains = {
        stat: average_gain(stat, int(getattr(bro, stat + "Stars")))
        for stat in STATS
    }
    normal_ranges = {
        stat: gain_range(stat, int(getattr(bro, stat + "Stars")))
        for stat in STATS
    }
    result = (raw_start, effects, current, levels, gains, normal_ranges)
    if len(_BRO_CONTEXT_CACHE) >= _BRO_CONTEXT_CACHE_MAX:
        _BRO_CONTEXT_CACHE.clear()
    _BRO_CONTEXT_CACHE[key] = result
    return result
