import pytest

from bbtool.incremental.dependencies import (
    ArtifactKind, InputKind, MissingDependencyEvidence, artifact_is_valid,
    artifact_signature, changed_inputs, recomputation_closure,
)
from bbtool.incremental.fingerprint import (
    ADVISOR_ENGINE_VERSION, advisor_fingerprint, brother_projection_state,
    role_fingerprint, stable_hash,
)


def _advisor_inputs(*, assignment="reach", definition="definition-a", revision=1):
    return {
        InputKind.BROTHER_STATE: {"stats": {"HP": 60}},
        InputKind.BUILD_DEFINITION: definition,
        InputKind.CURRENT_ROLLS: {"HP": 3},
        InputKind.ASSIGNED_BUILD: assignment,
        InputKind.ENGINE_SEMANTICS: {"advisor": 4},
        # Deliberately unrelated storage/concurrency metadata.
        "user_state_revision": revision,
    }


def test_unassigned_advisor_has_explicit_deterministic_intent_evidence():
    inputs = _advisor_inputs(assignment=None, definition=None)
    assert artifact_signature(ArtifactKind.LEVEL_ADVISOR, inputs) == artifact_signature(
        ArtifactKind.LEVEL_ADVISOR, dict(inputs)
    )


def test_current_advisor_bridge_preserves_existing_fingerprint_payload(
    bro_factory, simple_role
):
    bro = bro_factory()
    roles = [simple_role(("HP", "MAtk", "MDef"))]
    expected = stable_hash({
        "brother_state": brother_projection_state(bro),
        "roles": {role["name"]: role_fingerprint(role) for role in roles},
        "engine_version": ADVISOR_ENGINE_VERSION,
    })
    assert advisor_fingerprint(bro, roles) == expected


def test_signatures_are_deterministic_and_ignore_undeclared_inputs():
    first = _advisor_inputs(revision=1)
    reordered = dict(reversed(list(_advisor_inputs(revision=99).items())))
    assert artifact_signature(ArtifactKind.LEVEL_ADVISOR, first) == artifact_signature(
        ArtifactKind.LEVEL_ADVISOR, reordered
    )


def test_intent_aware_advisor_changes_for_assignment_or_definition():
    original = artifact_signature(ArtifactKind.LEVEL_ADVISOR, _advisor_inputs())
    assert original != artifact_signature(
        ArtifactKind.LEVEL_ADVISOR, _advisor_inputs(assignment="banner")
    )
    assert original != artifact_signature(
        ArtifactKind.LEVEL_ADVISOR, _advisor_inputs(definition="definition-b")
    )


def test_assigned_build_change_preserves_intrinsic_artifacts_and_closure_is_minimal():
    invalid = recomputation_closure({InputKind.ASSIGNED_BUILD})
    assert ArtifactKind.LEVEL_ADVISOR in invalid
    assert ArtifactKind.COMPANY_INTENDED_COVERAGE in invalid
    assert ArtifactKind.RELEVANT_ROSTER_NEED in invalid
    assert ArtifactKind.ROLE_PROJECTION not in invalid
    assert ArtifactKind.STRATEGIC_CLASSIFICATION not in invalid
    assert ArtifactKind.INTRINSIC_ALTERNATIVES not in invalid
    assert ArtifactKind.RECRUIT_INTRINSIC_POTENTIAL not in invalid


def test_classification_change_preserves_role_projection_but_invalidates_summary_only():
    invalid = recomputation_closure({InputKind.CLASSIFICATION_CONFIG})
    assert ArtifactKind.STRATEGIC_CLASSIFICATION in invalid
    assert ArtifactKind.ROLE_PROJECTION not in invalid
    assert ArtifactKind.LEVEL_ADVISOR not in invalid


def test_role_change_propagates_only_to_registered_consumers():
    invalid = recomputation_closure({InputKind.BROTHER_STATE})
    assert ArtifactKind.ROLE_PROJECTION in invalid
    assert ArtifactKind.STRATEGIC_CLASSIFICATION in invalid
    assert ArtifactKind.INTRINSIC_ALTERNATIVES in invalid
    assert ArtifactKind.COMPANY_INTRINSIC_COVERAGE in invalid
    assert ArtifactKind.RELEVANT_ROSTER_NEED in invalid

    assert recomputation_closure(
        {InputKind.BROTHER_STATE}, {ArtifactKind.STRATEGIC_CLASSIFICATION}
    ) == frozenset({ArtifactKind.STRATEGIC_CLASSIFICATION})


def test_missing_evidence_fails_conservatively():
    with pytest.raises(MissingDependencyEvidence, match="current_rolls"):
        artifact_signature(ArtifactKind.LEVEL_ADVISOR, {
            key: value for key, value in _advisor_inputs().items()
            if key != InputKind.CURRENT_ROLLS
        })


def test_changed_inputs_and_signature_validity_prove_unrelated_reuse():
    previous = {kind: f"same-{kind.value}" for kind in InputKind}
    current = dict(previous)
    current[InputKind.ASSIGNED_BUILD] = "changed"
    assert changed_inputs(previous, current) == frozenset({InputKind.ASSIGNED_BUILD})

    role_inputs = {
        InputKind.BROTHER_STATE: previous[InputKind.BROTHER_STATE],
        InputKind.BUILD_DEFINITION: previous[InputKind.BUILD_DEFINITION],
        InputKind.CURRENT_ROLLS: previous[InputKind.CURRENT_ROLLS],
        InputKind.ENGINE_SEMANTICS: previous[InputKind.ENGINE_SEMANTICS],
    }
    prior = artifact_signature(ArtifactKind.ROLE_PROJECTION, role_inputs)
    assert artifact_is_valid(prior, artifact_signature(
        ArtifactKind.ROLE_PROJECTION, {**role_inputs, InputKind.ASSIGNED_BUILD: "changed"}
    ))


def test_stable_build_identity_does_not_validate_changed_role_semantics():
    common = {
        InputKind.BROTHER_STATE: {"stats": {"HP": 60}},
        InputKind.CURRENT_ROLLS: {},
        InputKind.ENGINE_SEMANTICS: {"projection": 6},
    }
    reach_before = artifact_signature(ArtifactKind.ROLE_PROJECTION, {
        **common,
        InputKind.BUILD_DEFINITION: {
            "id": "reach_dps", "definition_hash": "sha256:before",
        },
    })
    reach_after = artifact_signature(ArtifactKind.ROLE_PROJECTION, {
        **common,
        InputKind.BUILD_DEFINITION: {
            "id": "reach_dps", "definition_hash": "sha256:after",
        },
    })
    banner_before = artifact_signature(ArtifactKind.ROLE_PROJECTION, {
        **common,
        InputKind.BUILD_DEFINITION: {
            "id": "banner", "definition_hash": "sha256:unchanged",
        },
    })
    banner_after = artifact_signature(ArtifactKind.ROLE_PROJECTION, {
        **common,
        InputKind.BUILD_DEFINITION: {
            "definition_hash": "sha256:unchanged", "id": "banner",
        },
    })

    assert reach_before != reach_after
    assert artifact_is_valid(banner_before, banner_after)
