import hashlib
import json
from pathlib import Path
import shutil

import pytest

from bbtool.app.cli import CliOptions, parse_args
import bbtool.app.main as app_main
import bbtool.app.render_only as render_only
from bbtool.app.render_only import RenderDatasetError, load_render_dataset, run_render_only


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "reference_analysis"


def _options(source: Path, out: Path) -> CliOptions:
    return CliOptions(
        save=None, targets=Path("unused"), classification=Path("unused"),
        out=out, no_projection=False, open_report=False,
        render_only=source,
    )


def _copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "dataset"
    shutil.copytree(FIXTURE, target)
    return target


def test_cli_accepts_render_only_without_save():
    options = parse_args(["--render-only", str(FIXTURE)])
    assert options.save is None
    assert options.render_only == FIXTURE


def test_cli_rejects_analysis_flags_in_render_only(capsys):
    with pytest.raises(SystemExit):
        parse_args(["--render-only", str(FIXTURE), "--verify-cache"])
    assert "cannot be used with --render-only" in capsys.readouterr().err


def test_main_dispatches_render_only_without_loading_analysis_runner(monkeypatch):
    calls = []
    monkeypatch.setattr(render_only, "run_render_only", lambda options: calls.append(options))
    app_main.main(["--render-only", str(FIXTURE)])
    assert len(calls) == 1
    assert calls[0].render_only == FIXTURE


def test_load_render_dataset_validates_relations_and_builds_brothers():
    dataset = load_render_dataset(FIXTURE)
    assert len(dataset.bros) == 5
    assert dataset.bros[0].BrotherID.startswith("human:")
    assert dataset.roles
    assert dataset.fits


@pytest.mark.parametrize("mutation, message", [
    (lambda manifest: manifest.update(schema="unknown.v9"), "unsupported schema"),
    (lambda manifest: manifest["files"].pop("roster"), "manifest files mismatch"),
])
def test_load_render_dataset_rejects_incompatible_manifest(tmp_path, mutation, message):
    source = _copy_fixture(tmp_path)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutation(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RenderDatasetError, match=message):
        load_render_dataset(source)


def test_load_render_dataset_rejects_corrupt_file_before_render(tmp_path):
    source = _copy_fixture(tmp_path)
    (source / "reference-roster.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(RenderDatasetError, match="SHA-256 mismatch for roster"):
        load_render_dataset(source)

    out = tmp_path / "out"
    with pytest.raises(RenderDatasetError, match="SHA-256 mismatch for roster"):
        run_render_only(_options(source, out))
    assert not out.exists()


def test_load_render_dataset_reports_malformed_json_with_matching_hash(tmp_path):
    source = _copy_fixture(tmp_path)
    roster = source / "reference-roster.json"
    roster.write_text("{broken", encoding="utf-8")
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["roster"]["sha256"] = hashlib.sha256(roster.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RenderDatasetError, match="malformed JSON in roster"):
        load_render_dataset(source)


def test_render_only_packages_public_json_and_report_without_analysis(tmp_path):
    workspace, archive = run_render_only(_options(FIXTURE, tmp_path / "out"))
    assert archive.is_file()
    assert (workspace.root / "manifest.json").is_file()
    assert (workspace.root / "report.css").is_file()
    assert (workspace.root / "report.js").is_file()
    reports = list(workspace.root.glob("*-report.html"))
    assert len(reports) == 1
    html = reports[0].read_text(encoding="utf-8")
    assert "Aldric" in html
    assert "Reference Hamlet" in html
