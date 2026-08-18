import io
import json
import zipfile

import pytest

from bbtool.projection import perks
from bbtool.projection.context import bro_fingerprint, bro_projection_context, reset_bro_context_cache
from references.update_references import battle_brothers_save_hash, build_trait_effect_dictionary


def _trait_registry():
    return {
        "AAAABBBB": {
            "ID": "AAAABBBB",
            "Name": "Strong",
            "Effects": [
                {
                    "stat": "Fatigue",
                    "property": "Stamina",
                    "op": "+=",
                    "value": 10,
                    "conditional": False,
                    "exact": True,
                }
            ],
        },
        "CCCCDDDD": {
            "ID": "CCCCDDDD",
            "Name": "Tough",
            "Effects": [
                {
                    "stat": "HP",
                    "property": "Hitpoints",
                    "op": "+=",
                    "value": 10,
                    "conditional": False,
                    "exact": True,
                }
            ],
        },
        "EEEEFFFF": {
            "ID": "EEEEFFFF",
            "Name": "Paranoid",
            "Effects": [
                {
                    "stat": "MDef",
                    "property": "MeleeDefense",
                    "op": "+=",
                    "value": 5,
                    "conditional": False,
                    "exact": True,
                },
                {
                    "stat": "RDef",
                    "property": "RangedDefense",
                    "op": "-=",
                    "value": 5,
                    "conditional": False,
                    "exact": True,
                },
            ],
        },
    }


@pytest.fixture(autouse=True)
def trait_registry(monkeypatch):
    monkeypatch.setattr(perks, "_TRAIT_EFFECTS_CACHE", _trait_registry())
    monkeypatch.setattr(perks, "_PERK_EFFECTS_CACHE", {})
    reset_bro_context_cache()
    yield
    reset_bro_context_cache()


def test_permanent_trait_modifies_effective_stats(bro_factory):
    bro = bro_factory(
        Fatigue=100,
        HP=60,
        MDef=5,
        RDef=8,
        TraitIDs=["AAAABBBB", "CCCCDDDD", "EEEEFFFF"],
        Traits=["Strong", "Tough", "Paranoid"],
    )
    effective, _ = perks.effective_stat_profile(bro)
    assert effective["Fatigue"] == 110
    assert effective["HP"] == 70
    assert effective["MDef"] == 10
    assert effective["RDef"] == 3


def test_trait_effects_apply_after_future_raw_gain(bro_factory):
    bro = bro_factory(Fatigue=100, TraitIDs=["AAAABBBB"], Traits=["Strong"])
    effects = perks._effects_by_stat(bro)
    assert perks.effective_stat_value(bro, "Fatigue", 120, effects) == 130


def test_temporary_injuries_remain_ignored(bro_factory):
    clean = bro_factory(HP=60, Injuries=[])
    injured = bro_factory(HP=60, Injuries=["Cut Artery", "Pierced Hand"])
    a, _ = perks.effective_stat_profile(clean)
    b, _ = perks.effective_stat_profile(injured)
    assert b == a


def test_context_fingerprint_changes_when_trait_ids_change(bro_factory):
    a = bro_factory(TraitIDs=[], Traits=[])
    b = bro_factory(TraitIDs=["AAAABBBB"], Traits=["Strong"])
    assert bro_fingerprint(a) != bro_fingerprint(b)


def test_projection_context_uses_trait_effective_current_value(bro_factory):
    bro = bro_factory(Fatigue=100, TraitIDs=["AAAABBBB"], Traits=["Strong"])
    _raw, _effects, current, *_rest = bro_projection_context(bro)
    assert current["Fatigue"] == 110


def test_trait_dictionary_extracts_exact_unconditional_effects(tmp_path):
    scripts = {
        "repo/scripts/skills/traits/strong_trait.nut": '''
            this.strong_trait <- this.inherit("scripts/skills/traits/character_trait", {
                function create() {
                    this.m.ID = "AAAABBBB";
                    this.m.Name = "Strong";
                }
                function onUpdate( _properties ) {
                    _properties.Stamina += 10;
                }
            });
        ''',
        "repo/scripts/skills/traits/paranoid_trait.nut": '''
            this.paranoid_trait <- this.inherit("scripts/skills/traits/character_trait", {
                function create() { this.m.ID = "EEEEFFFF"; }
                function onUpdate( _properties ) {
                    _properties.MeleeDefense += 5;
                    _properties.RangedDefense -= 5;
                }
            });
        ''',
        "repo/scripts/skills/traits/conditional_trait.nut": '''
            this.conditional_trait <- this.inherit("scripts/skills/traits/character_trait", {
                function create() { this.m.ID = "trait.conditional"; }
                function onUpdate( _properties ) {
                    if (this.isSomething()) {
                        _properties.Bravery += 10;
                    }
                }
            });
        ''',
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in scripts.items():
            z.writestr(name, text)
    out = tmp_path / "trait_effects.json"
    stats = build_trait_effect_dictionary(out, scripts_archive=buf.getvalue())
    raw = json.loads(out.read_text(encoding="utf-8"))

    assert stats["traits"] == 3
    strong_key = battle_brothers_save_hash("scripts/skills/traits/strong_trait")
    strong = raw["traits"][strong_key]
    assert strong["SaveHash"] == strong_key
    assert strong["Effects"] == [{
        "stat": "Fatigue",
        "property": "Stamina",
        "op": "+=",
        "value": 10,
        "conditional": False,
        "exact": True,
        "source_form": "readable",
    }]
    paranoid_key = battle_brothers_save_hash("scripts/skills/traits/paranoid_trait")
    conditional_key = battle_brothers_save_hash("scripts/skills/traits/conditional_trait")
    paranoid = raw["traits"][paranoid_key]
    assert {e["stat"] for e in paranoid["Effects"]} == {"MDef", "RDef"}
    assert raw["traits"][conditional_key]["HasExactCoreStatModifiers"] is False
    assert raw["traits"][conditional_key]["HasConditionalCoreStatModifiers"] is True


def test_trait_and_perk_effects_are_combined(monkeypatch, bro_factory):
    monkeypatch.setattr(
        perks,
        "_PERK_EFFECTS_CACHE",
        {
            "Flat HP": {
                "Effects": [{
                    "stat": "HP", "property": "Hitpoints", "op": "+=", "value": 5,
                    "conditional": False, "exact": True,
                }]
            }
        },
    )
    bro = bro_factory(
        HP=60,
        Perks=["Flat HP"],
        TraitIDs=["CCCCDDDD"],
        Traits=["Tough"],
    )
    effective, _ = perks.effective_stat_profile(bro)
    assert effective["HP"] == 75
