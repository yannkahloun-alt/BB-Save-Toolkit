
"""Shared mutable runtime state for one analyzer process."""

from copy import deepcopy


_PROFILE_TEMPLATE = {
    "project_role_calls": 0,
    "full_projection_calls": 0,
    "fast_projection_calls": 0,
    "trajectory_s": 0.0,
    "trajectory_cache_hits": 0,
    "trajectory_cache_misses": 0,
    "trajectory_adaptive_refinements": 0,
    "trajectory_cache_miss_reasons": {
        "missing_entry": 0,
        "fingerprint_change": 0,
        "schema_version_mismatch": 0,
        "refinement": 0,
        "other_fallback": 0,
    },
    "base_matrix_s": 0.0,
    "advisor_s": 0.0,
    "summary_s": 0.0,
    "brother_projection_s": {},
    "archetype_projection_s": {},
    "slowest_projections": [],
}

PROFILE = deepcopy(_PROFILE_TEMPLATE)


def reset_profile_values() -> None:
    PROFILE.clear()
    PROFILE.update(deepcopy(_PROFILE_TEMPLATE))


def get_profile_values() -> dict:
    return deepcopy(PROFILE)


def record_projection(brother_id: str, brother_name: str, role_name: str, kind: str, seconds: float) -> None:
    """Record bounded, JSON-safe projection timings for diagnostics."""
    seconds = float(seconds)
    brother_key = f"{brother_name} [{brother_id}]"
    PROFILE["brother_projection_s"][brother_key] = (
        PROFILE["brother_projection_s"].get(brother_key, 0.0) + seconds
    )
    PROFILE["archetype_projection_s"][role_name] = (
        PROFILE["archetype_projection_s"].get(role_name, 0.0) + seconds
    )
    PROFILE["slowest_projections"].append({
        "brother_id": brother_id,
        "brother": brother_name,
        "archetype": role_name,
        "kind": kind,
        "seconds": seconds,
        "structural_alternatives": 0,
    })
    PROFILE["slowest_projections"] = sorted(
        PROFILE["slowest_projections"], key=lambda item: item["seconds"], reverse=True
    )[:10]

