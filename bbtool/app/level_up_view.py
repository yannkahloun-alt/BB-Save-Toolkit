"""Backend-owned read model for the Target UI Level Up workspace."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .health import build_public_analysis_health
from .target_presentation import BOUND_ARTIFACTS, build_target_presentation

_STAT_ORDER = ("HP", "Fatigue", "Resolve", "Initiative", "MAtk", "RAtk", "MDef", "RDef")
_CONSEQUENCE_FIELDS = (
    "BuildIdentity", "Role", "FitBeforePct", "FitAfterPct", "FitDeltaPct",
    "FitMinAfterPct", "FitMaxAfterPct", "FitLikelyMinAfterPct",
    "FitLikelyMaxAfterPct", "FitFeasibilityBeforePct", "FitFeasibilityAfterPct",
)
_CANDIDATE_FIELDS = (
    "Stats", "Rolls", "RollQuality", "RoleBefore", "RoleAfter",
    "AnchorFitBeforePct", "AnchorFitAfterPct", "FitMinAfterPct",
    "FitMaxAfterPct", "FitLikelyMinAfterPct", "FitLikelyMaxAfterPct",
    "FitFeasibilityBeforePct", "FitFeasibilityAfterPct", "FitDeltaPct",
)
_CONDITIONAL_TEXT_FIELDS = (
    "Trigger", "Assumption", "Scenario", "Interpretation", "Reason",
)


def _consequence(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return {key: value.get(key) for key in _CONSEQUENCE_FIELDS}


def _candidate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    projected = {key: value.get(key) for key in _CANDIDATE_FIELDS}
    consequences = value.get("Consequences")
    projected["Consequences"] = {
        "AssignedBuild": _consequence(consequences.get("AssignedBuild")),
        "BestFit": _consequence(consequences.get("BestFit")),
    } if isinstance(consequences, Mapping) else {
        "AssignedBuild": None,
        "BestFit": None,
    }
    return projected


def _conditional_branch(value: Any) -> dict[str, Any] | None:
    """Project only the product-facing conditional branch contract.

    Runner-up gamble diagnostics are intentionally not promoted into this branch.
    A Gamble card exists only when the backend publishes ConditionalBranch.
    """
    projected = _candidate(value)
    if projected is None:
        return None
    for key in _CONDITIONAL_TEXT_FIELDS:
        if isinstance(value.get(key), str):
            projected[key] = value[key]
    return projected


def _assignment(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"status": "unavailable", "build_identity": None, "display_name": None}
    return {
        "status": value.get("status"),
        "build_identity": value.get("build_identity"),
        "display_name": value.get("display_name"),
    }


def _rolls(advice: Mapping[str, Any], snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    all_rolls = advice.get("AllRolls")
    if not isinstance(all_rolls, Mapping):
        return []
    primary_stats = set((advice.get("Primary") or {}).get("Stats") or [])
    runner_stats = set((advice.get("RunnerUp") or {}).get("Stats") or [])
    order = {stat: index for index, stat in enumerate(_STAT_ORDER)}
    rows = []
    for stat, meta in all_rolls.items():
        if not isinstance(meta, Mapping):
            continue
        rows.append({
            "stat": stat,
            "current_value": snapshot.get(stat),
            "stars": snapshot.get(f"{stat}Stars"),
            "offered_roll": meta.get("Roll"),
            "min_roll": meta.get("Min"),
            "max_roll": meta.get("Max"),
            "average_roll": meta.get("Average"),
            "band": meta.get("Label"),
            "quality": meta.get("Quality"),
            "primary": stat in primary_stats,
            "runner_up": stat in runner_stats,
        })
    rows.sort(key=lambda row: (order.get(row["stat"], len(order)), row["stat"]))
    return rows


def _explain(advice: Mapping[str, Any]) -> dict[str, Any]:
    reasons = advice.get("PickReasons")
    skipped = advice.get("SkippedImportant")
    excluded = advice.get("AdvisorExcludedStats")
    safe_skipped = []
    if isinstance(skipped, list):
        for row in skipped:
            if not isinstance(row, Mapping):
                continue
            roll = row.get("Roll") if isinstance(row.get("Roll"), Mapping) else {}
            safe_skipped.append({
                "stat": row.get("Stat"),
                "weight": row.get("Weight"),
                "core": row.get("Core"),
                "roll": {
                    key: roll.get(key)
                    for key in ("Roll", "Min", "Max", "Average", "Label", "Quality")
                },
                "reason": row.get("Reason"),
            })
    return {
        "pick_reasons": dict(reasons) if isinstance(reasons, Mapping) else {},
        "skipped_important": safe_skipped,
        "eligible_stats": list(advice.get("AdvisorEligibleStats") or []),
        "excluded_stats": dict(excluded) if isinstance(excluded, Mapping) else {},
        "free_pick_mode": bool(advice.get("FreePickMode")),
        "free_pick_stats": list(advice.get("FreePickStats") or []),
        "free_pick_candidates": list(advice.get("FreePickCandidates") or []),
        "method": advice.get("Method") if isinstance(advice.get("Method"), str) else None,
    }


def build_level_up_view(application) -> dict[str, Any]:
    """Return one coherent, least-privilege Level Up decision publication."""
    with application._command_lock:
        publication = application.coordinator.last_success
        if publication is None:
            return {"available": False}

        result = publication.result
        analysis_health = build_public_analysis_health(
            (getattr(result, "diagnostics", {}) or {}).get("run_health", {})
        )
        presentation = build_target_presentation(
            bros=result.roster,
            recruits=result.recruits,
            roles=result.roles,
            analysis_health=analysis_health,
            campaign_identity=result.campaign_identity,
            brother_identities=result.brother_identities,
            source_fingerprint=result.source_fingerprint,
            configuration_fingerprints=result.configuration_fingerprints,
            recruitment_analysis=result.recruitment_analysis,
            artifact_hashes={key: "live-application" for key in BOUND_ARTIFACTS},
            result_signatures=result.incremental_cache.publication_signatures(),
            company_intrinsic_coverage=result.analysis.company_intrinsic_coverage,
            summaries=result.analysis.summaries,
            assigned_builds=result.assigned_builds,
            company_intended_coverage=result.analysis.company_intended_coverage,
        )

        snapshots = {row["BrotherID"]: row for row in result.public_data["roster"]}
        presentation_brothers = {
            row["brother_id"]: row for row in presentation["brothers"]
        }
        decisions = []
        for row in presentation["advisors"]:
            advice = row.get("advice")
            observation_id = row.get("brother_id")
            if not isinstance(advice, Mapping) or observation_id not in snapshots:
                continue
            snapshot = snapshots[observation_id]
            identity = result.brother_identities.get(observation_id)
            identity_value = getattr(identity, "value", None)
            route_key = identity_value if isinstance(identity_value, str) else observation_id
            brother_contract = presentation_brothers.get(observation_id, {})
            assignment = _assignment(brother_contract.get("assigned_build"))
            best_fit = advice.get("BestFit") if isinstance(advice.get("BestFit"), Mapping) else {}
            anchor = advice.get("Anchor") if isinstance(advice.get("Anchor"), Mapping) else {}
            decisions.append({
                "brother_id": route_key,
                "name": snapshot.get("Name"),
                "title": snapshot.get("Title"),
                "background": snapshot.get("Background"),
                "level": snapshot.get("Level"),
                "assigned_build": assignment,
                "best_fit": {
                    "build_identity": best_fit.get("BuildIdentity"),
                    "role": best_fit.get("Role"),
                    "fit_pct": best_fit.get("ProjectedFitPct"),
                },
                "anchor": {
                    "source": anchor.get("Source"),
                    "build_identity": anchor.get("BuildIdentity"),
                    "role": anchor.get("Role"),
                    "assignment_status": anchor.get("AssignmentStatus"),
                },
                "rolls": _rolls(advice, snapshot),
                "primary": _candidate(advice.get("Primary")),
                "runner_up": _candidate(advice.get("RunnerUp")),
                "gamble": _conditional_branch(advice.get("ConditionalBranch")),
                "explain": _explain(advice),
            })

        return {
            "available": True,
            "generation": publication.generation,
            "decisions": decisions,
        }


__all__ = ["build_level_up_view"]
