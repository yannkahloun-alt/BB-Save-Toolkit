import hashlib
import json
from pathlib import Path
import shutil

import pytest

from bbtool.app.cli import CliOptions, parse_args
import bbtool.app.main as app_main
import bbtool.app.render_only as render_only
from bbtool.app.render_only import RenderDatasetError, load_render_dataset, run_render_only
from bbtool.html_report import render_html_report


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


def _rewrite_payload_and_hash(source: Path, label: str, mutate) -> None:
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload_path = source / manifest["files"][label]["path"]
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    mutate(payload)
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    manifest["files"][label]["sha256"] = hashlib.sha256(
        payload_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


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


@pytest.mark.parametrize("label, mutation, missing", [
    ("role_fit", lambda rows: rows[0].pop("ProjectedFitPct"), "ProjectedFitPct"),
    ("classification", lambda rows: rows[0].pop("Category"), "Category"),
])
def test_renderer_fields_are_validated_before_output_creation(
    tmp_path, label, mutation, missing
):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(source, label, mutation)
    out = tmp_path / "out"
    with pytest.raises(
        RenderDatasetError,
        match=rf"renderer contract rejected.*{missing}",
    ):
        run_render_only(_options(source, out))
    assert not out.exists()


def test_renderer_field_types_are_validated_before_output_creation(tmp_path):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(
        source, "role_fit", lambda rows: rows[0].update(ProjectedFitPct="high")
    )
    out = tmp_path / "out"
    with pytest.raises(RenderDatasetError, match="renderer contract rejected"):
        run_render_only(_options(source, out))
    assert not out.exists()


def test_hidden_future_roll_key_is_rejected_in_every_public_payload(tmp_path):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(
        source,
        "archetypes",
        lambda payload: payload.update(FutureRolls={"HP": [4]}),
    )
    with pytest.raises(RenderDatasetError, match="must not contain FutureRolls"):
        load_render_dataset(source)


def test_future_rolls_text_in_a_display_value_is_allowed(tmp_path):
    source = _copy_fixture(tmp_path)
    _rewrite_payload_and_hash(
        source,
        "recruits",
        lambda rows: rows[0].update(Title="the FutureRolls Historian"),
    )
    dataset = load_render_dataset(source)
    assert dataset.recruits[0]["Title"] == "the FutureRolls Historian"


def test_render_only_packages_public_json_and_report_without_analysis(tmp_path):
    workspace, archive = run_render_only(_options(FIXTURE, tmp_path / "out"))
    assert archive.is_file()
    assert (workspace.root / "manifest.json").is_file()
    assert (workspace.root / "report.css").is_file()
    assert (workspace.root / "report.js").is_file()
    reports = list(workspace.root.glob("*-report.html"))
    assert len(reports) == 1
    html = reports[0].read_text(encoding="utf-8")
    dataset = load_render_dataset(FIXTURE)
    expected = render_html_report(
        workspace.source_save,
        dataset.bros,
        dataset.fits,
        dataset.summaries,
        dataset.roles,
        dataset.classification,
        generated_at=workspace.generated_at,
        recruits=dataset.recruits,
    )
    assert html == expected
    assert "Aldric" in html
    assert "Reference Hamlet" in html
