"""Backend-owned read model for the Target UI Company and Brother workspace."""
from __future__ import annotations

from typing import Any

from .health import build_public_analysis_health
from .target_presentation import BOUND_ARTIFACTS, build_target_presentation


def build_company_brother_view(publication) -> dict[str, Any]:
    """Project one published analysis into Company/Brother UI data.

    Analytical meaning is reused from the existing Target presentation builder;
    the browser receives displayable public data and never reconstructs
    AssignedBuild, Company planning, Mechanical Facts, or Brother identity.
    """
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
        # The Company/Brother live view consumes semantic content only. Artifact
        # generation hashes belong to report-dataset publication and are discarded
        # below rather than being exposed as runtime UI state.
        artifact_hashes={key: "live-application" for key in BOUND_ARTIFACTS},
        result_signatures=result.incremental_cache.publication_signatures(),
        company_intrinsic_coverage=result.analysis.company_intrinsic_coverage,
        summaries=result.analysis.summaries,
        assigned_builds=result.assigned_builds,
        company_intended_coverage=result.analysis.company_intended_coverage,
    )
    public_data = result.public_data
    return {
        "available": True,
        "generation": publication.generation,
        "roster": public_data["roster"],
        "summaries": public_data["summaries"],
        "fits": public_data["fits"],
        "roles": public_data["roles"],
        "presentation": {
            "campaign_identity": presentation["campaign_identity"],
            "brothers": presentation["brothers"],
            "builds": presentation["builds"],
            "company": presentation["company"],
        },
    }


__all__ = ["build_company_brother_view"]
