import io
import json
import zipfile
from pathlib import Path

from references import update_references as refs


def _archive(scripts):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        for path, text in scripts.items():
            archive.writestr("pinned/" + path, text)
    return payload.getvalue()


def _weapon(name="Technical Weapon"):
    return f"""
function create(this)
{{
    this.weapon.create();
    this.m.ID = \"weapon.fixture\";
    this.m.Name = \"{name}\";
    this.m.SlotType = this.Const.ItemSlot.Mainhand;
    this.m.ItemType = this.Const.Items.ItemType.Weapon;
    this.m.Value = 100;
    this.m.ConditionMax = 50;
    this.m.StaminaModifier = -5;
    this.addSkill(this.new(\"scripts/skills/actives/fixture_primary\"));
    this.addSkill(this.new(\"scripts/skills/actives/fixture_secondary\"));
}}
"""


def test_family_derivation_follows_technical_specialization_flags_not_names():
    archive = _archive({
        "scripts/items/weapons/fixture.nut": _weapon("Completely Renamed Display"),
        "scripts/skills/actives/fixture_primary.nut": "if (_p.IsSpecializedInPolearms) return;",
        "scripts/skills/actives/fixture_secondary.nut": "if (_p.IsSpecializedInAxes) return;",
    })
    families = refs._weapon_mastery_families_by_script(archive)
    assert families["scripts/items/weapons/fixture"] == ["Axe", "Polearm"]


def test_generated_dictionary_carries_source_family_metadata(tmp_path):
    archive = _archive({
        "scripts/items/weapons/fixture.nut": _weapon(),
        "scripts/skills/actives/fixture_primary.nut": "if (_p.IsSpecializedInBows) return;",
        "scripts/skills/actives/fixture_secondary.nut": "if (_p.IsSpecializedInCrossbows) return;",
    })
    item_id = refs.battle_brothers_save_hash("scripts/items/weapons/fixture")
    output = tmp_path / "dictionary.json"
    refs.build_reference_dictionary(
        output,
        bbedit_dictionary={
            item_id: {"name": "Ignored Display", "type": "genericWeapon", "slot": "weapon", "durability": 50, "fatigue": -5}
        },
        scripts_archive=archive,
    )
    entry = json.loads(output.read_text(encoding="utf-8"))["entries"][item_id]
    assert entry["WeaponMasteryFamilies"] == ["Bow", "Crossbow"]
    assert entry["WeaponMasterySource"] == "vanilla-specialization-flag-closure"


def test_pinned_source_audit_covers_all_masteries_and_names_only_drum_exception():
    evidence = json.loads(
        (Path(__file__).resolve().parents[2] / "docs" / "sources" / "issue-233-weapon-family-investigation.json").read_text(encoding="utf-8")
    )
    assert set(evidence["classified_by_family"]) == set(refs.WEAPON_MASTERY_FAMILY_BY_FLAG.values())
    assert evidence["multi_family_count"] > 0
    assert [row["technical_id"] for row in evidence["unclassified_records"]] == ["weapon.barbarian_drum"]
    assert evidence["representative"]["bow"]
    assert evidence["representative"]["polearm"]
