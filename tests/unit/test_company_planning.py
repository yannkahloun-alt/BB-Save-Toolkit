from types import SimpleNamespace

import bbtool.app.analysis as analysis_module
from bbtool.build_identity import build_definition_hash
from bbtool.company_planning import (
    build_intent_company_coverage,
    build_intrinsic_company_coverage,
)


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


def _resolved(role):
    definition_hash = build_definition_hash(role)
    return {
        "status": "current", "build_identity": role["id"],
        "assigned_definition_hash": definition_hash,
        "current_definition_hash": definition_hash,
    }


def _intended(bros, roles, values, assigned):
    fits = [
        _fit(bro, role, values[(bro.BrotherID, role["id"])])
        for bro in bros for role in roles
    ]
    identities = {bro.BrotherID: bro.BrotherIdentity for bro in bros}
    return build_intent_company_coverage(
        bros, roles, fits, CLASSIFICATION, assigned, identities
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


def test_no_intent_preserves_intrinsic_depth_without_need():
    tank, banner = _role("tank"), _role("banner")
    bro = _bro("human:1", "campaign:1/entity:1")
    intended = _intended(
        [bro], [tank, banner],
        {(bro.BrotherID, "tank"): 80, (bro.BrotherID, "banner"): 80},
        {bro.BrotherIdentity: _resolved(banner)},
    )[1]

    assert intended["AssignedCount"] == 0
    assert intended["FreeViableBackupCount"] == 0
    assert intended["ContestedViableBackupCount"] == 1
    assert intended["FragilityFacts"]["NoIntent"] is True
    assert intended["NeedBases"] == []


def test_single_holder_free_and_contested_backup_facts_are_distinct():
    tank, banner = _role("tank"), _role("banner")
    holder = _bro("human:1", "campaign:1/entity:1")
    backup = _bro("human:2", "campaign:1/entity:2")
    values = {
        (holder.BrotherID, "tank"): 80, (holder.BrotherID, "banner"): 40,
        (backup.BrotherID, "tank"): 75, (backup.BrotherID, "banner"): 80,
    }
    holder_assignment = {holder.BrotherIdentity: _resolved(tank)}
    free = _intended([holder, backup], [tank, banner], values, holder_assignment)[1]
    # Stable BuildIdentity ordering puts banner before tank.
    assert free["BuildIdentity"] == "tank"
    assert free["FreeViableBackupCount"] == 1
    assert free["FragilityFacts"]["FreeBackupAvailable"] is True
    assert free["FragilityFacts"]["SinglePointOfFailure"] is False

    contested = _intended(
        [holder, backup], [tank, banner], values,
        {**holder_assignment, backup.BrotherIdentity: _resolved(banner)},
    )[1]
    assert contested["ContestedViableBackupCount"] == 1
    assert contested["FragilityFacts"]["ContestedBackupOnly"] is True
    assert contested["NeedBases"] == ["contested_backup_only"]

    no_spare = _intended([holder], [tank], {(holder.BrotherID, "tank"): 80}, holder_assignment)[0]
    assert no_spare["FragilityFacts"]["SinglePointOfFailure"] is True
    assert no_spare["NeedBases"] == ["single_point_of_failure"]


def test_below_viable_mismatch_and_multi_holder_evidence():
    alpha, beta = _role("alpha"), _role("beta")
    first = _bro("human:1", "campaign:1/entity:1")
    second = _bro("human:2", "campaign:1/entity:2")
    values = {
        (first.BrotherID, "alpha"): 55, (first.BrotherID, "beta"): 90,
        (second.BrotherID, "alpha"): 80, (second.BrotherID, "beta"): 40,
    }
    result = _intended(
        [first, second], [beta, alpha], values,
        {first.BrotherIdentity: _resolved(alpha)},
    )[0]
    assert result["AssignedBelowViableCount"] == 1
    assert result["FragilityFacts"]["AssignedButNoViableHolder"] is True
    assert result["NeedBases"] == ["assigned_but_no_viable_holder"]
    assert result["AssignedBrothers"][0] == {
        "BrotherIdentity": first.BrotherIdentity, "BrotherID": first.BrotherID,
        "AssignedFitPct": 55.0, "AssignedFitLabel": "LOW",
        "BestBuildIdentity": "beta", "BestFitPct": 90.0,
        "BestVsAssignedDeltaPctPoints": 35.0, "BestBuildDiffers": True,
    }

    both = _intended(
        [first, second], [alpha, beta],
        {**values, (first.BrotherID, "alpha"): 70},
        {
            first.BrotherIdentity: _resolved(alpha),
            second.BrotherIdentity: _resolved(alpha),
        },
    )[0]
    assert both["AssignedViableCount"] == 2
    assert both["FragilityFacts"]["MultiHolderDepth"] is True


def test_assignment_only_mutation_changes_only_intended_artifact_and_is_stable():
    alpha, beta = _role("alpha"), _role("beta")
    bros = [
        _bro("human:2", "campaign:1/entity:2"),
        _bro("human:1", "campaign:1/entity:1"),
    ]
    values = {(bro.BrotherID, role["id"]): 80 for bro in bros for role in (alpha, beta)}
    intrinsic_before = _coverage(bros, [beta, alpha], values)
    first = _intended(bros, [beta, alpha], values, {})
    assigned = {bros[0].BrotherIdentity: _resolved(alpha)}
    second = _intended(list(reversed(bros)), [alpha, beta], values, assigned)

    assert intrinsic_before == _coverage(list(reversed(bros)), [alpha, beta], values)
    assert first[0]["ArtifactSignature"] != second[0]["ArtifactSignature"]
    assert [row["BuildIdentity"] for row in second] == ["alpha", "beta"]
    assert [row["BrotherIdentity"] for row in second[0]["ViableAvailability"]] == [
        "campaign:1/entity:1", "campaign:1/entity:2"
    ]


def test_definition_changed_assignment_is_not_consumed_as_current_intent():
    role = _role("tank")
    bro = _bro("human:1", "campaign:1/entity:1")
    stale = {**_resolved(role), "status": "definition_changed"}
    result = _intended(
        [bro], [role], {(bro.BrotherID, "tank"): 80}, {bro.BrotherIdentity: stale}
    )[0]
    assert result["AssignedCount"] == 0
    assert result["FragilityFacts"]["NoIntent"] is True


def test_mismatch_best_build_uses_best_role_ranking_not_raw_fit_alone():
    alpha, beta = _role("alpha"), _role("beta")
    bro = _bro("human:1", "campaign:1/entity:1")
    fits = [_fit(bro, alpha, 90), _fit(bro, beta, 80)]
    fits[0]["PerkCompatibility"] = "CONFLICT"
    fits[1]["PerkCompatibility"] = "NEUTRAL"
    result = build_intent_company_coverage(
        [bro], [alpha, beta], fits, CLASSIFICATION,
        {bro.BrotherIdentity: _resolved(alpha)},
        {bro.BrotherID: bro.BrotherIdentity},
    )[0]

    assert result["AssignedBrothers"][0]["AssignedFitPct"] == 90
    assert result["AssignedBrothers"][0]["BestBuildIdentity"] == "beta"
    assert result["AssignedBrothers"][0]["BestFitPct"] == 80


def test_exact_best_role_tie_retains_first_configured_role_and_changes_signature():
    alpha, beta = _role("alpha"), _role("beta")
    bro = _bro("human:1", "campaign:1/entity:1")
    values = {
        (bro.BrotherID, "alpha"): 80,
        (bro.BrotherID, "beta"): 80,
    }
    assignment = {bro.BrotherIdentity: _resolved(beta)}

    alpha_first = _intended([bro], [alpha, beta], values, assignment)[1]
    beta_first = _intended([bro], [beta, alpha], values, assignment)[1]

    assert analysis_module._best([
        _fit(bro, alpha, 80), _fit(bro, beta, 80)
    ])["Role"] == "alpha"
    assert alpha_first["AssignedBrothers"][0]["BestBuildIdentity"] == "alpha"
    assert analysis_module._best([
        _fit(bro, beta, 80), _fit(bro, alpha, 80)
    ])["Role"] == "beta"
    assert beta_first["AssignedBrothers"][0]["BestBuildIdentity"] == "beta"
    assert alpha_first["ArtifactSignature"] != beta_first["ArtifactSignature"]


def test_unrelated_semantic_changes_preserve_per_build_signature():
    target, other, third = _role("target"), _role("other"), _role("third")
    holder = _bro("human:1", "campaign:1/entity:1")
    outsider = _bro("human:2", "campaign:1/entity:2")
    values = {
        (holder.BrotherID, "target"): 80, (holder.BrotherID, "other"): 70,
        (holder.BrotherID, "third"): 60,
        (outsider.BrotherID, "target"): 50, (outsider.BrotherID, "other"): 80,
        (outsider.BrotherID, "third"): 70,
    }
    no_target_assignment = {outsider.BrotherIdentity: _resolved(other)}
    before = _intended(
        [holder, outsider], [target, other, third], values, no_target_assignment
    )[1]

    changed_third = _role("third", target=95)
    unrelated_definition = _intended(
        [holder, outsider], [target, other, changed_third], values,
        no_target_assignment,
    )[1]
    reassigned_elsewhere = _intended(
        [holder, outsider], [target, other, third], values,
        {outsider.BrotherIdentity: _resolved(third)},
    )[1]
    assert before["BuildIdentity"] == "target"
    assert unrelated_definition["ArtifactSignature"] == before["ArtifactSignature"]
    assert reassigned_elsewhere["ArtifactSignature"] == before["ArtifactSignature"]

    assignments = {
        holder.BrotherIdentity: _resolved(target),
        outsider.BrotherIdentity: _resolved(other),
    }
    before_mismatch = _intended(
        [holder, outsider], [target, other, third], values, assignments
    )[1]
    changed_other = _role("other", target=95)
    mismatch = _intended(
        [holder, outsider], [target, changed_other, third], values,
        {
            holder.BrotherIdentity: _resolved(target),
            outsider.BrotherIdentity: _resolved(changed_other),
        },
    )[1]
    moved_holder = _intended(
        [holder, outsider], [target, other, third], values,
        {**assignments, holder.BrotherIdentity: _resolved(other)},
    )[1]
    assert mismatch["ArtifactSignature"] != before_mismatch["ArtifactSignature"]
    assert moved_holder["ArtifactSignature"] != before_mismatch["ArtifactSignature"]


def test_assignment_only_pipeline_mutation_preserves_fit_best_role_and_intrinsic(monkeypatch):
    alpha, beta = _role("alpha"), _role("beta")
    bro = _bro("human:1", "campaign:1/entity:1")

    def projected(_, role):
        pct = 80 if role["id"] == "alpha" else 70
        return _fit(bro, role, pct)

    monkeypatch.setattr(analysis_module, "_role_row", projected)
    monkeypatch.setattr(analysis_module, "advise_levelup", lambda *args: {})
    monkeypatch.setattr(analysis_module, "effective_stat_profile", lambda _: ({}, {}))
    monkeypatch.setattr(
        analysis_module, "_summary",
        lambda _, best, *args: {
            "BestRole": best["Role"], "ProjectedFitPct": best["ProjectedFitPct"]
        },
    )
    identities = {bro.BrotherID: bro.BrotherIdentity}
    before = analysis_module.analyze_brothers(
        [bro], [alpha, beta], CLASSIFICATION, brother_identities=identities,
        assigned_builds={},
    )
    after = analysis_module.analyze_brothers(
        [bro], [alpha, beta], CLASSIFICATION, brother_identities=identities,
        assigned_builds={bro.BrotherIdentity: _resolved(beta)},
    )

    assert before.fits == after.fits
    assert before.summaries == after.summaries
    assert before.company_intrinsic_coverage == after.company_intrinsic_coverage
    assert before.company_intended_coverage != after.company_intended_coverage
