import io
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import zipfile

import pytest

from bbtool.app import debug_export
from bbtool.app.debug_export import build_debug_export

pytestmark = pytest.mark.unit


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


def test_exported_api_snapshots_redact_selected_save_and_user_state_roots(monkeypatch):
    selected_save = r"C:\Users\Private\Documents\Battle Brothers\savegames\quicksave.sav"
    user_state_root = Path(r"C:\Users\Private\AppData\Local\BB-Save-Toolkit")
    result = SimpleNamespace(projection_validation={"summary": {}}, warnings=[])
    publication = SimpleNamespace(
        generation=4,
        job_id=9,
        source_fingerprint="sha256:" + "1" * 64,
        configuration_fingerprints={"archetypes": "a", "classification": "b"},
        artifact_signatures={},
        result=result,
    )

    class Application:
        def __init__(self):
            self._command_lock = threading.RLock()
            self.coordinator = SimpleNamespace(last_success=publication)
            self.store = SimpleNamespace(root=user_state_root)

        def followed_save(self):
            return {
                "selected_path": selected_save,
                "name": "quicksave.sav",
                "available": True,
            }

        def last_result(self):
            return {
                "available": True,
                "warning": {
                    "code": "last_success_persistence_failed",
                    "message": (
                        f"timed out acquiring state lock "
                        f"{user_state_root / '.last-success.json.lock'}"
                    ),
                },
                "debug_selected_save_echo": f"source was {selected_save}",
            }

        def effective_archetypes(self):
            return {"roles": []}

    app = Application()
    monkeypatch.setattr(debug_export, "_analysis_payloads", lambda _result: _minimal_analysis_payloads())
    monkeypatch.setattr(debug_export, "_target_presentation", lambda _result, _hashes: {})
    monkeypatch.setattr(debug_export, "_runtime_diagnostics", lambda _app, _result: {})
    monkeypatch.setattr(debug_export, "build_company_brother_view", lambda _app: {"available": True, "generation": 4})
    monkeypatch.setattr(debug_export, "build_level_up_view", lambda _app: {"available": True, "generation": 4})
    monkeypatch.setattr(debug_export, "build_recruitment_view", lambda _app: {"available": True, "generation": 4})

    payload, _filename = build_debug_export(
        app,
        shell_builder=lambda: {
            "result": {"available": True},
            "debug_user_state_echo": f"root={user_state_root}",
        },
    )

    serialized_archive = payload.decode("latin1", errors="ignore")
    assert selected_save not in serialized_archive
    assert str(user_state_root) not in serialized_archive

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        analysis_result = json.loads(archive.read("api/analysis-result.json"))
        shell = json.loads(archive.read("api/shell.json"))
        manifest = json.loads(archive.read("manifest.json"))

    serialized = json.dumps({"analysis_result": analysis_result, "shell": shell})
    assert selected_save not in serialized
    assert str(user_state_root) not in serialized
    assert "<selected-save>" in serialized
    assert "<user-state>" in serialized
    assert analysis_result["warning"]["code"] == "last_success_persistence_failed"
    assert manifest["scope"]["api_path_redaction"]
