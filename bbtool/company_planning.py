"""Presentation-independent intrinsic Company planning evidence.

This module deliberately has no player-intent input.  AssignedBuild availability,
intended coverage, fragility, and need facts belong to the #107-dependent slice.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .build_identity import build_definition_hash, build_identity
from .classification import fit_label
from .incremental.dependencies import (
    ArtifactKind,
    ENGINE_VERSIONS,
    InputKind,
    artifact_signature,
    stable_hash,
)
from .incremental.fingerprint import brother_projection_state, role_fingerprint


def _brother_identity(identity: object) -> str | None:
    value = identity if isinstance(identity, str) else getattr(identity, "value", None)
    return value if isinstance(value, str) and value else None


def _brother_sort_key(item: tuple[object, Mapping[str, Any], str | None]) -> tuple:
    bro, row, stable_identity = item
    brother_id = str(getattr(bro, "BrotherID", ""))
    return (
        -float(row["ProjectedFitPct"]),
        stable_identity is None,
        stable_identity or "",
        brother_id,
    )


def _role_projection_signature(bro: object, role: Mapping[str, Any]) -> str:
    state = brother_projection_state(bro)
    return artifact_signature(
        ArtifactKind.ROLE_PROJECTION,
        {
            InputKind.BROTHER_STATE: state,
            InputKind.BUILD_DEFINITION: role_fingerprint(dict(role)),
            InputKind.CURRENT_ROLLS: state["current_rolls"],
            InputKind.ENGINE_SEMANTICS: {
                "role_projection": ENGINE_VERSIONS[ArtifactKind.ROLE_PROJECTION]
            },
        },
    )


def _coverage_signature(
    role: Mapping[str, Any],
    evidence: list[tuple[object, Mapping[str, Any], str | None]],
    display_thresholds: Mapping[str, Any],
) -> str:
    roster_members = sorted(
        stable_identity or str(getattr(bro, "BrotherID", ""))
        for bro, _, stable_identity in evidence
    )
    role_signatures = sorted(
        _role_projection_signature(bro, role) for bro, _, _ in evidence
    )
    return artifact_signature(
        ArtifactKind.COMPANY_INTRINSIC_COVERAGE,
        {
            InputKind.ROSTER_STATE: roster_members,
            InputKind.CLASSIFICATION_CONFIG: {
                key: display_thresholds[key]
                for key in ("viable_fit", "good_fit", "premium_fit")
            },
            InputKind.ENGINE_SEMANTICS: {
                "company_intrinsic_coverage": ENGINE_VERSIONS[
                    ArtifactKind.COMPANY_INTRINSIC_COVERAGE
                ]
            },
        },
        {ArtifactKind.ROLE_PROJECTION: stable_hash(role_signatures)},
    )


def build_intrinsic_company_coverage(
    brothers: Iterable[object],
    roles: Iterable[dict],
    fits: Iterable[Mapping[str, Any]],
    classification: Mapping[str, Any],
    brother_identities: Mapping[str, object] | None = None,
) -> list[dict[str, Any]]:
    """Return intrinsic depth per authoritative BuildIdentity.

    Id-less legacy roles remain valid for ordinary analysis but cannot become
    durable Company planning records.  They are therefore omitted rather than
    receiving an identity derived from their display name.
    """
    brother_list = list(brothers)
    role_list = [(build_identity(role), role) for role in roles]
    authoritative_roles = [(identity, role) for identity, role in role_list if identity]
    if not authoritative_roles:
        return []
    role_by_name = {role["name"]: (identity, role) for identity, role in authoritative_roles}
    brother_by_id = {str(bro.BrotherID): bro for bro in brother_list}
    identities = brother_identities or {}
    evidence_by_build: dict[
        str, list[tuple[object, Mapping[str, Any], str | None]]
    ] = {
        identity: [] for identity, _ in authoritative_roles
    }
    for row in fits:
        matched = role_by_name.get(row.get("Role"))
        brother_id = str(row.get("BrotherID"))
        bro = brother_by_id.get(brother_id)
        if matched is not None and bro is not None:
            evidence_by_build[matched[0]].append(
                (bro, row, _brother_identity(identities.get(brother_id)))
            )

    display = classification["display"]
    output = []
    for identity, role in sorted(authoritative_roles, key=lambda item: item[0]):
        evidence = sorted(evidence_by_build[identity], key=_brother_sort_key)
        scores = [float(row["ProjectedFit"]) for _, row, _ in evidence]
        viable = [item for item in evidence if float(item[1]["ProjectedFit"]) >= display["viable_fit"]]
        output.append({
            "BuildIdentity": identity,
            "BuildDefinitionHash": build_definition_hash(role),
            "ArtifactSignature": _coverage_signature(role, evidence, display),
            "ViableCount": len(viable),
            "GoodCount": sum(score >= display["good_fit"] for score in scores),
            "PremiumCount": sum(score >= display["premium_fit"] for score in scores),
            "ViableBrothers": [
                {
                    "BrotherIdentity": stable_identity,
                    "BrotherID": str(bro.BrotherID),
                    "FitPct": float(row["ProjectedFitPct"]),
                    "FitLabel": fit_label(float(row["ProjectedFit"]), classification),
                }
                for bro, row, stable_identity in viable
            ],
            "TopFitPct": float(evidence[0][1]["ProjectedFitPct"]) if evidence else None,
            "SecondFitPct": float(evidence[1][1]["ProjectedFitPct"]) if len(evidence) > 1 else None,
        })
    return output
