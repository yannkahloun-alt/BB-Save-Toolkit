import pytest

pytestmark = pytest.mark.unit

from bbtool.classification import classify_bro, fit_label, perk_compatibility, role_sort_key


def _classification_cfg():
    return {
        "display": {
            "premium_fit": 0.95,
            "good_fit": 0.82,
            "viable_fit": 0.68,
        },
        "thresholds": {
            "Invest": {"min_projected_fit": 0.95},
            "Use": {"min_projected_fit": 0.65},
            "Fodder": {"min_full_max_fit": 0.65},
        },
    }


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1.20, "PREMIUM"),
        (0.951, "PREMIUM"),
        (0.95, "PREMIUM"),
        (0.949, "GOOD"),
        (0.90, "GOOD"),
        (0.82, "GOOD"),
        (0.819, "VIABLE"),
        (0.75, "VIABLE"),
        (0.68, "VIABLE"),
        (0.679, "LOW"),
        (0.10, "LOW"),
    ],
)
def test_fit_label_full_threshold_contract(score, expected):
    assert fit_label(score, _classification_cfg()) == expected


def test_perk_compatibility_conflicts_are_sorted_and_dominate_affinity(bro_factory):
    role = {
        "perk_conflicts": ["A", "B"],
        "perk_affinity": {"C": 6},
    }
    assert perk_compatibility(bro_factory(Perks=[]), role) == ("NEUTRAL", 0, [])
    assert perk_compatibility(bro_factory(Perks=["A"]), role) == ("CONFLICT", -100, ["A"])
    assert perk_compatibility(bro_factory(Perks=["B", "C", "A"]), role) == (
        "CONFLICT",
        -100,
        ["A", "B"],
    )


@pytest.mark.parametrize(
    ("weights", "perks", "expected_label", "expected_total", "expected_signals"),
    [
        ({}, [], "NEUTRAL", 0, []),
        ({"A": -1}, ["A"], "NEUTRAL", -1, ["A"]),
        ({"A": 1}, ["A"], "LOW", 1, ["A"]),
        ({"A": 2}, ["A"], "MEDIUM", 2, ["A"]),
        ({"A": 3}, ["A"], "MEDIUM", 3, ["A"]),
        ({"A": 4}, ["A"], "MEDIUM", 4, ["A"]),
        ({"A": 5}, ["A"], "HIGH", 5, ["A"]),
        ({"A": 6}, ["A"], "HIGH", 6, ["A"]),
        ({"A": "2", "B": 3, "C": 99}, ["A", "B"], "HIGH", 5, ["A", "B"]),
    ],
)
def test_perk_compatibility_affinity_thresholds_and_accumulation(
    bro_factory, weights, perks, expected_label, expected_total, expected_signals
):
    role = {"perk_conflicts": [], "perk_affinity": weights}
    assert perk_compatibility(bro_factory(Perks=perks), role) == (
        expected_label,
        expected_total,
        expected_signals,
    )


def test_perk_compatibility_defaults_missing_role_lists(bro_factory):
    assert perk_compatibility(bro_factory(Perks=["A"]), {}) == ("NEUTRAL", 0, [])


def _sort_row(**overrides):
    row = {
        "ProjectedFit": 0.80,
        "ProjectedFitPct": 80,
        "FitFeasibilityPct": 50,
        "ProjectedFitLikelyMinPct": 70,
    }
    row.update(overrides)
    return row


def test_role_sort_conflict_penalty_is_exactly_one_fit_point():
    normal = _sort_row()
    conflict = _sort_row(PerkCompatibility="CONFLICT")
    assert role_sort_key(normal) == (0.80, 50.0, 70.0)
    assert role_sort_key(conflict)[0] == pytest.approx(-0.20)
    assert role_sort_key(conflict)[1:] == (50.0, 70.0)
    assert role_sort_key(normal) > role_sort_key(conflict)


def test_role_sort_conflict_uses_value_equality_not_string_identity():
    expected_conflict = "CONFLICT"
    conflict_value = "".join(["CON", "FLICT"])
    assert conflict_value == expected_conflict
    assert conflict_value is not expected_conflict
    assert role_sort_key(_sort_row(PerkCompatibility=conflict_value))[0] == pytest.approx(-0.20)


def test_role_sort_secondary_and_tertiary_keys_are_effective():
    base = _sort_row()
    better_feasibility = _sort_row(FitFeasibilityPct=51)
    better_floor = _sort_row(ProjectedFitLikelyMinPct=71)
    assert role_sort_key(better_feasibility) > role_sort_key(base)
    assert role_sort_key(better_floor) > role_sort_key(base)


def test_role_sort_defaults_and_projected_fit_pct_fallback():
    row = {"ProjectedFit": 0.8, "ProjectedFitPct": 77}
    assert role_sort_key(row) == (0.8, 0.0, 77.0)


def test_role_sort_is_stable_for_equal_keys():
    rows = [_sort_row(Role="A"), _sort_row(Role="B")]
    assert sorted(rows, key=role_sort_key, reverse=True) == rows


def _classify_row(pf, full_max=None, *, projected_pct=None):
    if projected_pct is None:
        projected_pct = pf * 100
    row = {"ProjectedFit": pf, "ProjectedFitPct": projected_pct}
    if full_max is not None:
        row["ProjectedFitFullMaxPct"] = full_max
    return row


@pytest.mark.parametrize(
    ("pf", "full_max", "expected"),
    [
        (1.10, 10, "Invest"),
        (0.951, 10, "Invest"),
        (0.95, 10, "Invest"),
        (0.949, 10, "Use"),
        (0.80, 10, "Use"),
        (0.65, 10, "Use"),
        (0.649, 100, "Fodder"),
        (0.10, 65.1, "Fodder"),
        (0.10, 65.0, "Fodder"),
        (0.10, 64.9, "Trash"),
        (0.10, 0, "Trash"),
    ],
)
def test_classify_bro_full_threshold_contract(pf, full_max, expected):
    category, reason = classify_bro(_classify_row(pf, full_max), _classification_cfg())
    assert category == expected
    assert f"{pf:.2f}" in reason


def test_classify_bro_uses_full_max_percentage_conversion():
    cfg = _classification_cfg()
    # 64.9% is below the 0.65 Fodder threshold, 65.0% is exactly on it.
    assert classify_bro(_classify_row(0.10, 64.9), cfg)[0] == "Trash"
    assert classify_bro(_classify_row(0.10, 65.0), cfg)[0] == "Fodder"
    assert classify_bro(_classify_row(0.10, 6500.0), cfg)[0] == "Fodder"


def test_classify_bro_falls_back_to_projected_fit_pct_when_full_max_absent():
    cfg = _classification_cfg()
    assert classify_bro(_classify_row(0.10, None, projected_pct=65), cfg)[0] == "Fodder"
    assert classify_bro(_classify_row(0.10, None, projected_pct=64.9), cfg)[0] == "Trash"
