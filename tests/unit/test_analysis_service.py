from types import SimpleNamespace

import pytest

import bbtool.app.analysis_service as service
import bbtool.app.runner as runner
import bbtool.save_parser as save_parser
from bbtool.app.analysis import AnalysisResult


class FakeCache:
    def __init__(self, manifest, *, enabled, previous_path):
        self.received = (manifest, enabled, previous_path)
        self.stats = SimpleNamespace(
            role_reused=1,
            role_computed=2,
        )
        self.miss_reasons = {"role_hash": 2}

    def get_validation_oracle(self, bro, role):
        return None

    def store_validation_oracle(self, bro, role, trajectory):
        return None

    def publication_signatures(self):
        return {
            "role_projection": [], "strategic_classification": [],
            "level_advisor": [],
        }


def _patch_pipeline(monkeypatch):
    roster = [SimpleNamespace(Name="A")]
    recruits = [{"Name": "Candidate"}]
    analysis = AnalysisResult(fits=[{"Role": "Tank"}], summaries=[{"Name": "A"}])
    monkeypatch.setattr(service, "ensure_references", lambda verbose=False: {"generated_dictionary": False})
    monkeypatch.setattr(service, "parse_roster_bytes", lambda content, diagnostics=None: roster)
    monkeypatch.setattr(service, "resolve_brother_identities", lambda *args: {})
    monkeypatch.setattr(service, "parse_recruits_bytes", lambda content, diagnostics=None: recruits)
    monkeypatch.setattr(service, "configure_engine", lambda: None)
    monkeypatch.setattr(service, "reset_profile", lambda: None)
    monkeypatch.setattr(service, "get_profile", lambda: {"project_role_calls": 2})
    monkeypatch.setattr(
        service, "public_brother_data", lambda bro: {"Name": bro.Name}
    )
    monkeypatch.setattr(
        service,
        "build_projection_validation",
        lambda *args: {
            "summary": {"comparisons": 1, "roll_range_violations": 0}
        },
    )
    monkeypatch.setattr(service, "IncrementalCache", FakeCache)
    monkeypatch.setattr(service, "analyze_brothers", lambda *args: analysis)
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
    return roster, recruits, analysis


def test_service_analyzes_bytes_without_path_identity_and_reports_contract(monkeypatch):
    roster, recruits, analysis = _patch_pipeline(monkeypatch)
    observed = []
    request = service.AnalysisServiceRequest(
        source=service.SaveSource(b"same bytes", "renamed.sav"),
        roles=[{"name": "Tank", "stats": {}}],
        classification={"invest": 80},
        cache=service.CompatibleCacheContext(
            manifest={"schema": "test"}, previous_path="provenance-only"
        ),
        on_progress=observed.append,
    )

    result = service.analyze_save(request)

    assert result.roster is roster
    assert result.campaign_identity.confidence == "unavailable"
    assert result.brother_identities == {}
    assert result.recruits is recruits
    assert result.analysis is analysis
    assert result.public_data["fits"] == analysis.fits
    assert result.public_data["company_intrinsic_coverage"] == []
    assert "FutureRolls" not in result.public_data["roster"][0]
    assert result.source_fingerprint.startswith("sha256:")
    assert set(result.configuration_fingerprints) == {"archetypes", "classification"}
    assert [event.stage for event in observed] == [
        "references", "campaign_identity", "roster", "recruits", "analysis",
        "validation", "recruitment_analysis",
    ]
    assert result.recruitment_analysis[0]["analyses"][0]["state"] == "unavailable"
    assert result.presentation_context["source_fingerprint"] == result.source_fingerprint
    assert "campaign_identity" not in result.public_data
    assert result.incremental_cache.received == (
        {"schema": "test"}, True, "provenance-only"
    )
    assert result.diagnostics["cache_miss_reasons"] == {"role_hash": 2}
    assert result.diagnostics["validation_projection"] == {
        "seeded_projection_calls": 1,
        "blind_cache_lookups": 1,
        "trajectory_cache_hits": 0,
        "trajectory_cache_misses": 0,
        "trajectory_seconds": 0.0,
        "oracle_reused": 0,
        "oracle_recomputed": 0,
    }
    assert result.timings["analysis"] >= 0
    assert result.timings["validation"] >= 0

    renamed = service.analyze_save(
        service.AnalysisServiceRequest(
            source=service.SaveSource(b"same bytes", "other-location.sav"),
            roles=request.roles,
            classification=request.classification,
        )
    )
    assert renamed.source_fingerprint == result.source_fingerprint


def test_exact_campaign_resolves_authoritative_assignments_for_analysis(monkeypatch):
    _patch_pipeline(monkeypatch)
    campaign = service.CampaignIdentity(25809, confidence="exact")
    monkeypatch.setattr(service, "parse_campaign_identity_bytes", lambda _: campaign)
    observed = []
    monkeypatch.setattr(
        service, "analyze_brothers",
        lambda *args: observed.append(args[5]) or AnalysisResult([], []),
    )
    assignments = {"campaign:25809/entity:1": {"status": "current"}}
    resolver_calls = []
    service.analyze_save(service.AnalysisServiceRequest(
        source=service.SaveSource(b"save"), roles=[{"name": "Tank"}],
        classification={},
        assigned_build_resolver=lambda identity: (
            resolver_calls.append(identity) or assignments
        ),
    ))

    assert resolver_calls == [campaign]
    assert observed == [assignments]


def test_unavailable_campaign_does_not_consume_assignment_provider(monkeypatch):
    _patch_pipeline(monkeypatch)
    calls = []
    observed = []
    monkeypatch.setattr(
        service, "analyze_brothers",
        lambda *args: observed.append(args[5]) or AnalysisResult([], []),
    )
    service.analyze_save(service.AnalysisServiceRequest(
        source=service.SaveSource(b"save"), roles=[{"name": "Tank"}],
        classification={},
        assigned_build_resolver=lambda identity: calls.append(identity) or {},
    ))

    assert calls == []
    assert observed == [None]


def test_service_wraps_parser_failure_as_structured_error(monkeypatch):
    monkeypatch.setattr(service, "ensure_references", lambda verbose=False: {})
    monkeypatch.setattr(
        service,
        "parse_roster_bytes",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bad save")),
    )

    with pytest.raises(service.AnalysisServiceError) as raised:
        service.analyze_save(
            service.AnalysisServiceRequest(
                source=service.SaveSource(b"broken"),
                roles=[{"name": "Tank"}],
                classification={},
            )
        )

    assert raised.value.as_dict() == {
        "code": "roster_failed",
        "stage": "roster",
        "message": "bad save",
    }


def test_service_cache_verification_failure_is_structured(monkeypatch):
    _patch_pipeline(monkeypatch)
    calls = iter([
        AnalysisResult(fits=[1], summaries=[]),
        AnalysisResult(fits=[2], summaries=[]),
    ])
    monkeypatch.setattr(service, "analyze_brothers", lambda *args: next(calls))
    monkeypatch.setattr(service, "first_difference", lambda *args: ("$.fits[0]", 1, 2))

    with pytest.raises(service.AnalysisServiceError) as raised:
        service.analyze_save(
            service.AnalysisServiceRequest(
                source=service.SaveSource(b"save"),
                roles=[{"name": "Tank"}],
                classification={},
                options=service.AnalysisServiceOptions(verify_cache=True),
            )
        )

    assert raised.value.code == "cache_verification_failed"
    assert raised.value.stage == "cache_verification"


def test_service_validation_drives_structured_roll_warning(monkeypatch):
    _patch_pipeline(monkeypatch)
    validation = {
        "summary": {"comparisons": 1, "roll_range_violations": 1}
    }
    monkeypatch.setattr(service, "build_projection_validation", lambda *args: validation)
    monkeypatch.setattr(
        service,
        "build_run_health",
        lambda *args, validation_payload=None, **kwargs: {
            "recoverable_parsing_failure_sample": [],
            "unresolved_references_relevant_to_save": 0,
            "unresolved_reference_sample": [],
            "validation_roll_range_violations": validation_payload["summary"][
                "roll_range_violations"
            ],
        },
    )

    result = service.analyze_save(
        service.AnalysisServiceRequest(
            source=service.SaveSource(b"save"),
            roles=[{"name": "Tank"}],
            classification={},
        )
    )

    assert result.projection_validation is validation
    assert result.warnings == [{"code": "roll_range_violations", "count": 1}]


def test_parser_path_entrypoints_are_only_byte_adapters(monkeypatch, tmp_path):
    path = tmp_path / "campaign.sav"
    path.write_bytes(b"save content")
    calls = []
    monkeypatch.setattr(
        save_parser,
        "parse_roster_bytes",
        lambda content, diagnostics=None: calls.append(("roster", content, diagnostics)) or [1],
    )
    monkeypatch.setattr(
        save_parser,
        "parse_recruits_bytes",
        lambda content, diagnostics=None: calls.append(("recruits", content, diagnostics)) or [2],
    )
    diagnostics = {"recoverable_failures": []}

    assert save_parser.parse_roster(path, diagnostics=diagnostics) == [1]
    assert save_parser.parse_recruits(path, diagnostics=diagnostics) == [2]
    assert calls == [
        ("roster", b"save content", diagnostics),
        ("recruits", b"save content", diagnostics),
    ]


def test_cli_request_and_direct_service_have_equivalent_public_results(
    monkeypatch, tmp_path, bro_factory, cfg
):
    save = tmp_path / "same.sav"
    save.write_bytes(b"same supplied content")
    bro = bro_factory(Level=11, LevelPoints=0, FutureRolls={})
    role = cfg.roles[0]
    classification = cfg.classification
    monkeypatch.setattr(service, "ensure_references", lambda verbose=False: {})
    monkeypatch.setattr(
        service, "parse_roster_bytes", lambda content, diagnostics=None: [bro]
    )
    monkeypatch.setattr(
        service, "parse_recruits_bytes", lambda content, diagnostics=None: []
    )
    options = SimpleNamespace(
        save=save,
        full_recompute=True,
        verify_cache=False,
    )
    config = SimpleNamespace(roles=[role], classification=classification)

    cli_result = service.analyze_save(
        runner._analysis_request(
            options,
            config,
            previous_manifest=None,
            previous_path=None,
        )
    )
    direct_result = service.analyze_save(
        service.AnalysisServiceRequest(
            source=service.SaveSource(save.read_bytes(), "transport-name.sav"),
            roles=[role],
            classification=classification,
            cache=service.CompatibleCacheContext(enabled=False),
        )
    )

    assert cli_result.public_data == direct_result.public_data
    assert cli_result.source_fingerprint == direct_result.source_fingerprint
