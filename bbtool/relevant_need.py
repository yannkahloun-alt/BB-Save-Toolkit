"""Recruitment Relevant Roster Need, downstream of intrinsic evidence."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .incremental.dependencies import (
    ArtifactKind, ENGINE_VERSIONS, InputKind, artifact_signature, stable_hash,
)

_BASIS_ORDER = {
    "assigned_but_no_viable_holder": 0,
    "single_point_of_failure": 1,
    "contested_backup_only": 2,
}


def _plausible(analysis: Mapping[str, Any], viable_fit: float) -> bool:
    result = analysis.get("result")
    if analysis.get("state") not in {"prior_only", "known_evidence_estimate"}:
        return False
    distribution = (result or {}).get("candidate_estimate") or (result or {}).get("background_prior")
    distribution = (distribution or {}).get("distribution")
    return isinstance(distribution, Mapping) and float(distribution.get("mean_fit_pct", -1)) >= viable_fit * 100


def build_relevant_roster_need(
    recruitment_analysis: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    company_intended_coverage: Iterable[Mapping[str, Any]],
    *, viable_fit: float,
) -> dict[str, Any]:
    """Intersect candidate-plausible roles with authoritative Company needs.

    Candidate plausibility is established first from the existing intrinsic
    prior/known-evidence distribution. Company intent can only select among
    those roles; it cannot alter the candidate evidence or potential values.
    """
    analyses = recruitment_analysis.get("analyses", ()) if isinstance(recruitment_analysis, Mapping) else recruitment_analysis
    analyses = list(analyses)
    company_intended_coverage = list(company_intended_coverage)
    plausible = tuple(sorted(
        item["build_identity"] for item in analyses
        if isinstance(item, Mapping) and isinstance(item.get("build_identity"), str)
        and _plausible(item, viable_fit)
    ))
    plausible_set = set(plausible)
    gaps = []
    for coverage in company_intended_coverage:
        identity = coverage.get("BuildIdentity")
        bases = [basis for basis in coverage.get("NeedBases", ()) if basis in _BASIS_ORDER]
        if not isinstance(identity, str) or not bases:
            continue
        gaps.append({
            "build_identity": identity,
            "need_bases": sorted(set(bases), key=lambda basis: _BASIS_ORDER[basis]),
            "assigned_viable_count": coverage.get("AssignedViableCount"),
            "free_viable_backup_count": coverage.get("FreeViableBackupCount"),
            "contested_viable_backup_count": coverage.get("ContestedViableBackupCount"),
        })
    gaps.sort(key=lambda item: (min(_BASIS_ORDER[b] for b in item["need_bases"]), item["build_identity"]))
    relevant = [gap for gap in gaps if gap["build_identity"] in plausible_set]
    other = [gap for gap in gaps if gap["build_identity"] not in plausible_set]
    for item in (*relevant, *other):
        item["candidate_plausible"] = item["build_identity"] in plausible_set
    inputs = {
        InputKind.CANDIDATE_EVIDENCE: [
            {"build_identity": item.get("build_identity"), "state": item.get("state"),
             "result": item.get("result")}
            for item in analyses if isinstance(item, Mapping)
        ],
        InputKind.COMPANY_NEED: list(company_intended_coverage),
        InputKind.ENGINE_SEMANTICS: {"relevant_roster_need": ENGINE_VERSIONS.get(ArtifactKind.RELEVANT_ROSTER_NEED, 1)},
    }
    candidate_upstream = stable_hash(inputs[InputKind.CANDIDATE_EVIDENCE])
    company_upstream = stable_hash([
        {"BuildIdentity": item.get("BuildIdentity"),
         "ArtifactSignature": item.get("ArtifactSignature"),
         "NeedBases": item.get("NeedBases", ())}
        for item in company_intended_coverage
    ])
    return {
        "schema": "bbtool.relevant_roster_need.v1",
        "candidate_plausible_roles": list(plausible),
        "relevant_need": relevant[0] if relevant else None,
        "relevant_need_matches": relevant,
        "no_match": not relevant,
        "other_company_gaps": other,
        "artifact_signature": artifact_signature(ArtifactKind.RELEVANT_ROSTER_NEED, inputs, {
            ArtifactKind.RECRUIT_INTRINSIC_POTENTIAL: candidate_upstream,
            ArtifactKind.COMPANY_INTRINSIC_COVERAGE: company_upstream,
            ArtifactKind.COMPANY_INTENDED_COVERAGE: company_upstream,
        }),
    }
