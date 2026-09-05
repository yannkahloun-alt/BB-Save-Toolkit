import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from bbtool.app.app_server import LocalApplicationApi

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "http://127.0.0.1:48123"
HOST = "127.0.0.1:48123"


def decode(response):
    return json.loads(response.body)


def _consequence(role, identity, before, after, feasibility_before, feasibility_after):
    return {
        "BuildIdentity": identity,
        "Role": role,
        "FitBeforePct": before,
        "FitAfterPct": after,
        "FitDeltaPct": round(after - before, 1),
        "FitMinAfterPct": after - 5,
        "FitMaxAfterPct": after + 5,
        "FitLikelyMinAfterPct": after - 2,
        "FitLikelyMaxAfterPct": after + 2,
        "FitFeasibilityBeforePct": feasibility_before,
        "FitFeasibilityAfterPct": feasibility_after,
        "ArtifactSignature": "sha256:private-consequence",
    }


def _candidate(stats, assigned_after, best_after):
    return {
        "Stats": stats,
        "Rolls": {stat: 3 for stat in stats},
        "RollQuality": {stat: 1.0 for stat in stats},
        "RoleBefore": "BF Tank",
        "RoleAfter": "BF Tank",
        "AnchorFitBeforePct": 70.0,
        "AnchorFitAfterPct": assigned_after,
        "FitMinAfterPct": 66.0,
        "FitMaxAfterPct": 78.0,
        "FitLikelyMinAfterPct": 69.0,
        "FitLikelyMaxAfterPct": 75.0,
        "FitFeasibilityBeforePct": 42.0,
        "FitFeasibilityAfterPct": 48.0,
        "FitDeltaPct": round(assigned_after - 70.0, 1),
        "Consequences": {
            "AssignedBuild": _consequence(
                "BF Tank", "bf_tank", 70.0, assigned_after, 42.0, 48.0
            ),
            "BestFit": _consequence(
                "Reach DPS", "reach_dps", 86.0, best_after, 76.0, 79.0
            ),
        },
        "Gamble": {
            "IsGamble": True,
            "ChanceToBeatPrimaryPct": 12.5,
            "private_path": "C:/private/advisor-diagnostics.json",
        },
        "_SimBro": "must-not-leak",
    }


def _application(monkeypatch, *, conditional_branch=None):
    from bbtool.app import level_up_view

    observation_id = "human:12"
    identity = SimpleNamespace(value="campaign:7/entity:9")
    primary = _candidate(["MDef", "Fatigue", "HP"], 74.0, 87.0)
    runner = _candidate(["MDef", "Resolve", "HP"], 72.0, 88.0)
    advice = {
        "Anchor": {
            "Source": "AssignedBuild", "BuildIdentity": "bf_tank", "Role": "BF Tank",
            "AssignmentStatus": "current",
        },
        "AssignedBuild": {
            "Status": "current", "BuildIdentity": "bf_tank",
            "AssignedDefinitionHash": "sha256:assigned-private",
            "CurrentDefinitionHash": "sha256:current-private",
            "ValidAdvisorAnchor": True,
        },
        "BestFit": {
            "BuildIdentity": "reach_dps", "Role": "Reach DPS", "ProjectedFitPct": 86.0,
        },
        "Primary": primary,
        "RunnerUp": runner,
        "ConditionalBranch": conditional_branch,
        "AllRolls": {
            "HP": {"Roll": 4, "Min": 2, "Max": 4, "Average": 3.0, "Label": "MAX", "Quality": 1.0},
            "Fatigue": {"Roll": 3, "Min": 2, "Max": 4, "Average": 3.0, "Label": "AVG", "Quality": 0.5},
            "Resolve": {"Roll": 4, "Min": 2, "Max": 4, "Average": 3.0, "Label": "MAX", "Quality": 1.0},
            "MDef": {"Roll": 3, "Min": 1, "Max": 3, "Average": 2.0, "Label": "MAX", "Quality": 1.0},
        },
        "PickReasons": {"MDef": "Fit stat · current +3 is MAX"},
        "SkippedImportant": [{
            "Stat": "Resolve", "Weight": 0.4, "Core": True,
            "Roll": {"Roll": 4, "Min": 2, "Max": 4, "Average": 3.0, "Label": "MAX", "Quality": 1.0},
            "Reason": "Fit stat · current +4 is MAX",
            "ArtifactSignature": "sha256:skip-private",
        }],
        "AdvisorEligibleStats": ["HP", "Fatigue", "Resolve", "MDef"],
        "AdvisorExcludedStats": {"RAtk": "role weight 0"},
        "FreePickMode": False,
        "FreePickStats": [],
        "FreePickCandidates": [],
        "Method": "Backend-owned advisor method",
        "CombinationsEvaluated": 4,
        "private_reference_sample": "C:/private/reference-cache",
    }
    presentation = {
        "brothers": [{
            "brother_id": observation_id,
            "assigned_build": {
                "status": "current",
                "build_identity": "bf_tank",
                "display_name": "BF Tank",
                "assigned_definition_hash": "sha256:assignment-private",
                "current_definition_hash": "sha256:definition-private",
            },
        }],
        "advisors": [{"brother_id": observation_id, "advice": advice}],
    }
    monkeypatch.setattr(
        level_up_view, "build_target_presentation", lambda **_kwargs: presentation
    )

    result = SimpleNamespace(
        roster=[], recruits=[], roles=[], campaign_identity=None,
        brother_identities={observation_id: identity},
        source_fingerprint="sha256:source-private", configuration_fingerprints={},
        recruitment_analysis=[], assigned_builds={}, diagnostics={},
        incremental_cache=SimpleNamespace(publication_signatures=lambda: {}),
        analysis=SimpleNamespace(
            company_intrinsic_coverage=[], company_intended_coverage=[], summaries=[]
        ),
        public_data={"roster": [{
            "BrotherID": observation_id, "Name": "Aldric", "Title": "the Wall",
            "Background": "Farmhand", "Level": 7,
            "HP": 78, "HPStars": 2, "Fatigue": 104, "FatigueStars": 1,
            "Resolve": 48, "ResolveStars": 0, "MDef": 23, "MDefStars": 3,
            "FutureRolls": {"MDef": [3, 3, 3]},
            "SourcePath": "C:/private/quicksave.sav",
        }]},
    )
    return SimpleNamespace(
        coordinator=SimpleNamespace(
            last_success=SimpleNamespace(generation=5, result=result)
        ),
        _command_lock=threading.RLock(),
    )


def test_level_up_endpoint_handles_no_publication():
    app = SimpleNamespace(
        coordinator=SimpleNamespace(last_success=None),
        _command_lock=threading.RLock(),
    )
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")

    response = api.handle("GET", "/api/v1/level-up", {"Host": HOST})

    assert response.status == 200
    assert decode(response)["data"] == {"available": False}


def test_level_up_endpoint_projects_backend_decision_without_internal_provenance(monkeypatch):
    api = LocalApplicationApi(_application(monkeypatch), origin=ORIGIN, token="capability")

    response = api.handle("GET", "/api/v1/level-up", {"Host": HOST})
    payload = decode(response)["data"]
    decision = payload["decisions"][0]
    serialized = json.dumps(payload)

    assert response.status == 200
    assert payload["generation"] == 5
    assert decision["brother_id"] == "campaign:7/entity:9"
    assert decision["assigned_build"] == {
        "status": "current", "build_identity": "bf_tank", "display_name": "BF Tank"
    }
    assert decision["best_fit"] == {
        "build_identity": "reach_dps", "role": "Reach DPS", "fit_pct": 86.0
    }
    assert {row["stat"] for row in decision["rolls"]} == {"HP", "Fatigue", "Resolve", "MDef"}
    mdef = next(row for row in decision["rolls"] if row["stat"] == "MDef")
    assert mdef == {
        "stat": "MDef", "current_value": 23, "stars": 3,
        "offered_roll": 3, "min_roll": 1, "max_roll": 3, "average_roll": 2.0,
        "band": "MAX", "quality": 1.0, "primary": True, "runner_up": True,
    }
    assert decision["primary"]["Consequences"]["AssignedBuild"]["FitAfterPct"] == 74.0
    assert decision["runner_up"]["Consequences"]["BestFit"]["FitAfterPct"] == 88.0
    assert decision["gamble"] is None
    assert decision["explain"]["method"] == "Backend-owned advisor method"

    for private in (
        "FutureRolls", "C:/private/quicksave.sav", "C:/private/reference-cache",
        "sha256:source-private", "sha256:assigned-private", "sha256:definition-private",
        "sha256:private-consequence", "ChanceToBeatPrimaryPct", "must-not-leak",
        "CombinationsEvaluated", "private_reference_sample",
    ):
        assert private not in serialized


def test_level_up_exposes_gamble_only_from_backend_conditional_branch(monkeypatch):
    branch = _candidate(["MDef", "Fatigue", "Resolve"], 71.0, 89.0)
    branch["Trigger"] = "Take Resolve only if the player accepts lower assigned-build Fit."
    branch["Interpretation"] = "Conditional upside for the intrinsic trajectory."
    api = LocalApplicationApi(
        _application(monkeypatch, conditional_branch=branch),
        origin=ORIGIN,
        token="capability",
    )

    response = api.handle("GET", "/api/v1/level-up", {"Host": HOST})
    gamble = decode(response)["data"]["decisions"][0]["gamble"]

    assert gamble["Stats"] == ["MDef", "Fatigue", "Resolve"]
    assert gamble["Trigger"].startswith("Take Resolve only")
    assert gamble["Interpretation"].startswith("Conditional upside")
    assert "Gamble" not in gamble


def test_level_up_static_contract_preserves_scan_decision_explain_and_responsiveness():
    page = (ROOT / "bbtool" / "app" / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "bbtool" / "app" / "static" / "level-up.js").read_text(encoding="utf-8")
    css = (ROOT / "bbtool" / "app" / "static" / "level-up.css").read_text(encoding="utf-8")

    for marker in (
        'id="levelup-queue"', 'id="levelup-brother-select"',
        "Assigned Build · Player intent", "Best Fit · Intrinsic analysis",
        'id="levelup-primary-preview"', 'id="levelup-rolls"',
        ">Primary<", ">Runner-up<", ">Gamble<", "Detailed reasoning / Explain",
    ):
        assert marker in page
    assert 'href="/level-up.css"' in page
    assert 'src="/level-up.js"' in page
    assert "fetchData('/api/v1/level-up')" in js
    assert "renderRoleContext(decision)" in js
    assert "renderPrimaryPreview(decision.primary)" in js
    assert "renderRolls(decision)" in js
    assert "renderGamble(decision.gamble)" in js
    assert "innerHTML" not in js
    assert "ChanceToBeatPrimaryPct" not in js
    assert "@media (max-width: 980px)" in css
    assert "@media (max-width: 720px)" in css
    assert "@media (max-width: 420px)" in css
    assert "grid-template-columns: minmax(12rem, 15rem) minmax(0, 1fr);" in css
    assert ".levelup-queue {" in css and "position: sticky;" in css
    assert ".levelup-mobile-select {" in css and "display: none;" in css


def test_level_up_assets_are_fixed_local_routes(monkeypatch):
    api = LocalApplicationApi(_application(monkeypatch), origin=ORIGIN, token="capability")

    css = api.handle("GET", "/level-up.css", {"Host": HOST})
    js = api.handle("GET", "/level-up.js", {"Host": HOST})

    assert css.status == 200 and css.content_type == "text/css; charset=utf-8"
    assert js.status == 200 and js.content_type == "text/javascript; charset=utf-8"
    assert b"https://" not in css.body + js.body
    assert b"http://" not in css.body + js.body
