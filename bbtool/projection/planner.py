"""Fit-only role projection for the v3.x model."""
from __future__ import annotations

from ..models import STATS, Brother
from .context import bro_projection_context
from .runtime import PROFILE
from .scoring import weighted_role_score
from .trajectory import project_fit_trajectory


def _first_round_ranges(bro: Brother):
    rolls = getattr(bro, "CurrentRolls", {}) or {}
    level_points = getattr(bro, "LevelPoints", None)
    if level_points is not None and int(level_points) > 0 and rolls:
        return {stat: (int(value), int(value)) for stat, value in rolls.items()}
    return None


def _project_role_common(bro: Brother, role: dict) -> tuple[dict, dict, dict]:
    """Run the shared trajectory and scoring work used by full/fast projections."""
    _raw, _effects, _current, levels, _gains, _ranges = bro_projection_context(bro)
    trajectory = project_fit_trajectory(
        bro, role, rounds=levels, first_round_ranges=_first_round_ranges(bro)
    )
    values = {stat: trajectory["stat_ranges"][stat]["ev"] for stat in STATS}
    _, components, _, _ = weighted_role_score(values, role, "projected_curve")
    return trajectory, values, components


def _base_projection_payload(role: dict, trajectory: dict, values: dict, components: dict) -> dict:
    return {
        "Role": role["name"],
        "ProjectedFit": round(trajectory["expected_pct"] / 100.0, 4),
        "ProjectedFitPct": trajectory["expected_pct"],
        "ProjectedFitLikelyMinPct": trajectory["likely_min_pct"],
        "ProjectedFitLikelyMaxPct": trajectory["likely_max_pct"],
        "ProjectedFitFullMinPct": trajectory["full_min_pct"],
        "ProjectedFitFullMaxPct": trajectory["full_max_pct"],
        "FitFeasibilityPct": trajectory["feasibility_pct"],
        "ProjectedComponents": components,
        **{stat: round(values[stat], 1) for stat in STATS},
    }


def project_role_fast(bro: Brother, role: dict) -> dict:
    """Compact Fit projection for role/path searches."""
    PROFILE["project_role_calls"] += 1
    PROFILE["fast_projection_calls"] += 1
    trajectory, values, components = _project_role_common(bro, role)
    return _base_projection_payload(role, trajectory, values, components)


def project_role(bro: Brother, role: dict) -> dict:
    """Complete Fit projection used by reports and debug outputs."""
    PROFILE["project_role_calls"] += 1
    PROFILE["full_projection_calls"] += 1
    trajectory, values, components = _project_role_common(bro, role)
    return {
        **_base_projection_payload(role, trajectory, values, components),
        "ProjectedRanges": {
            stat: {
                "min": trajectory["stat_ranges"][stat]["min"],
                "ev": trajectory["stat_ranges"][stat]["ev"],
                "max": trajectory["stat_ranges"][stat]["max"],
                "baseline": float(role["stats"][stat]["baseline"]),
                "target": float(role["stats"][stat]["target"]),
                "weight": float(role["stats"][stat].get("weight", 1.0)),
            }
            for stat in STATS
            if stat in trajectory.get("fit_stats", ())
        },
        "FitTrajectoryStateCount": trajectory["state_count"],
        "FitTrajectoryPruned": trajectory["pruned"],
    }
