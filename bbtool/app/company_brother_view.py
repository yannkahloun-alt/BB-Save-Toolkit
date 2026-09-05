"""Backend-owned read model for the Target UI Company and Brother workspace."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .health import build_public_analysis_health
from .target_presentation import BOUND_ARTIFACTS, build_target_presentation


_EMPTY_ASSIGNMENT = {
    "status": "unassigned",
    "build_identity": None,
    "assigned_definition_hash": None,
    "current_definition_hash": None,
    "display_name": None,
}
_SNAPSHOT_FIELDS = (
    "Name", "Title", "Background", "Level",
    "HP", "HPStars", "Fatigue", "FatigueStars", "Resolve", "ResolveStars",
    "Initiative", "InitiativeStars", "MAtk", "MAtkStars", "RAtk", "RAtkStars",
    "MDef", "MDefStars", "RDef", "RDefStars",
    "Perks", "Traits", "Injuries", "Equipment", "GearFatigue",
)
_PRIVATE_FINGERPRINT_KEYS = frozenset({
    "ArtifactSignature",
    "BuildDefinitionHash",
    "assigned_definition_hash",
    "build_definition_hash",
    "current_definition_hash",
})


def _best_fit(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": summary.get("BestRole"),
        "fit_pct": summary.get("ProjectedFitPct"),
        "likely_min_pct": summary.get("ProjectedFitLikelyMinPct"),
        "likely_max_pct": summary.get("ProjectedFitLikelyMaxPct"),
        "full_min_pct": summary.get("ProjectedFitFullMinPct"),
        "full_max_pct": summary.get("ProjectedFitFullMaxPct"),
        "feasibility_pct": summary.get("FitFeasibilityPct"),
        "category": summary.get("Category"),
    }


def _potential_row(row: dict[str, Any], build_identity: str | None) -> dict[str, Any]:
    return {
        "build_identity": build_identity,
        "role": row.get("Role"),
        "fit_pct": row.get("ProjectedFitPct"),
        "likely_min_pct": row.get("ProjectedFitLikelyMinPct"),
        "likely_max_pct": row.get("ProjectedFitLikelyMaxPct"),
        "full_min_pct": row.get("ProjectedFitFullMinPct"),
        "full_max_pct": row.get("ProjectedFitFullMaxPct"),
        "feasibility_pct": row.get("FitFeasibilityPct"),
        "projected_ranges": row.get("ProjectedRanges") or {},
        "projected_components": row.get("ProjectedComponents") or {},
    }


def _snapshot_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Keep only current Brother fields rendered by #115."""
    return {key: snapshot.get(key) for key in _SNAPSHOT_FIELDS}


def _strip_private_fingerprints(value: Any) -> Any:
    """Remove validity/provenance hashes from the least-privilege UI read model."""
    if isinstance(value, dict):
        return {
            key: _strip_private_fingerprints(item)
            for key, item in value.items()
            if key not in _PRIVATE_FINGERPRINT_KEYS
        }
    if isinstance(value, list):
        return [_strip_private_fingerprints(item) for item in value]
    return value


def build_company_brother_view(application) -> dict[str, Any]:
    """Project the latest publication into one coherent Company/Brother read model.

    The application's command boundary is held across publication and durable-intent
    reads. That prevents the HTTP view from observing a mutation between its old
    publication read and its authoritative AssignedBuild read. Intrinsic analytical
    meaning still comes from the publication; freshly committed intent may differ and
    is then exposed explicitly as stale until refreshed analysis publishes.
    """
    with application._command_lock:
        return _build_company_brother_view_locked(application)


def _build_company_brother_view_locked(application) -> dict[str, Any]:
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
        # Publication hashes are report-dataset provenance. The live UI consumes
        # semantic content only and never exposes these placeholder values.
        artifact_hashes={key: "live-application" for key in BOUND_ARTIFACTS},
        result_signatures=result.incremental_cache.publication_signatures(),
        company_intrinsic_coverage=result.analysis.company_intrinsic_coverage,
        summaries=result.analysis.summaries,
        assigned_builds=result.assigned_builds,
        company_intended_coverage=result.analysis.company_intended_coverage,
    )

    campaign = result.campaign_identity
    live_assignments: dict[str, dict[str, Any]] = {}
    if getattr(campaign, "confidence", None) == "exact":
        assignment_view = application.assigned_builds.read_campaign(campaign)
        assignment_revision = assignment_view["revision"]
        live_assignments = assignment_view["assignments"]
    else:
        assignment_revision = application.store.load("assigned_builds").revision

    public_data = result.public_data
    summary_by_brother = {
        row["BrotherID"]: row for row in public_data["summaries"]
    }
    fits_by_brother: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in public_data["fits"]:
        fits_by_brother[row["BrotherID"]].append(row)
    build_id_by_name = {
        item["display_name"]: item["build_identity"]
        for item in presentation["builds"]
    }
    facts_by_brother = {
        item["brother_id"]: item for item in presentation["brothers"]
    }

    brothers = []
    for snapshot in public_data["roster"]:
        observation_id = snapshot["BrotherID"]
        summary = summary_by_brother.get(observation_id, {})
        identity = result.brother_identities.get(observation_id)
        identity_value = getattr(identity, "value", None)
        # Brother is a stable UI context, not a save-observation destination. Use
        # exact durable identity as the browser key whenever it is available, and
        # only fall back to the one-publication observation id conservatively.
        route_key = identity_value if isinstance(identity_value, str) else observation_id
        assignment = _strip_private_fingerprints(
            dict(live_assignments.get(identity_value, _EMPTY_ASSIGNMENT))
        )
        address = None
        if (
            getattr(identity, "confidence", None) == "exact"
            and getattr(identity, "campaign_value", None) is not None
            and getattr(identity, "native_token", None) is not None
        ):
            address = {
                "campaign_identity": identity.campaign_value,
                "native_entity_token": identity.native_token,
            }
        potential = [
            _potential_row(row, build_id_by_name.get(row.get("Role")))
            for row in sorted(
                fits_by_brother.get(observation_id, []),
                key=lambda item: float(item.get("ProjectedFitPct") or 0),
                reverse=True,
            )
        ]
        brothers.append({
            "brother_id": route_key,
            "brother_identity": facts_by_brother[observation_id]["brother_identity"],
            "assignment_address": address,
            "assigned_build": assignment,
            "best_fit": _best_fit(summary),
            "snapshot": _snapshot_view(snapshot),
            "mechanical_facts": facts_by_brother[observation_id]["mechanical_facts"],
            "potential": potential,
        })

    analyzed_assignments = dict(result.assigned_builds or {})
    builds = [
        {
            "build_identity": item["build_identity"],
            "display_name": item["display_name"],
        }
        for item in presentation["builds"]
    ]
    company = _strip_private_fingerprints(presentation["company"])
    company["intent_fresh"] = analyzed_assignments == live_assignments
    return {
        "available": True,
        "generation": publication.generation,
        "assignment_revision": assignment_revision,
        "builds": builds,
        "brothers": brothers,
        "company": company,
    }


__all__ = ["build_company_brother_view"]
