from dataclasses import replace

import pytest
from bbtool.app.output import public_brother_data
from bbtool.incremental.fingerprint import brother_projection_fingerprint
from bbtool.perk_gear import perk_gear_facts

pytestmark = pytest.mark.unit


def _item(item_type, **values):
    return {"Name": "Fixture item", "ItemID": "01020304", "Type": item_type, **values}


def _equipment(**slots):
    equipment = {
        "MainHand": None,
        "OffHand": None,
        "Body": None,
        "Head": None,
        "Accessory": None,
        "Ammo": None,
        "Bag": [],
    }
    equipment.update(slots)
    return equipment


@pytest.mark.parametrize(
    ("penalty", "multiplier", "reduction", "state"),
    [
        (0, 0.4, 60.0, "active"),
        (15, 0.4, 60.0, "active"),
        (25, 0.569824, 43.0176, "active"),
        (45, 1.0, 0.0, "no_current_reduction"),
    ],
)
def test_nimble_uses_exact_body_and_head_fatigue_formula(bro_factory, penalty, multiplier, reduction, state):
    bro = bro_factory(
        Perks=["Nimble"],
        Equipment=_equipment(
            Body=_item("armor", Fatigue=penalty),
            Head=_item("helmet", Fatigue=0),
        ),
    )

    assert perk_gear_facts(bro) == [
        {
            "Perk": "Nimble",
            "State": state,
            "Basis": "body_and_head_fatigue",
            "ArmorFatiguePenalty": penalty,
            "HitpointDamageMultiplier": multiplier,
            "HitpointDamageReductionPct": reduction,
        }
    ]


@pytest.mark.parametrize(
    ("body", "head", "total", "multiplier", "reduction", "state"),
    [
        (0, 0, 0, 1.0, 0.0, "no_current_reduction"),
        (175, 87, 262, 0.869, 13.1, "active"),
        (300, 300, 600, 0.7, 30.0, "active"),
    ],
)
def test_battle_forged_uses_current_not_maximum_armor(bro_factory, body, head, total, multiplier, reduction, state):
    bro = bro_factory(
        Perks=["Battle Forged"],
        Equipment=_equipment(
            Body=_item("armor", Armor=body, ArmorMax=400),
            Head=_item("helmet", Armor=head, ArmorMax=400),
        ),
    )

    assert perk_gear_facts(bro) == [
        {
            "Perk": "Battle Forged",
            "State": state,
            "Basis": "current_body_and_head_armor",
            "CurrentArmor": total,
            "ArmorDamageMultiplier": multiplier,
            "ArmorDamageReductionPct": reduction,
        }
    ]


@pytest.mark.parametrize(
    ("body", "head", "after", "benefit"),
    [(5, 2, 5, 2), (24, 5, 20, 9), (0, 0, 0, 0)],
)
def test_brawny_preserves_vanilla_per_slot_rounding(bro_factory, body, head, after, benefit):
    bro = bro_factory(
        Perks=["Brawny"],
        Equipment=_equipment(
            Body=_item("armor", Fatigue=body),
            Head=_item("helmet", Fatigue=head),
        ),
    )

    fact = perk_gear_facts(bro)[0]
    assert fact["ArmorFatiguePenaltyAfter"] == after
    assert fact["FatigueCapacityBenefit"] == benefit
    assert fact["State"] == ("active" if benefit else "no_current_reduction")


def test_shield_expert_active_empty_and_unresolved_states(bro_factory):
    resolved = _item("shield", Condition=38, ConditionMax=48)
    non_shield = _item("weapon", Condition=38, ConditionMax=48)
    unknown = {"Name": "Unknown", "ItemID": "DEADBEEF", "Type": "shield"}

    assert (
        perk_gear_facts(bro_factory(Perks=["Shield Expert"], Equipment=_equipment(OffHand=resolved)))[0]["State"]
        == "active"
    )
    assert perk_gear_facts(bro_factory(Perks=["Shield Expert"], Equipment=_equipment()))[0] == {
        "Perk": "Shield Expert",
        "State": "inactive",
        "Basis": "offhand_empty",
    }
    assert perk_gear_facts(bro_factory(Perks=["Shield Expert"], Equipment=_equipment(OffHand=non_shield)))[0] == {
        "Perk": "Shield Expert",
        "State": "inactive",
        "Basis": "offhand_not_shield",
    }
    assert (
        perk_gear_facts(bro_factory(Perks=["Shield Expert"], Equipment=_equipment(OffHand=unknown)))[0]["State"]
        == "unknown"
    )


def test_unresolved_and_empty_armor_are_distinct(bro_factory):
    unknown = _item("armor")
    assert perk_gear_facts(bro_factory(Perks=["Nimble"], Equipment=_equipment(Body=unknown))) == [
        {"Perk": "Nimble", "State": "unknown", "Basis": "armor_fatigue_unavailable"}
    ]
    assert (
        perk_gear_facts(bro_factory(Perks=["Battle Forged"], Equipment=_equipment()))[0]["State"]
        == "no_current_reduction"
    )


def test_missing_weapon_and_live_combat_metadata_degrade_to_unknown(bro_factory):
    bro = bro_factory(Perks=["Sword Mastery", "Bow Mastery", "Duelist", "Reach Advantage", "Dodge"])

    facts = {fact["Perk"]: fact for fact in perk_gear_facts(bro)}

    assert facts["Sword Mastery"]["Basis"] == "weapon_mastery_metadata_unavailable"
    assert facts["Bow Mastery"]["Basis"] == "weapon_mastery_metadata_unavailable"
    assert facts["Duelist"]["Basis"] == "weapon_handedness_and_class_unavailable"
    assert facts["Reach Advantage"]["Basis"] == "weapon_handedness_and_class_unavailable"
    assert facts["Dodge"]["Basis"] == "live_initiative_unavailable"
    assert {fact["State"] for fact in facts.values()} == {"unknown"}


def test_public_roster_exposes_facts_without_future_rolls(bro_factory):
    data = public_brother_data(bro_factory(Perks=["Nimble"], FutureRolls={"HP": [3]}, Equipment=_equipment()))

    assert data["PerkGearFacts"][0]["Perk"] == "Nimble"
    assert "FutureRolls" not in data


def test_public_roster_preserves_precomputed_render_only_facts(bro_factory):
    bro = bro_factory(Perks=["Nimble"], Equipment=_equipment())
    bro.PerkGearFacts = [{"Perk": "Nimble", "State": "unknown", "Basis": "fixture"}]

    assert public_brother_data(bro)["PerkGearFacts"] == bro.PerkGearFacts


def test_gear_facts_do_not_change_projection_or_summary_fingerprints(bro_factory):
    base = bro_factory(Perks=["Nimble"])
    equipped = replace(
        base,
        Equipment=_equipment(
            Body=_item("armor", Fatigue=20, Armor=200),
            Head=_item("helmet", Fatigue=10, Armor=150),
        ),
        GearFatigue={"Body": 20, "Head": 10, "Total": 30},
    )

    assert perk_gear_facts(base) != perk_gear_facts(equipped)
    assert brother_projection_fingerprint(base) == brother_projection_fingerprint(equipped)
