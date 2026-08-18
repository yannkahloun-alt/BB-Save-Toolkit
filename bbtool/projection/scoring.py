"""Continuous Fit utility curves and weighted archetype scoring."""
from __future__ import annotations


def curve_value(value: float, points) -> float:
    pts = tuple((float(x), float(y)) for x, y in points)
    if not pts:
        return 0.0
    value = max(value, pts[0][0])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        if value <= x1:
            t = (value - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return pts[-1][1]


def weighted_role_score(values: dict, role: dict, curve_key: str = "projected_curve"):
    components = {}
    numerator = denominator = 0.0
    for stat, cfg in role.get("stats", {}).items():
        if not cfg.get("fit"):
            continue
        weight = float(cfg.get("weight", 1.0))
        value = float(values[stat])
        ceiling = cfg.get("ceiling")
        fit_value = min(value, float(ceiling)) if ceiling is not None else value
        utility = curve_value(fit_value, cfg[curve_key])
        weighted = weight * utility
        numerator += weighted
        denominator += weight
        components[stat] = {
            "value": value,
            "fit_value": fit_value,
            "ceiling": float(ceiling) if ceiling is not None else None,
            "capped": ceiling is not None and value > float(ceiling),
            "weight": weight,
            "utility": round(utility, 4),
            "weighted": round(weighted, 4),
        }
    score = max(0.0, numerator / denominator) if denominator else 0.0
    return score, components, 1.0, {}


def reset_scoring_caches() -> None:
    return None
