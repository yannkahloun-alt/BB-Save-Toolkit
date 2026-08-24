import pytest
from bbtool.app.config import _fit_curve
from bbtool.projection.scoring import curve_value, weighted_role_score

pytestmark=pytest.mark.unit

PTS=[[0,0],[10,0.5],[20,1.0],[30,1.1]]
@pytest.mark.parametrize('x,y',[(-5,0),(0,0),(10,.5),(20,1),(30,1.1),(40,1.1),(5,.25),(15,.75)])
def test_curve_value_cases(x,y): assert curve_value(x,PTS)==pytest.approx(y)
def test_curve_empty(): assert curve_value(10,[])==0
def test_curve_duplicate_x_segment(): assert curve_value(10,[[0,0],[10,.4],[10,.7],[20,1]])==pytest.approx(.4)
def test_curve_continuity():
    assert curve_value(10-1e-9,PTS)==pytest.approx(.5,abs=1e-9); assert curve_value(10+1e-9,PTS)==pytest.approx(.5,abs=1e-9)

@pytest.mark.parametrize(
    "value,expected",
    [(42, -1.0), (72, -1.0), (74, -0.75), (78, -0.25),
     (80, 0.0), (82, 0.25), (86, 0.75), (88, 1.0), (96, 1.0)],
)
def test_archetype_curve_has_bounded_signed_contribution(value, expected):
    assert curve_value(value, _fit_curve(88, 80)) == pytest.approx(expected)

def test_signed_components_reduce_fit_without_exposing_negative_total():
    signed = _fit_curve(88, 80)
    cfg = role({"RAtk": c(4, curve=signed), "MAtk": c(4, curve=signed)})
    score, components, _, _ = weighted_role_score({"RAtk": 42, "MAtk": 88}, cfg)
    assert components["RAtk"]["weighted"] == pytest.approx(-4.0)
    assert components["MAtk"]["weighted"] == pytest.approx(4.0)
    assert score == pytest.approx(0.0)

def role(cfgs): return {'stats':cfgs}
def c(weight=1,fit=True,curve=PTS): return {'weight':weight,'fit':fit,'projected_curve':curve}
def test_weighted_single_stat(): assert weighted_role_score({'MAtk':20},role({'MAtk':c()}))[0]==1
def test_weighted_equal_weights(): assert weighted_role_score({'MAtk':10,'MDef':20},role({'MAtk':c(),'MDef':c()}))[0]==pytest.approx(.75)
def test_weighted_unequal_weights(): assert weighted_role_score({'MAtk':10,'MDef':20},role({'MAtk':c(1),'MDef':c(3)}))[0]==pytest.approx(.875)
def test_non_fit_ignored(): assert weighted_role_score({'MAtk':20,'MDef':0},role({'MAtk':c(),'MDef':c(99,False)}))[0]==1
def test_no_fit_zero(): assert weighted_role_score({'MAtk':20},role({'MAtk':c(1,False)}))[0]==0
def test_above_target_can_exceed_100(): assert weighted_role_score({'MAtk':30},role({'MAtk':c()}))[0]==pytest.approx(1.1)
def test_below_baseline_curve_value(): assert weighted_role_score({'MAtk':5},role({'MAtk':c()}))[0]==pytest.approx(.25)
def test_components_reconcile():
    score,comp,_,_=weighted_role_score({'MAtk':10,'MDef':20},role({'MAtk':c(2),'MDef':c(3)})); assert score==pytest.approx(sum(v['weighted'] for v in comp.values())/5)

def test_saturation_at_target_with_plateau_curve():
    plateau=[[0,0],[10,.5],[20,1.0],[30,1.0]]
    role_cfg=role({'MAtk':c(curve=plateau)})
    assert weighted_role_score({'MAtk':20},role_cfg)[0]==1
    assert weighted_role_score({'MAtk':999},role_cfg)[0]==1


def test_curve_below_first_point_uses_first_y_not_first_x():
    pts = [[10, 100], [20, 200]]
    assert curve_value(5, pts) == pytest.approx(100)

def test_non_fit_before_fit_does_not_stop_scoring():
    cfg = role({'HP': c(99, False), 'MAtk': c(1, True)})
    score, components, _, _ = weighted_role_score({'HP': 50, 'MAtk': 20}, cfg)
    assert score == pytest.approx(1.0)
    assert set(components) == {'MAtk'}

def test_default_weight_contract_is_one():
    score, components, _, _ = weighted_role_score(
        {'MAtk': 10},
        role({'MAtk': {'fit': True, 'projected_curve': PTS}})
    )
    assert score == pytest.approx(.5)
    assert components['MAtk']['weight'] == pytest.approx(1.0)

def test_component_rounding_contract_is_four_decimals():
    pts = [[0, 0.0], [10, 0.123456]]
    score, components, _, _ = weighted_role_score(
        {'MAtk': 10},
        role({'MAtk': c(2.0, True, pts)})
    )
    assert score == pytest.approx(0.123456)
    assert components['MAtk']['utility'] == 0.1235
    assert components['MAtk']['weighted'] == 0.2469

def test_negative_weighted_score_is_clamped_to_zero():
    pts = [[0, -1.0], [10, -0.5]]
    score, _, _, _ = weighted_role_score(
        {'MAtk': 5},
        role({'MAtk': c(1.0, True, pts)})
    )
    assert score == 0.0

def test_weighted_role_score_auxiliary_contract():
    score, components, factor, metadata = weighted_role_score(
        {'MAtk': 20},
        role({'MAtk': c()})
    )
    assert score == pytest.approx(1.0)
    assert components
    assert factor == 1.0
    assert metadata == {}


def test_curve_first_point_boundary_uses_exact_first_y():
    pts = [[10, 100], [20, 200]]
    assert curve_value(10, pts) == pytest.approx(100)

def test_curve_first_point_indices_are_not_interchangeable():
    pts = [[10, 3], [20, 9]]
    assert curve_value(2, pts) == pytest.approx(3)
    assert curve_value(10, pts) == pytest.approx(3)


@pytest.mark.parametrize(
    "value,expected",
    [
        (-100, 0.0),
        (0, 0.0),
        (2.5, 0.125),
        (5, 0.25),
        (10, 0.5),
        (12.5, 0.625),
        (15, 0.75),
        (20, 1.0),
        (25, 1.05),
        (30, 1.1),
        (100, 1.1),
    ],
)
def test_curve_value_full_piecewise_contract(value, expected):
    assert curve_value(value, PTS) == pytest.approx(expected)


def test_curve_value_is_monotone_for_monotone_curve():
    samples = [curve_value(x, PTS) for x in range(-10, 51)]
    assert samples == sorted(samples)


def test_curve_value_exact_knots_round_trip():
    pts = [[-3.5, 7.25], [1.25, 9.5], [8.75, 12.0]]
    for x, y in pts:
        assert curve_value(x, pts) == pytest.approx(y)


def test_curve_value_linear_interpolation_on_nonzero_origin():
    pts = [[10, 100], [20, 160]]
    assert curve_value(12.5, pts) == pytest.approx(115)
    assert curve_value(15, pts) == pytest.approx(130)
    assert curve_value(17.5, pts) == pytest.approx(145)


def test_curve_value_clamps_to_endpoint_values_not_endpoint_coordinates():
    pts = [[10, 3], [20, 9]]
    assert curve_value(-999, pts) == pytest.approx(3)
    assert curve_value(999, pts) == pytest.approx(9)


def test_curve_value_empty_points_contract():
    assert curve_value(123, []) == 0.0


def test_curve_value_single_point_contract():
    pts = [[10, 3]]
    assert curve_value(-100, pts) == pytest.approx(3)
    assert curve_value(10, pts) == pytest.approx(3)
    assert curve_value(100, pts) == pytest.approx(3)


def test_curve_value_does_not_mutate_input_points():
    pts = [[0, 0], [10, 1]]
    before = [row[:] for row in pts]
    curve_value(5, pts)
    assert pts == before


def test_weighted_role_score_ignores_non_fit_stats_but_keeps_later_fit_stats():
    cfg = role({
        "HP": c(999.0, False),
        "MAtk": c(2.0, True),
    })
    score, components, factor, metadata = weighted_role_score(
        {"HP": 999, "MAtk": 10},
        cfg,
    )
    assert score == pytest.approx(0.5)
    assert set(components) == {"MAtk"}
    assert factor == 1.0
    assert metadata == {}


def test_weighted_role_score_weighted_average_contract():
    cfg = role({
        "MAtk": c(1.0, True),
        "MDef": c(3.0, True),
    })
    values = {"MAtk": 10, "MDef": 20}
    score, components, _, _ = weighted_role_score(values, cfg)
    assert score == pytest.approx(0.875)
    assert components["MAtk"]["weighted"] == pytest.approx(0.5)
    assert components["MDef"]["weighted"] == pytest.approx(3.0)


def test_weighted_role_score_zero_denominator_returns_zero():
    cfg = role({
        "MAtk": c(0.0, True),
        "MDef": c(0.0, True),
    })
    score, components, _, _ = weighted_role_score(
        {"MAtk": 10, "MDef": 20},
        cfg,
    )
    assert score == 0.0
    assert set(components) == {"MAtk", "MDef"}


def test_weighted_role_score_negative_result_is_clamped_but_high_result_is_not():
    negative_pts = [[0, -1.0], [10, -0.5]]
    negative_score, _, _, _ = weighted_role_score(
        {"MAtk": 10},
        role({"MAtk": c(1.0, True, negative_pts)}),
    )
    assert negative_score == 0.0

    high_pts = [[0, 0.0], [10, 2.0]]
    high_score, _, _, _ = weighted_role_score(
        {"MAtk": 10},
        role({"MAtk": c(1.0, True, high_pts)}),
    )
    assert high_score == pytest.approx(2.0)


def test_curve_value_lower_clamp_is_part_of_the_contract():
    pts = [[10, 3], [20, 9], [30, 12]]
    assert curve_value(-1000, pts) == pytest.approx(3)
    assert curve_value(9.999, pts) == pytest.approx(3)
    assert curve_value(10, pts) == pytest.approx(3)
    assert curve_value(15, pts) == pytest.approx(6)
