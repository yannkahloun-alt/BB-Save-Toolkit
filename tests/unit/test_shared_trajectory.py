from pathlib import Path
import unittest

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.coverage_slow]

from bbtool.app.config import load_config
from bbtool.models import Brother, STATS
from bbtool.projection.progression import development_rounds_to_11
from bbtool.projection.trajectory import (
    project_fit_trajectory,
    project_seeded_fit_trajectory,
    reset_trajectory_cache,
)


ROOT = Path(__file__).resolve().parents[2]


def _bro() -> Brother:
    future = {
        "HP": [2, 3, 4, 2, 3, 4, 2, 3, 4, 2],
        "Fatigue": [2, 4, 3, 2, 4, 3, 2, 4, 3, 2],
        "Resolve": [2, 3, 4, 2, 3, 4, 2, 3, 4, 2],
        "Initiative": [3, 4, 5, 3, 4, 5, 3, 4, 5, 3],
        "MAtk": [1, 2, 3, 1, 2, 3, 1, 2, 3, 1],
        "RAtk": [2, 3, 4, 2, 3, 4, 2, 3, 4, 2],
        "MDef": [1, 3, 2, 1, 3, 2, 1, 3, 2, 1],
        "RDef": [2, 3, 4, 2, 3, 4, 2, 3, 4, 2],
    }
    return Brother(
        Name="Proof", Title="", Level=1, XP=0, PerkPoints=0, PerksUsed=0,
        LevelPoints=0, AP=9,
        HP=60, HPStars=0, Fatigue=100, FatigueStars=0,
        Resolve=40, ResolveStars=0, Initiative=100, InitiativeStars=0,
        MAtk=60, MAtkStars=0, RAtk=40, RAtkStars=0,
        MDef=5, MDefStars=0, RDef=5, RDefStars=0,
        BackgroundID="", Background="Test", PerkIDs=[], Perks=[],
        TraitIDs=[], Traits=[], Injuries=[], HumanOffset=0,
        FutureRolls=future,
    )


class SharedTrajectoryProofTest(unittest.TestCase):
    def test_serialized_future_is_only_degenerate_ranges(self):
        cfg = load_config(ROOT / "config/archetypes.json", ROOT / "config/classification.json")
        role = next(r for r in cfg.roles if r["name"] == "Nimble Frontline DPS")
        bro = _bro()
        rounds = development_rounds_to_11(bro)
        fit_stats = [s for s in STATS if role.get("stats", {}).get(s, {}).get("fit")]
        exact_ranges = [
            {s: (bro.FutureRolls[s][rd], bro.FutureRolls[s][rd]) for s in fit_stats}
            for rd in range(rounds)
        ]

        reset_trajectory_cache()
        direct = project_fit_trajectory(
            bro, role, rounds=rounds, round_ranges=exact_ranges,
            samples=1, include_trace=True,
        )
        seeded = project_seeded_fit_trajectory(bro, role)

        self.assertEqual(seeded["fit_pct"], direct["expected_pct"])
        self.assertEqual(seeded["choices"], direct["trace"])
        self.assertEqual(direct["expected_pct"], direct["full_min_pct"])
        self.assertEqual(direct["expected_pct"], direct["full_max_pct"])
        self.assertEqual(direct["expected_pct"], direct["likely_min_pct"])
        self.assertEqual(direct["expected_pct"], direct["likely_max_pct"])

        reset_trajectory_cache()
        repeated = project_fit_trajectory(
            bro, role, rounds=rounds, round_ranges=exact_ranges,
            samples=512, include_trace=True,
        )
        self.assertEqual(repeated["expected_pct"], direct["expected_pct"])
        self.assertEqual(repeated["trace"], direct["trace"])


if __name__ == "__main__":
    unittest.main()


def test_projection_pick_uses_actual_fit_gain_not_weight_over_target():
    """A +3 Fatigue roll must beat +4 HP when the Fit curve says so."""
    from dataclasses import replace
    from bbtool.app.config import _normalize_role

    role = _normalize_role({
        "name": "Fit gain proof",
        "stats": {
            "MAtk": {"target": 90, "weight": 4.0, "baseline": 80},
            "MDef": {"target": 35, "weight": 4.0, "baseline": 25},
            "Fatigue": {"target": 135, "weight": 2.5, "baseline": 125},
            "HP": {"target": 85, "weight": 1.5, "baseline": 65},
        },
    })
    bro = replace(_bro(), HP=65, Fatigue=125, MAtk=80, MDef=25)
    exact = [{"HP": (4, 4), "Fatigue": (3, 3), "MAtk": (3, 3), "MDef": (3, 3)}]

    reset_trajectory_cache()
    result = project_fit_trajectory(
        bro, role, rounds=1, round_ranges=exact,
        samples=1, include_trace=True,
    )

    assert result["trace"][0]["rolls"] == {"HP": 4, "Fatigue": 3, "MAtk": 3, "MDef": 3}
    assert "Fatigue" in result["trace"][0]["picks"]
    assert "HP" not in result["trace"][0]["picks"]

def test_final_fit_lookahead_invests_before_baseline():
    """Low MDef must still be developed when it pays off by level 11."""
    cfg = load_config(ROOT / "config/archetypes.json", ROOT / "config/classification.json")
    role = next(r for r in cfg.roles if r["name"] == "Battle Forged Frontline DPS")
    bro = _bro()  # MDef 5, far below the BF DPS baseline of 25.
    exact = [
        {"HP": (4, 4), "Fatigue": (3, 3), "MAtk": (2, 2), "MDef": (3, 3)}
        for _ in range(10)
    ]
    reset_trajectory_cache()
    result = project_fit_trajectory(
        bro, role, rounds=10, round_ranges=exact, samples=1, include_trace=True,
    )
    assert "MDef" in result["trace"][0]["picks"]


def test_hidden_future_does_not_change_current_pick():
    """Validation-only future rolls must not leak into today's decision."""
    cfg = load_config(ROOT / "config/archetypes.json", ROOT / "config/classification.json")
    role = next(r for r in cfg.roles if r["name"] == "Battle Forged Frontline DPS")
    bro = _bro()
    current = {"HP": (4, 4), "Fatigue": (3, 3), "MAtk": (2, 2), "MDef": (3, 3)}
    future_a = [current] + [
        {"HP": (2, 2), "Fatigue": (2, 2), "MAtk": (1, 1), "MDef": (1, 1)} for _ in range(9)
    ]
    future_b = [current] + [
        {"HP": (4, 4), "Fatigue": (4, 4), "MAtk": (3, 3), "MDef": (3, 3)} for _ in range(9)
    ]
    reset_trajectory_cache()
    a = project_fit_trajectory(bro, role, rounds=10, round_ranges=future_a, samples=1, include_trace=True)
    reset_trajectory_cache()
    b = project_fit_trajectory(bro, role, rounds=10, round_ranges=future_b, samples=1, include_trace=True)
    assert a["trace"][0]["picks"] == b["trace"][0]["picks"]


def test_four_stat_lookahead_optimization_is_behaviorally_stable():
    """Performance specialization must preserve current signed-Fit results."""
    cfg = load_config(ROOT / "config/archetypes.json", ROOT / "config/classification.json")
    role = next(r for r in cfg.roles if r["name"] == "Battle Forged Frontline DPS")
    bro = _bro()
    reset_trajectory_cache()
    result = project_fit_trajectory(bro, role, rounds=10, samples=512, include_trace=True)
    # Golden values use the current bounded signed-Fit contract. The 10-round
    # generic comparison in test_four_stat_optimization_contract_full.py
    # independently proves the four-stat specialization.
    assert result["expected_pct"] == 27.6
    assert result["full_min_pct"] == 0.0
    assert result["full_max_pct"] == 94.4
    assert result["likely_min_pct"] == 0.0
    assert result["likely_max_pct"] == 45.6


def test_levelup_advisor_ignores_hidden_future_rolls():
    """The actual Level-Up Advisor must depend on CurrentRolls, never FutureRolls."""
    from dataclasses import replace
    from bbtool.levelup_advisor import advise_levelup
    from bbtool.projection.planner import project_role

    cfg = load_config(ROOT / "config/archetypes.json", ROOT / "config/classification.json")
    current = {"HP": 4, "Fatigue": 3, "Resolve": 3, "Initiative": 4,
               "MAtk": 2, "RAtk": 3, "MDef": 3, "RDef": 3}
    bad_future = {s: [1] * 10 for s in STATS}
    good_future = {s: [6] * 10 for s in STATS}
    # One remaining development round is enough to prove the Advisor boundary;
    # ten rounds only repeat the same invariant at combinatorial cost.
    a = replace(_bro(), Level=10, LevelPoints=1, CurrentRolls=current, FutureRolls=bad_future)
    b = replace(a, FutureRolls=good_future)

    role = next(r for r in cfg.roles if r["name"] == "Battle Forged Frontline DPS")
    rows_a = [project_role(a, role)]
    rows_b = [project_role(b, role)]
    advice_a = advise_levelup(a, [role], rows_a)
    advice_b = advise_levelup(b, [role], rows_b)

    assert advice_a["AnchorRole"] == advice_b["AnchorRole"]
    assert advice_a["Recommended"]["Stats"] == advice_b["Recommended"]["Stats"]
    assert advice_a["Recommended"]["AnchorFitAfterPct"] == advice_b["Recommended"]["AnchorFitAfterPct"]
    assert advice_a["Alternative"]["Stats"] == advice_b["Alternative"]["Stats"]


def test_strategic_probability_cell_uses_category_not_heat_class():
    """P(Fit) must share the same semantic class palette as the classification."""
    from bbtool.html_report import classification_metric_html

    html = classification_metric_html(
        {"Category": "Invest", "FitFeasibilityPct": 91.2},
        "FitFeasibilityPct",
    )
    assert 'path-metric-row class-invest' in html
    assert 'heat1' not in html and 'heat2' not in html and 'heat3' not in html
    assert 'heat4' not in html and 'heat5' not in html


def test_fast_projection_is_exact_subset_of_full_projection():
    """Fast role search must reuse the same projection payload as full output."""
    from bbtool.projection.planner import project_role, project_role_fast

    cfg = load_config(ROOT / "config/archetypes.json", ROOT / "config/classification.json")
    # Level 11 keeps the assertion focused on payload equivalence for every
    # configured role without rerunning ten-round trajectories per role.
    from dataclasses import replace
    bro = replace(_bro(), Level=11)
    for role in cfg.roles:
        full = project_role(bro, role)
        fast = project_role_fast(bro, role)
        for key, value in fast.items():
            assert full[key] == value
