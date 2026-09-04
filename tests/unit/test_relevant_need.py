from bbtool.relevant_need import build_relevant_roster_need


def a(identity, mean, state="prior_only"):
    return {"build_identity": identity, "state": state, "result": {
        "background_prior": {"distribution": {"mean_fit_pct": mean}}
    }}


def gap(identity, bases):
    return {"BuildIdentity": identity, "NeedBases": bases,
            "AssignedViableCount": 1, "FreeViableBackupCount": 0,
            "ContestedViableBackupCount": 0}


def test_need_intersects_plausible_roles_and_preserves_no_match_and_other_gaps():
    result = build_relevant_roster_need(
        [a("tank", 80), a("banner", 40)],
        [gap("banner", ["single_point_of_failure"]), gap("tank", ["contested_backup_only"])],
        viable_fit=.5,
    )
    assert result["candidate_plausible_roles"] == ["tank"]
    assert result["relevant_need"]["build_identity"] == "tank"
    assert [x["build_identity"] for x in result["other_company_gaps"]] == ["banner"]


def test_no_intent_is_not_a_need_and_no_match_is_explicit():
    result = build_relevant_roster_need([a("tank", 80)], [{"BuildIdentity": "tank", "NeedBases": []}], viable_fit=.5)
    assert result["relevant_need"] is None and result["no_match"]


def test_ordering_ties_and_unavailable_candidates_are_deterministic():
    result = build_relevant_roster_need(
        [a("b", 80), a("a", 80), a("bad", 99, "unavailable")],
        [gap("b", ["contested_backup_only"]), gap("a", ["contested_backup_only"])], viable_fit=.5)
    assert [x["build_identity"] for x in result["relevant_need_matches"]] == ["a", "b"]


def test_company_need_only_changes_relevant_need_not_candidate_plausibility():
    analyses = [a("tank", 80), a("banner", 70)]
    first = build_relevant_roster_need(analyses, [gap("tank", ["single_point_of_failure"])], viable_fit=.5)
    second = build_relevant_roster_need(analyses, [gap("banner", ["assigned_but_no_viable_holder"])], viable_fit=.5)
    assert first["candidate_plausible_roles"] == second["candidate_plausible_roles"] == ["banner", "tank"]
    assert first["relevant_need"]["build_identity"] == "tank"
    assert second["relevant_need"]["build_identity"] == "banner"


def test_high_need_role_is_rejected_when_candidate_is_not_plausible():
    result = build_relevant_roster_need(
        [a("tank", 40)],
        [gap("banner", ["assigned_but_no_viable_holder"])],
        viable_fit=.5,
    )
    assert result["relevant_need_matches"] == []
    assert result["other_company_gaps"][0]["build_identity"] == "banner"
    assert result["no_match"] is True


def test_transitive_inputs_change_signature_but_unaffected_artifacts_are_reusable():
    analyses = [a("tank", 80)]
    first = build_relevant_roster_need(analyses, [gap("tank", ["single_point_of_failure"])], viable_fit=.5)
    changed_need = build_relevant_roster_need(analyses, [gap("tank", ["contested_backup_only"])], viable_fit=.5)
    changed_candidate = build_relevant_roster_need([a("tank", 40)], [gap("tank", ["single_point_of_failure"])], viable_fit=.5)
    assert first["artifact_signature"] != changed_need["artifact_signature"]
    assert first["artifact_signature"] != changed_candidate["artifact_signature"]
    assert first["candidate_plausible_roles"] == changed_need["candidate_plausible_roles"]
    assert first["relevant_need"]["build_identity"] == changed_need["relevant_need"]["build_identity"] == "tank"
    assert changed_candidate["relevant_need"] is None


def test_viability_threshold_invalidates_relevant_need_without_mutating_evidence():
    analyses = [a("tank", 60)]
    viable = build_relevant_roster_need(analyses, [gap("tank", ["single_point_of_failure"])], viable_fit=.5)
    strict = build_relevant_roster_need(analyses, [gap("tank", ["single_point_of_failure"])], viable_fit=.7)
    assert viable["candidate_plausible_roles"] == ["tank"]
    assert strict["candidate_plausible_roles"] == []
    assert viable["artifact_signature"] != strict["artifact_signature"]
