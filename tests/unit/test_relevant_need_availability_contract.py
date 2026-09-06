from __future__ import annotations

import threading
from types import SimpleNamespace

from bbtool.app import recruitment_view
from bbtool.app import target_presentation as presentation


def _analysis(state: str, *, result=None) -> dict:
    return {
        "build_identity": f"build:{state}",
        "state": state,
        "reason": "unavailable" if state == "unavailable" else None,
        "result": result,
    }


def _target(monkeypatch, analyses: list[dict], *, assigned_builds=None):
    calls = []

    def fake_relevant_need(*args, **kwargs):
        calls.append((args, kwargs))
        return {"schema": "bbtool.relevant_roster_need.v1", "marker": True}

    monkeypatch.setattr(
        presentation, "build_relevant_roster_need", fake_relevant_need
    )
    payload = presentation.build_target_presentation(
        bros=[], recruits=[{}], roles=[], analysis_health={},
        campaign_identity=None, brother_identities={},
        source_fingerprint="sha256:" + "a" * 64,
        configuration_fingerprints={},
        recruitment_analysis=[{
            "recruit_index": 0,
            "background_save_hash": None,
            "analyses": analyses,
        }],
        artifact_hashes={key: "fixture" for key in presentation.BOUND_ARTIFACTS},
        result_signatures={}, company_intrinsic_coverage=[], summaries=[],
        assigned_builds=assigned_builds, company_intended_coverage=[],
    )
    return payload["relevant_roster_need"][0], calls


def test_candidate_potential_requires_complete_supported_evidence():
    prior = _analysis("prior_only", result={})
    known = _analysis("known_evidence_estimate", result={})
    unavailable = _analysis("unavailable", result=None)

    assert not presentation._candidate_potential_available([])
    assert not presentation._candidate_potential_available([unavailable])
    assert not presentation._candidate_potential_available([prior, unavailable])
    assert presentation._candidate_potential_available([prior, known])


def test_target_relevant_need_fails_closed_without_complete_candidate_evidence(monkeypatch):
    unavailable, calls = _target(
        monkeypatch,
        [_analysis("unavailable", result=None)],
        assigned_builds={},
    )
    assert unavailable == {
        "recruit_index": 0,
        "state": "unavailable",
        "result": None,
    }
    assert calls == []

    partial, calls = _target(
        monkeypatch,
        [
            _analysis("prior_only", result={}),
            _analysis("unavailable", result=None),
        ],
        assigned_builds={},
    )
    assert partial["state"] == "unavailable"
    assert partial["result"] is None
    assert calls == []


def test_target_relevant_need_requires_candidate_and_company_evidence(monkeypatch):
    available, calls = _target(
        monkeypatch,
        [
            _analysis("prior_only", result={}),
            _analysis("known_evidence_estimate", result={}),
        ],
        assigned_builds={},
    )
    assert available["state"] == "available"
    assert available["result"]["marker"] is True
    assert len(calls) == 1

    without_intent, calls = _target(
        monkeypatch,
        [_analysis("prior_only", result={})],
        assigned_builds=None,
    )
    assert without_intent["state"] == "unavailable"
    assert without_intent["result"] is None
    assert calls == []


def test_recruitment_view_consumes_target_need_state_without_reinferring(monkeypatch):
    result = SimpleNamespace(
        diagnostics={}, roster=[], recruits=[], roles=[], campaign_identity=None,
        brother_identities={}, source_fingerprint="sha256:" + "b" * 64,
        configuration_fingerprints={}, recruitment_analysis=[],
        incremental_cache=SimpleNamespace(publication_signatures=lambda: {}),
        analysis=SimpleNamespace(
            company_intrinsic_coverage=[], summaries=[], company_intended_coverage=[]
        ),
        assigned_builds={},
        public_data={"recruits": [{"Name": "Candidate", "Settlement": "Town"}]},
    )
    application = SimpleNamespace(
        _command_lock=threading.RLock(),
        coordinator=SimpleNamespace(last_success=SimpleNamespace(
            result=result, generation=7, job_id="job-7"
        )),
    )
    monkeypatch.setattr(
        recruitment_view,
        "build_target_presentation",
        lambda **kwargs: {
            "builds": [{"build_identity": "build:test", "display_name": "Test"}],
            "recruitment": [{
                "recruit_index": 0,
                "analyses": [{
                    "build_identity": "build:test",
                    "state": "unavailable",
                    "reason": "disabled",
                    "result": None,
                }],
            }],
            "relevant_roster_need": [{
                "recruit_index": 0,
                "state": "available",
                "result": {
                    "relevant_need": None,
                    "relevant_need_matches": [],
                    "other_company_gaps": [],
                },
            }],
        },
    )

    view = recruitment_view.build_recruitment_view(application)
    candidate = view["settlements"][0]["candidates"][0]
    assert candidate["relevant_need"] == {
        "state": "available",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }
