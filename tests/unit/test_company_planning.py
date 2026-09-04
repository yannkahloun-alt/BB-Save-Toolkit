from types import SimpleNamespace

from bbtool.company_planning import build_intrinsic_company_coverage


DISPLAY = {"viable_fit": 0.60, "good_fit": 0.75, "premium_fit": 0.90}
CLASSIFICATION = {"display": DISPLAY}


def _bro(brother_id, brother_identity=None, hp=60):
    values = {
        "BrotherID": brother_id,
        "BrotherIdentity": brother_identity,
        "HP": hp,
        "Fatigue": 100,
        "Resolve": 40,
        "Initiative": 100,
        "MAtk": 50,
        "RAtk": 40,
        "MDef": 0,
        "RDef": 0,
        "HPStars": 0,
        "FatigueStars": 0,
        "ResolveStars": 0,
        "InitiativeStars": 0,
        "MAtkStars": 0,
        "RAtkStars": 0,
        "MDefStars": 0,
        "RDefStars": 0,
        "Level": 11,
        "LevelPoints": 0,
        "Perks": [],
        "Traits": [],
        "TraitIDs": [],
        "PermanentInjuryIDs": [],
        "BackgroundID": "background.test",
        "CurrentRolls": {},
    }
    return SimpleNamespace(**values)


def _role(identity, name=None, target=80):
    return {
        "id": identity,
        "name": name or identity,
        "stats": {
            "HP": {"fit": True, "baseline": 50, "target": target, "weight": 1}
        },
    }


def _fit(bro, role, pct):
    return {
        "BrotherID": bro.BrotherID,
        "Role": role["name"],
        "ProjectedFit": pct / 100,
        "ProjectedFitPct": pct,
    }


def _coverage(bros, roles, values, classification=CLASSIFICATION):
    fits = [
        _fit(bro, role, values[(bro.BrotherID, role["id"])])
        for bro in bros for role in roles
    ]
    identities = {
        bro.BrotherID: bro.BrotherIdentity
        for bro in bros if bro.BrotherIdentity is not None
    }
    return build_intrinsic_company_coverage(
        bros, roles, fits, classification, identities
    )


def test_no_assignments_exposes_intrinsic_depth_without_fabricating_need_or_intent():
    role = _role("tank")
    bros = [_bro("human:1", "native:a"), _bro("human:2")]
    result = _coverage(
        bros, [role], {("human:1", "tank"): 82, ("human:2", "tank"): 55}
    )[0]

    assert result["ViableCount"] == 1
    assert result["TopFitPct"] == 82
    assert result["SecondFitPct"] == 55
    assert result["ViableBrothers"] == [{
        "BrotherIdentity": "native:a",
        "BrotherID": "human:1",
        "FitPct": 82.0,
        "FitLabel": "GOOD",
    }]
    forbidden = {
        "AssignedCount", "Availability", "Need", "NeedFacts", "GapCount",
        "Redundant", "DesiredBuildSlots", "CompanyScore",
    }
    assert forbidden.isdisjoint(result)


def test_viable_good_and_premium_depth_use_configured_thresholds():
    role = _role("banner")
    bros = [_bro(f"human:{index}") for index in range(1, 6)]
    pcts = [59, 60, 74, 75, 90]
    result = _coverage(
        bros,
        [role],
        {(bro.BrotherID, "banner"): pct for bro, pct in zip(bros, pcts, strict=True)},
    )[0]

    assert (result["ViableCount"], result["GoodCount"], result["PremiumCount"]) == (4, 2, 1)
    assert [row["FitLabel"] for row in result["ViableBrothers"]] == [
        "PREMIUM", "GOOD", "VIABLE", "VIABLE"
    ]


def test_top_and_second_fit_are_nullable_only_when_roster_depth_is_missing():
    role = _role("thrower")
    one = _bro("human:1")
    singleton = _coverage([one], [role], {("human:1", "thrower"): 42})[0]
    empty = build_intrinsic_company_coverage([], [role], [], CLASSIFICATION)[0]

    assert (singleton["TopFitPct"], singleton["SecondFitPct"]) == (42, None)
    assert (empty["TopFitPct"], empty["SecondFitPct"]) == (None, None)


def test_builds_and_tied_brothers_have_stable_identity_ordering():
    alpha = _role("alpha", "Same display")
    zulu = _role("zulu", "Other display")
    bros = [_bro("human:2", "native:z"), _bro("human:1", "native:a")]
    values = {
        (bro.BrotherID, role["id"]): 80 for bro in bros for role in (alpha, zulu)
    }
    first = _coverage(bros, [zulu, alpha], values)
    second = _coverage(list(reversed(bros)), [alpha, zulu], values)

    assert first == second
    assert [row["BuildIdentity"] for row in first] == ["alpha", "zulu"]
    assert [row["BrotherIdentity"] for row in first[0]["ViableBrothers"]] == [
        "native:a", "native:z"
    ]


def test_legacy_idless_build_is_not_given_durable_company_identity():
    bro = _bro("human:1")
    legacy = {"name": "Mutable display", "stats": {}}
    assert build_intrinsic_company_coverage(
        [bro], [legacy], [_fit(bro, legacy, 90)], CLASSIFICATION
    ) == []


def test_affected_build_and_fit_inputs_invalidate_only_their_coverage_signature():
    alpha = _role("alpha")
    beta = _role("beta")
    bro = _bro("human:1")
    before = _coverage(
        [bro], [alpha, beta], {("human:1", "alpha"): 80, ("human:1", "beta"): 70}
    )
    changed_alpha = _role("alpha", target=90)
    build_changed = _coverage(
        [bro], [changed_alpha, beta], {("human:1", "alpha"): 75, ("human:1", "beta"): 70}
    )
    progressed = _bro("human:1", hp=61)
    fit_changed = _coverage(
        [progressed], [alpha, beta], {("human:1", "alpha"): 81, ("human:1", "beta"): 71}
    )

    assert before[0]["ArtifactSignature"] != build_changed[0]["ArtifactSignature"]
    assert before[1]["ArtifactSignature"] == build_changed[1]["ArtifactSignature"]
    assert all(
        old["ArtifactSignature"] != new["ArtifactSignature"]
        for old, new in zip(before, fit_changed, strict=True)
    )


def test_threshold_changes_invalidate_coverage_but_unrelated_state_cannot_enter_it():
    role = _role("tank")
    bro = _bro("human:1")
    fits = [_fit(bro, role, 80)]
    original = build_intrinsic_company_coverage([bro], [role], fits, CLASSIFICATION)[0]
    changed = build_intrinsic_company_coverage(
        [bro], [role], fits,
        {"display": {**DISPLAY, "good_fit": 0.85}, "AssignedBuild": "ignored"},
    )[0]

    assert original["ArtifactSignature"] != changed["ArtifactSignature"]
    same = build_intrinsic_company_coverage(
        [bro], [role], fits, {**CLASSIFICATION, "AssignedBuild": "also ignored"}
    )[0]
    assert original == same
