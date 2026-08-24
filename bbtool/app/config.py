"""Loading and normalization of editable analyzer configuration."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class AnalyzerConfig:
    roles: list[dict]
    classification: dict


def _fit_curve(target: float, baseline: float | None) -> list[list[float]]:
    """Compile a bounded signed Fit curve with baseline as its neutral point."""
    target = float(target)
    if baseline is None:
        baseline = target * 0.85
    minimum = min(float(baseline), target)
    gap = max(1.0, target - minimum)
    low = minimum - gap
    return [
        [round(low, 4), -1.0],
        [round(minimum, 4), 0.0],
        [round(target, 4), 1.0],
        [round(target + gap, 4), 1.0],
    ]



def _normalize_role(role: dict) -> dict:
    """Add engine-only derived fields without polluting the editable JSON."""
    role = deepcopy(role)
    for stat, cfg in role.get("stats", {}).items():
        target = cfg.get("target")
        baseline = cfg.get("baseline")
        ceiling = cfg.get("ceiling")
        if ceiling is not None:
            if isinstance(ceiling, bool) or not isinstance(ceiling, (int, float)):
                raise ValueError(
                    f"{role.get('name', '<unnamed>')}.{stat}.ceiling must be numeric"
                )
            ceiling = float(ceiling)
            if not math.isfinite(ceiling):
                raise ValueError(
                    f"{role.get('name', '<unnamed>')}.{stat}.ceiling must be finite"
                )
            if target is None:
                raise ValueError(
                    f"{role.get('name', '<unnamed>')}.{stat}.ceiling requires target"
                )
            if ceiling < float(target):
                raise ValueError(
                    f"{role.get('name', '<unnamed>')}.{stat}.ceiling must be >= target"
                )
            cfg["ceiling"] = ceiling
        if target is not None:
            cfg["projected_curve"] = _fit_curve(target, baseline)
            cfg["fit"] = True
        else:
            cfg["fit"] = False
    return role


def load_config(targets_path: Path, classification_path: Path) -> AnalyzerConfig:
    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    classification = json.loads(classification_path.read_text(encoding="utf-8"))
    roles = targets.get("roles")
    if not isinstance(roles, list) or not roles:
        raise ValueError(f"No roles found in {targets_path}")
    if not isinstance(classification, dict):
        raise ValueError(f"Invalid classification config: {classification_path}")
    return AnalyzerConfig(
        roles=[_normalize_role(role) for role in roles],
        classification=classification,
    )
