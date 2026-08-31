"""Approved-save validation and safe full-application preview packaging."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
import hashlib
import json
from pathlib import Path
import re
import shutil

from .render_only import DATASET_SCHEMA, load_render_dataset
from .report_server import render_served_report


APPROVED_SAVE_CATALOG_SCHEMA = "bbtool.approved_save_catalog.v1"
PREVIEW_CONTEXT_SCHEMA = "bbtool.full_preview_context.v1"
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DESTINATION = re.compile(r"^(?:pr-[0-9]+|ref-[a-z0-9._-]+)/full$")
_FORBIDDEN_PUBLICATION_NAMES = (
    ".sav", ".zip", "debug", "incremental", "validation", "cache", "log",
)


class FullPreviewError(ValueError):
    """A full-preview input or publication payload is unsafe or invalid."""


@dataclass(frozen=True)
class ApprovedSave:
    identifier: str
    path: Path
    sha256: str
    source: str
    approval: str


@dataclass(frozen=True)
class FullPreviewMetadata:
    source_label: str
    source_sha: str
    generated_at: str
    toolkit_version: str
    incremental_verified: bool


def _read_json(path: Path, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FullPreviewError(f"Invalid {label} {path}: {exc}") from exc


def load_approved_save(catalog_path: Path, fixture_id: str) -> ApprovedSave:
    """Resolve one allowlisted save and verify its immutable fingerprint."""
    catalog_path = catalog_path.resolve()
    catalog = _read_json(catalog_path, "approved-save catalog")
    if not isinstance(catalog, dict) or catalog.get("schema") != APPROVED_SAVE_CATALOG_SCHEMA:
        raise FullPreviewError("Unsupported approved-save catalog schema")
    fixtures = catalog.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise FullPreviewError("Approved-save catalog must contain fixtures")
    matches = [row for row in fixtures if isinstance(row, dict) and row.get("id") == fixture_id]
    if len(matches) != 1 or not _SAFE_ID.fullmatch(fixture_id):
        raise FullPreviewError(f"Unknown or ambiguous approved save {fixture_id!r}")
    row = matches[0]
    relative = Path(str(row.get("path", "")))
    if (
        relative.suffix.lower() != ".sav"
        or relative.is_absolute()
        or ".." in relative.parts
    ):
        raise FullPreviewError(f"Approved save {fixture_id!r} has an unsafe path")
    save_path = (catalog_path.parent / relative).resolve()
    if catalog_path.parent not in save_path.parents or not save_path.is_file():
        raise FullPreviewError(f"Approved save {fixture_id!r} is missing or escapes its catalog")
    expected = row.get("sha256")
    actual = hashlib.sha256(save_path.read_bytes()).hexdigest()
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected) or actual != expected:
        raise FullPreviewError(f"SHA-256 mismatch for approved save {fixture_id!r}")
    source = row.get("source")
    approval = row.get("approval")
    if not isinstance(source, str) or not source.strip() or not isinstance(approval, str) or not approval.strip():
        raise FullPreviewError(f"Approved save {fixture_id!r} lacks provenance or approval")
    return ApprovedSave(fixture_id, save_path, expected, source, approval)


def _banner(metadata: FullPreviewMetadata, fixture: ApprovedSave) -> str:
    verified = "yes" if metadata.incremental_verified else "no (full recompute)"
    return (
        '<aside class="preview-metadata" role="note">'
        '<strong>Full application preview</strong>'
        f'<span>Source: {escape(metadata.source_label)}</span>'
        f'<span>Commit: <code>{escape(metadata.source_sha)}</code></span>'
        f'<span>Fixture: {escape(fixture.identifier)}</span>'
        f'<span>Save fingerprint: <code>{escape(fixture.sha256)}</code></span>'
        f'<span>Toolkit: <code>{escape(metadata.toolkit_version)}</code></span>'
        f'<span>Output contract: <code>{DATASET_SCHEMA}</code></span>'
        f'<span>Incremental verification: {verified}</span>'
        f'<span>Generated: {escape(metadata.generated_at)}</span>'
        '</aside>'
    )


def build_full_preview(
    run_source: Path,
    output_root: Path,
    metadata: FullPreviewMetadata,
    fixture: ApprovedSave,
) -> Path:
    """Validate a real analysis run and emit only its public report payload."""
    dataset = load_render_dataset(run_source)
    if dataset.manifest.get("source") != fixture.path.name:
        raise FullPreviewError("Run manifest source does not match the approved save")
    _root, html = render_served_report(dataset.manifest_path)
    if "<body>" not in html:
        raise FullPreviewError("Rendered report has no body for preview metadata")
    html = html.replace("<body>", f"<body>{_banner(metadata, fixture)}", 1)

    target = output_root / fixture.identifier
    target.mkdir(parents=True, exist_ok=False)
    shutil.copy2(dataset.manifest_path, target / "manifest.json")
    for path in dataset.files:
        shutil.copy2(path, target / path.name)
    for asset in ("report.css", "report.js"):
        source = dataset.root / asset
        if not source.is_file():
            raise FullPreviewError(f"Run is missing required public asset {asset}")
        shutil.copy2(source, target / asset)
    (target / "index.html").write_text(html, encoding="utf-8")

    published = {path.name for path in target.iterdir() if path.is_file()}
    expected = {
        "index.html", "manifest.json", "report.css", "report.js",
        *(path.name for path in dataset.files),
    }
    if published != expected:
        raise FullPreviewError("Full preview contains an unexpected publication file")
    return target


def validate_full_preview_artifact(root: Path) -> dict:
    """Fail closed on a publication artifact produced by unprivileged code."""
    root = root.resolve()
    context = _read_json(root / "preview-context.json", "full-preview context")
    if not isinstance(context, dict) or context.get("schema") != PREVIEW_CONTEXT_SCHEMA:
        raise FullPreviewError("Unsupported full-preview context schema")
    destination = context.get("destination")
    fixture_id = context.get("fixture")
    source_sha = context.get("source_sha")
    save_sha = context.get("save_sha256")
    if not isinstance(destination, str) or not _DESTINATION.fullmatch(destination):
        raise FullPreviewError("Unsafe full-preview destination")
    if not isinstance(fixture_id, str) or not _SAFE_ID.fullmatch(fixture_id):
        raise FullPreviewError("Unsafe full-preview fixture ID")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise FullPreviewError("Invalid full-preview source SHA")
    if not isinstance(save_sha, str) or not _SHA256.fullmatch(save_sha):
        raise FullPreviewError("Invalid full-preview save fingerprint")

    target = (root / fixture_id).resolve()
    if target.parent != root or not target.is_dir():
        raise FullPreviewError("Full-preview fixture directory is missing")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise FullPreviewError("Full-preview artifact contains a symbolic link")
        if path.is_dir():
            if path != target:
                raise FullPreviewError("Full-preview artifact contains an unexpected directory")
            continue
        relative = path.relative_to(root)
        if relative == Path("preview-context.json"):
            continue
        if relative.parent != Path(fixture_id):
            raise FullPreviewError("Full-preview artifact contains a misplaced file")
        lowered = path.name.casefold()
        if any(token in lowered for token in _FORBIDDEN_PUBLICATION_NAMES):
            raise FullPreviewError(f"Forbidden full-preview publication file {path.name}")
        if path.suffix.lower() not in {".html", ".css", ".js", ".json"}:
            raise FullPreviewError(f"Unsupported full-preview publication file {path.name}")
    required = {"index.html", "manifest.json", "report.css", "report.js"}
    if not required.issubset({path.name for path in target.iterdir()}):
        raise FullPreviewError("Full-preview artifact is missing required report files")
    dataset = load_render_dataset(target / "manifest.json")
    html = (target / "index.html").read_text(encoding="utf-8")
    if "Full application preview" not in html or source_sha not in html or save_sha not in html:
        raise FullPreviewError("Full-preview HTML metadata does not match its context")
    if any("FutureRolls" in path.read_text(encoding="utf-8") for path in dataset.files):
        raise FullPreviewError("Full-preview public JSON contains FutureRolls")
    expected = {
        "index.html", "manifest.json", "report.css", "report.js",
        *(path.name for path in dataset.files),
    }
    if {path.name for path in target.iterdir()} != expected:
        raise FullPreviewError("Full-preview artifact contains unexpected files")
    return context
