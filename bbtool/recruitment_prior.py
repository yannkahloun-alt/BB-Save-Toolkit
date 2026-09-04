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
from .projection.perks import _load_trait_effects


MODEL_ID = "bbtool.background_archetype_prior.v1"
CANDIDATE_MODEL_ID = "bbtool.recruit_candidate_estimate.v1"
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


def _reference_brother(
    background_id: str, profile: dict, stars: dict,
    trait_ids: tuple[str, ...] = (),
) -> Brother:
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
        TraitIDs=list(trait_ids), Traits=[], Injuries=[], HumanOffset=0, **kwargs,
    )


def _project_distribution(
    background_key: str, profile: dict, role: dict,
    trait_ids: tuple[str, ...] = (),
) -> dict:
    """Evaluate the shared #110 outcome space with optional known traits."""
    fit_stats = tuple(
        stat for stat in STATS if role.get("stats", {}).get(stat, {}).get("fit")
    )
    outcomes, total_weight = _weighted_relevant_talents(profile, fit_stats)
    projected = []
    sample_denominator = 1
    histogram: dict[str, int] = defaultdict(int)
    for star_tuple, weight in outcomes.items():
        bro = _reference_brother(
            background_key,
            profile,
            dict(zip(fit_stats, star_tuple, strict=True)),
            trait_ids,
        )
        samples = project_validation_oracle(bro, role)["outcomes_pct"]
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
        "talent_weight_denominator": total_weight,
        "trajectory_sample_denominator": sample_denominator,
        "weight_denominator": combined_weight,
        "unique_talent_profiles": len(outcomes),
        "fit_histogram_weight": dict(sorted(histogram.items())),
        "mean_fit_pct": round(weighted_sum / combined_weight, 1),
    }


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
        reason = record.get("PotentialUnsupportedReason", "unspecified")
        raise ValueError(
            f"background {key} has no exact potential profile: {reason}"
        )

    distribution = _project_distribution(key, profile, role)

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
        "distribution": distribution,
    }


def _conditioned_distribution(
    background_save_hash: str, role: dict, reference: dict,
    trait_ids: tuple[str, ...],
) -> dict:
    """Re-run the v1 prior outcome space with exact public trait transforms."""
    identity = build_identity(role)
    backgrounds = reference.get("backgrounds", {})
    key = str(background_save_hash).upper()
    record = backgrounds.get(key)
    if record is None:
        raise KeyError(f"unsupported background save hash: {key}")
    profile = record.get("PotentialProfile")
    if not isinstance(profile, dict):
        reason = record.get("PotentialUnsupportedReason", "unspecified")
        raise ValueError(f"background {key} has no exact potential profile: {reason}")
    if identity is None:
        raise ValueError("candidate estimate requires authoritative BuildIdentity")
    return _project_distribution(key, profile, role, trait_ids)


def recruit_candidate_estimate(
    recruit: dict, role: dict, reference: dict,
) -> dict:
    """Condition a background prior only on exact, revealed pre-hire traits.

    Extra recruit fields are deliberately ignored. In particular, level, cost,
    wage, settlement, roster state, and hidden serialized state cannot affect
    this intrinsic estimate.
    """
    background_hash = recruit.get("BackgroundSaveHash")
    prior = background_archetype_prior(background_hash, role, reference)
    fit_stats = {
        stat for stat in STATS if role.get("stats", {}).get(stat, {}).get("fit")
    }
    evidence = []
    applied_ids = []
    revealed_items = (
        recruit.get("RevealedTraitEvidence", ()) or ()
        if recruit.get("TryoutDone") is True else ()
    )
    # Use the projection engine's exact source-derived registry so evidence
    # qualification and the resulting trajectory cannot disagree. Prior-only
    # recruits do not require the generated trait cache.
    registry = _load_trait_effects() if revealed_items else {}
    for revealed in revealed_items:
        trait_id = str(revealed.get("save_hash", "")).upper()
        rec = registry.get(trait_id)
        effects = [] if not isinstance(rec, dict) else [
            effect for effect in rec.get("Effects", ())
            if effect.get("exact") and not effect.get("conditional")
            and effect.get("stat") in fit_stats
        ]
        usable = bool(effects)
        evidence.append({
            "kind": "revealed_trait",
            "save_hash": trait_id or None,
            "name": revealed.get("name"),
            "status": (
                "applied_exact_unconditional_fit_effect" if usable
                else "insufficient_for_estimate"
            ),
            "effects": [
                {key: effect.get(key) for key in ("stat", "property", "op", "value")}
                for effect in effects
            ],
        })
        if usable:
            applied_ids.append(trait_id)
    applied_ids = sorted(set(applied_ids))
    estimate = (
        _conditioned_distribution(
            background_hash, role, reference, tuple(applied_ids),
        ) if applied_ids else None
    )
    return {
        "schema": CANDIDATE_MODEL_ID,
        "model_version": 1,
        "state": "known_evidence_estimate" if estimate is not None else "prior_only",
        "background_prior": prior,
        "candidate_estimate": None if estimate is None else {
            "distribution": estimate,
            "applied_trait_save_hashes": applied_ids,
        },
        "evidence_basis": {
            "public_fields_considered": [
                "BackgroundSaveHash", "RevealedTraitEvidence",
            ],
            "items": evidence,
            "excluded": [
                "level", "settlement", "name", "title", "hire_cost",
                "daily_wage", "roster_need", "assigned_build",
                "hidden_stats", "talent_stars", "future_rolls",
            ],
        },
    }


def supported_backgrounds(reference: dict) -> list[dict]:
    """Enumerate backgrounds with an exact v1 potential profile."""
    return [
        {"save_hash": key, "background_id": rec.get("BackgroundID"), "key": rec.get("Key")}
        for key, rec in sorted(reference.get("backgrounds", {}).items())
        if isinstance(rec.get("PotentialProfile"), dict)
    ]
