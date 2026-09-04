"""End-of-run aggregation for warnings and conservative fallbacks."""
from __future__ import annotations

from collections.abc import Iterable


_REFERENCE_FIELDS = (
    "Background",
    "Perks",
    "Traits",
    "Injuries",
)

PUBLIC_ANALYSIS_HEALTH_SCHEMA = "bbtool.analysis_health.v1"


def _unknown_reference_values(records: Iterable[object]) -> list[str]:
    unknown = []
    for record in records:
        for field in _REFERENCE_FIELDS:
            value = (
                record.get(field)
                if isinstance(record, dict)
                else getattr(record, field, None)
            )
            values = value if isinstance(value, (list, tuple)) else (value,)
            unknown.extend(
                str(item)
                for item in values
                if isinstance(item, str)
                and (item == "Unknown" or item.startswith("Unknown ["))
            )
    return sorted(unknown)


def _unknown_background_values(records: Iterable[object]) -> list[str]:
    unknown = []
    for record in records:
        value = (
            record.get("Background")
            if isinstance(record, dict)
            else getattr(record, "Background", None)
        )
        if isinstance(value, str) and (
            value == "Unknown" or value.startswith("Unknown [")
        ):
            unknown.append(value)
    return sorted(unknown)


def build_run_health(
    bros,
    recruits,
    reference_status: dict,
    *,
    parse_diagnostics: dict | None = None,
    incremental_cache=None,
    validation_payload: dict | None = None,
) -> dict:
    """Build a deterministic summary without changing analysis behavior."""
    records = [*bros, *recruits]
    unresolved = _unknown_reference_values(records)
    unresolved_backgrounds = _unknown_background_values(records)
    validation_summary = (validation_payload or {}).get("summary", {})
    roll_violations = int(validation_summary.get("roll_range_violations", 0) or 0)

    miss_reasons = dict(
        sorted(getattr(incremental_cache, "miss_reasons", {}).items())
    )
    cache_fallbacks = sum(int(count) for count in miss_reasons.values())
    stats = getattr(incremental_cache, "stats", None)
    previous_found = bool(getattr(stats, "previous_found", False))
    conservative_recomputations = 0
    if previous_found:
        conservative_recomputations = sum(
            int(getattr(stats, field, 0))
            for field in ("role_computed", "advisor_computed", "summary_computed")
        )

    generated = sorted(
        key.removeprefix("generated_")
        for key, value in reference_status.items()
        if key.startswith("generated_") and value
    )
    parsing_failures = list(
        (parse_diagnostics or {}).get("recoverable_failures", [])
    )
    unresolved_equipment = sorted(
        str(item.get("reference_hash"))
        for item in parsing_failures
        if item.get("kind") == "unresolved_recruit_equipment"
        and item.get("reference_hash")
    )
    recoverable_parsing_failures = len(parsing_failures)
    unresolved_reference_count = len(unresolved) + len(unresolved_equipment)
    result_affecting_warnings = (
        recoverable_parsing_failures + len(unresolved) + roll_violations
    )
    informational_notices = len(generated)
    if cache_fallbacks:
        informational_notices += 1
    if conservative_recomputations:
        informational_notices += 1

    return {
        "result_affecting_warnings": result_affecting_warnings,
        "informational_notices": informational_notices,
        "recoverable_parsing_failures": recoverable_parsing_failures,
        "recoverable_parsing_failure_sample": parsing_failures[:10],
        "unresolved_references_relevant_to_save": unresolved_reference_count,
        "unresolved_reference_sample": sorted(
            [
                *unresolved,
                *[
                    f"Unknown equipment [{value}]"
                    for value in unresolved_equipment
                ],
            ]
        )[:10],
        "unresolved_recruit_equipment_relevant_to_save": len(unresolved_equipment),
        "unresolved_recruit_equipment_hash_sample": unresolved_equipment[:10],
        "unresolved_backgrounds_relevant_to_save": len(unresolved_backgrounds),
        "unresolved_background_sample": unresolved_backgrounds[:10],
        "validation_roll_range_violations": roll_violations,
        "cache_fallbacks": cache_fallbacks,
        "cache_fallback_reasons": miss_reasons,
        "conservative_recomputations": conservative_recomputations,
        "generated_reference_caches": generated,
        "evidence": {
            "unknown_references": "$.roster / $.recruits",
            "parsing_recoveries": "$.runtime.run_health.recoverable_parsing_failure_sample",
            "reference_runtime": "$.runtime.references",
            "cache": "$.runtime.run_health.cache_fallback_reasons",
            "projection_validation": "sibling *-projection-validation.json $.summary",
        },
    }


def build_public_analysis_health(run_health: dict) -> dict:
    """Return the least-privilege health contract used by public reports."""
    counts = {
        "result_affecting_warnings": int(
            run_health.get("result_affecting_warnings", 0) or 0
        ),
        "recoverable_parsing_failures": int(
            run_health.get("recoverable_parsing_failures", 0) or 0
        ),
        "unresolved_references_relevant_to_save": int(
            run_health.get("unresolved_references_relevant_to_save", 0) or 0
        ),
        "unresolved_backgrounds_relevant_to_save": int(
            run_health.get("unresolved_backgrounds_relevant_to_save", 0) or 0
        ),
        "unresolved_recruit_equipment_relevant_to_save": int(
            run_health.get(
                "unresolved_recruit_equipment_relevant_to_save", 0
            ) or 0
        ),
    }
    violations = int(
        run_health.get("validation_roll_range_violations", 0) or 0
    )
    category_sources = (
        ("recoverable_parsing_failures", counts["recoverable_parsing_failures"]),
        ("unresolved_references", counts["unresolved_references_relevant_to_save"]),
        ("unresolved_backgrounds", counts["unresolved_backgrounds_relevant_to_save"]),
        ("projection_validation_violations", violations),
    )
    return {
        "schema": PUBLIC_ANALYSIS_HEALTH_SCHEMA,
        "status": (
            "degraded" if counts["result_affecting_warnings"] else "healthy"
        ),
        "counts": counts,
        "projection_validation": {
            "status": "fail" if violations else "pass",
            "roll_range_violations": violations,
        },
        "warning_categories": [
            {"code": code, "count": count}
            for code, count in category_sources
            if count
        ],
    }


def print_run_health(health: dict, debug_name: str | None) -> None:
    """Print the concise, stable footer for a completed run."""
    print("Run health:")
    print(
        "  result-affecting warnings: "
        f"{health['result_affecting_warnings']} · "
        f"informational notices: {health['informational_notices']}"
    )
    print(
        "  recoverable parsing failures: "
        f"{health['recoverable_parsing_failures']} · "
        "unresolved references relevant to save: "
        f"{health['unresolved_references_relevant_to_save']}"
    )
    print(
        "  unresolved backgrounds relevant to save: "
        f"{health['unresolved_backgrounds_relevant_to_save']}"
    )
    unresolved = health["unresolved_references_relevant_to_save"]
    if unresolved:
        print(
            "  WARNING: unresolved reference data affects the current analysis "
            f"({unresolved} save-visible value(s))."
        )
    else:
        print(
            "  Reference audit: no unresolved references are present in the "
            "current save; analysis results are unaffected."
        )
    print(
        f"  cache fallbacks: {health['cache_fallbacks']} · "
        f"conservative recomputations: {health['conservative_recomputations']}"
    )
    if health["result_affecting_warnings"] == 0:
        print("  No result-affecting warnings.")
    if debug_name:
        print(
            f"  Evidence: {debug_name} $.runtime.run_health; "
            "supporting sections are listed in $.runtime.run_health.evidence"
        )
