"""Validated report-only delivery from public analysis JSON."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from ..html_report import render_html_report
from ..models import Brother
from .cli import CliOptions
from .console import Step, format_bytes, print_generated_files, sha256_file
from .output import (
    REPORT_DATASET_SCHEMA, archive_workspace, create_workspace, prune_outputs,
    write_html,
)

DATASET_SCHEMA = REPORT_DATASET_SCHEMA
REQUIRED_FILES = frozenset({
    "roster", "recruits", "role_fit", "classification",
    "archetypes", "classification_config",
})


class RenderDatasetError(ValueError):
    """A public report dataset is missing, unsafe, or incompatible."""


@dataclass(frozen=True)
class RenderDataset:
    root: Path
    manifest_path: Path
    manifest: dict
    bros: list[Brother]
    recruits: list[dict]
    fits: list[dict]
    summaries: list[dict]
    roles: list[dict]
    classification: dict
    files: tuple[Path, ...]


def _fail(message: str) -> RenderDatasetError:
    return RenderDatasetError(f"Invalid render dataset: {message}")


def _load_json(path: Path, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise _fail(f"cannot read {label} file {path.name}: {exc}") from exc
    except UnicodeError as exc:
        raise _fail(f"invalid UTF-8 in {label} file {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise _fail(
            f"malformed JSON in {label} file {path.name} at line {exc.lineno}, "
            f"column {exc.colno}"
        ) from exc


def _manifest_path(source: Path) -> Path:
    if source.is_dir():
        return source / "manifest.json"
    if source.suffix.lower() in {".html", ".htm"}:
        return source.parent / "manifest.json"
    return source


def _contains_key(value, forbidden: str) -> bool:
    if isinstance(value, dict):
        return forbidden in value or any(
            _contains_key(child, forbidden) for child in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(child, forbidden) for child in value)
    return False


def load_render_dataset(source: Path) -> RenderDataset:
    """Load and validate the complete public dataset before rendering."""
    manifest_path = _manifest_path(source).resolve()
    if not manifest_path.is_file():
        raise _fail(f"manifest not found: {manifest_path}")
    root = manifest_path.parent
    manifest = _load_json(manifest_path, "manifest")
    if not isinstance(manifest, dict):
        raise _fail("manifest root must be an object")
    if manifest.get("schema") != DATASET_SCHEMA:
        raise _fail(
            f"unsupported schema {manifest.get('schema')!r}; expected {DATASET_SCHEMA!r}"
        )
    entries = manifest.get("files")
    if not isinstance(entries, dict) or set(entries) != REQUIRED_FILES:
        missing = sorted(REQUIRED_FILES - set(entries or {}))
        extra = sorted(set(entries or {}) - REQUIRED_FILES)
        raise _fail(f"manifest files mismatch; missing={missing}, extra={extra}")

    payloads = {}
    paths = []
    for label in sorted(REQUIRED_FILES):
        entry = entries[label]
        if not isinstance(entry, dict):
            raise _fail(f"manifest entry {label!r} must be an object")
        relative = Path(str(entry.get("path", "")))
        if not relative.name or relative.is_absolute() or ".." in relative.parts:
            raise _fail(f"unsafe path for {label}: {relative}")
        path = (root / relative).resolve()
        if root not in path.parents:
            raise _fail(f"path for {label} escapes the dataset directory")
        if not path.is_file():
            raise _fail(f"required {label} file not found: {relative}")
        expected_hash = entry.get("sha256")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_hash != actual_hash:
            raise _fail(f"SHA-256 mismatch for {label} file {relative}")
        payloads[label] = _load_json(path, label)
        paths.append(path)

    for label in ("roster", "recruits", "role_fit", "classification"):
        if not isinstance(payloads[label], list):
            raise _fail(f"{label} root must be an array")
    if any(_contains_key(payload, "FutureRolls") for payload in payloads.values()):
        raise _fail("public report inputs must not contain FutureRolls")
    if not isinstance(payloads["archetypes"], dict):
        raise _fail("archetypes root must be an object")
    roles = payloads["archetypes"].get("roles")
    if not isinstance(roles, list) or not roles:
        raise _fail("archetypes.roles must be a non-empty array")
    if not isinstance(payloads["classification_config"], dict):
        raise _fail("classification_config root must be an object")

    bros = []
    for index, raw in enumerate(payloads["roster"]):
        if not isinstance(raw, dict):
            raise _fail(f"roster[{index}] must be an object")
        data = dict(raw)
        declared_id = data.pop("BrotherID", None)
        data.pop("FutureRolls", None)
        # Derived current-state facts remain part of the supplied public
        # dataset; render-only reconstructs Brother solely for existing
        # renderer joins and must not recompute this mechanics payload.
        supplied_perk_gear_facts = data.pop("PerkGearFacts", None)
        try:
            bro = Brother(**data)
        except (TypeError, ValueError) as exc:
            raise _fail(f"invalid roster[{index}]: {exc}") from exc
        if declared_id != bro.BrotherID:
            raise _fail(
                f"roster[{index}] BrotherID {declared_id!r} does not match HumanOffset"
            )
        if supplied_perk_gear_facts is not None:
            bro.PerkGearFacts = supplied_perk_gear_facts
        bros.append(bro)

    bro_ids = {bro.BrotherID for bro in bros}
    if len(bro_ids) != len(bros):
        raise _fail("roster contains duplicate BrotherID values")
    role_names = {role.get("name") for role in roles if isinstance(role, dict)}
    if None in role_names or len(role_names) != len(roles):
        raise _fail("archetypes contain missing or duplicate role names")
    fits = payloads["role_fit"]
    summaries = payloads["classification"]
    if any(not isinstance(recruit, dict) for recruit in payloads["recruits"]):
        raise _fail("recruit rows must be objects")
    if any(not isinstance(row, dict) for row in fits + summaries):
        raise _fail("role_fit and classification rows must be objects")
    if {row.get("BrotherID") for row in fits} != bro_ids:
        raise _fail("role_fit BrotherID values do not match the roster")
    if {row.get("Role") for row in fits} != role_names:
        raise _fail("role_fit Role values do not match archetypes")
    fit_keys = {(row.get("BrotherID"), row.get("Role")) for row in fits}
    if len(fits) != len(bro_ids) * len(role_names) or len(fit_keys) != len(fits):
        raise _fail("role_fit must contain exactly one row per brother and role")
    if {row.get("BrotherID") for row in summaries} != bro_ids:
        raise _fail("classification BrotherID values do not match the roster")
    if len(summaries) != len(bro_ids):
        raise _fail("classification must contain exactly one row per brother")
    if any(row.get("BestRole") not in role_names for row in summaries):
        raise _fail("classification BestRole values do not match archetypes")

    dataset = RenderDataset(
        root=root, manifest_path=manifest_path, manifest=manifest, bros=bros,
        recruits=payloads["recruits"], fits=fits, summaries=summaries,
        roles=roles, classification=payloads["classification_config"],
        files=tuple(paths),
    )
    try:
        render_html_report(
            Path("validated-dataset.json"), dataset.bros, dataset.fits,
            dataset.summaries, dataset.roles, dataset.classification,
            recruits=dataset.recruits,
        )
    except Exception as exc:
        raise _fail(
            "renderer contract rejected the dataset before output creation: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    return dataset


def run_render_only(options: CliOptions) -> tuple:
    """Render, package, and optionally open a report without analysis."""
    assert options.render_only is not None
    step = Step("Validate report dataset")
    step.__enter__()
    dataset = load_render_dataset(options.render_only)
    step.done(DATASET_SCHEMA)

    source = Path(f"{dataset.root.name or 'report-dataset'}.json")
    workspace = create_workspace(source, options.out)
    step = Step("Generate HTML report (render only)")
    step.__enter__()
    report_path = write_html(
        workspace, dataset.bros, dataset.recruits, dataset.fits,
        dataset.summaries, dataset.roles, dataset.classification,
    )
    step.done("analysis not executed")

    step = Step("Create run archive")
    step.__enter__()
    archive_path = archive_workspace(workspace, options.out)
    archive_size = archive_path.stat().st_size
    prune_outputs(options.out, source.stem, archive_path)
    step.done(f"{format_bytes(archive_size)} — SHA-256 {sha256_file(archive_path)}")

    print("[DONE ] Render only — parsing and analysis were not executed")
    print(f"Output: {workspace.root}")
    print_generated_files(workspace.root)
    print(f"Report: {report_path}")
    print(f"Archive: {archive_path}")
    if options.open_report:
        try:
            from .report_server import launch_report_server
            if not launch_report_server(workspace.root):
                print("Warning: the browser did not confirm that the report opened")
        except Exception as exc:
            print(f"Warning: unable to open report: {type(exc).__name__}: {exc}")
    return workspace, archive_path
