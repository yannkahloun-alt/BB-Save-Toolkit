import io
import json
import zipfile

from references import update_references as refs


def _archive(scripts):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        for path, text in scripts.items():
            archive.writestr("pinned/" + path, text)
    return payload.getvalue()


def test_executioners_sword_hash_is_source_derived_and_source_only_weapon_is_emitted(tmp_path):
    assert refs.battle_brothers_save_hash("scripts/items/weapons/exesword") == "35A5074F"
    script = """
function create(this)
{
    this.weapon.create();
    this.m.ID = \"weapon.exesword\";
    this.m.Name = \"Executioner's Sword\";
    this.m.SlotType = this.Const.ItemSlot.Mainhand;
    this.m.ItemType = ((this.Const.Items.ItemType.Weapon | this.Const.Items.ItemType.MeleeWeapon) | this.Const.Items.ItemType.TwoHanded);
    this.m.Value = 2900;
    this.m.ConditionMax = 72.0;
    this.m.StaminaModifier = -12;
}
"""
    output = tmp_path / "dictionary.json"
    stats = refs.build_reference_dictionary(output, bbedit_dictionary={}, scripts_archive=_archive({"scripts/items/weapons/exesword.nut": script}))
    payload = json.loads(output.read_text(encoding="utf-8"))
    item = payload["entries"]["35A5074F"]
    assert stats["source_only_added"] == 1
    assert item["name"] == "Executioner's Sword"
    assert item["TechnicalID"] == "weapon.exesword"
    assert item["type"] == "genericWeapon"
    assert item["slot"] == "mainhand"
    assert item["SerializedLength"] == 21
    assert item["Value"] == 2900
    assert item["durability"] == 72
    assert item["fatigue"] == -12
    assert item["ReferenceSource"] == "vanilla-script-source-only"


def test_weapon_base_tool_is_not_promoted_to_generic_weapon(tmp_path):
    script = """
function create(this)
{
    this.weapon.create();
    this.m.ID = \"weapon.test_bomb\";
    this.m.Name = \"Test Bomb\";
    this.m.SlotType = this.Const.ItemSlot.Offhand;
    this.m.ItemType = this.Const.Items.ItemType.Tool;
    this.m.Value = 100;
    this.m.ConditionMax = 1.0;
    this.m.StaminaModifier = 0;
}
"""
    save_hash = refs.battle_brothers_save_hash("scripts/items/tools/test_bomb_item")
    output = tmp_path / "dictionary.json"
    stats = refs.build_reference_dictionary(output, bbedit_dictionary={}, scripts_archive=_archive({"scripts/items/tools/test_bomb_item.nut": script}))
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert stats["source_only_added"] == 0
    assert save_hash not in payload["entries"]


def test_source_only_weapon_missing_required_static_metadata_stays_excluded(tmp_path):
    script = """
function create(this)
{
    this.weapon.create();
    this.m.ID = \"weapon.incomplete\";
    this.m.Name = \"Incomplete Weapon\";
    this.m.SlotType = this.Const.ItemSlot.Mainhand;
    this.m.ItemType = this.Const.Items.ItemType.Weapon;
    this.m.Value = 100;
}
"""
    save_hash = refs.battle_brothers_save_hash("scripts/items/weapons/incomplete")
    output = tmp_path / "dictionary.json"
    stats = refs.build_reference_dictionary(output, bbedit_dictionary={}, scripts_archive=_archive({"scripts/items/weapons/incomplete.nut": script}))
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert stats["source_only_added"] == 0
    assert save_hash not in payload["entries"]
