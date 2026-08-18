
"""Projection subsystem public API."""

from .perks import (
    effective_stat_profile,
    effective_stat_value,
    effective_values,
    structural_projection_perks,
)
from .progression import (
    average_gain,
    development_rounds_to_11,
    gain_range,
)
from .planner import project_role, project_role_fast
from .runtime import (
    get_profile_values,
    reset_profile_values,
)
from .perks import reset_perk_cache
from .scoring import reset_scoring_caches
from .context import reset_bro_context_cache
from .trajectory import project_fit_trajectory, project_seeded_fit_trajectory, reset_trajectory_cache


def configure_engine() -> None:
    reset_perk_cache()
    reset_bro_context_cache()
    reset_trajectory_cache()


def reset_profile() -> None:
    reset_profile_values()
    reset_scoring_caches()


def get_profile() -> dict:
    return get_profile_values()


__all__ = [
    "average_gain",
    "configure_engine",
    "development_rounds_to_11",
    "effective_stat_profile",
    "effective_stat_value",
    "effective_values",
    "gain_range",
    "get_profile",
    "project_fit_trajectory",
    "project_role",
    "project_role_fast",
    "project_seeded_fit_trajectory",
    "reset_profile",
    "structural_projection_perks",
]

