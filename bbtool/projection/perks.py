
"""Permanent exact perk and trait effects applied to aggregated raw stats."""
from __future__ import annotations

import json
import math
from pathlib import Path

from ..models import Brother, STATS

_PERK_EFFECTS_CACHE = None
_TRAIT_EFFECTS_CACHE = None
_PERMANENT_INJURY_EFFECTS_CACHE = None


def reset_perk_cache() -> None:
    global _PERK_EFFECTS_CACHE, _TRAIT_EFFECTS_CACHE, _PERMANENT_INJURY_EFFECTS_CACHE
    _PERK_EFFECTS_CACHE = None
    _TRAIT_EFFECTS_CACHE = None
    _PERMANENT_INJURY_EFFECTS_CACHE = None

def _load_perk_effects() -> dict:
    global _PERK_EFFECTS_CACHE
    if _PERK_EFFECTS_CACHE is not None:
        return _PERK_EFFECTS_CACHE

    path = Path(__file__).resolve().parents[2] / "references" / "perk_effects.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(
            "references/perk_effects.json is a generated runtime cache and is missing. "
            "Run the toolkit through bb_analyze.py so ensure_references() can build it."
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "references/perk_effects.json is invalid. Delete it and rerun bb_analyze.py "
            "to regenerate the cache."
        ) from exc

    by_name = {}
    for rec in raw.get("perks", {}).values():
        name = rec.get("Name")
        if name:
            by_name[name] = rec
    _PERK_EFFECTS_CACHE = by_name
    return _PERK_EFFECTS_CACHE



def _load_trait_effects() -> dict:
    global _TRAIT_EFFECTS_CACHE
    if _TRAIT_EFFECTS_CACHE is not None:
        return _TRAIT_EFFECTS_CACHE

    path = Path(__file__).resolve().parents[2] / "references" / "trait_effects.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(
            "references/trait_effects.json is a generated runtime cache and is missing. "
            "Run the toolkit through bb_analyze.py so ensure_references() can build it."
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "references/trait_effects.json is invalid. Delete it and rerun bb_analyze.py "
            "to regenerate the cache."
        ) from exc

    traits = raw.get("traits", {})
    _TRAIT_EFFECTS_CACHE = {
        str(key).upper(): rec for key, rec in traits.items() if isinstance(rec, dict)
    }
    return _TRAIT_EFFECTS_CACHE



def _load_permanent_injury_effects() -> dict:
    global _PERMANENT_INJURY_EFFECTS_CACHE
    if _PERMANENT_INJURY_EFFECTS_CACHE is not None:
        return _PERMANENT_INJURY_EFFECTS_CACHE

    path = Path(__file__).resolve().parents[2] / "references" / "permanent_injury_effects.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(
            "references/permanent_injury_effects.json is a generated runtime cache and is missing. "
            "Run the toolkit through bb_analyze.py so ensure_references() can build it."
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "references/permanent_injury_effects.json is invalid. Delete it and rerun bb_analyze.py."
        ) from exc

    injuries = raw.get("injuries", {})
    _PERMANENT_INJURY_EFFECTS_CACHE = {
        str(key).upper(): rec for key, rec in injuries.items() if isinstance(rec, dict)
    }
    return _PERMANENT_INJURY_EFFECTS_CACHE


def _exact_perk_effects_for_bro(bro: Brother) -> list[dict]:
    registry = _load_perk_effects()
    effects = []
    for perk_name in getattr(bro, "Perks", []) or []:
        rec = registry.get(perk_name)
        if not rec:
            continue
        effects.extend(
            effect for effect in rec.get("Effects", [])
            if effect.get("exact") and not effect.get("conditional")
        )
    return effects


def _exact_trait_effects_for_bro(bro: Brother) -> list[dict]:
    trait_ids = list(getattr(bro, "TraitIDs", []) or [])
    if not trait_ids:
        return []
    registry = _load_trait_effects()
    effects = []
    for trait_id in trait_ids:
        rec = registry.get(str(trait_id).upper())
        if not rec:
            continue
        effects.extend(
            effect for effect in rec.get("Effects", [])
            if effect.get("exact") and not effect.get("conditional")
        )
    return effects



def _exact_permanent_injury_effects_for_bro(bro: Brother) -> list[dict]:
    injury_ids = list(getattr(bro, "PermanentInjuryIDs", []) or [])
    if not injury_ids:
        return []
    registry = _load_permanent_injury_effects()
    effects = []
    for injury_id in injury_ids:
        rec = registry.get(str(injury_id).upper())
        if not rec:
            continue
        effects.extend(
            effect for effect in rec.get("Effects", [])
            if effect.get("exact") and not effect.get("conditional")
        )
    return effects


def _effects_by_stat(bro: Brother) -> dict[str, list[dict]]:
    out = {stat: [] for stat in STATS}
    for effect in (
        _exact_perk_effects_for_bro(bro)
        + _exact_trait_effects_for_bro(bro)
        + _exact_permanent_injury_effects_for_bro(bro)
    ):
        stat = effect.get("stat")
        if stat in out:
            out[stat].append(effect)
    return out


def natural_projection_effects_by_stat(bro: Brother) -> dict[str, list[dict]]:
    """Exact intrinsic effects used to evaluate natural archetype potential.

    Owned perks describe a chosen build and must not improve the underlying
    stat potential that is used to decide whether that build fits. Permanent
    traits and permanent injuries remain intrinsic brother state and therefore
    continue to participate in projection.
    """
    out = {stat: [] for stat in STATS}
    for effect in (
        _exact_trait_effects_for_bro(bro)
        + _exact_permanent_injury_effects_for_bro(bro)
    ):
        stat = effect.get("stat")
        if stat in out:
            out[stat].append(effect)
    return out

def effective_stat_value(
    bro: Brother,
    stat: str,
    raw_value: float,
    effects_by_stat: dict[str, list[dict]] | None = None,
) -> float:
    """
    Apply permanent exact perk/trait/permanent-injury effects to one AGGREGATED raw stat value.

    Multipliers are applied after all raw future gains have been aggregated.
    Finalization mirrors the game's integer-facing stat behavior for the two
    exact integer-facing multipliers currently present in vanilla:
      - HitpointsMult -> floor (Colossus)
      - BraveryMult   -> nearest integer (Fortified Mind)
    """
    effects = (
        effects_by_stat if effects_by_stat is not None else _effects_by_stat(bro)
    ).get(stat, [])

    value = float(raw_value)
    multiplier_properties = set()

    for effect in effects:
        op = effect.get("op")
        amount = float(effect.get("value", 0.0))
        prop = effect.get("property")

        if op == "+=":
            value += amount
        elif op == "-=":
            value -= amount
        elif op == "*=":
            value *= amount
            if prop:
                multiplier_properties.add(prop)
        elif op == "/=" and amount != 0:
            value /= amount
            if prop:
                multiplier_properties.add(prop)

    if stat == "HP" and "HitpointsMult" in multiplier_properties:
        value = math.floor(value)
    elif stat == "Resolve" and "BraveryMult" in multiplier_properties:
        # Battle Brothers exposes Resolve/Bravery as an integer. Use the
        # game's positive-number Math.round behavior, not Python bankers-round.
        value = math.floor(value + 0.5)

    return float(value)

def effective_values(
    bro: Brother,
    raw_values: dict[str, float],
    effects_by_stat: dict[str, list[dict]] | None = None,
) -> dict[str, float]:
    effects_by_stat = effects_by_stat or _effects_by_stat(bro)
    return {
        stat: effective_stat_value(
            bro, stat, raw_values[stat], effects_by_stat
        )
        for stat in STATS
    }

def effective_stat_profile(bro: Brother) -> tuple[dict[str, float], dict[str, float]]:
    """
    Backward-compatible public helper.

    Returns current effective stats plus informational multipliers. Projection
    code no longer multiplies individual future rolls; it transforms the
    aggregated raw total through effective_stat_value().
    """
    raw = {stat: float(getattr(bro, stat)) for stat in STATS}
    effects = _effects_by_stat(bro)
    effective = effective_values(bro, raw, effects)

    mult = {stat: 1.0 for stat in STATS}
    for stat, stat_effects in effects.items():
        for effect in stat_effects:
            if effect.get("op") == "*=":
                mult[stat] *= float(effect.get("value", 1.0))
            elif effect.get("op") == "/=" and float(effect.get("value", 0.0)) != 0:
                mult[stat] /= float(effect["value"])
    return effective, mult
