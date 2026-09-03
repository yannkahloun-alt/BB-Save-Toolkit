import struct
import io
import json
import zipfile

import pytest

from bbtool.save_parser import parse_brother_equipment
from references.update_references import (
    battle_brothers_save_hash,
    build_reference_dictionary,
)


pytestmark = pytest.mark.unit


def _generic_state(condition):
    return (
        b"\x00"
        + struct.pack("<Hf", 1, condition)
        + b"\x00" * 4
        + b"\x64"
        + b"\x00" * 2
    )


def _item(slot, item_id, payload):
    return bytes([slot]) + bytes.fromhex(item_id) + payload


def _inventory(*items, pouches=2):
    prefix = b"\x00" * 6 + bytes([pouches, len(items)])
    return prefix + b"".join(items)


def test_parses_equipped_slots_bag_order_conditions_and_fatigue():
    refs = {
        "01020304": {
            "name": "Noble Sword",
            "type": "genericWeapon",
            "slot": "weapon",
            "durability": 64,
            "fatigue": -8,
        },
        "11121314": {
            "name": "Kite Shield",
            "type": "genericShield",
            "slot": "shield",
            "durability": 48,
            "fatigue": -14,
        },
        "21222324": {
            "name": "Mail Hauberk",
            "type": "genericArmor",
            "slot": "body",
            "durability": 210,
            "fatigue": -24,
        },
        "31323334": {
            "name": "Nasal Helmet",
            "type": "genericHelmet",
            "slot": "helmet",
            "durability": 105,
            "fatigue": -5,
        },
        "41424344": {
            "name": "Dagger",
            "type": "genericWeapon",
            "slot": "weapon",
            "durability": 40,
            "fatigue": -2,
        },
    }
    body = b"\x00" * 4 + _generic_state(175) + struct.pack("<ff", 175, -24)
    blob = _inventory(
        _item(0, "01020304", _generic_state(64) + struct.pack("<H", 0)),
        _item(1, "11121314", _generic_state(38)),
        _item(2, "21222324", body),
        _item(3, "31323334", _generic_state(87) + struct.pack("<f", 87)),
        _item(6, "41424344", _generic_state(40) + struct.pack("<H", 0)),
    )

    equipment, fatigue = parse_brother_equipment(blob, 0, len(blob), refs)

    assert equipment["MainHand"] == {
        "Name": "Noble Sword",
        "ItemID": "01020304",
        "Type": "weapon",
        "Condition": 64,
        "Quantity": 0,
        "Fatigue": 8,
        "ConditionMax": 64,
    }
    assert equipment["OffHand"]["Name"] == "Kite Shield"
    assert equipment["Body"]["Armor"] == 175
    assert equipment["Body"]["ArmorMax"] == 210
    assert equipment["Head"]["Armor"] == 87
    assert equipment["Accessory"] is None
    assert equipment["Ammo"] is None
    assert [(item["Slot"], item["Name"]) for item in equipment["Bag"]] == [(1, "Dagger")]
    assert fatigue == {
        "MainHand": 8,
        "OffHand": 14,
        "Body": 24,
        "Head": 5,
        "Accessory": 0,
        "Ammo": 0,
        "Bag": 2,
        "Total": 53,
    }


def test_named_weapon_exposes_serialized_name_combat_stats_and_fatigue():
    refs = {
        "A1A2A3A4": {
            "name": "Named Sword",
            "type": "namedWeapon",
            "slot": "weapon",
        }
    }
    name = b"Famed Blade"
    named = (
        struct.pack("<H", len(name))
        + name
        + struct.pack("<fbHHfBHHfhH", 80, -9, 45, 50, 0.9, 10, 16, 5, 0.25, 3, 0)
        + b"\x00" * 8
        + _generic_state(61)
        + struct.pack("<H", 0)
    )
    blob = _inventory(_item(0, "A1A2A3A4", named))

    equipment, fatigue = parse_brother_equipment(blob, 0, len(blob), refs)

    weapon = equipment["MainHand"]
    assert weapon["Name"] == "Famed Blade"
    assert weapon["Condition"] == 61
    assert weapon["ConditionMax"] == 80
    assert weapon["DamageMin"] == 45
    assert weapon["DamageMax"] == 50
    assert weapon["ArmorDamagePercent"] == 90
    assert weapon["DirectDamagePercent"] == 25
    assert weapon["Fatigue"] == 9
    assert fatigue["Total"] == 9


def test_unknown_item_is_emitted_and_does_not_abort_roster_equipment():
    blob = _inventory(_item(0, "DEADBEEF", b"unrecognized payload"))
    diagnostics = {"recoverable_failures": []}

    equipment, fatigue = parse_brother_equipment(
        blob,
        0,
        len(blob),
        {},
        diagnostics=diagnostics,
        brother_name="Alrik",
    )

    assert equipment["MainHand"] == {
        "Name": "Unknown [DEADBEEF]",
        "ItemID": "DEADBEEF",
        "Type": "weapon",
    }
    assert fatigue["Total"] == 0
    assert diagnostics["recoverable_failures"][0] == {
        "scope": "roster",
        "kind": "equipment_item_unresolved",
        "name": "Alrik",
        "item_index": 0,
        "item_id": "DEADBEEF",
        "reason": "'DEADBEEF'",
    }


def test_unknown_item_recovers_a_provable_known_tail():
    refs = {
        "31323334": {
            "name": "Nasal Helmet",
            "type": "genericHelmet",
            "slot": "helmet",
            "durability": 105,
            "fatigue": -5,
        }
    }
    unknown = _item(0, "DEADBEEF", b"opaque mod payload")
    helmet = _item(3, "31323334", _generic_state(87) + struct.pack("<f", 87))
    blob = _inventory(unknown, helmet)

    equipment, fatigue = parse_brother_equipment(blob, 0, len(blob), refs)

    assert equipment["MainHand"]["ItemID"] == "DEADBEEF"
    assert equipment["Head"] == {
        "Name": "Nasal Helmet",
        "ItemID": "31323334",
        "Type": "helmet",
        "Condition": 87,
        "Armor": 87,
        "Fatigue": 5,
        "ConditionMax": 105,
        "ArmorMax": 105,
    }
    assert fatigue["Head"] == 5
    assert fatigue["Total"] == 5


def test_nonfinite_named_item_values_degrade_to_partial_item_data():
    refs = {
        "A1A2A3A4": {
            "name": "Named Sword",
            "type": "namedWeapon",
            "slot": "weapon",
        }
    }
    name = b"Broken Blade"
    blob = _inventory(
        _item(
            0,
            "A1A2A3A4",
            struct.pack("<H", len(name)) + name + struct.pack("<f", float("nan")),
        )
    )

    equipment, fatigue = parse_brother_equipment(blob, 0, len(blob), refs)

    assert equipment["MainHand"] == {
        "Name": "Named Sword",
        "ItemID": "A1A2A3A4",
        "Type": "weapon",
    }
    assert fatigue["Total"] == 0


def test_empty_inventory_has_stable_null_and_empty_slot_shape():
    equipment, fatigue = parse_brother_equipment(_inventory(), 0, 8, {})

    assert equipment == {
        "MainHand": None,
        "OffHand": None,
        "Body": None,
        "Head": None,
        "Accessory": None,
        "Ammo": None,
        "Bag": [],
    }
    assert fatigue["Total"] == 0


def test_enriched_dictionary_preserves_generic_item_condition_and_fatigue(tmp_path):
    script_path = "scripts/items/armor/mail.nut"
    script = b'''this.m.ID = "armor.mail";\nthis.m.Name = "Mail";\nthis.m.Value = 900;'''
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr(f"source/{script_path}", script)
    item_id = battle_brothers_save_hash(script_path)
    output = tmp_path / "dictionary.json"

    build_reference_dictionary(
        output_path=output,
        bbedit_dictionary={
            item_id: {
                "name": "Mail",
                "type": "genericArmor",
                "slot": "body",
                "durability": 210,
                "fatigue": -24,
            }
        },
        scripts_archive=archive_bytes.getvalue(),
    )

    entry = json.loads(output.read_text(encoding="utf-8"))["entries"][item_id]
    assert entry["durability"] == 210
    assert entry["fatigue"] == -24
