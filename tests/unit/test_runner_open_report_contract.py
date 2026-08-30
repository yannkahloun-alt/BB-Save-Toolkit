from pathlib import Path
from types import SimpleNamespace
import json

import bbtool.app.runner as runner


def test_runner_opens_generated_report_when_requested(monkeypatch, tmp_path):
    report = tmp_path / "report.html"
    report.write_text("<html></html>", encoding="utf-8")
    validation = tmp_path / "validation.json"
    validation.write_text(json.dumps({"summary": {"roll_range_violations": 0}}), encoding="utf-8")
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"archive")
    workspace = SimpleNamespace(root=tmp_path, source_save=tmp_path/"x.sav", base="x", generated_at="now")
    opts = SimpleNamespace(
        save=tmp_path/"x.sav", targets=Path("targets"), classification=Path("classification"),
        out=tmp_path, no_projection=False, open_report=True
    )
    monkeypatch.setattr(runner, "ensure_references", lambda verbose=False: {
        "generated_dictionary": False, "generated_backgrounds": False, "generated_perks": False
    })
    monkeypatch.setattr(runner, "print_reference_status", lambda x: None)
    monkeypatch.setattr(runner, "parse_roster", lambda p, **kwargs: [])
    monkeypatch.setattr(runner, "parse_recruits", lambda p, diagnostics=None: [])
    monkeypatch.setattr(runner, "create_workspace", lambda *a: workspace)
    monkeypatch.setattr(runner, "write_raw_inputs", lambda *a: None)
    monkeypatch.setattr(runner, "load_config", lambda *a: SimpleNamespace(roles=[], classification={}))
    monkeypatch.setattr(runner, "configure_engine", lambda: None)
    monkeypatch.setattr(runner, "reset_profile", lambda: None)
    monkeypatch.setattr(runner, "analyze_brothers", lambda *a: SimpleNamespace(fits=[], summaries=[]))
    monkeypatch.setattr(runner, "get_profile", lambda: {})
    monkeypatch.setattr(runner, "print_projection_profile", lambda x: None)
    monkeypatch.setattr(runner, "write_analysis_json", lambda *a: None)
    monkeypatch.setattr(runner, "write_html", lambda *a: report)
    monkeypatch.setattr(runner, "write_projection_validation", lambda *a: validation)
    monkeypatch.setattr(runner, "write_debug_bundle", lambda *a: Path("debug.json"))
    monkeypatch.setattr(runner, "finalize_debug_bundle_metadata", lambda *a: None)
    monkeypatch.setattr(runner, "archive_workspace", lambda *a: archive)
    opened = []
    monkeypatch.setattr(
        runner, "launch_report_server", lambda source: opened.append(source) or True
    )

    runner.run(opts)

    assert opened == [workspace.root]
