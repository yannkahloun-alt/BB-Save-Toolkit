"""Declared semantic dependencies for reusable analysis artifacts.

This module is deliberately a small registry, not a reactive execution system.
Callers provide normalized semantic evidence; missing evidence never proves that
an artifact is current.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    )


def stable_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class InputKind(StrEnum):
    BROTHER_STATE = "brother_state"
    BUILD_DEFINITION = "build_definition"
    ROLE_RESULTS = "role_results"
    CLASSIFICATION_CONFIG = "classification_config"
    ENGINE_SEMANTICS = "engine_semantics"
    CURRENT_ROLLS = "current_rolls"
    ASSIGNED_BUILD = "assigned_build"
    ROSTER_STATE = "roster_state"
    COMPANY_NEED = "company_need"
    CANDIDATE_EVIDENCE = "candidate_evidence"


class ArtifactKind(StrEnum):
    ROLE_PROJECTION = "role_projection"
    STRATEGIC_CLASSIFICATION = "strategic_classification"
    INTRINSIC_ALTERNATIVES = "intrinsic_alternatives"
    LEVEL_ADVISOR = "level_advisor"
    COMPANY_INTRINSIC_COVERAGE = "company_intrinsic_coverage"
    COMPANY_INTENDED_COVERAGE = "company_intended_coverage"
    RECRUIT_INTRINSIC_POTENTIAL = "recruit_intrinsic_potential"
    RELEVANT_ROSTER_NEED = "relevant_roster_need"
    VALIDATION_ORACLE = "validation_oracle"


@dataclass(frozen=True)
class ArtifactDependency:
    inputs: frozenset[InputKind]
    upstream: frozenset[ArtifactKind] = frozenset()


# One authoritative declaration of result-affecting dependency categories.
# Planned artifacts are registered here as extension points; their domain tickets
# still own their formulas and normalized evidence schemas.
ARTIFACT_DEPENDENCIES: Mapping[ArtifactKind, ArtifactDependency] = {
    ArtifactKind.ROLE_PROJECTION: ArtifactDependency(frozenset({
        InputKind.BROTHER_STATE, InputKind.BUILD_DEFINITION,
        InputKind.CURRENT_ROLLS, InputKind.ENGINE_SEMANTICS,
    })),
    ArtifactKind.STRATEGIC_CLASSIFICATION: ArtifactDependency(
        frozenset({InputKind.CLASSIFICATION_CONFIG, InputKind.ENGINE_SEMANTICS}),
        frozenset({ArtifactKind.ROLE_PROJECTION}),
    ),
    ArtifactKind.INTRINSIC_ALTERNATIVES: ArtifactDependency(
        frozenset({InputKind.ENGINE_SEMANTICS}),
        frozenset({ArtifactKind.ROLE_PROJECTION}),
    ),
    ArtifactKind.LEVEL_ADVISOR: ArtifactDependency(frozenset({
        InputKind.BROTHER_STATE, InputKind.BUILD_DEFINITION,
        InputKind.CURRENT_ROLLS, InputKind.ASSIGNED_BUILD,
        InputKind.ENGINE_SEMANTICS,
    })),
    ArtifactKind.COMPANY_INTRINSIC_COVERAGE: ArtifactDependency(
        frozenset({
            InputKind.ROSTER_STATE,
            InputKind.CLASSIFICATION_CONFIG,
            InputKind.ENGINE_SEMANTICS,
        }),
        frozenset({ArtifactKind.ROLE_PROJECTION}),
    ),
    ArtifactKind.COMPANY_INTENDED_COVERAGE: ArtifactDependency(frozenset({
        InputKind.ROSTER_STATE, InputKind.ASSIGNED_BUILD,
        InputKind.BUILD_DEFINITION, InputKind.CLASSIFICATION_CONFIG,
        InputKind.ENGINE_SEMANTICS,
    }), frozenset({ArtifactKind.ROLE_PROJECTION})),
    ArtifactKind.RECRUIT_INTRINSIC_POTENTIAL: ArtifactDependency(frozenset({
        InputKind.CANDIDATE_EVIDENCE, InputKind.BUILD_DEFINITION,
        InputKind.ENGINE_SEMANTICS,
    })),
    ArtifactKind.RELEVANT_ROSTER_NEED: ArtifactDependency(
        frozenset({InputKind.COMPANY_NEED, InputKind.ENGINE_SEMANTICS}),
        frozenset({
            ArtifactKind.RECRUIT_INTRINSIC_POTENTIAL,
            ArtifactKind.COMPANY_INTRINSIC_COVERAGE,
            ArtifactKind.COMPANY_INTENDED_COVERAGE,
        }),
    ),
    ArtifactKind.VALIDATION_ORACLE: ArtifactDependency(frozenset({
        InputKind.BROTHER_STATE, InputKind.BUILD_DEFINITION,
        InputKind.CURRENT_ROLLS, InputKind.ENGINE_SEMANTICS,
    })),
}


# Semantic versions live beside dependency declarations. A formatting-only
# change must not bump these; a result-affecting engine change must.
ENGINE_VERSIONS: Mapping[ArtifactKind, int] = {
    ArtifactKind.ROLE_PROJECTION: 7,
    ArtifactKind.STRATEGIC_CLASSIFICATION: 7,
    ArtifactKind.LEVEL_ADVISOR: 6,
    ArtifactKind.VALIDATION_ORACLE: 2,
    ArtifactKind.COMPANY_INTRINSIC_COVERAGE: 1,
    ArtifactKind.COMPANY_INTENDED_COVERAGE: 1,
}


class MissingDependencyEvidence(ValueError):
    """Raised when validity cannot be proven from complete semantic evidence."""


def artifact_signature(
    artifact: ArtifactKind,
    inputs: Mapping[InputKind, Any],
    upstream_signatures: Mapping[ArtifactKind, str] | None = None,
) -> str:
    """Hash the exact declared evidence for *artifact*.

    Extra input categories are ignored, which is what permits proof of reuse
    across unrelated durable-state revisions. Missing declared evidence fails
    conservatively.
    """
    dependency = ARTIFACT_DEPENDENCIES[artifact]
    upstream_signatures = upstream_signatures or {}
    missing_inputs = dependency.inputs.difference(inputs)
    missing_upstream = dependency.upstream.difference(upstream_signatures)
    if missing_inputs or missing_upstream:
        missing = sorted(x.value for x in (*missing_inputs, *missing_upstream))
        raise MissingDependencyEvidence(
            f"incomplete dependency evidence for {artifact.value}: {', '.join(missing)}"
        )
    return stable_hash({
        "artifact": artifact.value,
        "inputs": {key.value: inputs[key] for key in sorted(
            dependency.inputs, key=lambda item: item.value
        )},
        "upstream": {key.value: upstream_signatures[key] for key in sorted(
            dependency.upstream, key=lambda item: item.value
        )},
    })


def changed_inputs(
    previous: Mapping[InputKind, Any], current: Mapping[InputKind, Any]
) -> frozenset[InputKind]:
    """Return categories whose normalized value changed or lacks evidence."""
    return frozenset(
        kind for kind in InputKind
        if kind not in previous or kind not in current
        or stable_hash(previous[kind]) != stable_hash(current[kind])
    )


def recomputation_closure(
    changed: Iterable[InputKind],
    artifacts: Iterable[ArtifactKind] | None = None,
) -> frozenset[ArtifactKind]:
    """Return the minimal registered direct + transitive invalidation closure."""
    requested = frozenset(artifacts) if artifacts is not None else None
    # Traverse the complete graph before filtering. Otherwise a requested
    # downstream artifact could look valid merely because its invalid upstream
    # was omitted from the caller's requested subset.
    candidates = frozenset(ARTIFACT_DEPENDENCIES)
    changed_set = frozenset(changed)
    invalid = {
        artifact for artifact in candidates
        if ARTIFACT_DEPENDENCIES[artifact].inputs.intersection(changed_set)
    }
    while True:
        transitive = {
            artifact for artifact in candidates.difference(invalid)
            if ARTIFACT_DEPENDENCIES[artifact].upstream.intersection(invalid)
        }
        if not transitive:
            closure = frozenset(invalid)
            return closure if requested is None else closure.intersection(requested)
        invalid.update(transitive)


def artifact_is_valid(previous_signature: str | None, current_signature: str) -> bool:
    return bool(previous_signature) and previous_signature == current_signature


# Compatibility payload builders for the existing manifest. They keep the
# serialized hashes stable while locating their dependency knowledge here.
def validation_oracle_payload(
    brother_state: Any, build_signature: str, role_engine: int, oracle_engine: int
) -> dict[str, Any]:
    return {
        "brother_state": brother_state,
        "role": build_signature,
        "role_projection_engine": role_engine,
        "validation_oracle_engine": oracle_engine,
    }


def strategic_classification_payload(
    brother_state: Any, build_signatures: Any,
    classification: Any, engine_version: int,
) -> dict[str, Any]:
    return {
        "brother_state": brother_state,
        "roles": build_signatures,
        "classification": classification,
        "engine_version": engine_version,
    }


def current_advisor_payload(
    brother_state: Any, build_signatures: Any, assigned_build: Any,
    engine_version: int,
) -> dict[str, Any]:
    """Normalized intent-aware Advisor evidence for the manifest bridge."""
    return {
        "brother_state": brother_state,
        "roles": build_signatures,
        "assigned_build": assigned_build,
        "engine_version": engine_version,
    }
