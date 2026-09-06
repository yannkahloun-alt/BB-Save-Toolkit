from pathlib import Path

path = Path('references/update_references.py')
text = path.read_text(encoding='utf-8')

needle = '''VALUE_RE = re.compile(
    r'(?:this\\.)?m\\.Value\\s*=\\s*(-?\\d+(?:\\.\\d+)?)',
    re.MULTILINE,
)
'''
replacement = needle + '''CONDITION_MAX_RE = re.compile(
    r'(?:this\\.)?m\\.ConditionMax\\s*=\\s*(-?\\d+(?:\\.\\d+)?)',
    re.MULTILINE,
)
STAMINA_MODIFIER_RE = re.compile(
    r'(?:this\\.)?m\\.StaminaModifier\\s*=\\s*(-?\\d+(?:\\.\\d+)?)',
    re.MULTILINE,
)
ITEM_TYPE_EXPRESSION_RE = re.compile(
    r'(?:this\\.)?m\\.ItemType\\s*=\\s*(.*?);',
    re.MULTILINE,
)
SLOT_TYPE_EXPRESSION_RE = re.compile(
    r'(?:this\\.)?m\\.SlotType\\s*=\\s*(.*?);',
    re.MULTILINE,
)
CREATE_ITEM_PARENT_RE = re.compile(
    r'\\bthis\\.([a-z0-9_]+)\\.create\\s*\\(\\s*\\)\\s*;',
    re.MULTILINE,
)
'''
if needle not in text:
    raise SystemExit('VALUE_RE insertion point not found')
text = text.replace(needle, replacement, 1)

needle = '''            value_match = VALUE_RE.search(text)

            local_value = None
            if value_match:
                numeric = float(value_match.group(1))
                local_value = int(numeric) if numeric.is_integer() else numeric

            display_name = (
'''
replacement = '''            value_match = VALUE_RE.search(text)
            condition_max_match = CONDITION_MAX_RE.search(text)
            stamina_modifier_match = STAMINA_MODIFIER_RE.search(text)
            item_type_match = ITEM_TYPE_EXPRESSION_RE.search(text)
            slot_type_match = SLOT_TYPE_EXPRESSION_RE.search(text)
            create_parent_match = CREATE_ITEM_PARENT_RE.search(text)

            def local_number(match):
                if match is None:
                    return None
                numeric = float(match.group(1))
                return int(numeric) if numeric.is_integer() else numeric

            local_value = local_number(value_match)
            local_condition_max = local_number(condition_max_match)
            local_stamina_modifier = local_number(stamina_modifier_match)

            display_name = (
'''
if needle not in text:
    raise SystemExit('source parse insertion point not found')
text = text.replace(needle, replacement, 1)

needle = '''                "ID": id_match.group(1) if id_match else None,
                "Name": display_name,
                "LocalValue": local_value,
            }
'''
replacement = '''                "ID": id_match.group(1) if id_match else None,
                "Name": display_name,
                "LocalValue": local_value,
                "LocalConditionMax": local_condition_max,
                "LocalStaminaModifier": local_stamina_modifier,
                "ItemTypeExpression": (
                    item_type_match.group(1).strip() if item_type_match else None
                ),
                "SlotTypeExpression": (
                    slot_type_match.group(1).strip() if slot_type_match else None
                ),
                "CreateParent": (
                    create_parent_match.group(1) if create_parent_match else None
                ),
            }
'''
if needle not in text:
    raise SystemExit('script record insertion point not found')
text = text.replace(needle, replacement, 1)

needle = '''            "ID": rec["ID"],
            "Parent": rec["Parent"],
            "InheritedValue": inherited_value,
        }
'''
replacement = '''            "ID": rec["ID"],
            "Parent": rec["Parent"],
            "InheritedValue": inherited_value,
            "ConditionMax": rec["LocalConditionMax"],
            "StaminaModifier": rec["LocalStaminaModifier"],
            "ItemTypeExpression": rec["ItemTypeExpression"],
            "SlotTypeExpression": rec["SlotTypeExpression"],
            "CreateParent": rec["CreateParent"],
        }
'''
if needle not in text:
    raise SystemExit('enriched record insertion point not found')
text = text.replace(needle, replacement, 1)

marker = 'def build_reference_dictionary(\n'
helper = '''def _source_only_generic_weapon_entry(
    ref_id: str, candidates: list[dict]
) -> dict | None:
    """Build a source-only generic weapon only when pinned semantics prove it."""
    if len(candidates) != 1:
        return None
    source = candidates[0]
    expression = source.get("ItemTypeExpression") or ""
    if (
        source.get("CreateParent") != "weapon"
        or "this.Const.Items.ItemType.Weapon" not in expression
        or "this.Const.Items.ItemType.Tool" in expression
    ):
        return None
    if not isinstance(source.get("Name"), str) or not source["Name"].strip():
        return None
    if not isinstance(source.get("ID"), str) or not source["ID"].strip():
        return None
    if not isinstance(source.get("Value"), (int, float)):
        return None
    if not isinstance(source.get("ConditionMax"), (int, float)):
        return None
    if not isinstance(source.get("StaminaModifier"), (int, float)):
        return None

    slot_expression = source.get("SlotTypeExpression") or ""
    slot = (
        "mainhand" if "Const.ItemSlot.Mainhand" in slot_expression
        else "offhand" if "Const.ItemSlot.Offhand" in slot_expression
        else None
    )
    return {
        "name": source["Name"].strip(),
        "type": "genericWeapon",
        "slot": slot,
        "subType": None,
        "durability": source["ConditionMax"],
        "fatigue": source["StaminaModifier"],
        "Value": source["Value"],
        "SerializedLength": SERIALIZED_LENGTH_BY_TYPE["genericWeapon"],
        "ValueSource": "vanilla-script-save-hash",
        "Script": source["Source"],
        "ValueScript": source.get("ValueScript"),
        "InheritedValue": bool(source.get("InheritedValue")),
        "TechnicalID": source["ID"],
        "ReferenceSource": "vanilla-script-source-only",
        "SaveHash": ref_id,
    }


'''
if marker not in text:
    raise SystemExit('build_reference_dictionary marker not found')
text = text.replace(marker, helper + marker, 1)

needle = '''    unresolved = 0
    unresolved_ids = []
    type_stats = {}
'''
replacement = '''    unresolved = 0
    unresolved_ids = []
    type_stats = {}
    source_only_added = 0
'''
if needle not in text:
    raise SystemExit('counter insertion point not found')
text = text.replace(needle, replacement, 1)

needle = '''        entries[ref_id] = entry

    join_seconds = time.perf_counter() - t
'''
replacement = '''        entries[ref_id] = entry

    # BB-Edit is not a complete vanilla key index. Admit only source-only generic
    # weapons whose pinned script semantics prove their serialized type and all
    # parser-required static metadata. Ambiguous/base/tool scripts stay excluded.
    for ref_id in sorted(set(by_save_hash) - set(bbedit_dictionary)):
        entry = _source_only_generic_weapon_entry(ref_id, by_save_hash[ref_id])
        if entry is None:
            continue
        entries[ref_id] = entry
        source_only_added += 1
        equipment_like += 1
        with_value += 1
        exact_hash_matches += 1
        exact_hash_with_value += 1
        ts = type_stats.setdefault(
            "genericWeapon", {"ids": 0, "with_value": 0, "unresolved": 0}
        )
        ts["ids"] += 1
        ts["with_value"] += 1

    join_seconds = time.perf_counter() - t
'''
if needle not in text:
    raise SystemExit('source-only join insertion point not found')
text = text.replace(needle, replacement, 1)

needle = '''        "inherited_value_matches": inherited_value_matches,
        "source_scripts": source_model["script_count"],
'''
replacement = '''        "inherited_value_matches": inherited_value_matches,
        "source_only_added": source_only_added,
        "source_scripts": source_model["script_count"],
'''
if needle not in text:
    raise SystemExit('result counter insertion point not found')
text = text.replace(needle, replacement, 1)
path.write_text(text, encoding='utf-8')

test = Path('tests/unit/test_reference_source_only_items.py')
test.write_text('''import io\nimport json\nimport zipfile\n\nfrom references import update_references as refs\n\n\ndef _archive(scripts):\n    payload = io.BytesIO()\n    with zipfile.ZipFile(payload, "w") as archive:\n        for path, text in scripts.items():\n            archive.writestr("pinned/" + path, text)\n    return payload.getvalue()\n\n\ndef test_executioners_sword_hash_is_source_derived_and_source_only_weapon_is_emitted(tmp_path):\n    assert refs.battle_brothers_save_hash("scripts/items/weapons/exesword") == "35A5074F"\n    script = """\nfunction create(this)\n{\n    this.weapon.create();\n    this.m.ID = \\\"weapon.exesword\\\";\n    this.m.Name = \\\"Executioner's Sword\\\";\n    this.m.SlotType = this.Const.ItemSlot.Mainhand;\n    this.m.ItemType = ((this.Const.Items.ItemType.Weapon | this.Const.Items.ItemType.MeleeWeapon) | this.Const.Items.ItemType.TwoHanded);\n    this.m.Value = 2900;\n    this.m.ConditionMax = 72.0;\n    this.m.StaminaModifier = -12;\n}\n"""\n    output = tmp_path / "dictionary.json"\n    stats = refs.build_reference_dictionary(output, bbedit_dictionary={}, scripts_archive=_archive({"scripts/items/weapons/exesword.nut": script}))\n    payload = json.loads(output.read_text(encoding="utf-8"))\n    item = payload["entries"]["35A5074F"]\n    assert stats["source_only_added"] == 1\n    assert item["name"] == "Executioner's Sword"\n    assert item["TechnicalID"] == "weapon.exesword"\n    assert item["type"] == "genericWeapon"\n    assert item["slot"] == "mainhand"\n    assert item["SerializedLength"] == 21\n    assert item["Value"] == 2900\n    assert item["durability"] == 72\n    assert item["fatigue"] == -12\n    assert item["ReferenceSource"] == "vanilla-script-source-only"\n\n\ndef test_weapon_base_tool_is_not_promoted_to_generic_weapon(tmp_path):\n    script = """\nfunction create(this)\n{\n    this.weapon.create();\n    this.m.ID = \\\"weapon.test_bomb\\\";\n    this.m.Name = \\\"Test Bomb\\\";\n    this.m.SlotType = this.Const.ItemSlot.Offhand;\n    this.m.ItemType = this.Const.Items.ItemType.Tool;\n    this.m.Value = 100;\n    this.m.ConditionMax = 1.0;\n    this.m.StaminaModifier = 0;\n}\n"""\n    save_hash = refs.battle_brothers_save_hash("scripts/items/tools/test_bomb_item")\n    output = tmp_path / "dictionary.json"\n    stats = refs.build_reference_dictionary(output, bbedit_dictionary={}, scripts_archive=_archive({"scripts/items/tools/test_bomb_item.nut": script}))\n    payload = json.loads(output.read_text(encoding="utf-8"))\n    assert stats["source_only_added"] == 0\n    assert save_hash not in payload["entries"]\n\n\ndef test_source_only_weapon_missing_required_static_metadata_stays_excluded(tmp_path):\n    script = """\nfunction create(this)\n{\n    this.weapon.create();\n    this.m.ID = \\\"weapon.incomplete\\\";\n    this.m.Name = \\\"Incomplete Weapon\\\";\n    this.m.SlotType = this.Const.ItemSlot.Mainhand;\n    this.m.ItemType = this.Const.Items.ItemType.Weapon;\n    this.m.Value = 100;\n}\n"""\n    save_hash = refs.battle_brothers_save_hash("scripts/items/weapons/incomplete")\n    output = tmp_path / "dictionary.json"\n    stats = refs.build_reference_dictionary(output, bbedit_dictionary={}, scripts_archive=_archive({"scripts/items/weapons/incomplete.nut": script}))\n    payload = json.loads(output.read_text(encoding="utf-8"))\n    assert stats["source_only_added"] == 0\n    assert save_hash not in payload["entries"]\n''', encoding='utf-8')

docs = Path('docs/REFERENCE_SOURCES.md')
doc_text = docs.read_text(encoding='utf-8')
anchor = 'Existing valid caches remain preferred and usable offline, so a cache-only run has no downloaded-content-digest to report for that run.\n'
addition = anchor + '''\n`dictionary.json` normally preserves BB-Edit as its bootstrap key set, but the pinned\nvanilla source may also contribute a source-only **generic weapon** when the script\nitself proves `ItemType.Weapon` (not `ItemType.Tool`) and directly supplies the\ntechnical ID, display name, value, maximum condition, and stamina modifier needed\nby the save parser. This bounded exception closes source-key coverage gaps such as\n`35A5074F` (`weapon.exesword`) without promoting ambiguous base, tool, modded, or\nincomplete scripts through path/name heuristics.\n'''
if anchor not in doc_text:
    raise SystemExit('REFERENCE_SOURCES anchor not found')
docs.write_text(doc_text.replace(anchor, addition, 1), encoding='utf-8')
