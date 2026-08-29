"""End-of-run aggregation for warnings and conservative fallbacks."""
from __future__ import annotations

from collections.abc import Iterable


_REFERENCE_FIELDS = (
    "Background",
    "Perks",
    "Traits",
    "Injuries",
    "PermanentInjuries",
)


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


def build_run_health(
    bros,
    recruits,
    reference_status: dict,
    *,
    incremental_cache=None,
    validation_payload: dict | None = None,
) -> dict:
    """Build a deterministic summary without changing analysis behavior."""
    unresolved = _unknown_reference_values([*bros, *recruits])
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
    recoverable_parsing_failures = 0
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
        "unresolved_references_relevant_to_save": len(unresolved),
        "unresolved_reference_sample": unresolved[:10],
        "validation_roll_range_violations": roll_violations,
        "cache_fallbacks": cache_fallbacks,
        "cache_fallback_reasons": miss_reasons,
        "conservative_recomputations": conservative_recomputations,
        "generated_reference_caches": generated,
        "evidence": {
            "unknown_references": "$.roster / $.recruits",
            "reference_runtime": "$.runtime.references",
            "cache": "$.runtime.run_health.cache_fallback_reasons",
            "projection_validation": "sibling *-projection-validation.json $.summary",
        },
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
