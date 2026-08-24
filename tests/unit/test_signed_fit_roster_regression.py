from copy import deepcopy

import pytest

from bbtool.classification import classify_bro, fit_label
from bbtool.models import STATS
from bbtool.projection.scoring import weighted_role_score

pytestmark = pytest.mark.unit


def _legacy_curve(target, baseline):
    target = float(target)
    minimum = min(float(baseline), target)
    gap = max(1.0, target - minimum)
    low = minimum - gap * (0.55 / 0.45)
    return [[low, 0.0], [minimum, 0.55], [target, 1.0], [target + gap, 1.05]]


def _legacy_role(role):
    old = deepcopy(role)
    for stat in old["stats"].values():
        if stat.get("fit"):
            stat["projected_curve"] = _legacy_curve(stat["target"], stat["baseline"])
    return old


def _profile(**overrides):
    values = dict.fromkeys(STATS, 50.0)
    values.update({"HP": 80.0, "Fatigue": 100.0, "Initiative": 90.0})
    values.update(overrides)
    return values


def _comparison(profile_name, values, roles, classification):
    rows = []
    for role in roles:
        old_fit = weighted_role_score(values, _legacy_role(role))[0]
        new_fit = weighted_role_score(values, role)[0]
        old_row = {"ProjectedFit": old_fit, "ProjectedFitPct": old_fit * 100,
                   "ProjectedFitFullMaxPct": old_fit * 100}
        new_row = {"ProjectedFit": new_fit, "ProjectedFitPct": new_fit * 100,
                   "ProjectedFitFullMaxPct": new_fit * 100}
        rows.append({
            "Brother": profile_name,
            "Archetype": role["name"],
            "OldFit": old_fit,
            "NewFit": new_fit,
            "FitDelta": new_fit - old_fit,
            "OldFitLabel": fit_label(old_fit, classification),
            "NewFitLabel": fit_label(new_fit, classification),
            "OldClassification": classify_bro(old_row, classification)[0],
            "NewClassification": classify_bro(new_row, classification)[0],
        })
    old_rank = {
        row["Archetype"]: rank
        for rank, row in enumerate(sorted(rows, key=lambda row: row["OldFit"], reverse=True), 1)
    }
    new_rank = {
        row["Archetype"]: rank
        for rank, row in enumerate(sorted(rows, key=lambda row: row["NewFit"], reverse=True), 1)
    }
    for row in rows:
        row["OldRank"] = old_rank[row["Archetype"]]
        row["NewRank"] = new_rank[row["Archetype"]]
    return rows


@pytest.fixture(scope="module")
def signed_fit_comparison(cfg):
    hybrid = next(role for role in cfg.roles if role["name"] == "Thrower Hybrid")
    slightly_below = _profile(**{
        stat: float(stat_cfg["baseline"]) - 1.0
        for stat, stat_cfg in hybrid["stats"].items()
        if stat_cfg.get("fit")
    })
    profiles = {
        "Melee-heavy Hybrid false positive": _profile(
            RAtk=42, MAtk=89, Fatigue=138, HP=103, Resolve=50, MDef=10, RDef=10
        ),
        "Ranged-heavy Hybrid false positive": _profile(
            RAtk=95, MAtk=42, Fatigue=138, HP=103, Resolve=50, MDef=10, RDef=10
        ),
        "Genuine dual-attack candidate": _profile(
            RAtk=88, MAtk=90, Fatigue=120, HP=90, Resolve=55, MDef=20, RDef=15
        ),
        "Slightly sub-baseline Hybrid": slightly_below,
    }
    return {
        name: _comparison(name, values, cfg.roles, cfg.classification)
        for name, values in profiles.items()
    }


def test_known_hybrid_false_positives_are_materially_penalized(signed_fit_comparison):
    for profile in ("Melee-heavy Hybrid false positive", "Ranged-heavy Hybrid false positive"):
        hybrid = next(
            row for row in signed_fit_comparison[profile]
            if row["Archetype"] == "Thrower Hybrid"
        )
        assert hybrid["FitDelta"] <= -0.20
        assert hybrid["NewFit"] < hybrid["OldFit"]


def test_genuine_and_slightly_sub_baseline_hybrids_remain_score_based(signed_fit_comparison):
    genuine = next(
        row for row in signed_fit_comparison["Genuine dual-attack candidate"]
        if row["Archetype"] == "Thrower Hybrid"
    )
    slight = next(
        row for row in signed_fit_comparison["Slightly sub-baseline Hybrid"]
        if row["Archetype"] == "Thrower Hybrid"
    )
    assert genuine["NewFit"] > slight["NewFit"]
    assert slight["NewFit"] >= 0.0


def test_old_new_matrix_covers_all_archetypes_classification_and_rank(signed_fit_comparison, cfg):
    expected_roles = {role["name"] for role in cfg.roles}
    rows = [row for profile_rows in signed_fit_comparison.values() for row in profile_rows]

    assert all({"Brother", "Archetype", "OldFit", "NewFit", "FitDelta",
                "OldClassification", "NewClassification", "OldRank", "NewRank"} <= row.keys()
               for row in rows)
    assert all({row["Archetype"] for row in profile_rows} == expected_roles
               for profile_rows in signed_fit_comparison.values())
    assert all(row["NewFit"] <= row["OldFit"] + 1e-12 for row in rows)
    assert any(row["OldClassification"] != row["NewClassification"] for row in rows)
    assert any(row["OldRank"] != row["NewRank"] for row in rows)
