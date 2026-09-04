from bbtool.app import analysis as analysis_module
from bbtool.build_identity import build_definition_hash
from bbtool.incremental.cache import IncrementalCache
from bbtool.levelup_advisor import advise_levelup
from bbtool.models import BrotherIdentity
from bbtool.projection.planner import project_role


def _resolved(role, *, status="current"):
    definition = build_definition_hash(role)
    return {
        "status": status,
        "build_identity": role["id"],
        "assigned_definition_hash": definition,
        "current_definition_hash": definition,
    }


def test_current_assignment_anchors_advisor_and_exposes_two_sided_consequences(
    bro_factory, simple_role,
):
    best = {**simple_role(("HP", "Fatigue", "Resolve")), "id": "best_fit"}
    assigned = {
        **simple_role(("MAtk", "RAtk", "MDef", "RDef")),
        "id": "assigned_build", "name": "Assigned Build",
    }
    bro = bro_factory(
        Level=11, LevelPoints=1,
        CurrentRolls={
            "HP": 4, "Fatigue": 4, "Resolve": 4,
            "MAtk": 3, "RAtk": 4, "MDef": 3, "RDef": 3,
        },
    )
    roles = [best, assigned]
    rows = [project_role(bro, role) for role in roles]
    # Preserve an independently selected intrinsic Best Fit regardless of the
    # synthetic role values produced by this compact fixture.
    rows[0]["ProjectedFitPct"] = 90.0
    rows[0]["ProjectedFit"] = 0.9
    rows[1]["ProjectedFitPct"] = 70.0
    rows[1]["ProjectedFit"] = 0.7

    advice = advise_levelup(bro, roles, rows, _resolved(assigned))

    assert advice["Anchor"] == {
        "Source": "AssignedBuild", "BuildIdentity": "assigned_build",
        "Role": "Assigned Build", "AssignmentStatus": "current",
    }
    assert advice["BestFit"]["BuildIdentity"] == "best_fit"
    assert advice["AssignedBuild"]["ValidAdvisorAnchor"] is True
    assert set(advice["Primary"]["Stats"]) <= {"MAtk", "RAtk", "MDef", "RDef"}
    assert advice["Primary"] == advice["Recommended"]
    assert advice["RunnerUp"] == advice["Alternative"]
    assert advice["ConditionalBranch"] is None
    for candidate in (advice["Primary"], advice["RunnerUp"]):
        assert candidate["Consequences"]["AssignedBuild"]["BuildIdentity"] == "assigned_build"
        assert candidate["Consequences"]["BestFit"]["BuildIdentity"] == "best_fit"


def test_invalid_or_absent_assignment_uses_explicit_best_fit_fallback(
    bro_factory, simple_role,
):
    role = {**simple_role(("HP", "MAtk", "MDef")), "id": "best_fit"}
    bro = bro_factory(
        Level=11, LevelPoints=1, CurrentRolls={"HP": 4, "MAtk": 3, "MDef": 3}
    )
    rows = [project_role(bro, role)]

    absent = advise_levelup(bro, [role], rows)
    changed = advise_levelup(
        bro, [role], rows, _resolved(role, status="definition_changed")
    )

    assert absent["Anchor"]["Source"] == "BestFitFallback"
    assert absent["Anchor"]["AssignmentStatus"] == "unassigned"
    assert changed["Anchor"]["Source"] == "BestFitFallback"
    assert changed["Anchor"]["AssignmentStatus"] == "definition_changed"
    assert changed["AssignedBuild"]["BuildIdentity"] == "best_fit"
    assert changed["AssignedBuild"]["ValidAdvisorAnchor"] is False
    assert changed["Primary"]["Consequences"]["AssignedBuild"] is None


def test_assignment_only_change_recomputes_advisor_but_reuses_intrinsic_summary(
    monkeypatch, bro_factory, simple_role, cfg,
):
    alpha = {**simple_role(("HP", "Fatigue", "Resolve")), "id": "alpha"}
    beta = {
        **simple_role(("MAtk", "RAtk", "MDef")), "id": "beta", "name": "Beta",
    }
    bro = bro_factory(Level=11, LevelPoints=0)
    identity = BrotherIdentity(7, 9, confidence="exact")
    identities = {bro.BrotherID: identity}
    classification = cfg.classification
    monkeypatch.setattr(analysis_module, "build_intrinsic_company_coverage", lambda *args: [])
    monkeypatch.setattr(analysis_module, "build_intent_company_coverage", lambda *args: [])

    cold = IncrementalCache(None)
    before = analysis_module.analyze_brothers(
        [bro], [alpha, beta], classification, cold, identities,
        {identity.value: _resolved(alpha)},
    )
    manifest = cold.manifest_payload(generated_at="cold", source_save="same.sav")
    warm_cache = IncrementalCache(manifest)
    after = analysis_module.analyze_brothers(
        [bro], [alpha, beta], classification, warm_cache, identities,
        {identity.value: _resolved(beta)},
    )

    assert before.fits == after.fits
    assert [item["BestRole"] for item in before.summaries] == [
        item["BestRole"] for item in after.summaries
    ]
    assert warm_cache.stats.role_reused == 2
    assert warm_cache.stats.summary_reused == 1
    assert warm_cache.stats.advisor_reused == 0
    assert warm_cache.stats.advisor_computed == 1
    assert warm_cache.miss_reasons["advisor_inputs_changed"] == 1
