"""Privacy-conscious metadata and resource telemetry for analyzer runs."""
from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path
import platform
import tracemalloc

from ..incremental.fingerprint import (
    ADVISOR_ENGINE_VERSION,
    BROTHER_SUMMARY_ENGINE_VERSION,
    ROLE_PROJECTION_ENGINE_VERSION,
)
from ..incremental.manifest import SCHEMA as INCREMENTAL_SCHEMA
from .console import format_bytes, sha256_file


TOOLKIT_VERSION = "3.87"
DEBUG_BUNDLE_SCHEMA = "bbtool.debug_bundle.v1"
PROJECTION_VALIDATION_SCHEMA = "bbtool.projection_validation.v3"


def start_resource_monitoring() -> bool:
    """Start portable Python-heap monitoring, preserving an existing monitor."""
    if tracemalloc.is_tracing():
        return False
    tracemalloc.start()
    return True


def stop_resource_monitoring(started_here: bool) -> None:
    if started_here and tracemalloc.is_tracing():
        tracemalloc.stop()


def _file_metadata(path: Path, *, include_mtime: bool) -> dict:
    resolved = path.resolve()
    result = {
        "path": str(resolved),
        "size_bytes": None,
        "sha256": None,
        "status": "unavailable",
    }
    if include_mtime:
        result["modified_at_utc"] = None
    try:
        stat = resolved.stat()
        result.update(
            size_bytes=stat.st_size,
            sha256=sha256_file(resolved),
            status="available",
        )
        if include_mtime:
            result["modified_at_utc"] = datetime.fromtimestamp(
                stat.st_mtime, UTC
            ).isoformat(timespec="seconds")
    except OSError as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def build_run_metadata(options) -> dict:
    """Collect stable reproduction metadata without reading save contents."""
    cpu_count = os.cpu_count()
    return {
        "format": "bbtool.run_metadata.v1",
        "toolkit_version": TOOLKIT_VERSION,
        "schemas": {
            "debug_bundle": DEBUG_BUNDLE_SCHEMA,
            "projection_validation": PROJECTION_VALIDATION_SCHEMA,
            "incremental_cache": INCREMENTAL_SCHEMA,
        },
        "engines": {
            "role_projection": ROLE_PROJECTION_ENGINE_VERSION,
            "advisor": ADVISOR_ENGINE_VERSION,
            "summary": BROTHER_SUMMARY_ENGINE_VERSION,
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "operating_system": platform.platform(),
        },
        "input_save": _file_metadata(Path(options.save), include_mtime=True),
        "configuration": {
            "archetypes": _file_metadata(Path(options.targets), include_mtime=False),
            "classification": _file_metadata(
                Path(options.classification), include_mtime=False
            ),
        },
        "execution": {
            "mode": "single-process",
            "configured_workers": 1,
            "logical_cpu_count": cpu_count,
            "logical_cpu_count_status": (
                "available" if cpu_count is not None else "unavailable"
            ),
        },
        "cache": {
            "analysis_directory": str(Path(options.out).resolve()),
            "reference_directory": str(
                (Path(__file__).resolve().parents[2] / "references").resolve()
            ),
            "schema": INCREMENTAL_SCHEMA,
        },
        "resources": resource_snapshot(),
    }


def resource_snapshot() -> dict:
    if not tracemalloc.is_tracing():
        return {
            "python_heap_current_bytes": None,
            "python_heap_peak_bytes": None,
            "status": "unavailable",
        }
    current, peak = tracemalloc.get_traced_memory()
    return {
        "python_heap_current_bytes": current,
        "python_heap_peak_bytes": peak,
        "status": "available",
    }


def refresh_resources(metadata: dict) -> None:
    metadata["resources"] = resource_snapshot()


def print_run_header(metadata: dict) -> None:
    save = metadata["input_save"]
    execution = metadata["execution"]
    print("Run metadata:")
    print(
        f"  toolkit v{metadata['toolkit_version']} · "
        f"Python {metadata['environment']['python_version']} · "
        f"{execution['mode']} (1/{execution['logical_cpu_count'] or 'unavailable'} CPUs)"
    )
    size = (
        format_bytes(save["size_bytes"])
        if save["size_bytes"] is not None
        else "unavailable"
    )
    checksum = save["sha256"] or "unavailable"
    print(f"  save {size} · SHA-256 {checksum}")
    print(
        "  engines "
        + " · ".join(
            f"{name}={version}"
            for name, version in metadata["engines"].items()
        )
    )


def print_resource_summary(metadata: dict) -> None:
    resources = metadata["resources"]
    peak = resources["python_heap_peak_bytes"]
    value = format_bytes(peak) if peak is not None else "unavailable"
    print(f"Peak Python memory: {value}")
