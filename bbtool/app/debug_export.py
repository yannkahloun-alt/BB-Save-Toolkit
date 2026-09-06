"""Coherent local-app debug export for real-save algorithm and UI triage."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
import hashlib
import io
import json
import re
from typing import Any
import zipfile

from .company_brother_view import build_company_brother_view
from .health import build_public_analysis_health
from .level_up_view import build_level_up_view
from .output import _decorate_fit_rows
from .recruitment_view import build_recruitment_view
from .target_presentation import BOUND_ARTIFACTS, build_target_presentation
from .telemetry import TOOLKIT_VERSION


DEBUG_EXPORT_SCHEMA = "bbtool.local_debug_export.v1"
DIAGNOSTIC_INVENTORY_SCHEMA = "bbtool.local_debug_diagnostic_inventory.v1"
_DOWNLOAD_PREFIX = "BB-Save-Toolkit-debug-json"
_SIMPLE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INCOMPLETE_STATES = frozenset({"unknown", "unavailable", "degraded", "failed", "failure", "error"})


class DebugExportGenerationChanged(RuntimeError):
    """The published analysis changed while an export was being assembled."""



def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            default=str,
        ).encode("utf-8")
        + b"\n"
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_path(base: str, key: str) -> str:
    if _SIMPLE_KEY.fullmatch(key):
        return f"{base}.{key}"
    return f"{base}[{json.dumps(key, ensure_ascii=False)}]"


def _finding_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        code = value.get("code")
        if isinstance(code, str):
            return {"code": code}
        return {"type": "object", "keys": sorted(str(key) for key in value)[:20]}
    if isinstance(value, list):
        return {"type": "array", "count": len(value)}
    return str(value)


def build_diagnostic_inventory(snapshots: Mapping[str, Any]) -> dict[str, Any]:
    """Inventory explicit evidence gaps without inferring hidden game facts."""
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add(source: str, path: str, category: str, value: Any, *, state: str | None = None) -> None:
        rendered = _finding_value(value)
        marker = (source, path, category, json.dumps(rendered, sort_keys=True, default=str))
        if marker in seen:
            return
        seen.add(marker)
        finding = {
            "source": source,
            "path": path,
            "category": category,
            "value": rendered,
        }
        if state is not None:
            finding["state"] = state
        findings.append(finding)

    def visit(source: str, value: Any, path: str, inherited_state: str | None = None) -> None:
        if isinstance(value, Mapping):
            state = inherited_state
            for state_key in ("state", "status", "confidence"):
                candidate = value.get(state_key)
                if isinstance(candidate, str) and candidate.strip():
                    state = candidate.strip().lower()
                    break

            if state in _INCOMPLETE_STATES:
                for key, item in value.items():
                    if item is None:
                        add(
                            source,
                            _json_path(path, str(key)),
                            "null_with_incomplete_state",
                            None,
                            state=state,
                        )

            for key, item in value.items():
                key_text = str(key)
                child_path = _json_path(path, key_text)
                lower_key = key_text.lower()
                if lower_key == "reason" and isinstance(item, str) and item.strip():
                    add(source, child_path, "reason", item, state=state)
                warning_or_error_key = (
                    lower_key in {"warning", "warnings", "error", "errors"}
                    or lower_key.startswith("warning_")
                    or lower_key.endswith("_warnings")
                    or lower_key.startswith("error_")
                    or lower_key.endswith("_errors")
                )
                if warning_or_error_key and item not in (None, [], {}, ""):
                    add(source, child_path, "warning_or_error", item, state=state)
                if (
                    lower_key == "code"
                    and isinstance(item, str)
                    and any(token in path.lower() for token in ("warning", "error"))
                ):
                    add(source, child_path, "warning_or_error_code", item, state=state)
                visit(source, item, child_path, state)
            return

        if isinstance(value, list):
            for index, item in enumerate(value):
                visit(source, item, f"{path}[{index}]", inherited_state)
            return

        if not isinstance(value, str):
            return
        normalized = value.strip().lower()
        if "unavailable" in normalized:
            add(source, path, "unavailable", value, state=inherited_state)
        elif "unknown" in normalized:
            add(source, path, "unknown", value, state=inherited_state)
        elif normalized == "degraded":
            add(source, path, "degraded", value, state=inherited_state)
        elif normalized in {"failed", "failure", "error"}:
            add(source, path, "failure", value, state=inherited_state)

    for source, payload in sorted(snapshots.items()):
        visit(source, payload, "$")

    findings.sort(
        key=lambda item: (
            item["source"],
            item["path"],
            item["category"],
            json.dumps(item["value"], sort_keys=True, default=str),
        )
    )
    counts: dict[str, int] = {}
    for finding in findings:
        category = finding["category"]
        counts[category] = counts.get(category, 0) + 1
    return {
        "schema": DIAGNOSTIC_INVENTORY_SCHEMA,
        "purpose": (
            "Explicit unknown/unavailable/degraded/warning evidence for backlog triage; "
            "findings are observations, not automatic defects."
        ),
        "counts": dict(sorted(counts.items())),
        "findings": findings,
    }


def _redact_selected_save(value: Any, selected_path: str | None) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _redact_selected_save(item, selected_path)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_selected_save(item, selected_path) for item in value]
    if isinstance(value, str) and selected_path:
        return value.replace(selected_path, "<selected-save>")
    return value


def _sanitized_followed_save(application) -> dict[str, Any]:
    raw = deepcopy(application.followed_save())
    selected = raw.get("selected_path")
    selected_path = selected if isinstance(selected, str) else None
    sanitized = _redact_selected_save(raw, selected_path)
    if selected_path is not None:
        sanitized["selected_path"] = "<redacted>"
        sanitized["selected_path_redacted"] = True
    return sanitized


def _redact_known_local_paths(application, value: Any) -> Any:
    """Redact known machine-local roots while preserving diagnostic structure."""
    try:
        followed = application.followed_save()
    except Exception:
        followed = {}
    selected = followed.get("selected_path")
    replacements = []
    if isinstance(selected, str) and selected:
        replacements.append((selected, "<selected-save>"))
    store = getattr(application, "store", None)
    root = getattr(store, "root", None)
    if root is not None:
        root_text = str(root)
        if root_text:
            replacements.append((root_text, "<user-state>"))
    replacements.sort(key=lambda item: len(item[0]), reverse=True)

    def redact(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {key: redact(child) for key, child in item.items()}
        if isinstance(item, list):
            return [redact(child) for child in item]
        if isinstance(item, str):
            for private, replacement_text in replacements:
                item = item.replace(private, replacement_text)
            return item
        return item

    return redact(value)


def _capture(builder: Callable[[], Any]) -> Any:
    """Keep the bundle available even if one UI read model itself is broken."""
    try:
        return builder()
    except Exception as exc:
        return {
            "available": False,
            "debug_capture_error": {
                "type": type(exc).__name__,
                "message": "read model raised while building debug evidence",
            },
        }


def _runtime_diagnostics(application, result) -> dict[str, Any]:
    """Expose safe algorithm diagnostics while excluding path-heavy reference internals."""
    diagnostics = deepcopy(getattr(result, "diagnostics", {}) or {})
    safe = {
        key: diagnostics.get(key)
        for key in (
            "parse",
            "run_health",
            "projection_profile",
            "validation_projection",
            "cache_miss_reasons",
        )
        if key in diagnostics
    }
    safe["timings"] = dict(getattr(result, "timings", {}) or {})
    safe["warnings"] = deepcopy(getattr(result, "warnings", []) or [])
    safe["excluded"] = {
        "references": (
            "reference-runtime diagnostics are excluded because they may contain "
            "machine-local cache paths; unresolved reference evidence remains in run_health"
        ),
        "progress_events": (
            "worker progress is excluded because reference-stage details may contain "
            "machine-local paths; completed stage timings are exported above"
        ),
    }
    try:
        followed = application.followed_save()
    except Exception:
        followed = {}
    selected = followed.get("selected_path")
    selected_path = selected if isinstance(selected, str) else None
    return _redact_known_local_paths(
        application, _redact_selected_save(safe, selected_path)
    )


def _analysis_payloads(result) -> dict[str, Any]:
    public = result.public_data
    fits = deepcopy(public.get("fits", []))
    _decorate_fit_rows(fits)
    health = build_public_analysis_health(
        (getattr(result, "diagnostics", {}) or {}).get("run_health", {})
    )
    return {
        "roster": public.get("roster", []),
        "recruits": public.get("recruits", []),
        "role_fit": fits,
        "classification": public.get("summaries", []),
        "archetypes": {"roles": result.roles},
        "classification_config": result.classification,
        "analysis_health": health,
    }


def _target_presentation(result, artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    return build_target_presentation(
        bros=result.roster,
        recruits=result.recruits,
        roles=result.roles,
        analysis_health=build_public_analysis_health(
            (getattr(result, "diagnostics", {}) or {}).get("run_health", {})
        ),
        campaign_identity=result.campaign_identity,
        brother_identities=result.brother_identities,
        source_fingerprint=result.source_fingerprint,
        configuration_fingerprints=result.configuration_fingerprints,
        recruitment_analysis=result.recruitment_analysis,
        artifact_hashes=artifact_hashes,
        result_signatures=result.incremental_cache.publication_signatures(),
        company_intrinsic_coverage=result.analysis.company_intrinsic_coverage,
        summaries=result.analysis.summaries,
        assigned_builds=result.assigned_builds,
        company_intended_coverage=result.analysis.company_intended_coverage,
    )


def build_debug_export(
    application,
    *,
    shell_builder: Callable[[], dict[str, Any]],
) -> tuple[bytes, str]:
    """Build one coherent ZIP from the current publication and live UI read boundary."""
    with application._command_lock:
        publication = application.coordinator.last_success
        if publication is None:
            raise ValueError("no published analysis is available")
        result = publication.result

        files: dict[str, bytes] = {}
        analysis_payloads = _analysis_payloads(result)
        artifact_hashes: dict[str, str] = {}
        for label, payload in analysis_payloads.items():
            filename = {
                "role_fit": "role-fit",
                "classification_config": "classification-config",
                "analysis_health": "analysis-health",
            }.get(label, label.replace("_", "-"))
            path = f"analysis/{filename}.json"
            data = _json_bytes(payload)
            files[path] = data
            if label in BOUND_ARTIFACTS:
                artifact_hashes[label] = _sha256(data)

        presentation = _capture(lambda: _target_presentation(result, artifact_hashes))
        files["analysis/target-presentation.json"] = _json_bytes(presentation)
        files["analysis/projection-validation.json"] = _json_bytes(
            result.projection_validation
        )
        runtime_diagnostics = _runtime_diagnostics(application, result)
        files["analysis/runtime-diagnostics.json"] = _json_bytes(runtime_diagnostics)

        api_snapshots = {
            "api/shell.json": _capture(shell_builder),
            "api/followed-save.json": _capture(
                lambda: _sanitized_followed_save(application)
            ),
            "api/analysis-result.json": _capture(application.last_result),
            "api/company-brother.json": _capture(
                lambda: build_company_brother_view(application)
            ),
            "api/level-up.json": _capture(
                lambda: build_level_up_view(application)
            ),
            "api/recruitment.json": _capture(
                lambda: build_recruitment_view(application)
            ),
            "api/effective-archetypes.json": _capture(
                application.effective_archetypes
            ),
        }
        api_snapshots = {
            path: _redact_known_local_paths(application, payload)
            for path, payload in api_snapshots.items()
        }
        for path, payload in api_snapshots.items():
            files[path] = _json_bytes(payload)

        inventory_inputs = {
            path: payload
            for path, payload in api_snapshots.items()
        }
        inventory_inputs["analysis/analysis-health.json"] = analysis_payloads[
            "analysis_health"
        ]
        inventory_inputs["analysis/target-presentation.json"] = presentation
        inventory_inputs["analysis/runtime-diagnostics.json"] = runtime_diagnostics
        inventory = build_diagnostic_inventory(inventory_inputs)
        files["diagnostic-inventory.json"] = _json_bytes(inventory)

        manifest_files = {
            path: {
                "sha256": _sha256(data),
                "bytes": len(data),
            }
            for path, data in sorted(files.items())
        }
        manifest = {
            "schema": DEBUG_EXPORT_SCHEMA,
            "toolkit_version": TOOLKIT_VERSION,
            "publication": {
                "generation": publication.generation,
                "job_id": publication.job_id,
                "source_fingerprint": publication.source_fingerprint,
                "configuration_fingerprints": dict(
                    publication.configuration_fingerprints
                ),
                "dependency_signatures": deepcopy(
                    getattr(publication, "dependency_signatures", {})
                ),
                "artifact_signatures": deepcopy(publication.artifact_signatures),
            },
            "scope": {
                "analysis": "exact published generation",
                "api_shell": "live command-boundary status plus published generation",
                "api_followed_save": "live state with selected path redacted",
                "api_analysis_result": "published result plus live freshness",
                "api_company_brother": "published analysis plus live AssignedBuild intent",
                "api_level_up": "published generation",
                "api_recruitment": "published generation",
                "api_effective_archetypes": "live command-boundary catalog; may be newer than publication",
                "api_path_redaction": "known selected-save and user-state roots are replaced with placeholders",
            },
            "privacy": {
                "save_bytes_included": False,
                "selected_save_path_included": False,
                "note": "The bundle contains player-visible roster/recruit names and analytical evidence for local debugging.",
            },
            "files": manifest_files,
        }
        files["manifest.json"] = _json_bytes(manifest)

        archive = io.BytesIO()
        with zipfile.ZipFile(
            archive,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as target:
            for path, data in sorted(files.items()):
                info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                target.writestr(info, data)
        current_publication = application.coordinator.last_success
        if (
            current_publication is not publication
            or current_publication.generation != publication.generation
            or current_publication.job_id != publication.job_id
        ):
            raise DebugExportGenerationChanged(
                "published analysis changed while debug export was being assembled"
            )
        filename = f"{_DOWNLOAD_PREFIX}-generation-{publication.generation}.zip"
        return archive.getvalue(), filename


__all__ = [
    "DEBUG_EXPORT_SCHEMA",
    "DIAGNOSTIC_INVENTORY_SCHEMA",
    "DebugExportGenerationChanged",
    "build_debug_export",
    "build_diagnostic_inventory",
]
