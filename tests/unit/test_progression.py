import pytest
from types import SimpleNamespace

pytestmark = pytest.mark.unit

from bbtool.models import Brother, STATS
from bbtool.projection.progression import average_gain, development_rounds_to_11, gain_range


BASE_RANGES = {
    "HP": (2, 4),
    "Fatigue": (2, 4),
    "Resolve": (2, 4),
    "Initiative": (3, 5),
    "MAtk": (1, 3),
    "RAtk": (2, 4),
    "MDef": (1, 3),
    "RDef": (2, 4),
}

STAR_ADJUSTMENTS = {
    0: (0, 0),
    1: (1, 0),
    2: (2, 0),
    3: (2, 1),
}


def _bro(*, level: int, level_points: int = 0) -> Brother:
    kwargs = {
        "Name": "Progression Test",
        "Title": "",
        "Level": level,
        "XP": 0,
        "PerkPoints": 0,
        "PerksUsed": 0,
        "LevelPoints": level_points,
        "AP": 9,
        "BackgroundID": "",
        "Background": "Test",
        "PerkIDs": [],
        "Perks": [],
        "TraitIDs": [],
        "Traits": [],
        "Injuries": [],
        "HumanOffset": 0,
    }
    for stat in STATS:
        kwargs[stat] = 50
        kwargs[f"{stat}Stars"] = 0
    return Brother(**kwargs)


@pytest.mark.parametrize(
    ("stat", "expected"),
    [
        ("Initiative", (3, 5)),
        ("MAtk", (1, 3)),
        ("MDef", (1, 3)),
        ("HP", (2, 4)),
        ("Fatigue", (2, 4)),
        ("Resolve", (2, 4)),
        ("RAtk", (2, 4)),
        ("RDef", (2, 4)),
    ],
)
def test_gain_range_zero_star_family_ranges(stat, expected):
    assert gain_range(stat, 0) == expected


@pytest.mark.parametrize("stat", STATS)
@pytest.mark.parametrize("stars", (0, 1, 2, 3))
def test_gain_range_all_stats_all_star_counts(stat, stars):
    base_lo, base_hi = BASE_RANGES[stat]
    lo_delta, hi_delta = STAR_ADJUSTMENTS[stars]
    assert gain_range(stat, stars) == (base_lo + lo_delta, base_hi + hi_delta)


@pytest.mark.parametrize("stat", STATS)
@pytest.mark.parametrize("stars", (0, 1, 2, 3))
def test_average_gain_is_exact_midpoint_of_gain_range(stat, stars):
    lo, hi = gain_range(stat, stars)
    assert average_gain(stat, stars) == (lo + hi) / 2.0


@pytest.mark.parametrize(
    ("level", "level_points", "expected_rounds"),
    [
        (1, 0, 10),
        (2, 1, 10),
        (10, 0, 1),
        (11, 0, 0),
        (12, 0, 0),
        (25, 0, 0),
    ],
)
def test_development_rounds_to_11(level, level_points, expected_rounds):
    assert development_rounds_to_11(_bro(level=level, level_points=level_points)) == expected_rounds


def test_development_rounds_to_11_never_negative_even_with_negative_pending_points():
    assert development_rounds_to_11(_bro(level=20, level_points=-3)) == 0

def test_gain_range_uses_string_value_equality_not_object_identity():
    expected_name = "Initiative"
    stat = "".join(["Initia", "tive"])
    assert stat == expected_name
    assert stat is not expected_name
    assert gain_range(stat, 0) == (3, 5)


def test_development_rounds_to_11_missing_levelpoints_defaults_to_zero():
    bro = SimpleNamespace(Level=2)
    assert development_rounds_to_11(bro) == 9

