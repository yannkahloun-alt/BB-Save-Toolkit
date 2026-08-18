from types import SimpleNamespace

import pytest

import bbtool.projection.context as context
from bbtool.models import STATS, Brother


def _bro(name="B", *, perks=None, level=5, level_points=0):
    return Brother(
        Name=name, Title="", Level=level, XP=0, PerkPoints=0, PerksUsed=0,
        LevelPoints=level_points, AP=9,
        HP=70, HPStars=0,
        Fatigue=100, FatigueStars=0,
        Resolve=40, ResolveStars=0,
        Initiative=90, InitiativeStars=0,
        MAtk=70, MAtkStars=0,
        RAtk=40, RAtkStars=0,
        MDef=20, MDefStars=0,
        RDef=5, RDefStars=0,
        BackgroundID="", Background="",
        PerkIDs=[], Perks=list(perks or []),
        TraitIDs=[], Traits=[], Injuries=[], HumanOffset=0,
        CurrentRolls={}, FutureRolls={},
    )


def _fingerprint_stub(*, perks=None, include_level=True, include_level_points=True):
    values = {}
    for idx, stat in enumerate(STATS):
        values[stat] = 50 + idx
        values[stat + "Stars"] = idx % 4
    values["Perks"] = list(perks or [])
    if include_level:
        values["Level"] = 7
    if include_level_points:
        values["LevelPoints"] = 2
    return SimpleNamespace(**values)


def test_context_cache_limit_is_exactly_256():
    assert context._BRO_CONTEXT_CACHE_MAX == 256


@pytest.mark.parametrize(
    "existing_count,should_preserve_existing",
    [
        (254, True),
        (255, True),
        (256, False),
        (257, False),
    ],
)
def test_context_cache_clears_at_or_above_limit(monkeypatch, existing_count, should_preserve_existing):
    context.reset_bro_context_cache()
    monkeypatch.setattr(context, "_BRO_CONTEXT_CACHE_MAX", 256)

    sentinels = {("sentinel", i): ("cached", i) for i in range(existing_count)}
    context._BRO_CONTEXT_CACHE.update(sentinels)

    bro = _bro(name=f"B{existing_count}")
    result = context.bro_projection_context(bro)
    key = context.bro_fingerprint(bro)

    assert context._BRO_CONTEXT_CACHE[key] is result
    if should_preserve_existing:
        assert all(k in context._BRO_CONTEXT_CACHE for k in sentinels)
        assert len(context._BRO_CONTEXT_CACHE) == existing_count + 1
    else:
        assert all(k not in context._BRO_CONTEXT_CACHE for k in sentinels)
        assert {key: result} == context._BRO_CONTEXT_CACHE


def test_bro_fingerprint_includes_sorted_perks():
    a = _fingerprint_stub(perks=["B", "A"])
    b = _fingerprint_stub(perks=["A", "B"])
    c = _fingerprint_stub(perks=["A"])

    assert context.bro_fingerprint(a) == context.bro_fingerprint(b)
    assert context.bro_fingerprint(a) != context.bro_fingerprint(c)
    assert context.bro_fingerprint(a)[2] == ("A", "B")


def test_bro_fingerprint_defaults_missing_level_to_zero():
    bro = _fingerprint_stub(include_level=False)
    assert context.bro_fingerprint(bro)[3] == 0


def test_bro_fingerprint_defaults_missing_level_points_to_zero():
    bro = _fingerprint_stub(include_level_points=False)
    assert context.bro_fingerprint(bro)[4] == 0
