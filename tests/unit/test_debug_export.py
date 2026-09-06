import hashlib
import io
import json
import threading
from types import SimpleNamespace
import zipfile

import pytest

from bbtool.app import debug_export
from bbtool.app.app_server import LocalApplicationApi
from bbtool.app.debug_export import (
    DEBUG_EXPORT_SCHEMA,
    DIAGNOSTIC_INVENTORY_SCHEMA,
    build_debug_export,
    build_diagnostic_inventory,
)


pytestmark = pytest.mark.unit
ORIGIN = "http://127.0.0.1:48123"
HOST = "127.0.0.1:48123"


def _decode_json_member(archive, name):
    return json.loads(archive.read(name))


def test_diagnostic_inventory_exposes_unknown_unavailable_reasons_and_warnings():
    inventory = build_diagnostic_inventory({
        "api/company-brother.json": {
            "available": True,
            "brothers": [{
                "snapshot": {"Background": "Unknown [0x1234]"},
                "mechanical_facts": [{
                    "name": "Live Initiative",
                    "status": "unavailable",
                    "value": None,
                    "reason": "live_initiative_not_exposed",
                }],
            }],
        },
        "api/shell.json": {
            "analysis_health": {
                "status": "degraded",
                "warning_categories": [
                    {"code": "unresolved_backgrounds", "count": 1}
                ],
            }
        },
    })

    assert inventory["schema"] == DIAGNOSTIC_INVENTORY_SCHEMA
    findings = {
        (item["source"], item["path"], item["category"])
        for item in inventory["findings"]
    }
    assert (
        "api/company-brother.json",
        "$.brothers[0].snapshot.Background",
        "unknown",
    ) in findings
    assert (
        "api/company-brother.json",
        "$.brothers[0].mechanical_facts[0].status",
        "unavailable",
    ) in findings
    assert (
        "api/company-brother.json",
        "$.brothers[0].mechanical_facts[0].value",
        "null_with_incomplete_state",
    ) in findings
    assert (
        "api/company-brother.json",
        "$.brothers[0].mechanical_facts[0].reason",
        "reason",
    ) in findings
    assert (
        "api/shell.json",
        "$.analysis_health.status",
        "degraded",
    ) in findings
    assert any(
        item["category"] == "warning_or_error"
        and item["path"] == "$.analysis_health.warning_categories"
        for item in inventory["findings"]
    )


def test_debug_export_is_generation_bound_cli_equivalent_and_path_redacted(monkeypatch):
    private_path = r"C:\Users\Private\Documents\Battle Brothers\savegames\quicksave.sav"
    fits = [{
        "BrotherID": "human:1",
        "Role": "Nimble DPS",
        "ProjectedFitPct": 81.5,
        "ProjectedComponents": {},
        "ProjectedRanges": {},
    }]
    public_data = {
        "roster": [{
            "BrotherID": "human:1",
            "Name": "Debug Bro",
            "Background": "Unknown [0x1234]",
        }],
        "recruits": [],
        "fits": fits,
        "summaries": [{
            "BrotherID": "human:1",
            "BestRole": "Nimble DPS",
            "ProjectedFitPct": 81.5,
        }],
    }
    result = SimpleNamespace(
        public_data=public_data,
        roster=[],
        recruits=[],
        roles=[{"id": "nimble_dps", "name": "Nimble DPS", "stats": {}}],
        classification={"invest": 70},
        diagnostics={
            "run_health": {
                "result_affecting_warnings": 1,
                "unresolved_references_relevant_to_save": 1,
                "unresolved_backgrounds_relevant_to_save": 1,
            }
        },
        campaign_identity=None,
        brother_identities={},
        source_fingerprint="sha256:" + "1" * 64,
        configuration_fingerprints={
            "archetypes": "sha256:" + "2" * 64,
            "classification": "sha256:" + "3" * 64,
        },
        recruitment_analysis=[],
        incremental_cache=SimpleNamespace(publication_signatures=lambda: {}),
        analysis=SimpleNamespace(
            company_intrinsic_coverage=[],
            company_intended_coverage=[],
            summaries=public_data["summaries"],
            fits=fits,
        ),
        assigned_builds={},
        projection_validation={
            "summary": {"comparisons": 0, "roll_range_violations": 0}
        },
        warnings=[{"code": "unresolved_backgrounds"}],
    )
    publication = SimpleNamespace(
        generation=9,
        job_id=17,
        source_fingerprint=result.source_fingerprint,
        configuration_fingerprints=result.configuration_fingerprints,
        artifact_signatures={"role_projection": "sha256:signature"},
        result=result,
    )

    class Application:
        def __init__(self):
            self._command_lock = threading.RLock()
            self.coordinator = SimpleNamespace(
                last_success=publication,
                desired_job_id=17,
            )

        def followed_save(self):
            return {
                "revision": 2,
                "selected_path": private_path,
                "name": "quicksave.sav",
                "available": False,
                "warning": {
                    "code": "selected_save_unavailable",
                    "message": f"cannot read {private_path}",
                },
            }

        def last_result(self):
            return {
                "available": True,
                "freshness": {
                    "status": "current",
                    "generation": 9,
                    "represented_source_fingerprint": result.source_fingerprint,
                    "represented_configuration_fingerprints": result.configuration_fingerprints,
                },
                "warnings": result.warnings,
                "data": result.public_data,
            }

        def effective_archetypes(self):
            return {
                "revision": 4,
                "roles": result.roles,
                "definition_hashes": {"nimble_dps": "sha256:live"},
            }

    monkeypatch.setattr(
        debug_export,
        "build_target_presentation",
        lambda **kwargs: {
            "schema": "bbtool.target_presentation.v1",
            "publication": {
                "provenance": {
                    "artifact_hashes": dict(kwargs["artifact_hashes"]),
                    "source_fingerprint": kwargs["source_fingerprint"],
                }
            },
            "company": {},
        },
    )
    monkeypatch.setattr(
        debug_export,
        "build_company_brother_view",
        lambda _app: {
            "available": True,
            "generation": 9,
            "brothers": [{
                "snapshot": {"Background": "Unknown [0x1234]"},
                "mechanical_facts": [{
                    "name": "Live Initiative",
                    "status": "unavailable",
                    "value": None,
                    "reason": "live_initiative_not_exposed",
                }],
            }],
        },
    )
    monkeypatch.setattr(
        debug_export,
        "build_level_up_view",
        lambda _app: {"available": True, "generation": 9, "decisions": []},
    )
    monkeypatch.setattr(
        debug_export,
        "build_recruitment_view",
        lambda _app: {
            "available": True,
            "generation": 9,
            "settlements": [],
        },
    )

    shell = {
        "followed_save": {
            "name": "quicksave.sav",
            "available": False,
            "freshness": {"status": "unavailable", "reason": "save_missing"},
        },
        "result": {"available": True, "freshness": {"status": "current"}},
        "analysis_health": {"status": "degraded"},
        "active_job": None,
    }
    payload, filename = build_debug_export(
        Application(), shell_builder=lambda: shell
    )

    assert filename == "BB-Save-Toolkit-debug-json-generation-9.zip"
    assert private_path.encode() not in payload
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = set(archive.namelist())
        expected = {
            "analysis/roster.json",
            "analysis/recruits.json",
            "analysis/role-fit.json",
            "analysis/classification.json",
            "analysis/archetypes.json",
            "analysis/classification-config.json",
            "analysis/analysis-health.json",
            "analysis/target-presentation.json",
            "analysis/projection-validation.json",
            "api/shell.json",
            "api/followed-save.json",
            "api/analysis-result.json",
            "api/company-brother.json",
            "api/level-up.json",
            "api/recruitment.json",
            "api/effective-archetypes.json",
            "diagnostic-inventory.json",
            "manifest.json",
        }
        assert names == expected
        assert all(not name.lower().endswith(".sav") for name in names)

        roster = _decode_json_member(archive, "analysis/roster.json")
        role_fit = _decode_json_member(archive, "analysis/role-fit.json")
        followed = _decode_json_member(archive, "api/followed-save.json")
        inventory = _decode_json_member(archive, "diagnostic-inventory.json")
        manifest = _decode_json_member(archive, "manifest.json")
        presentation = _decode_json_member(
            archive, "analysis/target-presentation.json"
        )

        assert roster == public_data["roster"]
        assert role_fit[0]["ProjectedFitPct"] == 81.5
        assert "ProjectedComponentSummary" in role_fit[0]
        assert followed["selected_path"] == "<redacted>"
        assert followed["selected_path_redacted"] is True
        assert private_path not in json.dumps(followed)
        assert inventory["schema"] == DIAGNOSTIC_INVENTORY_SCHEMA
        assert any(
            finding["source"] == "api/company-brother.json"
            and finding["path"] == "$.brothers[0].mechanical_facts[0].status"
            and finding["category"] == "unavailable"
            for finding in inventory["findings"]
        )

        assert manifest["schema"] == DEBUG_EXPORT_SCHEMA
        assert manifest["publication"]["generation"] == 9
        assert manifest["publication"]["job_id"] == 17
        assert manifest["publication"]["source_fingerprint"] == result.source_fingerprint
        assert manifest["privacy"]["save_bytes_included"] is False
        assert manifest["privacy"]["selected_save_path_included"] is False
        for member, metadata in manifest["files"].items():
            data = archive.read(member)
            assert metadata["bytes"] == len(data)
            assert metadata["sha256"] == hashlib.sha256(data).hexdigest()

        artifact_hashes = presentation["publication"]["provenance"]["artifact_hashes"]
        assert artifact_hashes["roster"] == hashlib.sha256(
            archive.read("analysis/roster.json")
        ).hexdigest()
        assert artifact_hashes["role_fit"] == hashlib.sha256(
            archive.read("analysis/role-fit.json")
        ).hexdigest()


def test_debug_export_endpoint_is_zip_download_and_requires_publication(monkeypatch):
    class App:
        def __init__(self, publication):
            self.coordinator = SimpleNamespace(last_success=publication)
            self._command_lock = threading.RLock()

    empty = LocalApplicationApi(App(None), origin=ORIGIN, token="capability")
    unavailable = empty.handle("GET", "/api/v1/debug-export", {"Host": HOST})
    assert unavailable.status == 409
    assert json.loads(unavailable.body)["error"]["code"] == "analysis_unavailable"

    publication = SimpleNamespace(generation=5)
    app = App(publication)
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    monkeypatch.setattr(
        "bbtool.app.app_server.build_debug_export",
        lambda application, shell_builder: (b"PKdebug", "debug-generation-5.zip"),
    )
    monkeypatch.setattr(api, "_shell_state", lambda: {"result": {"available": True}})

    response = api.handle("GET", "/api/v1/debug-export", {"Host": HOST})
    assert response.status == 200
    assert response.body == b"PKdebug"
    assert response.content_type == "application/zip"
    assert response.headers["Content-Disposition"] == (
        'attachment; filename="debug-generation-5.zip"'
    )


def test_local_app_static_shell_exposes_disabled_then_downloadable_debug_control():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    page = (root / "bbtool" / "app" / "static" / "index.html").read_text(
        encoding="utf-8"
    )
    script = (root / "bbtool" / "app" / "static" / "app.js").read_text(
        encoding="utf-8"
    )

    assert 'id="debug-export-button"' in page
    assert "Export debug JSON" in page
    assert 'id="debug-export-button"' in page and "disabled" in page
    assert "'/api/v1/debug-export'" in script
    assert "debug-export-button" in script
    assert "state.result?.available" in script
