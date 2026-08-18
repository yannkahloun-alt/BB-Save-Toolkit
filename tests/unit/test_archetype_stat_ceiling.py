import copy
import json
import math

import pytest

from bbtool.app.config import _normalize_role
from bbtool.projection.scoring import weighted_role_score


def role(ceiling_marker="missing"):
    stat = {"target": 100, "baseline": 80, "weight": 2.0}
    if ceiling_marker != "missing":
        stat["ceiling"] = ceiling_marker
    return _normalize_role({"name": "Ceiling Test", "stats": {"Fatigue": stat}})


def test_no_ceiling_preserves_existing_below_target_target_and_above_target_values():
    r = role()
    for value in (90, 100, 110, 130):
        score, comp, _, _ = weighted_role_score({"Fatigue": value}, r)
        cfg = r["stats"]["Fatigue"]
        from bbtool.projection.scoring import curve_value
        assert score == pytest.approx(curve_value(value, cfg["projected_curve"]))
        assert comp["Fatigue"]["fit_value"] == value
        assert comp["Fatigue"]["ceiling"] is None
        assert comp["Fatigue"]["capped"] is False


def test_below_and_exact_ceiling_use_projected_value():
    r = role(120)
    for value in (110, 120):
        score, comp, _, _ = weighted_role_score({"Fatigue": value}, r)
        assert comp["Fatigue"]["value"] == value
        assert comp["Fatigue"]["fit_value"] == value
        assert comp["Fatigue"]["capped"] is False


def test_above_ceiling_equals_ceiling_contribution():
    r = role(120)
    at, at_comp, _, _ = weighted_role_score({"Fatigue": 120}, r)
    above, above_comp, _, _ = weighted_role_score({"Fatigue": 140}, r)
    assert above == at
    assert above_comp["Fatigue"]["value"] == 140
    assert above_comp["Fatigue"]["fit_value"] == 120
    assert above_comp["Fatigue"]["capped"] is True
    assert above_comp["Fatigue"]["utility"] == at_comp["Fatigue"]["utility"]


def test_ceiling_equal_target_saturates_at_target():
    r = role(100)
    scores = [weighted_role_score({"Fatigue": v}, r)[0] for v in (100, 110, 150)]
    assert scores[0] == scores[1] == scores[2]


@pytest.mark.parametrize("bad", [99, "120", True, float("inf"), float("-inf"), float("nan")])
def test_invalid_ceiling_rejected(bad):
    with pytest.raises(ValueError):
        role(bad)


def test_ceiling_without_target_rejected():
    with pytest.raises(ValueError):
        _normalize_role({"name": "Bad", "stats": {"Fatigue": {"ceiling": 120}}})


def test_backward_compatibility_no_ceiling_normalization_is_identical():
    original = {
        "name": "Legacy",
        "stats": {
            "RAtk": {"target": 88, "weight": 4.5, "baseline": 80},
            "Fatigue": {"target": 115, "weight": 2.0, "baseline": 95},
        },
    }
    a = _normalize_role(copy.deepcopy(original))
    b = _normalize_role(copy.deepcopy(original))
    assert a == b
    assert all("ceiling" not in cfg for cfg in a["stats"].values())


def test_classification_component_extra_surplus_does_not_improve_fit_with_ceiling():
    capped = _normalize_role({
        "name": "Thrower",
        "stats": {
            "RAtk": {"target": 88, "baseline": 80, "weight": 4.5},
            "Fatigue": {"target": 115, "baseline": 95, "weight": 2.0, "ceiling": 120},
        },
    })
    a, ca, _, _ = weighted_role_score({"RAtk": 88, "Fatigue": 120}, capped)
    b, cb, _, _ = weighted_role_score({"RAtk": 88, "Fatigue": 140}, capped)
    assert a == b
    assert ca["Fatigue"]["utility"] == cb["Fatigue"]["utility"]

    uncapped = _normalize_role({
        "name": "Thrower",
        "stats": {
            "RAtk": {"target": 88, "baseline": 80, "weight": 4.5},
            "Fatigue": {"target": 115, "baseline": 95, "weight": 2.0},
        },
    })
    ua, _, _, _ = weighted_role_score({"RAtk": 88, "Fatigue": 120}, uncapped)
    ub, _, _, _ = weighted_role_score({"RAtk": 88, "Fatigue": 140}, uncapped)
    assert ub >= ua


def _bro(fatigue):
    from bbtool.models import Brother
    return Brother(
        Name="Ceiling", Title="", Level=11, XP=0, PerkPoints=0, PerksUsed=0,
        LevelPoints=0, AP=9,
        HP=80, HPStars=0, Fatigue=fatigue, FatigueStars=0,
        Resolve=45, ResolveStars=0, Initiative=100, InitiativeStars=0,
        MAtk=70, MAtkStars=0, RAtk=88, RAtkStars=0,
        MDef=10, MDefStars=0, RDef=5, RDefStars=0,
        BackgroundID="", Background="Test", PerkIDs=[], Perks=[],
        TraitIDs=[], Traits=[], Injuries=[], HumanOffset=fatigue,
    )


def test_trajectory_keeps_projected_stat_uncapped_but_caps_fit_valuation():
    from bbtool.projection.planner import project_role
    from bbtool.projection.trajectory import reset_trajectory_cache

    r = _normalize_role({
        "name": "Thrower",
        "stats": {
            "RAtk": {"target": 88, "baseline": 80, "weight": 4.5},
            "Fatigue": {"target": 115, "baseline": 95, "weight": 2.0, "ceiling": 120},
        },
    })

    reset_trajectory_cache()
    at = project_role(_bro(120), r)
    reset_trajectory_cache()
    above = project_role(_bro(140), r)

    assert at["Fatigue"] == 120
    assert above["Fatigue"] == 140
    assert above["ProjectedFitPct"] == at["ProjectedFitPct"]
    assert above["ProjectedComponents"]["Fatigue"]["value"] == 140
    assert above["ProjectedComponents"]["Fatigue"]["fit_value"] == 120
    assert above["ProjectedComponents"]["Fatigue"]["capped"] is True


def test_report_explains_ceiling_without_rewriting_projection():
    from bbtool.html_report import development_focus_html

    b = _bro(140)
    row = {
        "ProjectedComponents": {
            "Fatigue": {
                "value": 140.0,
                "fit_value": 120.0,
                "ceiling": 120.0,
                "capped": True,
                "weight": 2.0,
                "utility": 1.05,
                "weighted": 2.1,
            }
        },
        "ProjectedRanges": {
            "Fatigue": {"min": 140.0, "ev": 140.0, "max": 140.0}
        },
    }
    html = development_focus_html(b, row)
    assert "Expected 140" in html
    assert "Fit ceiling 120" in html
    assert "using 120" in html
