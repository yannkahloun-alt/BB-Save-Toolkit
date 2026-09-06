import io
import json
import threading
from types import SimpleNamespace
import zipfile

import pytest

from bbtool.app import debug_export
from bbtool.app.app_server import LocalApplicationApi
from bbtool.app.debug_export import DebugExportGenerationChanged, build_debug_export

pytestmark = pytest.mark.unit
ORIGIN = "http://127.0.0.1:48123"
HOST = "127.0.0.1:48123"


def _minimal_analysis_payloads():
    return {
        "roster": [],
        "recruits": [],
        "role_fit": [],
        "classification": [],
        "archetypes": {"roles": []},
        "classification_config": {},
        "analysis_health": {"schema": "bbtool.analysis_health.v1", "status": "healthy"},
    }


def test_debug_export_aborts_if_publication_changes_mid_capture(monkeypatch):
    result = SimpleNamespace(projection_validation={"summary": {}}, warnings=[])
    first = SimpleNamespace(
        generation=3,
        job_id=7,
        source_fingerprint="sha256:" + "1" * 64,
        configuration_fingerprints={"archetypes": "a", "classification": "b"},
        artifact_signatures={},
        result=result,
    )
    second = SimpleNamespace(
        generation=4,
        job_id=8,
        source_fingerprint="sha256:" + "2" * 64,
        configuration_fingerprints={"archetypes": "c", "classification": "d"},
        artifact_signatures={},
        result=result,
    )

    class Application:
        def __init__(self):
            self._command_lock = threading.RLock()
            self.coordinator = SimpleNamespace(last_success=first)

        def followed_save(self):
            return {"selected_path": None, "available": True, "name": "quicksave.sav"}

        def last_result(self):
            return {"available": True}

        def effective_archetypes(self):
            return {"roles": []}

    app = Application()
    monkeypatch.setattr(debug_export, "_analysis_payloads", lambda _result: _minimal_analysis_payloads())
    monkeypatch.setattr(debug_export, "_target_presentation", lambda _result, _hashes: {})
    monkeypatch.setattr(debug_export, "_runtime_diagnostics", lambda _app, _result: {})
    monkeypatch.setattr(debug_export, "build_company_brother_view", lambda _app: {"available": True, "generation": 3})
    monkeypatch.setattr(debug_export, "build_level_up_view", lambda _app: {"available": True, "generation": 3})
    monkeypatch.setattr(debug_export, "build_recruitment_view", lambda _app: {"available": True, "generation": 3})

    def shell_builder():
        app.coordinator.last_success = second
        return {"result": {"available": True}}

    with pytest.raises(DebugExportGenerationChanged):
        build_debug_export(app, shell_builder=shell_builder)


def test_runtime_diagnostics_exclude_reference_paths_and_redact_selected_save():
    private_save = r"C:\Users\Private\Documents\Battle Brothers\savegames\quicksave.sav"
    result = SimpleNamespace(
        diagnostics={
            "parse": {
                "recoverable_failures": [
                    {
                        "kind": "example",
                        "message": f"read failed for {private_save}",
                    }
                ]
            },
            "run_health": {
                "result_affecting_warnings": 1,
                "unresolved_reference_sample": ["Unknown [0x1234]"],
            },
            "projection_profile": {"trajectory_cache_hits": 12},
            "validation_projection": {"trajectory_seconds": 0.25},
            "cache_miss_reasons": {"brother_state_changed": 2},
            "references": {
                "cache_directory": r"C:\Users\Private\AppData\Local\reference-cache",
            },
        },
        timings={"analysis": 5.2, "validation": 0.1, "total": 5.5},
        warnings=[{"code": "unresolved_references"}],
    )
    app = SimpleNamespace(
        followed_save=lambda: {"selected_path": private_save}
    )

    payload = debug_export._runtime_diagnostics(app, result)
    serialized = json.dumps(payload)

    assert payload["timings"]["analysis"] == 5.2
    assert payload["projection_profile"]["trajectory_cache_hits"] == 12
    assert payload["warnings"] == [{"code": "unresolved_references"}]
    assert "references" not in {key for key in payload if key != "excluded"}
    assert payload["excluded"]["references"]
    assert private_save not in serialized
    assert "<selected-save>" in serialized
    assert "reference-cache" not in serialized


def test_debug_export_generation_conflict_maps_to_retryable_http_conflict(monkeypatch):
    publication = SimpleNamespace(generation=2)
    app = SimpleNamespace(
        coordinator=SimpleNamespace(last_success=publication),
        _command_lock=threading.RLock(),
    )
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")

    def changed(_application, shell_builder):
        raise DebugExportGenerationChanged("changed")

    monkeypatch.setattr("bbtool.app.app_server.build_debug_export", changed)

    response = api.handle(
        "GET",
        "/api/v1/debug-export",
        {"Host": HOST, "X-BBST-Session": "capability"},
    )
    payload = json.loads(response.body)

    assert response.status == 409
    assert payload["error"]["code"] == "debug_export_generation_changed"
    assert "retry" in payload["error"]["message"]


def test_debug_export_endpoint_returns_zip_only_with_session_capability(monkeypatch):
    publication = SimpleNamespace(generation=5)
    app = SimpleNamespace(
        coordinator=SimpleNamespace(last_success=publication),
        _command_lock=threading.RLock(),
    )
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    called = []

    def builder(application, shell_builder):
        called.append(application)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as target:
            target.writestr("manifest.json", "{}")
        return archive.getvalue(), "debug-generation-5.zip"

    monkeypatch.setattr("bbtool.app.app_server.build_debug_export", builder)

    denied = api.handle("GET", "/api/v1/debug-export", {"Host": HOST})
    assert denied.status == 403
    assert not called

    allowed = api.handle(
        "GET",
        "/api/v1/debug-export",
        {"Host": HOST, "X-BBST-Session": "capability"},
    )
    assert allowed.status == 200
    assert allowed.content_type == "application/zip"
    assert called == [app]


def test_path_redaction_survives_unreadable_followed_save_state():
    private_root = r"C:\Users\Private\AppData\Local\BB-Save-Toolkit"

    class Application:
        store = SimpleNamespace(root=private_root)

        @staticmethod
        def followed_save():
            raise RuntimeError("preferences unreadable")

    app = Application()
    snapshot = {
        "warning": {
            "code": "last_success_persistence_failed",
            "message": f"timed out acquiring state lock {private_root}\\.last-success.json.lock",
        }
    }
    redacted = debug_export._redact_known_local_paths(app, snapshot)

    assert redacted["warning"]["code"] == "last_success_persistence_failed"
    assert private_root not in json.dumps(redacted)
    assert "<user-state>" in redacted["warning"]["message"]

    result = SimpleNamespace(
        diagnostics={"run_health": {"result_affecting_warnings": 0}},
        timings={"total": 1.25},
        warnings=[snapshot["warning"]],
    )
    runtime = debug_export._runtime_diagnostics(app, result)
    serialized_runtime = json.dumps(runtime)

    assert runtime["timings"]["total"] == 1.25
    assert private_root not in serialized_runtime
    assert "<user-state>" in serialized_runtime
