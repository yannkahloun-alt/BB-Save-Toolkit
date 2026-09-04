"""Presentation-independent intrinsic and intent-aware Company evidence."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any

from .build_identity import build_definition_hash, build_identity
from .classification import fit_label, role_sort_key
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


def _normalized_current_assignments(
    assignments: Mapping[str, Mapping[str, Any]],
    definition_hashes: Mapping[str, str],
) -> dict[str, str]:
    """Return only authoritative assignments valid for the effective catalog.

    ``AssignedBuildStore.read`` payloads are deliberately accepted directly.
    Definition-changed, deprecated, missing, and malformed records are not
    silently treated as current intent.
    """
    current: dict[str, str] = {}
    for brother_identity, payload in assignments.items():
        resolved = payload.get("assignment", payload)
        build = resolved.get("build_identity")
        if (
            resolved.get("status") == "current"
            and isinstance(brother_identity, str)
            and re.fullmatch(r"campaign:(?:0|[1-9][0-9]*)/entity:[1-9][0-9]*", brother_identity)
            and isinstance(build, str)
            and resolved.get("assigned_definition_hash") == definition_hashes.get(build)
            and resolved.get("current_definition_hash") == definition_hashes.get(build)
        ):
            current[brother_identity] = build
    return current


def build_intent_company_coverage(
    brothers: Iterable[object],
    roles: Iterable[dict],
    fits: Iterable[Mapping[str, Any]],
    classification: Mapping[str, Any],
    assignments: Mapping[str, Mapping[str, Any]],
    brother_identities: Mapping[str, object],
) -> list[dict[str, Any]]:
    """Return intended coverage for valid, resolved AssignedBuild state.

    The returned records are a separate validity domain from intrinsic Company
    coverage.  Callers must provide resolved AssignedBuild payloads keyed by
    exact BrotherIdentity; unresolved intent is conservatively unavailable.
    """
    brother_list = list(brothers)
    authoritative_roles = sorted(
        ((build_identity(role), role) for role in roles if build_identity(role)),
        key=lambda item: item[0],
    )
    if not authoritative_roles:
        return []
    role_by_name = {role["name"]: (identity, role) for identity, role in authoritative_roles}
    definition_hashes = {
        identity: build_definition_hash(role) for identity, role in authoritative_roles
    }
    current_assignments = _normalized_current_assignments(assignments, definition_hashes)
    brother_by_id = {str(bro.BrotherID): bro for bro in brother_list}
    identities = {
        brother_id: _brother_identity(identity)
        for brother_id, identity in brother_identities.items()
    }
    roster_identities = {identity for identity in identities.values() if identity is not None}
    current_assignments = {
        identity: build for identity, build in current_assignments.items()
        if identity in roster_identities
    }
    evidence_by_brother: dict[str, dict[str, tuple[object, Mapping[str, Any]]]] = {}
    role_signatures: dict[tuple[str, str], str] = {}
    for row in fits:
        brother_id = str(row.get("BrotherID"))
        bro = brother_by_id.get(brother_id)
        matched = role_by_name.get(row.get("Role"))
        if bro is None or matched is None:
            continue
        evidence_by_brother.setdefault(brother_id, {})[matched[0]] = (bro, row)
        role_signatures[(brother_id, matched[0])] = _role_projection_signature(
            bro, matched[1]
        )

    display = classification["display"]
    normalized_roster = sorted(
        (identities.get(str(bro.BrotherID)) or str(bro.BrotherID))
        for bro in brother_list
    )
    output: list[dict[str, Any]] = []
    for identity, _role in authoritative_roles:
        available: list[dict[str, Any]] = []
        assigned: list[dict[str, Any]] = []
        for brother_id, by_role in evidence_by_brother.items():
            item = by_role.get(identity)
            stable_identity = identities.get(brother_id)
            if item is None or stable_identity is None:
                continue
            bro, row = item
            fit = float(row["ProjectedFit"])
            assigned_build = current_assignments.get(stable_identity)
            availability = (
                "assigned_here" if assigned_build == identity
                else "unassigned" if assigned_build is None
                else "assigned_elsewhere"
            )
            if fit >= display["viable_fit"]:
                available.append({
                    "BrotherIdentity": stable_identity,
                    "BrotherID": brother_id,
                    "FitPct": float(row["ProjectedFitPct"]),
                    "FitLabel": fit_label(fit, classification),
                    "Availability": availability,
                })
            if availability == "assigned_here":
                # Match BestRole's complete ranking tuple. BuildIdentity is the
                # deterministic final tie-break because display/order is not authority.
                best_identity, (_, best_row) = min(
                    by_role.items(), key=lambda candidate: (
                        tuple(-value for value in role_sort_key(dict(candidate[1][1]))),
                        candidate[0],
                    )
                )
                assigned_pct = float(row["ProjectedFitPct"])
                best_pct = float(best_row["ProjectedFitPct"])
                assigned.append({
                    "BrotherIdentity": stable_identity,
                    "BrotherID": brother_id,
                    "AssignedFitPct": assigned_pct,
                    "AssignedFitLabel": fit_label(fit, classification),
                    "BestBuildIdentity": best_identity,
                    "BestFitPct": best_pct,
                    "BestVsAssignedDeltaPctPoints": best_pct - assigned_pct,
                    "BestBuildDiffers": best_identity != identity,
                })
        available.sort(key=lambda row: (-row["FitPct"], row["BrotherIdentity"], row["BrotherID"]))
        assigned.sort(key=lambda row: (row["BrotherIdentity"], row["BrotherID"]))
        assigned_viable = sum(
            row["AssignedFitPct"] / 100 >= display["viable_fit"] for row in assigned
        )
        free = sum(row["Availability"] == "unassigned" for row in available)
        contested = sum(row["Availability"] == "assigned_elsewhere" for row in available)
        no_intent = not assigned
        no_viable_holder = bool(assigned) and assigned_viable == 0
        single_point = assigned_viable == 1 and free == 0 and contested == 0
        contested_only = bool(assigned) and assigned_viable <= 1 and free == 0 and contested > 0
        facts = {
            "NoIntent": no_intent,
            "AssignedButNoViableHolder": no_viable_holder,
            "SinglePointOfFailure": single_point,
            "ContestedBackupOnly": contested_only,
            "FreeBackupAvailable": free > 0,
            "MultiHolderDepth": assigned_viable >= 2,
        }
        need_bases = [
            basis for basis, present in (
                ("assigned_but_no_viable_holder", no_viable_holder),
                ("single_point_of_failure", single_point),
                ("contested_backup_only", contested_only),
            ) if present
        ]
        assigned_identities = {row["BrotherIdentity"] for row in assigned}
        target_projection_signatures = [
            signature for (brother_id, build), signature in role_signatures.items()
            if build == identity
            or identities.get(brother_id) in assigned_identities
        ]
        availability_intent = sorted(
            (row["BrotherIdentity"], row["Availability"])
            for row in available
        )
        # Below-viable holders are absent from availability but remain semantic.
        availability_intent.extend(sorted(
            (row["BrotherIdentity"], "assigned_here")
            for row in assigned
            if row["BrotherIdentity"] not in {
                viable["BrotherIdentity"] for viable in available
            }
        ))
        output.append({
            "BuildIdentity": identity,
            "BuildDefinitionHash": definition_hashes[identity],
            "ArtifactSignature": artifact_signature(
                ArtifactKind.COMPANY_INTENDED_COVERAGE,
                {
                    InputKind.ROSTER_STATE: normalized_roster,
                    InputKind.ASSIGNED_BUILD: availability_intent,
                    InputKind.BUILD_DEFINITION: {
                        "covered_build": identity,
                        "definition_hash": definition_hashes[identity],
                    },
                    InputKind.CLASSIFICATION_CONFIG: {
                        key: display[key] for key in ("viable_fit", "good_fit", "premium_fit")
                    },
                    InputKind.ENGINE_SEMANTICS: {
                        "company_intended_coverage": ENGINE_VERSIONS[
                            ArtifactKind.COMPANY_INTENDED_COVERAGE
                        ]
                    },
                },
                {ArtifactKind.ROLE_PROJECTION: stable_hash(
                    sorted(target_projection_signatures)
                )},
            ),
            "AssignedCount": len(assigned),
            "AssignedBrothers": assigned,
            "AssignedViableCount": assigned_viable,
            "AssignedBelowViableCount": len(assigned) - assigned_viable,
            "FreeViableBackupCount": free,
            "ContestedViableBackupCount": contested,
            "ViableAvailability": available,
            "FragilityFacts": facts,
            "NeedBases": need_bases,
        })
    return output
