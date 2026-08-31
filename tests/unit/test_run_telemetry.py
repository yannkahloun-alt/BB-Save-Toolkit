from pathlib import Path
from types import SimpleNamespace

import bbtool.app.telemetry as telemetry


def _options(tmp_path: Path):
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"private-save-bytes")
    targets = tmp_path / "archetypes.json"
    targets.write_text('{"roles": []}', encoding="utf-8")
    classification = tmp_path / "classification.json"
    classification.write_text('{"thresholds": {}}', encoding="utf-8")
    return SimpleNamespace(
        save=save,
        targets=targets,
        classification=classification,
        out=tmp_path / "output",
    )


def test_run_metadata_records_reproducible_environment_and_hashes(tmp_path):
    options = _options(tmp_path)
    started = telemetry.start_resource_monitoring()
    try:
        metadata = telemetry.build_run_metadata(options)
    finally:
        telemetry.stop_resource_monitoring(started)

    assert metadata["format"] == "bbtool.run_metadata.v1"
    assert metadata["toolkit_version"] == "3.88"
    assert metadata["schemas"]["incremental_cache"] == "bb-incremental-v1"
    assert metadata["engines"] == {
        "role_projection": 6,
        "advisor": 4,
        "summary": 6,
    }
    assert metadata["input_save"]["path"] == str(options.save.resolve())
    assert metadata["input_save"]["size_bytes"] == len(b"private-save-bytes")
    assert len(metadata["input_save"]["sha256"]) == 64
    assert metadata["input_save"]["modified_at_utc"].endswith("+00:00")
    assert metadata["configuration"]["archetypes"]["path"] == str(
        options.targets.resolve()
    )
    assert len(metadata["configuration"]["archetypes"]["sha256"]) == 64
    assert metadata["execution"]["mode"] == "single-process"
    assert metadata["execution"]["configured_workers"] == 1
    assert metadata["cache"]["analysis_directory"] == str(options.out.resolve())
    assert metadata["resources"]["status"] == "available"
    assert metadata["resources"]["python_heap_peak_bytes"] is not None


def test_run_metadata_explicitly_marks_missing_files_and_memory_unavailable(
    tmp_path, monkeypatch
):
    options = SimpleNamespace(
        save=tmp_path / "missing.sav",
        targets=tmp_path / "missing-targets.json",
        classification=tmp_path / "missing-classification.json",
        out=tmp_path / "output",
    )
    monkeypatch.setattr(telemetry.tracemalloc, "is_tracing", lambda: False)

    metadata = telemetry.build_run_metadata(options)

    assert metadata["input_save"]["status"] == "unavailable"
    assert metadata["input_save"]["sha256"] is None
    assert metadata["configuration"]["classification"]["status"] == "unavailable"
    assert metadata["resources"] == {
        "python_heap_current_bytes": None,
        "python_heap_peak_bytes": None,
        "status": "unavailable",
    }


def test_run_header_and_resource_summary_are_compact(tmp_path, capsys):
    options = _options(tmp_path)
    started = telemetry.start_resource_monitoring()
    try:
        metadata = telemetry.build_run_metadata(options)
        telemetry.print_run_header(metadata)
        telemetry.print_resource_summary(metadata)
    finally:
        telemetry.stop_resource_monitoring(started)

    output = capsys.readouterr().out
    assert "Run metadata:" in output
    assert "toolkit v3.88" in output
    assert "single-process" in output
    assert "SHA-256" in output
    assert "engines role_projection=6 · advisor=4 · summary=6" in output
    assert "Peak Python memory:" in output
