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


def _analysis(build_identity, *, state, prior, estimate=None, evidence=None):
    result = {
        "background_prior": {
            "distribution": {"mean_fit_pct": prior},
            "artifact_signature": "sha256:private-prior",
        },
        "candidate_estimate": None,
        "evidence_basis": {
            "items": [],
            "private_reference": "C:/private/reference-cache.json",
        },
    }
    if state == "known_evidence_estimate":
        result["candidate_estimate"] = {
            "distribution": {"mean_fit_pct": estimate},
            "applied_trait_save_hashes": ["PRIVATE_TRAIT_HASH"],
        }
        result["evidence_basis"]["items"] = [{
            "kind": "revealed_trait",
            "save_hash": "PRIVATE_TRAIT_HASH",
            "name": evidence,
            "status": "applied_exact_unconditional_fit_effect",
            "effects": [{"stat": "HP", "value": 10}],
        }]
    return {
        "build_identity": build_identity,
        "state": state,
        "reason": None,
        "result": result,
    }


def _application(monkeypatch, presentation_mutator=None):
    from bbtool.app import recruitment_view

    presentation = {
        "company": {"intent_available": True},
        "builds": [
            {"build_identity": "bf_tank", "display_name": "BF Tank", "build_definition_hash": "sha256:private-build-1"},
            {"build_identity": "reach_dps", "display_name": "Reach DPS", "build_definition_hash": "sha256:private-build-2"},
            {"build_identity": "banner", "display_name": "Banner", "build_definition_hash": "sha256:private-build-3"},
        ],
        "recruitment": [
            {
                "recruit_index": 0,
                "background_save_hash": "PRIVATE_BACKGROUND_1",
                "analyses": [
                    _analysis("bf_tank", state="prior_only", prior=72.0),
                    _analysis("reach_dps", state="prior_only", prior=61.0),
                    _analysis("banner", state="prior_only", prior=34.0),
                ],
            },
            {
                "recruit_index": 1,
                "background_save_hash": "PRIVATE_BACKGROUND_2",
                "analyses": [
                    _analysis("bf_tank", state="known_evidence_estimate", prior=55.0, estimate=64.0, evidence="Tough"),
                    _analysis("reach_dps", state="known_evidence_estimate", prior=59.0, estimate=68.0, evidence="Tough"),
                    _analysis("banner", state="prior_only", prior=80.0),
                ],
            },
            {
                "recruit_index": 2,
                "background_save_hash": "PRIVATE_BACKGROUND_3",
                "analyses": [
                    _analysis("bf_tank", state="prior_only", prior=48.0),
                    _analysis("reach_dps", state="prior_only", prior=52.0),
                    _analysis("banner", state="prior_only", prior=75.0),
                ],
            },
        ],
        "relevant_roster_need": [
            {
                "recruit_index": 0,
                "state": "available",
                "result": {
                    "relevant_need": {
                        "build_identity": "banner",
                        "need_bases": ["assigned_but_no_viable_holder"],
                        "assigned_viable_count": 0,
                        "free_viable_backup_count": 0,
                        "contested_viable_backup_count": 0,
                        "candidate_plausible": True,
                    },
                    "relevant_need_matches": [{
                        "build_identity": "banner",
                        "need_bases": ["assigned_but_no_viable_holder"],
                        "assigned_viable_count": 0,
                        "free_viable_backup_count": 0,
                        "contested_viable_backup_count": 0,
                        "candidate_plausible": True,
                    }],
                    "other_company_gaps": [],
                    "artifact_signature": "sha256:private-need",
                },
            },
            {
                "recruit_index": 1,
                "state": "available",
                "result": {
                    "relevant_need": {
                        "build_identity": "bf_tank",
                        "need_bases": ["single_point_of_failure"],
                        "assigned_viable_count": 1,
                        "free_viable_backup_count": 0,
                        "contested_viable_backup_count": 0,
                        "candidate_plausible": True,
                    },
                    "relevant_need_matches": [],
                    "other_company_gaps": [],
                    "artifact_signature": "sha256:private-need-2",
                },
            },
            {
                "recruit_index": 2,
                "state": "available",
                "result": {
                    "relevant_need": None,
                    "relevant_need_matches": [],
                    "other_company_gaps": [],
                    "artifact_signature": "sha256:private-need-3",
                },
            },
        ],
    }
    if presentation_mutator is not None:
        presentation_mutator(presentation)
    monkeypatch.setattr(recruitment_view, "build_target_presentation", lambda **_kwargs: presentation)

    result = SimpleNamespace(
        roster=[],
        recruits=[object(), object(), object()],
        roles=[],
        campaign_identity=None,
        brother_identities={},
        source_fingerprint="sha256:source-private",
        configuration_fingerprints={},
        recruitment_analysis=[],
        assigned_builds={},
        diagnostics={},
        incremental_cache=SimpleNamespace(publication_signatures=lambda: {}),
        analysis=SimpleNamespace(
            company_intrinsic_coverage=[], company_intended_coverage=[], summaries=[]
        ),
        public_data={
            "recruits": [
                {
                    "Name": "Horic", "Title": "the Younger", "Background": "Farmhand",
                    "Level": 1, "Settlement": "Birkhaven", "HireCost": 430,
                    "DailyWage": 8, "TryoutDone": False,
                    "BackgroundSaveHash": "PRIVATE_BACKGROUND_1", "SourcePath": "C:/private/save.sav",
                },
                {
                    "Name": "Albrecht", "Title": "the Quiet", "Background": "Brawler",
                    "Level": 1, "Settlement": "Birkhaven", "HireCost": 510,
                    "DailyWage": 9, "TryoutDone": True,
                    "Traits": ["Tough"], "FutureRolls": {"HP": [4, 4, 4]},
                },
                {
                    "Name": "Ulrich", "Title": "", "Background": "Monk",
                    "Level": 1, "Settlement": "Dornheim", "HireCost": 320,
                    "DailyWage": 6, "TryoutDone": False,
                },
            ]
        },
    )
    return SimpleNamespace(
        coordinator=SimpleNamespace(last_success=SimpleNamespace(generation=7, job_id=77, result=result)),
        _command_lock=threading.RLock(),
    )


def test_recruitment_endpoint_handles_no_publication():
    app = SimpleNamespace(
        coordinator=SimpleNamespace(last_success=None),
        _command_lock=threading.RLock(),
    )
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")

    response = api.handle("GET", "/api/v1/recruitment", {"Host": HOST})

    assert response.status == 200
    assert decode(response)["data"] == {"available": False}


def test_recruitment_projects_intrinsic_top_potential_without_fabricating_prior_estimate(monkeypatch):
    api = LocalApplicationApi(_application(monkeypatch), origin=ORIGIN, token="capability")

    response = api.handle("GET", "/api/v1/recruitment", {"Host": HOST})
    payload = decode(response)["data"]
    horic = payload["settlements"][0]["candidates"][0]
    albrecht = payload["settlements"][0]["candidates"][1]

    assert response.status == 200
    assert payload["generation"] == 7
    assert payload["job_id"] == 77
    assert horic["top_potential"] == {
        "build_identity": "bf_tank",
        "role": "BF Tank",
        "state": "prior_only",
        "background_prior_pct": 72.0,
        "candidate_estimate_pct": None,
        "score_pct": 72.0,
    }
    assert horic["potential_availability"] == {"state": "available", "reason": None}
    assert all(row["candidate_estimate_pct"] is None for row in horic["potential"])
    assert horic["relevant_need"]["relevant"]["role"] == "Banner"
    assert horic["top_potential"]["role"] == "BF Tank"

    assert albrecht["top_potential"]["role"] == "Reach DPS"
    assert albrecht["top_potential"]["candidate_estimate_pct"] == 68.0
    assert next(row for row in albrecht["potential"] if row["role"] == "Banner")["background_prior_pct"] == 80.0
    assert next(row for row in albrecht["potential"] if row["role"] == "Reach DPS")["evidence"] == ["Tough"]


def test_recruitment_groups_settlements_and_strips_private_provenance(monkeypatch):
    api = LocalApplicationApi(_application(monkeypatch), origin=ORIGIN, token="capability")

    payload = decode(api.handle("GET", "/api/v1/recruitment", {"Host": HOST}))["data"]
    serialized = json.dumps(payload)

    assert [row["settlement"] for row in payload["settlements"]] == ["Birkhaven", "Dornheim"]
    assert payload["settlements"][0]["observation_summary"] == "2 candidates in current analysis"
    assert payload["settlements"][1]["observation_summary"] == "1 candidate in current analysis"
    for private in (
        "PRIVATE_BACKGROUND", "PRIVATE_TRAIT_HASH", "private-prior", "private-build",
        "private-need", "C:/private", "FutureRolls", "SourcePath", "artifact_signature",
        "save_hash", "applied_trait_save_hashes", "source-private",
    ):
        assert private not in serialized


def test_recruitment_static_contract_covers_settlement_browser_shortlist_and_responsiveness():
    page = (ROOT / "bbtool" / "app" / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "bbtool" / "app" / "static" / "recruitment.js").read_text(encoding="utf-8")
    app_js = (ROOT / "bbtool" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "bbtool" / "app" / "static" / "recruitment.css").read_text(encoding="utf-8")

    for marker in (
        'id="recruit-browser"', 'id="recruit-current-settlement-name"',
        'id="recruit-current-settlement-summary"', 'id="recruit-mobile-select"',
        'id="recruit-potential"', 'id="recruit-needs"', 'id="recruit-shortlist-chips"',
        'id="recruit-compare-grid"', "Potential, Relevant Need, and economics stay separate",
    ):
        assert marker in page
    assert 'href="/recruitment.css"' in page
    assert 'src="/recruitment.js"' in page
    assert "fetchData('/api/v1/recruitment')" in js
    assert "syncCurrentSettlement()" in js
    assert "const hysteresis = 24" in js
    assert "const scrollTop = browser.scrollTop" in js
    assert "browser.scrollTop = scrollTop" in js
    assert "loadedJobId" in js
    assert "top_potential" in js
    assert "potential_availability" in js
    assert "candidate_potential_unavailable" in js
    assert "candidate_potential_incomplete" in js
    assert "value === null || value === undefined || value === ''" in app_js
    assert "innerHTML" not in js
    assert "@media (max-width: 980px)" in css
    assert "@media (max-width: 720px)" in css
    assert "@media (max-width: 420px)" in css
    assert "overflow-x" not in css
    assert "minmax(0, 1fr)" in css


def test_recruitment_assets_are_fixed_local_routes(monkeypatch):
    api = LocalApplicationApi(_application(monkeypatch), origin=ORIGIN, token="capability")

    css = api.handle("GET", "/recruitment.css", {"Host": HOST})
    js = api.handle("GET", "/recruitment.js", {"Host": HOST})

    assert css.status == 200 and css.content_type == "text/css; charset=utf-8"
    assert js.status == 200 and js.content_type == "text/javascript; charset=utf-8"
    assert b"https://" not in css.body + js.body
    assert b"http://" not in css.body + js.body



def _unavailable_analysis(build_identity, reason="background_archetype_prior_disabled_pending_validation"):
    return {
        "build_identity": build_identity,
        "state": "unavailable",
        "reason": reason,
        "result": None,
    }


def test_recruitment_compacts_uniform_unavailability_and_preserves_backend_reason(monkeypatch):
    def mutate(presentation):
        presentation["recruitment"][0]["analyses"] = [
            _unavailable_analysis("bf_tank"),
            _unavailable_analysis("reach_dps"),
            _unavailable_analysis("banner"),
        ]
        presentation["relevant_roster_need"][0] = {
            "recruit_index": 0,
            "state": "unavailable",
            "result": None,
        }

    api = LocalApplicationApi(
        _application(monkeypatch, presentation_mutator=mutate),
        origin=ORIGIN,
        token="capability",
    )
    payload = decode(api.handle("GET", "/api/v1/recruitment", {"Host": HOST}))["data"]
    candidate = payload["settlements"][0]["candidates"][0]

    assert candidate["top_potential"] is None
    assert candidate["potential_availability"] == {
        "state": "unavailable",
        "reason": "background_archetype_prior_disabled_pending_validation",
    }
    assert {row["reason"] for row in candidate["potential"]} == {
        "background_archetype_prior_disabled_pending_validation"
    }
    assert candidate["relevant_need"] == {
        "state": "unavailable",
        "reason": "candidate_potential_unavailable",
        "upstream_reason": "background_archetype_prior_disabled_pending_validation",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }


def test_recruitment_distinguishes_company_coverage_unavailability(monkeypatch):
    def mutate(presentation):
        presentation["company"]["intent_available"] = False
        presentation["relevant_roster_need"][0] = {
            "recruit_index": 0,
            "state": "unavailable",
            "result": None,
        }

    api = LocalApplicationApi(
        _application(monkeypatch, presentation_mutator=mutate),
        origin=ORIGIN,
        token="capability",
    )
    payload = decode(api.handle("GET", "/api/v1/recruitment", {"Host": HOST}))["data"]
    candidate = payload["settlements"][0]["candidates"][0]

    assert candidate["potential_availability"]["state"] == "available"
    assert candidate["relevant_need"]["reason"] == "company_intent_coverage_unavailable"
    assert candidate["relevant_need"]["upstream_reason"] is None


def test_recruitment_preserves_partial_per_build_evidence(monkeypatch):
    def mutate(presentation):
        presentation["recruitment"][0]["analyses"][1] = _unavailable_analysis(
            "reach_dps", reason="background_identity_unavailable"
        )
        presentation["relevant_roster_need"][0] = {
            "recruit_index": 0,
            "state": "unavailable",
            "result": None,
        }

    api = LocalApplicationApi(
        _application(monkeypatch, presentation_mutator=mutate),
        origin=ORIGIN,
        token="capability",
    )
    payload = decode(api.handle("GET", "/api/v1/recruitment", {"Host": HOST}))["data"]
    candidate = payload["settlements"][0]["candidates"][0]

    assert candidate["potential_availability"] == {
        "state": "partial",
        "reason": "candidate_potential_partially_unavailable",
    }
    assert len(candidate["potential"]) == 3
    assert next(row for row in candidate["potential"] if row["role"] == "Reach DPS")["reason"] == "background_identity_unavailable"
    assert candidate["top_potential"]["role"] == "BF Tank"
    assert candidate["relevant_need"]["reason"] == "candidate_potential_incomplete"
