import pytest

pytestmark = pytest.mark.unit

from bbtool.app.output import _midrank_from_counts, _discrete_sum_distribution, _roll_luck_to_level11, _role_relevant_roll_rank
from bbtool.models import Brother, STATS


def _bro(future):
    kwargs = dict(Name='Test', Title='', Level=10, XP=0, PerkPoints=0, PerksUsed=0,
                  LevelPoints=0, AP=9, BackgroundID='', Background='', PerkIDs=[], Perks=[],
                  TraitIDs=[], Traits=[], Injuries=[], HumanOffset=0, FutureRolls=future)
    for stat in STATS:
        kwargs[stat] = 50
        kwargs[stat + 'Stars'] = 0
    return Brother(**kwargs)


def test_single_roll_midrank_percentiles():
    dist = _discrete_sum_distribution(1, 3, 1)
    assert _midrank_from_counts(dist, 1) == 16.7
    assert _midrank_from_counts(dist, 2) == 50.0
    assert _midrank_from_counts(dist, 3) == 83.3


def test_roll_luck_and_role_weighting():
    future = {s: [2] for s in STATS}
    future['MAtk'] = [3]  # top 0-star MAtk roll => P83.3
    future['MDef'] = [1]  # bottom 0-star MDef roll => P16.7
    bro = _bro(future)
    luck = _roll_luck_to_level11(bro)
    assert luck['ByStat']['MAtk']['PercentilePct'] == 83.3
    assert luck['ByStat']['MDef']['PercentilePct'] == 16.7
    role = {'stats': {'MAtk': {'weight': 4.0}, 'MDef': {'weight': 4.0}}}
    assert _role_relevant_roll_rank(role, luck) == 50.0
