from types import SimpleNamespace
import threading

import bbtool.app.analysis_service as service
import bbtool.app.target_presentation as target_presentation
from bbtool.app import recruitment_view
from bbtool.app.analysis import AnalysisResult
from bbtool.app.recruitment_policy import RECRUITMENT_PRIOR_DISABLED_REASON


class _FakeCache:
    def __init__(self, manifest, *, enabled, previous_path):
        self.stats = SimpleNamespace(role_reused=0, role_computed=0)
        self.miss_reasons = {}

    def get_validation_oracle(self, bro, role):
        return None

    def store_validation_oracle(self, bro, role, trajectory):
        return None

    def publication_signatures(self):
        return {
            "role_projection": [],
            "strategic_classification": [],
            "level_advisor": [],
        }


def _fail_if_called(*_args, **_kwargs):
    raise AssertionError("production analysis must not invoke recruitment potential")


def test_production_analysis_does_not_run_background_archetype_prior(monkeypatch):
    recruits = [
        {"BackgroundSaveHash": f"{index:08X}", "TryoutDone": False}
        for index in range(86)
    ]
    roles = [
        {"id": f"build_{index}", "name": f"Build {index}", "stats": {}}
        for index in range(11)
    ]

    monkeypatch.setattr(service, "ensure_references", lambda verbose=False: {})
    monkeypatch.setattr(
        service,
        "parse_campaign_identity_bytes",
        lambda _content: service.CampaignIdentity(None, confidence="unavailable"),
    )
    monkeypatch.setattr(service, "parse_roster_bytes", lambda *args, **kwargs: [])
    monkeypatch.setattr(service, "resolve_brother_identities", lambda *args: {})
    monkeypatch.setattr(
        service, "parse_recruits_bytes", lambda *args, **kwargs: recruits
    )
    monkeypatch.setattr(service, "configure_engine", lambda: None)
    monkeypatch.setattr(service, "reset_profile", lambda: None)
    monkeypatch.setattr(service, "get_profile", lambda: {})
    monkeypatch.setattr(service, "IncrementalCache", _FakeCache)
    monkeypatch.setattr(
        service, "analyze_brothers", lambda *args: AnalysisResult([], [])
    )
    monkeypatch.setattr(
        service,
        "build_projection_validation",
        lambda *args: {"summary": {"comparisons": 0, "roll_range_violations": 0}},
    )
    monkeypatch.setattr(
        service,
        "build_run_health",
        lambda *args, **kwargs: {
            "recoverable_parsing_failure_sample": [],
            "unresolved_references_relevant_to_save": 0,
            "unresolved_reference_sample": [],
            "validation_roll_range_violations": 0,
        },
    )
    monkeypatch.setattr(
        target_presentation, "build_recruitment_presentation", _fail_if_called
    )
    monkeypatch.setattr(
        target_presentation, "recruit_candidate_estimate", _fail_if_called
    )

    result = service.analyze_save(
        service.AnalysisServiceRequest(
            source=service.SaveSource(b"real-save-shaped-workload"),
            roles=roles,
            classification={},
        )
    )

    assert len(result.recruitment_analysis) == 86
    assert all(len(row["analyses"]) == 11 for row in result.recruitment_analysis)
    assert all(
        analysis == {
            "build_identity": role["id"],
            "state": "unavailable",
            "reason": RECRUITMENT_PRIOR_DISABLED_REASON,
            "result": None,
        }
        for row in result.recruitment_analysis
        for analysis, role in zip(row["analyses"], roles, strict=True)
    )
    recruitment_event = result.progress_events[-1]
    assert recruitment_event.stage == "recruitment_analysis"
    assert recruitment_event.details == {
        "recruits": 86,
        "analytical_potential": "disabled_pending_validation",
    }


def test_disabled_potential_keeps_player_facing_relevant_need_unavailable(monkeypatch):
    presentation = {
        "builds": [{
            "build_identity": "bf_tank",
            "display_name": "BF Tank",
            "build_definition_hash": "sha256:build",
        }],
        "recruitment": [{
            "recruit_index": 0,
            "background_save_hash": "DEADBEEF",
            "analyses": [{
                "build_identity": "bf_tank",
                "state": "unavailable",
                "reason": RECRUITMENT_PRIOR_DISABLED_REASON,
                "result": None,
            }],
        }],
        "relevant_roster_need": [{
            "recruit_index": 0,
            "state": "unavailable",
            "result": None,
        }],
    }
    monkeypatch.setattr(
        recruitment_view, "build_target_presentation", lambda **_kwargs: presentation
    )
    result = SimpleNamespace(
        roster=[],
        recruits=[{}],
        roles=[],
        campaign_identity=None,
        brother_identities={},
        source_fingerprint="sha256:source",
        configuration_fingerprints={},
        recruitment_analysis=[],
        assigned_builds={},
        diagnostics={},
        incremental_cache=SimpleNamespace(publication_signatures=lambda: {}),
        analysis=SimpleNamespace(
            company_intrinsic_coverage=[], company_intended_coverage=[], summaries=[]
        ),
        public_data={"recruits": [{
            "Name": "Candidate",
            "Title": "",
            "Background": "Farmhand",
            "Level": 1,
            "Settlement": "Town",
            "HireCost": 300,
            "DailyWage": 6,
            "TryoutDone": False,
        }]},
    )
    application = SimpleNamespace(
        _command_lock=threading.RLock(),
        coordinator=SimpleNamespace(
            last_success=SimpleNamespace(generation=1, job_id=2, result=result)
        ),
    )

    payload = recruitment_view.build_recruitment_view(application)
    candidate = payload["settlements"][0]["candidates"][0]

    assert candidate["top_potential"] is None
    assert candidate["relevant_need"] == {
        "state": "unavailable",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }
