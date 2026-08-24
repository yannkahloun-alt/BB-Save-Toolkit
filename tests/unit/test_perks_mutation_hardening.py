import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from bbtool.models import STATS
from bbtool.projection import perks


def _bro(bro_factory, **kwargs):
    return bro_factory(**kwargs)


def _effects(stat, *effects):
    return {stat: list(effects)}


def test_effective_value_missing_effect_value_defaults_to_zero(bro_factory):
    b = _bro(bro_factory)
    assert perks.effective_stat_value(b, "HP", 60, _effects("HP", {"op": "+="})) == 60
    assert perks.effective_stat_value(b, "HP", 60, _effects("HP", {"op": "-="})) == 60


@pytest.mark.parametrize("unknown_op", ["!=", ".=", "?=", "zz", "==="])
def test_effective_value_unknown_operators_are_ignored(bro_factory, unknown_op):
    b = _bro(bro_factory)
    assert perks.effective_stat_value(
        b, "HP", 60.5, _effects("HP", {"op": unknown_op, "value": 7, "property": "HitpointsMult"})
    ) == pytest.approx(60.5)


def test_effective_value_dynamic_operator_strings_use_value_equality(bro_factory):
    b = _bro(bro_factory)
    mul = "".join(["*", "="])
    div = "".join(["/", "="])
    expected_mul = "*="
    expected_div = "/="
    assert mul == expected_mul and mul is not expected_mul
    assert div == expected_div and div is not expected_div
    assert perks.effective_stat_value(b, "MAtk", 10, _effects("MAtk", {"op": mul, "value": 2})) == 20
    assert perks.effective_stat_value(b, "MAtk", 10, _effects("MAtk", {"op": div, "value": 2})) == 5


def test_effective_value_negative_divisor_is_valid(bro_factory):
    b = _bro(bro_factory)
    assert perks.effective_stat_value(b, "MAtk", 10, _effects("MAtk", {"op": "/=", "value": -2})) == -5


def test_division_multiplier_property_is_recorded_for_finalization(bro_factory):
    b = _bro(bro_factory)
    eff = _effects("HP", {"op": "/=", "value": 2, "property": "HitpointsMult"})
    assert perks.effective_stat_value(b, "HP", 121, eff) == 60


@pytest.mark.parametrize(
    "stat,prop,raw,expected",
    [
        ("HP", "OtherMult", 60.75, 60.75),
        ("MAtk", "HitpointsMult", 60.75, 60.75),
        ("Resolve", "OtherMult", 42.4, 42.4),
        ("MAtk", "BraveryMult", 42.4, 42.4),
    ],
)
def test_finalization_requires_both_stat_and_matching_property(bro_factory, stat, prop, raw, expected):
    b = _bro(bro_factory)
    eff = _effects(stat, {"op": "*=", "value": 1.0, "property": prop})
    assert perks.effective_stat_value(b, stat, raw, eff) == pytest.approx(expected)


def test_finalization_stat_comparisons_are_exact_not_ordering(bro_factory):
    b = _bro(bro_factory)
    hp_prop = {"op": "*=", "value": 1.0, "property": "HitpointsMult"}
    bravery_prop = {"op": "*=", "value": 1.0, "property": "BraveryMult"}
    for stat in ("A", "Z"):
        assert perks.effective_stat_value(b, stat, 60.75, _effects(stat, hp_prop)) == pytest.approx(60.75)
    for stat in ("A", "Z"):
        assert perks.effective_stat_value(b, stat, 42.4, _effects(stat, bravery_prop)) == pytest.approx(42.4)


def test_finalization_dynamic_stat_strings_use_value_equality(bro_factory):
    b = _bro(bro_factory)
    hp = "".join(["H", "P"])
    resolve = "".join(["Res", "olve"])
    expected_hp = "HP"
    expected_resolve = "Resolve"
    assert hp == expected_hp and hp is not expected_hp
    assert resolve == expected_resolve and resolve is not expected_resolve
    assert perks.effective_stat_value(
        b, hp, 61, _effects(hp, {"op": "*=", "value": 1.25, "property": "HitpointsMult"})
    ) == 76
    assert perks.effective_stat_value(
        b, resolve, 42, _effects(resolve, {"op": "*=", "value": 1.25, "property": "BraveryMult"})
    ) == 53


def test_effective_values_honors_explicit_effect_map(bro_factory):
    b = _bro(bro_factory)
    raw = {stat: float(getattr(b, stat)) for stat in STATS}
    explicit = {stat: [] for stat in STATS}
    explicit["HP"] = [{"op": "+=", "value": 7}]
    values = perks.effective_values(b, raw, explicit)
    assert values["HP"] == raw["HP"] + 7


def test_effective_values_empty_explicit_map_falls_back_to_bro_effects(monkeypatch, bro_factory):
    b = _bro(bro_factory)
    raw = {stat: float(getattr(b, stat)) for stat in STATS}
    fallback = {stat: [] for stat in STATS}
    fallback["HP"] = [{"op": "+=", "value": 3}]
    monkeypatch.setattr(perks, "_effects_by_stat", lambda _bro: fallback)
    assert perks.effective_values(b, raw, {})["HP"] == raw["HP"] + 3


def test_profile_multiplier_contract_all_operator_edges(monkeypatch, bro_factory):
    b = _bro(bro_factory)
    effects = {stat: [] for stat in STATS}
    effects["HP"] = [
        {"op": "*=", "value": 2},
        {"op": "/=", "value": -4},
        {"op": "/=", "value": 0},
        {"op": "+=", "value": 99},
    ]
    effects["MAtk"] = [{"op": "*="}]  # default multiplier is exactly 1.0
    effects["MDef"] = [{"op": "/="}]  # missing divisor defaults to zero and is ignored
    monkeypatch.setattr(perks, "_effects_by_stat", lambda _bro: effects)
    _effective, mult = perks.effective_stat_profile(b)
    assert mult["HP"] == pytest.approx(-0.5)
    assert mult["MAtk"] == pytest.approx(1.0)
    assert mult["MDef"] == pytest.approx(1.0)


@pytest.mark.parametrize("unknown_op", ["!=", ".=", "?=", "zz", "==="])
def test_profile_unknown_operators_do_not_change_multiplier(monkeypatch, bro_factory, unknown_op):
    b = _bro(bro_factory)
    effects = {stat: [] for stat in STATS}
    effects["HP"] = [{"op": unknown_op, "value": 7}]
    monkeypatch.setattr(perks, "_effects_by_stat", lambda _bro: effects)
    _effective, mult = perks.effective_stat_profile(b)
    assert mult["HP"] == pytest.approx(1.0)


def test_profile_dynamic_operator_strings_use_value_equality(monkeypatch, bro_factory):
    b = _bro(bro_factory)
    mul = "".join(["*", "="])
    div = "".join(["/", "="])
    effects = {stat: [] for stat in STATS}
    effects["HP"] = [{"op": mul, "value": 3}, {"op": div, "value": 2}]
    monkeypatch.setattr(perks, "_effects_by_stat", lambda _bro: effects)
    _effective, mult = perks.effective_stat_profile(b)
    assert mult["HP"] == pytest.approx(1.5)


def test_exact_perk_effects_continue_after_unknown_perk(monkeypatch, bro_factory):
    registry = {
        "Known": {"Effects": [
            {"stat": "HP", "op": "+=", "value": 5, "exact": True, "conditional": False},
            {"stat": "HP", "op": "+=", "value": 7, "exact": False, "conditional": False},
            {"stat": "HP", "op": "+=", "value": 9, "exact": True, "conditional": True},
        ]}
    }
    monkeypatch.setattr(perks, "_load_perk_effects", lambda: registry)
    b = _bro(bro_factory, Perks=["Missing", "Known"])
    assert perks.effective_stat_value(b, "HP", 60) == 65


def test_load_perk_effects_missing_file_has_controlled_error(monkeypatch):
    perks.reset_perk_cache()
    def boom(*_args, **_kwargs):
        raise FileNotFoundError("missing")
    monkeypatch.setattr(Path, "read_text", boom)
    with pytest.raises(RuntimeError, match="generated runtime cache and is missing") as exc:
        perks._load_perk_effects()
    assert isinstance(exc.value.__cause__, FileNotFoundError)


def test_load_perk_effects_invalid_json_has_controlled_error(monkeypatch):
    perks.reset_perk_cache()
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: "{")
    with pytest.raises(RuntimeError, match="is invalid") as exc:
        perks._load_perk_effects()
    assert isinstance(exc.value.__cause__, json.JSONDecodeError)
