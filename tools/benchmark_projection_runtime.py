"""Deterministic, network-free cold projection benchmark for issue #70."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import tracemalloc

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


def _representative_brothers() -> list[Brother]:
    """Sanitized real-state shapes from issue #131's public diagnostic bundle."""
    shapes = [
        {
            "Level": 1, "HP": 52, "Fatigue": 94, "Resolve": 32,
            "Initiative": 105, "MAtk": 57, "RAtk": 48, "MDef": 5,
            "RDef": 4, "HPStars": 0, "FatigueStars": 0,
            "ResolveStars": 0, "InitiativeStars": 0, "MAtkStars": 1,
            "RAtkStars": 0, "MDefStars": 1, "RDefStars": 2,
        },
        {
            "Level": 3, "HP": 61, "Fatigue": 101, "Resolve": 41,
            "Initiative": 109, "MAtk": 53, "RAtk": 63, "MDef": 1,
            "RDef": 1, "HPStars": 0, "FatigueStars": 0,
            "ResolveStars": 0, "InitiativeStars": 1, "MAtkStars": 0,
            "RAtkStars": 2, "MDefStars": 0, "RDefStars": 1,
        },
    ]
    brothers = []
    for index, shape in enumerate(shapes):
        brother = _brother(index)
        values = {**brother.__dict__, **shape}
        values.update(
            Name=f"Representative {index + 1}",
            Background="Sanitized issue-131 shape",
            HumanOffset=10_000 + index,
        )
        values["FutureRolls"] = {
            stat: [sum(gain_range(stat, values[stat + "Stars"])) // 2] * 10
            for stat in STATS
        }
        brothers.append(Brother(**values))
    return brothers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brothers", type=int, default=10)
    parser.add_argument(
        "--workload", choices=("synthetic", "representative"),
        default="synthetic",
    )
    parser.add_argument(
        "--measure-python-heap", action="store_true",
        help="Reproduce the costly allocation tracing that issue #131 identified",
    )
    args = parser.parse_args()
    config = load_config(
        ROOT / "config" / "archetypes.json",
        ROOT / "config" / "classification.json",
    )
    brothers = (
        _representative_brothers()
        if args.workload == "representative"
        else [_brother(index) for index in range(args.brothers)]
    )
    configure_engine()
    reset_profile()
    if args.measure_python_heap:
        tracemalloc.start()
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
    payload = {
        "workload": args.workload,
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
        "validation_summary": validation["summary"],
        "validation_cache_hits": (
            final_profile["trajectory_cache_hits"]
            - after_analysis["trajectory_cache_hits"]
        ),
        "validation_cache_misses": (
            final_profile["trajectory_cache_misses"]
            - after_analysis["trajectory_cache_misses"]
        ),
        "slowest_projection": (
            after_analysis["slowest_projections"][0]
            if after_analysis["slowest_projections"] else None
        ),
        "python_heap_tracing": args.measure_python_heap,
    }
    if args.measure_python_heap:
        payload["python_heap_peak_bytes"] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
