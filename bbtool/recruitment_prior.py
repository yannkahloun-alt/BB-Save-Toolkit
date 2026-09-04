"""Intrinsic Background x Archetype potential prior (model v1).

This module deliberately accepts no recruit, roster, intent, or economy inputs.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations, product
import json
from math import comb, lcm
from pathlib import Path

from .build_identity import build_definition_hash, build_identity
from .incremental.dependencies import ArtifactKind, ENGINE_VERSIONS
from .models import STATS, Brother
from .projection.planner import project_validation_oracle


MODEL_ID = "bbtool.background_archetype_prior.v1"
_STAR_WEIGHTS = {1: 6, 2: 3, 3: 1}


def load_background_potential_reference(path: Path) -> dict:
    """Load the source-pinned v2 background reference used by this model."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("_meta", {}).get("format") != "bbtool.backgrounds.v2":
        raise ValueError("background potential requires bbtool.backgrounds.v2")
    return raw


def _weighted_relevant_talents(profile: dict, fit_stats: tuple[str, ...]):
    if profile.get("untalented"):
        return {(0,) * len(fit_stats): 1}, 1
    excluded = set(profile.get("excluded_talents", ()))
    eligible = tuple(stat for stat in STATS if stat not in excluded)
    if len(eligible) < 3:
        raise ValueError("background has fewer than three eligible talent stats")
    grouped: dict[tuple[int, ...], int] = defaultdict(int)
    for talented in combinations(eligible, 3):
        for grades in product((1, 2, 3), repeat=3):
            by_stat = dict(zip(talented, grades, strict=True))
            key = tuple(by_stat.get(stat, 0) for stat in fit_stats)
            weight = 1
            for grade in grades:
                weight *= _STAR_WEIGHTS[grade]
            grouped[key] += weight
    return dict(sorted(grouped.items())), comb(len(eligible), 3) * 1000


def _reference_brother(background_id: str, profile: dict, stars: dict) -> Brother:
    values = {
        stat: (int(profile["stat_ranges"][stat][0])
               + int(profile["stat_ranges"][stat][1])) // 2
        for stat in STATS
    }
    kwargs = {stat: values[stat] for stat in STATS}
    kwargs.update({f"{stat}Stars": int(stars.get(stat, 0)) for stat in STATS})
    return Brother(
        Name="Background reference profile", Title="", Level=1, XP=0,
        PerkPoints=0, PerksUsed=0, LevelPoints=0, AP=9,
        BackgroundID=background_id, Background="", PerkIDs=[], Perks=[],
        TraitIDs=[], Traits=[], Injuries=[], HumanOffset=0, **kwargs,
    )


def background_archetype_prior(
    background_save_hash: str, role: dict, reference: dict,
) -> dict:
    """Return a deterministic intrinsic prior for one background/build pair.

    Initial stats use the lower integer midpoint of each source-defined range.
    The probability space is the exact vanilla talent lottery, collapsed over
    role-irrelevant stars. Each outcome is then evaluated by the production
    level-11 projection/Fit engine.
    """
    identity = build_identity(role)
    if identity is None:
        raise ValueError("background prior requires authoritative BuildIdentity")
    backgrounds = reference.get("backgrounds", {})
    key = str(background_save_hash).upper()
    record = backgrounds.get(key)
    if record is None:
        raise KeyError(f"unsupported background save hash: {key}")
    profile = record.get("PotentialProfile")
    if not isinstance(profile, dict):
        raise ValueError(f"background {key} has no exact potential profile")

    fit_stats = tuple(
        stat for stat in STATS if role.get("stats", {}).get(stat, {}).get("fit")
    )
    outcomes, total_weight = _weighted_relevant_talents(profile, fit_stats)
    projected = []
    sample_denominator = 1
    histogram: dict[str, int] = defaultdict(int)
    for star_tuple, weight in outcomes.items():
        bro = _reference_brother(key, profile, dict(zip(fit_stats, star_tuple, strict=True)))
        oracle = project_validation_oracle(bro, role)
        samples = oracle["outcomes_pct"]
        if not samples:
            raise ValueError("projection oracle returned an empty outcome distribution")
        sample_denominator = lcm(sample_denominator, len(samples))
        projected.append((weight, samples))
    combined_weight = total_weight * sample_denominator
    weighted_sum = 0.0
    for weight, samples in projected:
        outcome_weight = weight * (sample_denominator // len(samples))
        for fit in samples:
            fit = float(fit)
            weighted_sum += fit * outcome_weight
            lower = min(90, max(0, int(fit // 10) * 10))
            label = "90-100" if lower == 90 else f"{lower:02d}-{lower + 9:02d}"
            histogram[label] += outcome_weight

    return {
        "schema": MODEL_ID,
        "model_version": 1,
        "background": {
            "save_hash": key,
            "background_id": record.get("BackgroundID"),
            "source_revision": reference.get("_meta", {}).get("source_revision"),
        },
        "build": {
            "id": identity,
            "definition_hash": build_definition_hash(role),
        },
        "engine_versions": {
            "role_projection": ENGINE_VERSIONS[ArtifactKind.ROLE_PROJECTION],
            "validation_oracle": ENGINE_VERSIONS[ArtifactKind.VALIDATION_ORACLE],
        },
        "assumptions": {
            "starting_stats": "lower integer midpoint of each vanilla level-1 range",
            "talents": "vanilla three-distinct-stat 60/30/10 star lottery",
            "traits_and_injuries": "none; recruit-specific evidence is excluded",
            "projection": "existing blind natural level-11 Fit trajectory",
        },
        "distribution": {
            "talent_weight_denominator": total_weight,
            "trajectory_sample_denominator": sample_denominator,
            "weight_denominator": combined_weight,
            "unique_talent_profiles": len(outcomes),
            "fit_histogram_weight": dict(sorted(histogram.items())),
            "mean_fit_pct": round(weighted_sum / combined_weight, 1),
        },
    }


def supported_backgrounds(reference: dict) -> list[dict]:
    """Enumerate backgrounds with an exact v1 potential profile."""
    return [
        {"save_hash": key, "background_id": rec.get("BackgroundID"), "key": rec.get("Key")}
        for key, rec in sorted(reference.get("backgrounds", {}).items())
        if isinstance(rec.get("PotentialProfile"), dict)
    ]
