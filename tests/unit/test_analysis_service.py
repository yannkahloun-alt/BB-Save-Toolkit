from types import SimpleNamespace

import pytest

import bbtool.app.analysis_service as service
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


def _patch_pipeline(monkeypatch):
    roster = [SimpleNamespace(Name="A")]
    recruits = [{"Name": "Candidate"}]
    analysis = AnalysisResult(fits=[{"Role": "Tank"}], summaries=[{"Name": "A"}])
    monkeypatch.setattr(service, "ensure_references", lambda verbose=False: {"generated_dictionary": False})
    monkeypatch.setattr(service, "parse_roster_bytes", lambda content, diagnostics=None: roster)
    monkeypatch.setattr(service, "parse_recruits_bytes", lambda content, diagnostics=None: recruits)
    monkeypatch.setattr(service, "configure_engine", lambda: None)
    monkeypatch.setattr(service, "reset_profile", lambda: None)
    monkeypatch.setattr(service, "get_profile", lambda: {"project_role_calls": 2})
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
    assert result.recruits is recruits
    assert result.analysis is analysis
    assert result.public_data["fits"] == analysis.fits
    assert result.source_fingerprint.startswith("sha256:")
    assert set(result.configuration_fingerprints) == {"archetypes", "classification"}
    assert [event.stage for event in observed] == [
        "references", "roster", "recruits", "analysis"
    ]
    assert result.incremental_cache.received == (
        {"schema": "test"}, True, "provenance-only"
    )
    assert result.diagnostics["cache_miss_reasons"] == {"role_hash": 2}

    renamed = service.analyze_save(
        service.AnalysisServiceRequest(
            source=service.SaveSource(b"same bytes", "other-location.sav"),
            roles=request.roles,
            classification=request.classification,
        )
    )
    assert renamed.source_fingerprint == result.source_fingerprint


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
