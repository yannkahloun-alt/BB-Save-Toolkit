
"""Shared mutable runtime state for one analyzer process."""

PROFILE = {
    "project_role_calls": 0,
    "full_projection_calls": 0,
    "fast_projection_calls": 0,
    "trajectory_s": 0.0,
    "trajectory_cache_hits": 0,
    "trajectory_cache_misses": 0,
    "trajectory_adaptive_refinements": 0,
    "base_matrix_s": 0.0,
    "advisor_s": 0.0,
    "summary_s": 0.0,
}


def reset_profile_values() -> None:
    for key in PROFILE:
        PROFILE[key] = 0 if (key.endswith("_calls") or key.endswith("_hits") or key.endswith("_misses") or key.endswith("_refinements")) else 0.0


def get_profile_values() -> dict:
    return dict(PROFILE)

