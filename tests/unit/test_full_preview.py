import hashlib
import json
from pathlib import Path
import shutil

import pytest

from bbtool.app.full_preview import (
    FullPreviewError, FullPreviewMetadata, build_full_preview,
    load_approved_save, validate_full_preview_artifact,
)


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "tests" / "fixtures" / "reference_analysis"
META = FullPreviewMetadata("PR #10", "a" * 40, "2026-08-31T08:00:00Z", "3.87", True)


def _catalog(tmp_path: Path, *, digest: str | None = None) -> Path:
    save = tmp_path / "reference-save.sav"
    save.write_bytes(b"approved fixture")
    digest = digest or hashlib.sha256(save.read_bytes()).hexdigest()
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({
        "schema": "bbtool.approved_save_catalog.v1",
        "fixtures": [{
            "id": "reference-save", "path": save.name, "sha256": digest,
            "source": "issue attachment", "approval": "owner approved",
        }],
    }), encoding="utf-8")
    return path


def _run_dataset(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    shutil.copytree(DATASET, run)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    manifest["source"] = "reference-save.sav"
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    shutil.copy2(ROOT / "bbtool" / "report.css", run / "report.css")
    shutil.copy2(ROOT / "bbtool" / "report.js", run / "report.js")
    return run


def test_full_preview_publishes_only_validated_public_files(tmp_path):
    fixture = load_approved_save(_catalog(tmp_path), "reference-save")
    target = build_full_preview(_run_dataset(tmp_path), tmp_path / "site", META, fixture)

    html = (target / "index.html").read_text(encoding="utf-8")
    assert "Full application preview" in html
    assert "PR #10" in html and "a" * 40 in html
    assert fixture.sha256 in html
    assert "bbtool.reference_analysis.v1" in html
    assert "Incremental verification: yes" in html
    assert "Aldric" in html
    assert not list(target.glob("*.sav"))
    assert not list(target.glob("*debug*"))
    assert not list(target.glob("*incremental*"))
    assert not list(target.glob("*validation*"))


def test_committed_approved_save_matches_documented_fingerprint():
    fixture = load_approved_save(
        ROOT / "tests" / "fixtures" / "full_preview" / "catalog.json",
        "reference-save",
    )
    assert fixture.sha256 == "220294d33c363200a8a55b75458e2483af6d3b77e6ab3b99da8997fedc88e3ac"
    assert "issue #10" in fixture.source
    assert "owner" in fixture.approval.casefold()


def test_approved_save_rejects_digest_mismatch(tmp_path):
    with pytest.raises(FullPreviewError, match="SHA-256 mismatch"):
        load_approved_save(_catalog(tmp_path, digest="0" * 64), "reference-save")


def test_full_preview_rejects_run_from_another_save(tmp_path):
    fixture = load_approved_save(_catalog(tmp_path), "reference-save")
    run = _run_dataset(tmp_path)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    manifest["source"] = "other.sav"
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(FullPreviewError, match="does not match"):
        build_full_preview(run, tmp_path / "site", META, fixture)


def test_publication_validator_rejects_forbidden_run_artifacts(tmp_path):
    catalog = _catalog(tmp_path)
    fixture = load_approved_save(catalog, "reference-save")
    site = tmp_path / "site"
    build_full_preview(_run_dataset(tmp_path), site, META, fixture)
    (site / "preview-context.json").write_text(json.dumps({
        "schema": "bbtool.full_preview_context.v1",
        "destination": "pr-10/full",
        "fixture": fixture.identifier,
        "save_sha256": fixture.sha256,
        "source_sha": "a" * 40,
    }), encoding="utf-8")
    assert validate_full_preview_artifact(site, catalog)["destination"] == "pr-10/full"

    (site / fixture.identifier / "source.sav").write_bytes(b"forbidden")
    with pytest.raises(FullPreviewError, match="Forbidden"):
        validate_full_preview_artifact(site, catalog)


def test_publication_validator_rejects_self_declared_save_fingerprint(tmp_path):
    catalog = _catalog(tmp_path)
    fixture = load_approved_save(catalog, "reference-save")
    site = tmp_path / "site"
    build_full_preview(_run_dataset(tmp_path), site, META, fixture)
    context = {
        "schema": "bbtool.full_preview_context.v1",
        "destination": "pr-10/full",
        "fixture": fixture.identifier,
        "save_sha256": "f" * 64,
        "source_sha": "a" * 40,
    }
    (site / "preview-context.json").write_text(
        json.dumps(context), encoding="utf-8"
    )
    with pytest.raises(FullPreviewError, match="not approved"):
        validate_full_preview_artifact(site, catalog)


@pytest.mark.parametrize("asset", ["index.html", "report.css", "report.js"])
def test_publication_validator_rejects_future_rolls_in_every_asset(tmp_path, asset):
    catalog = _catalog(tmp_path)
    fixture = load_approved_save(catalog, "reference-save")
    site = tmp_path / "site"
    target = build_full_preview(_run_dataset(tmp_path), site, META, fixture)
    (site / "preview-context.json").write_text(json.dumps({
        "schema": "bbtool.full_preview_context.v1",
        "destination": "pr-10/full",
        "fixture": fixture.identifier,
        "save_sha256": fixture.sha256,
        "source_sha": "a" * 40,
    }), encoding="utf-8")
    with (target / asset).open("a", encoding="utf-8") as handle:
        handle.write('\nconst leaked = {"FutureRolls": [1, 2, 3]};')
    with pytest.raises(FullPreviewError, match="Forbidden.*content"):
        validate_full_preview_artifact(site, catalog)


def test_publication_validator_rejects_encoded_binary_blob(tmp_path):
    catalog = _catalog(tmp_path)
    fixture = load_approved_save(catalog, "reference-save")
    site = tmp_path / "site"
    target = build_full_preview(_run_dataset(tmp_path), site, META, fixture)
    (site / "preview-context.json").write_text(json.dumps({
        "schema": "bbtool.full_preview_context.v1",
        "destination": "pr-10/full",
        "fixture": fixture.identifier,
        "save_sha256": fixture.sha256,
        "source_sha": "a" * 40,
    }), encoding="utf-8")
    with (target / "report.js").open("a", encoding="utf-8") as handle:
        handle.write("\nconst encodedSave = '" + "A" * 4096 + "';")
    with pytest.raises(FullPreviewError, match="Forbidden.*content"):
        validate_full_preview_artifact(site, catalog)
