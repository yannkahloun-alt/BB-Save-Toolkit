from types import SimpleNamespace

import bbtool.projection.planner as planner
from bbtool.models import STATS


def _trajectory(expected_pct=37.25):
    return {
        "expected_pct": expected_pct,
        "likely_min_pct": 30.0,
        "likely_max_pct": 45.0,
        "full_min_pct": 20.0,
        "full_max_pct": 55.0,
        "feasibility_pct": 12.5,
        "stat_ranges": {
            stat: {"min": 10.0 + i, "ev": 10.55 + i, "max": 11.0 + i}
            for i, stat in enumerate(STATS)
        },
        "fit_stats": tuple(STATS[:4]),
        "state_count": 17,
        "pruned": True,
    }


def _values():
    return {stat: 10.55 + i for i, stat in enumerate(STATS)}


def test_base_projection_payload_contract_is_exact():
    role = {"name": "Role X"}
    trajectory = _trajectory(37.25)
    values = _values()
    components = {"MAtk": {"weighted": 1.23}}

    payload = planner._base_projection_payload(role, trajectory, values, components)

    assert payload["Role"] == "Role X"
    assert payload["ProjectedFit"] == 0.3725

    precision_payload = planner._base_projection_payload(
        role, _trajectory(37.256), values, components
    )
    assert precision_payload["ProjectedFit"] == 0.3726
    assert payload["ProjectedFitPct"] == 37.25
    assert payload["ProjectedFitLikelyMinPct"] == 30.0
    assert payload["ProjectedFitLikelyMaxPct"] == 45.0
    assert payload["ProjectedFitFullMinPct"] == 20.0
    assert payload["ProjectedFitFullMaxPct"] == 55.0
    assert payload["FitFeasibilityPct"] == 12.5
    assert payload["ProjectedComponents"] is components

    for i, stat in enumerate(STATS):
        assert payload[stat] == round(10.55 + i, 1)


def test_first_round_ranges_requires_positive_level_points_and_nonempty_rolls():
    positive = SimpleNamespace(LevelPoints=1, CurrentRolls={"HP": 4, "MAtk": 3})
    zero = SimpleNamespace(LevelPoints=0, CurrentRolls={"HP": 4, "MAtk": 3})
    negative = SimpleNamespace(LevelPoints=-1, CurrentRolls={"HP": 4, "MAtk": 3})
    missing_points = SimpleNamespace(CurrentRolls={"HP": 4, "MAtk": 3})
    no_rolls = SimpleNamespace(LevelPoints=1, CurrentRolls={})

    assert planner._first_round_ranges(positive) == {"HP": (4, 4), "MAtk": (3, 3)}
    assert planner._first_round_ranges(zero) is None
    assert planner._first_round_ranges(negative) is None
    assert planner._first_round_ranges(missing_points) is None
    assert planner._first_round_ranges(no_rolls) is None


def test_project_role_fast_increments_only_fast_and_total(monkeypatch):
    original = dict(planner.PROFILE)
    try:
        planner.PROFILE["project_role_calls"] = 10
        planner.PROFILE["fast_projection_calls"] = 20
        planner.PROFILE["full_projection_calls"] = 30

        trajectory = _trajectory()
        values = _values()
        components = {"x": 1}
        monkeypatch.setattr(planner, "_project_role_common", lambda bro, role: (trajectory, values, components))

        result = planner.project_role_fast(object(), {"name": "R"})

        assert planner.PROFILE["project_role_calls"] == 11
        assert planner.PROFILE["fast_projection_calls"] == 21
        assert planner.PROFILE["full_projection_calls"] == 30
        assert result["ProjectedFit"] == 0.3725
    finally:
        planner.PROFILE.clear()
        planner.PROFILE.update(original)


def test_project_role_increments_only_full_and_total_and_returns_exact_ranges(monkeypatch):
    original = dict(planner.PROFILE)
    try:
        planner.PROFILE["project_role_calls"] = 10
        planner.PROFILE["fast_projection_calls"] = 20
        planner.PROFILE["full_projection_calls"] = 30

        trajectory = _trajectory()
        values = _values()
        components = {"x": 1}
        monkeypatch.setattr(planner, "_project_role_common", lambda bro, role: (trajectory, values, components))

        result = planner.project_role(object(), {"name": "R"})

        assert planner.PROFILE["project_role_calls"] == 11
        assert planner.PROFILE["fast_projection_calls"] == 20
        assert planner.PROFILE["full_projection_calls"] == 31
        assert result["ProjectedFit"] == 0.3725
        assert result["FitTrajectoryStateCount"] == 17
        assert result["FitTrajectoryPruned"] is True
        assert set(result["ProjectedRanges"]) == set(STATS[:4])
        for stat in STATS[:4]:
            assert result["ProjectedRanges"][stat] == trajectory["stat_ranges"][stat]
    finally:
        planner.PROFILE.clear()
        planner.PROFILE.update(original)
