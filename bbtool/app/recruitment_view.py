"""Backend-owned read model for the Target UI Recruitment workspace."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from .health import build_public_analysis_health
from .target_presentation import BOUND_ARTIFACTS, build_target_presentation

_RECRUIT_FACT_FIELDS = (
    "Name", "Title", "Background", "Level", "Settlement", "HireCost", "DailyWage", "TryoutDone",
)


def _mean_fit(value: Any) -> float | None:
    if not isinstance(value, Mapping):
        return None
    distribution = value.get("distribution")
    if not isinstance(distribution, Mapping):
        return None
    mean = distribution.get("mean_fit_pct")
    if isinstance(mean, bool) or not isinstance(mean, (int, float)):
        return None
    return float(mean)


def _potential_row(analysis: Mapping[str, Any], build_names: Mapping[str, str]) -> dict[str, Any]:
    state = analysis.get("state")
    result = analysis.get("result") if isinstance(analysis.get("result"), Mapping) else {}
    prior = _mean_fit(result.get("background_prior"))
    estimate = _mean_fit(result.get("candidate_estimate")) if state == "known_evidence_estimate" else None
    evidence = []
    basis = result.get("evidence_basis")
    items = basis.get("items") if isinstance(basis, Mapping) else None
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, Mapping):
                continue
            name = item.get("name")
            if isinstance(name, str) and name and item.get("status") == "applied_exact_unconditional_fit_effect":
                evidence.append(name)
    build_identity = analysis.get("build_identity")
    return {
        "build_identity": build_identity,
        "role": build_names.get(build_identity, build_identity),
        "state": state,
        "background_prior_pct": prior,
        "candidate_estimate_pct": estimate,
        "evidence": sorted(set(evidence)),
    }


def _top_potential(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Apply the validated intrinsic max rule without roster-need inputs."""
    known = [row for row in rows if row.get("candidate_estimate_pct") is not None]
    if known:
        eligible = known
        value_key = "candidate_estimate_pct"
    else:
        eligible = [row for row in rows if row.get("background_prior_pct") is not None]
        value_key = "background_prior_pct"
    if not eligible:
        return None
    winner = max(
        eligible,
        key=lambda row: (row[value_key], str(row.get("build_identity") or "")),
    )
    return {
        "build_identity": winner.get("build_identity"),
        "role": winner.get("role"),
        "state": winner.get("state"),
        "background_prior_pct": winner.get("background_prior_pct"),
        "candidate_estimate_pct": winner.get("candidate_estimate_pct"),
        "score_pct": winner.get(value_key),
    }


def _need_row(value: Any, build_names: Mapping[str, str]) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    build_identity = value.get("build_identity")
    return {
        "build_identity": build_identity,
        "role": build_names.get(build_identity, build_identity),
        "need_bases": list(value.get("need_bases") or []),
        "assigned_viable_count": value.get("assigned_viable_count"),
        "free_viable_backup_count": value.get("free_viable_backup_count"),
        "contested_viable_backup_count": value.get("contested_viable_backup_count"),
        "candidate_plausible": bool(value.get("candidate_plausible")),
    }


def _relevant_need(value: Any, build_names: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("state") != "available":
        return {"state": "unavailable", "relevant": None, "matches": [], "other_company_gaps": []}
    result = value.get("result")
    if not isinstance(result, Mapping):
        return {"state": "unavailable", "relevant": None, "matches": [], "other_company_gaps": []}
    matches = [
        row
        for row in (
            _need_row(item, build_names)
            for item in result.get("relevant_need_matches") or []
        )
        if row is not None
    ]
    others = [
        row
        for row in (
            _need_row(item, build_names)
            for item in result.get("other_company_gaps") or []
        )
        if row is not None
    ]
    return {
        "state": "available",
        "relevant": _need_row(result.get("relevant_need"), build_names),
        "matches": matches,
        "other_company_gaps": others,
    }


def build_recruitment_view(application) -> dict[str, Any]:
    """Return one coherent, least-privilege Recruitment publication."""
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

        public_recruits = result.public_data.get("recruits", [])
        builds = {
            row.get("build_identity"): row.get("display_name")
            for row in presentation.get("builds", [])
            if isinstance(row, Mapping) and isinstance(row.get("build_identity"), str)
        }
        need_by_index = {
            row.get("recruit_index"): row
            for row in presentation.get("relevant_roster_need", [])
            if isinstance(row, Mapping)
        }
        candidates = []
        for analytical in presentation.get("recruitment", []):
            if not isinstance(analytical, Mapping):
                continue
            index = analytical.get("recruit_index")
            if not isinstance(index, int) or index < 0 or index >= len(public_recruits):
                continue
            snapshot = public_recruits[index]
            if not isinstance(snapshot, Mapping):
                continue
            facts = {key: snapshot.get(key) for key in _RECRUIT_FACT_FIELDS}
            potentials = [
                _potential_row(item, builds)
                for item in analytical.get("analyses", [])
                if isinstance(item, Mapping)
            ]
            candidates.append({
                "recruit_index": index,
                "facts": facts,
                "top_potential": _top_potential(potentials),
                "potential": potentials,
                "relevant_need": _relevant_need(need_by_index.get(index), builds),
            })

        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        order = []
        for candidate in candidates:
            settlement = str(
                candidate["facts"].get("Settlement") or "Unknown settlement"
            )
            if settlement not in groups:
                order.append(settlement)
            groups[settlement].append(candidate)
        settlements = [
            {
                "settlement": settlement,
                "observation_summary": (
                    f"{len(groups[settlement])} candidate"
                    f"{'s' if len(groups[settlement]) != 1 else ''} in current analysis"
                ),
                "candidates": groups[settlement],
            }
            for settlement in order
        ]
        return {
            "available": True,
            "generation": publication.generation,
            "job_id": getattr(publication, "job_id", None),
            "settlements": settlements,
        }


__all__ = ["build_recruitment_view"]
