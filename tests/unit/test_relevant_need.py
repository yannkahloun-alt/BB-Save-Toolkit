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
