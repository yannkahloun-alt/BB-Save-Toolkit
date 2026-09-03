"""Deterministic, network-free cold projection benchmark for issue #70."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bbtool.app.analysis import analyze_brothers
from bbtool.app.config import load_config
from bbtool.app.output import build_projection_validation
from bbtool.models import Brother, STATS
from bbtool.projection import configure_engine, get_profile, reset_profile
from bbtool.projection.progression import gain_range


def _brother(index: int) -> Brother:
    values = {
        "Name": f"Benchmark {index}", "Title": "", "Level": 1, "XP": 0,
        "PerkPoints": 0, "PerksUsed": 0, "LevelPoints": 0, "AP": 9,
        "HP": 56 + index, "Fatigue": 92 + 2 * index,
        "Resolve": 35 + index, "Initiative": 90 + index,
        "MAtk": 52 + 2 * index, "RAtk": 38 + index,
        "MDef": 2 + index, "RDef": 1 + index,
        "BackgroundID": "", "Background": "Benchmark", "PerkIDs": [],
        "Perks": [], "TraitIDs": [], "Traits": [], "Injuries": [],
        "HumanOffset": index, "CurrentRolls": {},
    }
    for stat_index, stat in enumerate(STATS):
        values[stat + "Stars"] = (index + stat_index) % 4
    values["FutureRolls"] = {
        stat: [sum(gain_range(stat, values[stat + "Stars"])) // 2] * 10
        for stat in STATS
    }
    return Brother(**values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brothers", type=int, default=10)
    args = parser.parse_args()
    config = load_config(
        ROOT / "config" / "archetypes.json",
        ROOT / "config" / "classification.json",
    )
    brothers = [_brother(index) for index in range(args.brothers)]
    configure_engine()
    reset_profile()
    started = time.perf_counter()
    analysis_started = time.perf_counter()
    analysis = analyze_brothers(
        brothers, config.roles, config.classification, None
    )
    analysis_seconds = time.perf_counter() - analysis_started
    after_analysis = get_profile()
    validation_started = time.perf_counter()
    validation = build_projection_validation(
        brothers, analysis.fits, config.roles
    )
    validation_seconds = time.perf_counter() - validation_started
    final_profile = get_profile()
    print(json.dumps({
        "brothers": len(brothers),
        "archetypes": len(config.roles),
        "analysis_seconds": round(analysis_seconds, 3),
        "fit_trajectory_seconds": round(after_analysis["trajectory_s"], 3),
        "validation_seconds": round(validation_seconds, 3),
        "validation_trajectory_seconds": round(
            final_profile["trajectory_s"] - after_analysis["trajectory_s"], 3
        ),
        "total_seconds": round(time.perf_counter() - started, 3),
        "analysis_projection_calls": after_analysis["project_role_calls"],
        "validation_seeded_projection_calls": validation["summary"]["comparisons"],
        "validation_cache_hits": (
            final_profile["trajectory_cache_hits"]
            - after_analysis["trajectory_cache_hits"]
        ),
        "validation_cache_misses": (
            final_profile["trajectory_cache_misses"]
            - after_analysis["trajectory_cache_misses"]
        ),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
