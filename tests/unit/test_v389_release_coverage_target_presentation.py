from __future__ import annotations

from types import SimpleNamespace

import pytest

from bbtool.app import target_presentation as presentation


SHA = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64


def build_entry(identity="build:test", definition=SHA, name="Test"):
    return {
        "build_identity": identity,
        "build_definition_hash": definition,
        "display_name": name,
    }


def assignment(status="unassigned", **overrides):
    value = {
        "status": status,
        "build_identity": None,
        "assigned_definition_hash": None,
        "current_definition_hash": None,
        "display_name": None,
    }
    value.update(overrides)
    return value


def exact_campaign(value=12):
    return {
        "value": value,
        "basis": "native_campaign_id",
        "confidence": "exact",
        "reason": None,
    }


def exact_brother(value="campaign:12/entity:34"):
    return {
        "value": value,
        "basis": "native_campaign_entity_token",
        "confidence": "exact",
        "reason": None,
    }


def unavailable_identity(*, brother=False):
    return {
        "value": None,
        "basis": None,
        "confidence": "unavailable",
        "reason": "not_provided",
    }


def valid_distribution():
    return {
        "talent_weight_denominator": 10,
        "trajectory_sample_denominator": 20,
        "weight_denominator": 200,
        "unique_talent_profiles": 3,
        "fit_histogram_weight": {"50-59": 200},
        "mean_fit_pct": 55.5,
    }


def valid_prior():
    return {
        "schema": "bbtool.background_archetype_prior.v1",
        "model_version": 1,
        "background": {
            "save_hash": "AABBCCDD",
            "background_id": "background.raider",
            "source_revision": "rev",
        },
        "build": {"id": "build:test", "definition_hash": SHA},
        "engine_versions": {
            "role_projection": presentation.ENGINE_VERSIONS[presentation.ArtifactKind.ROLE_PROJECTION],
            "validation_oracle": presentation.ENGINE_VERSIONS[presentation.ArtifactKind.VALIDATION_ORACLE],
        },
        "assumptions": dict(presentation.PRIOR_ASSUMPTIONS),
        "distribution": valid_distribution(),
    }


def evidence_item(*, status="applied_exact_unconditional_fit_effect", effects=None):
    if effects is None:
        effects = [{"stat": "HP", "property": "Hitpoints", "op": "+", "value": 5}]
    return {
        "kind": "revealed_trait",
        "save_hash": "DEADBEEF",
        "name": "Strong",
        "status": status,
        "effects": effects,
    }


def valid_estimate(*, state="known_evidence_estimate"):
    items = [evidence_item()] if state == "known_evidence_estimate" else []
    return {
        "schema": "bbtool.recruit_candidate_estimate.v1",
        "model_version": 1,
        "state": state,
        "background_prior": valid_prior(),
        "candidate_estimate": (
            {
                "distribution": valid_distribution(),
                "applied_trait_save_hashes": ["DEADBEEF"],
            }
            if state == "known_evidence_estimate"
            else None
        ),
        "evidence_basis": {
            "public_fields_considered": list(presentation.PUBLIC_RECRUIT_FIELDS),
            "items": items,
            "excluded": list(presentation.EXCLUDED_RECRUIT_FIELDS),
        },
    }


def test_identity_payload_and_identity_validation_contracts():
    assert presentation._identity_payload(None) == {
        "value": None,
        "basis": None,
        "confidence": "unavailable",
        "reason": "not_provided",
    }
    assert presentation._validate_identity(exact_campaign(), brother=False) == 12
    assert presentation._validate_identity(exact_brother(), brother=True) == 12
    assert presentation._validate_identity(unavailable_identity(), brother=False) is None

    bad_cases = [
        ({}, False),
        ({**unavailable_identity(), "reason": "wrong"}, False),
        ({**unavailable_identity(), "basis": "wrong"}, False),
        ({**exact_campaign(), "reason": "bad"}, False),
        ({**exact_campaign(), "value": True}, False),
        ({**exact_campaign(), "value": -1}, False),
        ({**exact_campaign(), "value": presentation.CAMPAIGN_ID_MAX + 1}, False),
        ({**exact_brother(), "value": 123}, True),
        ({**exact_brother(), "value": "wrong"}, True),
        ({**exact_brother(), "value": "campaign:12/entity:0"}, True),
        ({**exact_brother(), "value": f"campaign:{presentation.CAMPAIGN_ID_MAX + 1}/entity:1"}, True),
        ({**exact_brother(), "value": f"campaign:1/entity:{presentation.ENTITY_TOKEN_MAX + 1}"}, True),
        ({"value": 1, "basis": "native_campaign_id", "confidence": "invalid", "reason": "x"}, False),
        ({"value": None, "basis": "native_campaign_id", "confidence": "invalid", "reason": ""}, False),
    ]
    for value, brother in bad_cases:
        with pytest.raises(ValueError):
            presentation._validate_identity(value, brother=brother)


def test_assigned_build_validation_all_states_and_rejections():
    builds = [build_entry()]
    presentation._validate_assigned_build(assignment(), builds)
    presentation._validate_assigned_build(assignment("unavailable"), builds)
    current = assignment(
        "current",
        build_identity="build:test",
        assigned_definition_hash=SHA,
        current_definition_hash=SHA,
        display_name="Test",
    )
    presentation._validate_assigned_build(current, builds)
    presentation._validate_assigned_build(
        {**current, "status": "definition_changed", "assigned_definition_hash": SHA_B},
        builds,
    )
    for status in ("deprecated", "missing"):
        presentation._validate_assigned_build(
            assignment(status, build_identity="build:old", assigned_definition_hash=SHA_B),
            builds,
        )

    rejected = [
        {"status": "unassigned"},
        assignment("bogus"),
        assignment("unassigned", display_name="should-be-empty"),
        assignment("current", build_identity="", assigned_definition_hash=SHA,
                   current_definition_hash=SHA, display_name="Test"),
        assignment("current", build_identity="missing", assigned_definition_hash=SHA,
                   current_definition_hash=SHA, display_name="Test"),
        {**current, "display_name": "Wrong"},
        {**current, "assigned_definition_hash": "not-a-hash"},
        {**current, "assigned_definition_hash": SHA_B},
        assignment("deprecated", build_identity="build:old", assigned_definition_hash="bad"),
        assignment("missing", build_identity="build:old", assigned_definition_hash=SHA,
                   current_definition_hash=SHA),
    ]
    for value in rejected:
        with pytest.raises(ValueError):
            presentation._validate_assigned_build(value, builds)


def test_advice_binding_tracks_current_and_fallback_assignment():
    current_assignment = assignment(
        "current",
        build_identity="build:test",
        assigned_definition_hash=SHA,
        current_definition_hash=SHA,
        display_name="Test",
    )
    current_advice = {
        "AssignedBuild": {
            "Status": "current",
            "BuildIdentity": "build:test",
            "AssignedDefinitionHash": SHA,
            "CurrentDefinitionHash": SHA,
            "ValidAdvisorAnchor": True,
        },
        "Anchor": {"Source": "AssignedBuild", "BuildIdentity": "build:test"},
        "BestFit": {"BuildIdentity": "build:best"},
    }
    assert presentation._advice_is_bound_to_assignment(None, current_assignment)
    assert not presentation._advice_is_bound_to_assignment("bad", current_assignment)
    assert presentation._advice_is_bound_to_assignment(current_advice, current_assignment)
    assert not presentation._advice_is_bound_to_assignment(
        {**current_advice, "Anchor": {"Source": "BestFitFallback", "BuildIdentity": "build:test"}},
        current_assignment,
    )
    assert not presentation._advice_is_bound_to_assignment(
        {**current_advice, "AssignedBuild": {}}, current_assignment
    )

    unassigned = assignment()
    fallback = {
        "AssignedBuild": {
            "Status": "unassigned",
            "BuildIdentity": None,
            "AssignedDefinitionHash": None,
            "CurrentDefinitionHash": None,
            "ValidAdvisorAnchor": False,
        },
        "Anchor": {"Source": "BestFitFallback", "BuildIdentity": "build:best"},
        "BestFit": {"BuildIdentity": "build:best"},
    }
    assert presentation._advice_is_bound_to_assignment(fallback, unassigned)
    wrong = {**fallback, "AssignedBuild": {**fallback["AssignedBuild"], "ValidAdvisorAnchor": True}}
    assert not presentation._advice_is_bound_to_assignment(wrong, unassigned)


def test_dependency_signature_evidence_requires_complete_unique_exact_rows():
    expected = {("b1",): SHA, ("b2",): SHA_B}
    roster = {"b1": {}, "b2": {}}
    rows = [
        {"brother_id": "b1", "dependency_signature": SHA},
        {"brother_id": "b2", "dependency_signature": SHA_B},
    ]
    presentation._validate_signature_evidence(
        rows, expected=expected, key_fields=("brother_id",), roster=roster
    )

    bad_rows = [
        ["bad"],
        [{"brother_id": "b1"}],
        [{"brother_id": 1, "dependency_signature": SHA}],
        [{"brother_id": "unknown", "dependency_signature": SHA}],
        [{"brother_id": "b1", "dependency_signature": "bad"}],
        [rows[0], rows[0]],
        [rows[0]],
        [rows[0], {"brother_id": "b2", "dependency_signature": SHA}],
    ]
    for candidate in bad_rows:
        with pytest.raises(ValueError):
            presentation._validate_signature_evidence(
                candidate, expected=expected, key_fields=("brother_id",), roster=roster
            )


def test_fit_distribution_accepts_coherent_weights_and_rejects_invalid_shapes():
    good = valid_distribution()
    presentation._validate_fit_distribution(good)
    bad = [
        None,
        {**good, "extra": 1},
        {**good, "talent_weight_denominator": True},
        {**good, "trajectory_sample_denominator": 0},
        {**good, "weight_denominator": 199},
        {**good, "fit_histogram_weight": {}},
        {**good, "fit_histogram_weight": {"bad-bin": 200}},
        {**good, "fit_histogram_weight": {"50-59": True}},
        {**good, "fit_histogram_weight": {"50-59": 199}},
        {**good, "mean_fit_pct": True},
        {**good, "mean_fit_pct": "55"},
        {**good, "mean_fit_pct": 101},
    ]
    for candidate in bad:
        with pytest.raises(ValueError):
            presentation._validate_fit_distribution(candidate)


def test_recruitment_evidence_items_accept_exact_and_insufficient_states():
    applied = evidence_item()
    insufficient = evidence_item(
        status="insufficient_for_estimate", effects=[]
    )
    assert presentation._validate_recruitment_evidence_items([applied, applied, insufficient]) == ["DEADBEEF"]

    rejected = [
        [None],
        [{**applied, "kind": "wrong"}],
        [{**applied, "status": "wrong"}],
        [{**applied, "save_hash": "bad"}],
        [{**applied, "name": 5}],
        [{**applied, "effects": ["bad"]}],
        [{**applied, "effects": [{"stat": "HP"}]}],
        [{**applied, "save_hash": None}],
        [{**insufficient, "effects": applied["effects"]}],
    ]
    for candidate in rejected:
        with pytest.raises(ValueError):
            presentation._validate_recruitment_evidence_items(candidate)


def test_background_prior_validation_locks_identity_engines_and_distribution():
    good = valid_prior()
    presentation._validate_background_prior(
        good,
        background_save_hash="aabbccdd",
        build_identity_value="build:test",
        build_definition_hash_value=SHA,
    )
    bad = [
        {**good, "schema": "wrong"},
        {**good, "model_version": 2},
        {**good, "assumptions": {}},
        {**good, "background": {**good["background"], "save_hash": "FFFFFFFF"}},
        {**good, "background": {**good["background"], "background_id": 1}},
        {**good, "build": {"id": "other", "definition_hash": SHA}},
        {**good, "engine_versions": {}},
    ]
    for candidate in bad:
        with pytest.raises(ValueError):
            presentation._validate_background_prior(
                candidate,
                background_save_hash="aabbccdd",
                build_identity_value="build:test",
                build_definition_hash_value=SHA,
            )
    with pytest.raises(ValueError):
        presentation._validate_background_prior(
            good,
            background_save_hash="aabbccdd",
            build_identity_value=None,
            build_definition_hash_value=SHA,
        )


def test_recruitment_analysis_unavailable_prior_and_known_evidence_contracts():
    unavailable = {
        "build_identity": "build:test",
        "state": "unavailable",
        "reason": "missing",
        "result": None,
    }
    presentation._validate_recruitment_analysis(
        unavailable,
        background_save_hash="AABBCCDD",
        build_definition_hash_value=SHA,
        recruit={},
    )
    with pytest.raises(ValueError):
        presentation._validate_recruitment_analysis(
            {**unavailable, "reason": ""},
            background_save_hash="AABBCCDD",
            build_definition_hash_value=SHA,
            recruit={},
        )

    prior = {
        "build_identity": "build:test",
        "state": "prior_only",
        "reason": None,
        "result": valid_estimate(state="prior_only"),
    }
    presentation._validate_recruitment_analysis(
        prior,
        background_save_hash="AABBCCDD",
        build_definition_hash_value=SHA,
        recruit={},
    )
    known = {
        "build_identity": "build:test",
        "state": "known_evidence_estimate",
        "reason": None,
        "result": valid_estimate(),
    }
    recruit = {
        "TryoutDone": True,
        "RevealedTraitEvidence": [{"save_hash": "DEADBEEF", "name": "Strong"}],
    }
    presentation._validate_recruitment_analysis(
        known,
        background_save_hash="AABBCCDD",
        build_definition_hash_value=SHA,
        recruit=recruit,
    )

    bad_result = valid_estimate()
    bad_result["evidence_basis"] = {**bad_result["evidence_basis"], "excluded": []}
    with pytest.raises(ValueError):
        presentation._validate_recruitment_analysis(
            {**known, "result": bad_result},
            background_save_hash="AABBCCDD",
            build_definition_hash_value=SHA,
            recruit=recruit,
        )
    with pytest.raises(ValueError):
        presentation._validate_recruitment_analysis(
            known,
            background_save_hash="AABBCCDD",
            build_definition_hash_value=SHA,
            recruit={"TryoutDone": True, "RevealedTraitEvidence": ["bad"]},
        )
    with pytest.raises(ValueError):
        presentation._validate_recruitment_analysis(
            known,
            background_save_hash="AABBCCDD",
            build_definition_hash_value=SHA,
            recruit={"TryoutDone": True, "RevealedTraitEvidence": [{"save_hash": "11111111", "name": "Strong"}]},
        )


def test_build_recruitment_presentation_covers_unavailable_failure_and_success(monkeypatch):
    roles = [
        {"name": "NoIdentity"},
        {"name": "MissingBackground"},
        {"name": "Failure"},
        {"name": "Success"},
    ]

    def identity(role):
        return None if role["name"] == "NoIdentity" else "build:" + role["name"]

    monkeypatch.setattr(presentation, "build_identity", identity)
    monkeypatch.setattr(presentation, "load_background_potential_reference", lambda _path: {"ref": True})

    def estimate(_recruit, role, _reference):
        if role["name"] == "Failure":
            raise ValueError("unsupported")
        return {"state": "prior_only"}

    monkeypatch.setattr(presentation, "recruit_candidate_estimate", estimate)
    rows = presentation.build_recruitment_presentation(
        [
            {},
            {"BackgroundSaveHash": "AABBCCDD"},
        ],
        roles,
        "reference.json",
    )
    assert rows[0]["analyses"][0]["reason"] == "build_identity_unavailable"
    assert rows[0]["analyses"][1]["reason"] == "background_identity_unavailable"
    assert rows[1]["analyses"][2]["reason"] == "ValueError"
    assert rows[1]["analyses"][3]["state"] == "prior_only"


def test_build_target_presentation_handles_assignment_availability_and_malformed_mapping(monkeypatch):
    role = {"name": "Test"}
    bro = SimpleNamespace(BrotherID="b1", PerkGearFacts=[{"fact": "x"}])
    monkeypatch.setattr(presentation, "build_identity", lambda _role: "build:test")
    monkeypatch.setattr(presentation, "build_definition_hash", lambda _role: SHA)
    monkeypatch.setattr(presentation, "perk_gear_facts", lambda _bro: [{"fact": "x"}])
    monkeypatch.setattr(presentation, "build_relevant_roster_need", lambda *_args, **_kwargs: {"need": True})
    artifact_hashes = {key: SHA for key in presentation.BOUND_ARTIFACTS}
    signatures = {
        "role_projection": [],
        "strategic_classification": [],
        "level_advisor": [],
    }
    identity = SimpleNamespace(value="campaign:12/entity:34", basis="native_campaign_entity_token", confidence="exact", reason=None)

    unavailable = presentation.build_target_presentation(
        bros=[bro], recruits=[], roles=[role], analysis_health={},
        campaign_identity=None, brother_identities={"b1": identity},
        source_fingerprint=SHA, configuration_fingerprints={},
        recruitment_analysis=[], artifact_hashes=artifact_hashes,
        result_signatures=signatures, company_intrinsic_coverage=[],
    )
    assert unavailable["brothers"][0]["assigned_build"]["status"] == "unavailable"
    assert unavailable["company"]["intent_available"] is False

    malformed = presentation.build_target_presentation(
        bros=[bro], recruits=[], roles=[role], analysis_health={},
        campaign_identity=None, brother_identities={"b1": identity},
        source_fingerprint=SHA, configuration_fingerprints={},
        recruitment_analysis=[], artifact_hashes=artifact_hashes,
        result_signatures=signatures, company_intrinsic_coverage=[],
        assigned_builds={"campaign:12/entity:34": {"assignment": "bad"}},
    )
    assert malformed["brothers"][0]["assigned_build"]["status"] == "unassigned"
    assert malformed["company"]["intent_available"] is True
