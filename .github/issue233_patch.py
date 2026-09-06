from pathlib import Path


def replace_once(path, old, new, label):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"{label} anchor not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# references/update_references.py
path = Path("references/update_references.py")
replace_once(
    path,
    '''CREATE_ITEM_PARENT_RE = re.compile(
    r'\\bthis\\.([a-z0-9_]+)\\.create\\s*\\(\\s*\\)\\s*;',
    re.MULTILINE,
)
''',
    '''CREATE_ITEM_PARENT_RE = re.compile(
    r'\\bthis\\.([a-z0-9_]+)\\.create\\s*\\(\\s*\\)\\s*;',
    re.MULTILINE,
)
WEAPON_MASTERY_FAMILY_BY_FLAG = {
    "Axes": "Axe",
    "Bows": "Bow",
    "Cleavers": "Cleaver",
    "Crossbows": "Crossbow",
    "Daggers": "Dagger",
    "Flails": "Flail",
    "Hammers": "Hammer",
    "Maces": "Mace",
    "Polearms": "Polearm",
    "Spears": "Spear",
    "Swords": "Sword",
    "Throwing": "Throwing",
}
WEAPON_MASTERY_SOURCE = "vanilla-specialization-flag-closure"
SPECIALIZATION_FLAG_RE = re.compile(r"\\bIsSpecializedIn([A-Za-z]+)\\b")
SCRIPT_REFERENCE_RE = re.compile(r'"(scripts/[A-Za-z0-9_./-]+)"')
''',
    "weapon mastery constants",
)
replace_once(
    path,
    '''def _extract_script_item_values(
    archive_bytes: bytes,
) -> dict:
''',
    '''def _weapon_mastery_families_by_script(archive_bytes: bytes) -> dict[str, list[str]]:
    """Derive mastery applicability from vanilla technical specialization flags.

    Mastery perks set ``IsSpecializedIn*`` properties and item/skill scripts
    consume those same properties.  Following only exact ``scripts/...`` string
    references preserves hybrid weapons without using display names, categories,
    filenames, or inferred one-family taxonomy.
    """
    texts: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for info in archive.infolist():
            archive_path = info.filename.replace("\\\\", "/")
            if not archive_path.endswith(".nut"):
                continue
            try:
                text = archive.read(info).decode("utf-8")
            except UnicodeDecodeError:
                continue
            rel = archive_path.split("/", 1)[-1].removesuffix(".nut")
            texts[rel] = text

    supported_flags = set(WEAPON_MASTERY_FAMILY_BY_FLAG)
    local_flags: dict[str, set[str]] = {}
    edges: dict[str, tuple[str, ...]] = {}
    for script_path, text in texts.items():
        local_flags[script_path] = set(SPECIALIZATION_FLAG_RE.findall(text)) & supported_flags
        targets = {
            target.removesuffix(".nut")
            for target in SCRIPT_REFERENCE_RE.findall(text)
            if target.removesuffix(".nut") in texts
        }
        edges[script_path] = tuple(sorted(targets))

    output: dict[str, list[str]] = {}
    for script_path in sorted(texts):
        seen: set[str] = set()
        pending = [script_path]
        flags: set[str] = set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            flags.update(local_flags.get(current, ()))
            pending.extend(reversed(edges.get(current, ())))
        families = sorted(WEAPON_MASTERY_FAMILY_BY_FLAG[flag] for flag in flags)
        if families:
            output[script_path] = families
    return output


def _extract_script_item_values(
    archive_bytes: bytes,
) -> dict:
''',
    "weapon mastery helper",
)
replace_once(
    path,
    '''    scripts = {}

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
''',
    '''    scripts = {}
    weapon_mastery_families = _weapon_mastery_families_by_script(archive_bytes)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
''',
    "source family index",
)
replace_once(
    path,
    '''            "CreateParent": rec["CreateParent"],
        }
''',
    '''            "CreateParent": rec["CreateParent"],
            "WeaponMasteryFamilies": weapon_mastery_families.get(path, []),
            "WeaponMasterySource": (
                WEAPON_MASTERY_SOURCE if weapon_mastery_families.get(path) else None
            ),
        }
''',
    "enriched family fields",
)
replace_once(
    path,
    '''    return {
        "name": source["Name"].strip(),
        "type": "genericWeapon",
''',
    '''    entry = {
        "name": source["Name"].strip(),
        "type": "genericWeapon",
''',
    "source-only entry variable",
)
replace_once(
    path,
    '''        "SaveHash": ref_id,
    }


def build_reference_dictionary(
''',
    '''        "SaveHash": ref_id,
    }
    families = source.get("WeaponMasteryFamilies")
    if families and source.get("WeaponMasterySource") == WEAPON_MASTERY_SOURCE:
        entry["WeaponMasteryFamilies"] = list(families)
        entry["WeaponMasterySource"] = WEAPON_MASTERY_SOURCE
    return entry


def build_reference_dictionary(
''',
    "source-only family metadata",
)
replace_once(
    path,
    '''            candidates = by_save_hash.get(ref_id, [])
            chosen = _unique_value(candidates)

            if candidates:
                exact_hash_matches += 1
''',
    '''            candidates = by_save_hash.get(ref_id, [])
            chosen = _unique_value(candidates)

            if len(candidates) == 1:
                source = candidates[0]
                families = source.get("WeaponMasteryFamilies")
                if families and source.get("WeaponMasterySource") == WEAPON_MASTERY_SOURCE:
                    entry["WeaponMasteryFamilies"] = list(families)
                    entry["WeaponMasterySource"] = WEAPON_MASTERY_SOURCE

            if candidates:
                exact_hash_matches += 1
''',
    "existing entry family metadata",
)

# bbtool/save_parser.py
path = Path("bbtool/save_parser.py")
replace_once(
    path,
    '''    item = {
        "Name": record.get("name") or f"Unknown [{item_id}]",
        "ItemID": item_id,
        "Type": _public_item_type(record, slot),
    }
    serialized_fatigue = None
''',
    '''    item = {
        "Name": record.get("name") or f"Unknown [{item_id}]",
        "ItemID": item_id,
        "Type": _public_item_type(record, slot),
    }
    families = record.get("WeaponMasteryFamilies")
    if (
        item["Type"] == "weapon"
        and record.get("WeaponMasterySource") == "vanilla-specialization-flag-closure"
        and isinstance(families, list)
        and bool(families)
        and all(isinstance(family, str) and family for family in families)
    ):
        item["WeaponMasteryFamilies"] = sorted(set(families))
        item["WeaponMasterySource"] = "vanilla-specialization-flag-closure"
    serialized_fatigue = None
''',
    "parser family metadata",
)

# bbtool/perk_gear.py
path = Path("bbtool/perk_gear.py")
text = path.read_text(encoding="utf-8")
old = '''_WEAPON_DEPENDENT = {
    "Axe Mastery",
    "Bow Mastery",
    "Cleaver Mastery",
    "Crossbow Mastery",
    "Dagger Mastery",
    "Flail Mastery",
    "Hammer Mastery",
    "Mace Mastery",
    "Polearm Mastery",
    "Spear Mastery",
    "Sword Mastery",
    "Throwing Mastery",
}
'''
new = '''_WEAPON_MASTERY_FAMILY = {
    "Axe Mastery": "Axe",
    "Bow Mastery": "Bow",
    "Cleaver Mastery": "Cleaver",
    "Crossbow Mastery": "Crossbow",
    "Dagger Mastery": "Dagger",
    "Flail Mastery": "Flail",
    "Hammer Mastery": "Hammer",
    "Mace Mastery": "Mace",
    "Polearm Mastery": "Polearm",
    "Spear Mastery": "Spear",
    "Sword Mastery": "Sword",
    "Throwing Mastery": "Throwing",
}
_WEAPON_DEPENDENT = frozenset(_WEAPON_MASTERY_FAMILY)
_WEAPON_MASTERY_FAMILIES = frozenset(_WEAPON_MASTERY_FAMILY.values())
_WEAPON_MASTERY_SOURCE = "vanilla-specialization-flag-closure"
'''
if old not in text:
    raise SystemExit("weapon mastery set anchor not found")
text = text.replace(old, new, 1)
old = '''        elif perk in _WEAPON_DEPENDENT:
            facts.append(_fact(perk, "unknown", "weapon_mastery_metadata_unavailable"))
'''
new = '''        elif perk in _WEAPON_DEPENDENT:
            mastery_family = _WEAPON_MASTERY_FAMILY[perk]
            mainhand = equipment.get("MainHand")
            if mainhand is None:
                facts.append(_fact(
                    perk, "inactive", "mainhand_empty",
                    MasteryFamily=mastery_family,
                ))
                continue
            if mainhand.get("Type") != "weapon":
                facts.append(_fact(
                    perk, "inactive", "mainhand_not_weapon",
                    MasteryFamily=mastery_family,
                ))
                continue
            families = mainhand.get("WeaponMasteryFamilies")
            source = mainhand.get("WeaponMasterySource")
            valid_families = (
                isinstance(families, list)
                and bool(families)
                and all(
                    isinstance(family, str) and family in _WEAPON_MASTERY_FAMILIES
                    for family in families
                )
            )
            if source != _WEAPON_MASTERY_SOURCE or not valid_families:
                facts.append(_fact(
                    perk, "unknown", "weapon_mastery_metadata_unavailable",
                    MasteryFamily=mastery_family,
                ))
                continue
            normalized = sorted(set(families))
            matches = mastery_family in normalized
            facts.append(_fact(
                perk,
                "active" if matches else "inactive",
                "mainhand_mastery_family_match" if matches else "mainhand_mastery_family_mismatch",
                MasteryFamily=mastery_family,
                WeaponMasteryFamilies=normalized,
            ))
'''
if old not in text:
    raise SystemExit("weapon mastery branch anchor not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

# tests/unit/test_perk_gear_facts.py
path = Path("tests/unit/test_perk_gear_facts.py")
text = path.read_text(encoding="utf-8")
old = '''def test_missing_weapon_and_live_combat_metadata_degrade_to_unknown(bro_factory):
    bro = bro_factory(Perks=["Sword Mastery", "Bow Mastery", "Duelist", "Reach Advantage", "Dodge"])

    facts = {fact["Perk"]: fact for fact in perk_gear_facts(bro)}

    assert facts["Sword Mastery"]["Basis"] == "weapon_mastery_metadata_unavailable"
    assert facts["Bow Mastery"]["Basis"] == "weapon_mastery_metadata_unavailable"
    assert facts["Duelist"]["Basis"] == "weapon_handedness_and_class_unavailable"
    assert facts["Reach Advantage"]["Basis"] == "weapon_handedness_and_class_unavailable"
    assert facts["Dodge"]["Basis"] == "live_initiative_unavailable"
    assert {fact["State"] for fact in facts.values()} == {"unknown"}
'''
new = '''def test_empty_mainhand_is_known_inactive_but_live_combat_metadata_stays_unknown(bro_factory):
    bro = bro_factory(Perks=["Sword Mastery", "Bow Mastery", "Duelist", "Reach Advantage", "Dodge"])

    facts = {fact["Perk"]: fact for fact in perk_gear_facts(bro)}

    assert facts["Sword Mastery"] == {
        "Perk": "Sword Mastery", "State": "inactive", "Basis": "mainhand_empty",
        "MasteryFamily": "Sword",
    }
    assert facts["Bow Mastery"] == {
        "Perk": "Bow Mastery", "State": "inactive", "Basis": "mainhand_empty",
        "MasteryFamily": "Bow",
    }
    assert facts["Duelist"]["Basis"] == "weapon_handedness_and_class_unavailable"
    assert facts["Reach Advantage"]["Basis"] == "weapon_handedness_and_class_unavailable"
    assert facts["Dodge"]["Basis"] == "live_initiative_unavailable"
    assert {facts[name]["State"] for name in ("Duelist", "Reach Advantage", "Dodge")} == {"unknown"}


def test_weapon_mastery_uses_source_derived_multi_family_metadata(bro_factory):
    weapon = _item(
        "weapon",
        WeaponMasteryFamilies=["Axe", "Polearm"],
        WeaponMasterySource="vanilla-specialization-flag-closure",
    )
    bro = bro_factory(
        Perks=["Axe Mastery", "Polearm Mastery", "Sword Mastery"],
        Equipment=_equipment(MainHand=weapon),
    )
    facts = {fact["Perk"]: fact for fact in perk_gear_facts(bro)}

    assert facts["Axe Mastery"]["State"] == "active"
    assert facts["Polearm Mastery"]["State"] == "active"
    assert facts["Sword Mastery"]["State"] == "inactive"
    assert facts["Axe Mastery"]["WeaponMasteryFamilies"] == ["Axe", "Polearm"]
    assert facts["Sword Mastery"]["Basis"] == "mainhand_mastery_family_mismatch"


def test_unresolved_weapon_mastery_metadata_remains_unknown(bro_factory):
    weapon = _item("weapon")
    fact = perk_gear_facts(
        bro_factory(Perks=["Bow Mastery"], Equipment=_equipment(MainHand=weapon))
    )[0]
    assert fact == {
        "Perk": "Bow Mastery",
        "State": "unknown",
        "Basis": "weapon_mastery_metadata_unavailable",
        "MasteryFamily": "Bow",
    }
'''
if old not in text:
    raise SystemExit("perk gear old unavailable test anchor not found")
text = text.replace(old, new, 1)
old = '''    assert perk_gear_facts(base) != perk_gear_facts(equipped)
    assert brother_projection_fingerprint(base) == brother_projection_fingerprint(equipped)
'''
new = '''    assert perk_gear_facts(base) != perk_gear_facts(equipped)
    assert brother_projection_fingerprint(base) == brother_projection_fingerprint(equipped)

    family_equipped = replace(
        base,
        Equipment=_equipment(
            MainHand=_item(
                "weapon",
                WeaponMasteryFamilies=["Sword"],
                WeaponMasterySource="vanilla-specialization-flag-closure",
            )
        ),
    )
    assert brother_projection_fingerprint(base) == brother_projection_fingerprint(family_equipped)
'''
if old not in text:
    raise SystemExit("projection purity anchor not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

# tests/unit/test_roster_equipment.py
path = Path("tests/unit/test_roster_equipment.py")
text = path.read_text(encoding="utf-8")
old = '''            "durability": 64,
            "fatigue": -8,
        },
'''
new = '''            "durability": 64,
            "fatigue": -8,
            "WeaponMasteryFamilies": ["Sword"],
            "WeaponMasterySource": "vanilla-specialization-flag-closure",
        },
'''
if old not in text:
    raise SystemExit("roster weapon reference anchor not found")
text = text.replace(old, new, 1)
old = '''        "Fatigue": 8,
        "ConditionMax": 64,
    }
'''
new = '''        "Fatigue": 8,
        "ConditionMax": 64,
        "WeaponMasteryFamilies": ["Sword"],
        "WeaponMasterySource": "vanilla-specialization-flag-closure",
    }
'''
if old not in text:
    raise SystemExit("roster expected weapon anchor not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

# New deterministic source-family tests.
Path("tests/unit/test_weapon_mastery_reference.py").write_text('''import io\nimport json\nimport zipfile\nfrom pathlib import Path\n\nfrom references import update_references as refs\n\n\ndef _archive(scripts):\n    payload = io.BytesIO()\n    with zipfile.ZipFile(payload, "w") as archive:\n        for path, text in scripts.items():\n            archive.writestr("pinned/" + path, text)\n    return payload.getvalue()\n\n\ndef _weapon(name="Technical Weapon"):\n    return f\"\"\"\nfunction create(this)\n{{\n    this.weapon.create();\n    this.m.ID = \\\"weapon.fixture\\\";\n    this.m.Name = \\\"{name}\\\";\n    this.m.SlotType = this.Const.ItemSlot.Mainhand;\n    this.m.ItemType = this.Const.Items.ItemType.Weapon;\n    this.m.Value = 100;\n    this.m.ConditionMax = 50;\n    this.m.StaminaModifier = -5;\n    this.addSkill(this.new(\\\"scripts/skills/actives/fixture_primary\\\"));\n    this.addSkill(this.new(\\\"scripts/skills/actives/fixture_secondary\\\"));\n}}\n\"\"\"\n\n\ndef test_family_derivation_follows_technical_specialization_flags_not_names():\n    archive = _archive({\n        "scripts/items/weapons/fixture.nut": _weapon("Completely Renamed Display"),\n        "scripts/skills/actives/fixture_primary.nut": "if (_p.IsSpecializedInPolearms) return;",\n        "scripts/skills/actives/fixture_secondary.nut": "if (_p.IsSpecializedInAxes) return;",\n    })\n    families = refs._weapon_mastery_families_by_script(archive)\n    assert families["scripts/items/weapons/fixture"] == ["Axe", "Polearm"]\n\n\ndef test_generated_dictionary_carries_source_family_metadata(tmp_path):\n    archive = _archive({\n        "scripts/items/weapons/fixture.nut": _weapon(),\n        "scripts/skills/actives/fixture_primary.nut": "if (_p.IsSpecializedInBows) return;",\n        "scripts/skills/actives/fixture_secondary.nut": "if (_p.IsSpecializedInCrossbows) return;",\n    })\n    item_id = refs.battle_brothers_save_hash("scripts/items/weapons/fixture")\n    output = tmp_path / "dictionary.json"\n    refs.build_reference_dictionary(\n        output,\n        bbedit_dictionary={\n            item_id: {"name": "Ignored Display", "type": "genericWeapon", "slot": "weapon", "durability": 50, "fatigue": -5}\n        },\n        scripts_archive=archive,\n    )\n    entry = json.loads(output.read_text(encoding="utf-8"))["entries"][item_id]\n    assert entry["WeaponMasteryFamilies"] == ["Bow", "Crossbow"]\n    assert entry["WeaponMasterySource"] == "vanilla-specialization-flag-closure"\n\n\ndef test_pinned_source_audit_covers_all_masteries_and_names_only_drum_exception():\n    evidence = json.loads(\n        (Path(__file__).resolve().parents[2] / "docs" / "sources" / "issue-233-weapon-family-investigation.json").read_text(encoding="utf-8")\n    )\n    assert set(evidence["classified_by_family"]) == set(refs.WEAPON_MASTERY_FAMILY_BY_FLAG.values())\n    assert evidence["multi_family_count"] > 0\n    assert [row["technical_id"] for row in evidence["unclassified_records"]] == ["weapon.barbarian_drum"]\n    assert evidence["representative"]["bow"]\n    assert evidence["representative"]["polearm"]\n''', encoding="utf-8")

# Documentation.
path = Path("docs/PERK_GEAR_FACTS.md")
text = path.read_text(encoding="utf-8")
old = '''- **Shield Expert:** `active` for a resolved equipped shield, `inactive` for an
  empty offhand, and `unknown` for unresolved offhand data. This reports only
  activation, not tactical value.

## Intentionally unavailable mechanics

- Weapon masteries require authoritative weapon-family metadata.
- Reach Advantage requires authoritative melee and two-handed flags.
'''
new = '''- **Shield Expert:** `active` for a resolved equipped shield, `inactive` for an
  empty offhand, and `unknown` for unresolved offhand data. This reports only
  activation, not tactical value.
- **Weapon masteries:** the generated vanilla reference follows exact
  `scripts/...` dependencies from each weapon into item/active-skill code and
  records the supported `IsSpecializedIn*` properties those scripts consume.
  These are exposed as `WeaponMasteryFamilies`, which is intentionally a list:
  vanilla has hybrid weapons whose available skills consume more than one
  mastery. An owned mastery is `active` when its family is in that list,
  `inactive` for an empty main hand or a proven different family set, and
  `unknown` when authoritative family metadata is unavailable. The one pinned
  vanilla Weapon record without supported mastery evidence is the barbarian
  drum; it remains unknown rather than being guessed.

## Intentionally unavailable mechanics

- Reach Advantage requires authoritative melee and two-handed flags.
'''
if old not in text:
    raise SystemExit("perk gear docs anchor not found")
text = text.replace(old, new, 1)
old = '''The current normalized item contract does not provide those weapon flags or
families, and parsed saves do not provide the required live combat state.
Accordingly, an owned perk in these groups emits `State: "unknown"` with a
machine-readable basis. Display names and archetype names are never used as
substitutes. Empty armor slots are known zero values; unresolved equipped armor
is not.
'''
new = '''The normalized item contract now provides source-derived mastery-family
applicability only; it still does not claim general melee/two-handed/handedness
facts, and parsed saves do not provide the required live combat state.
Accordingly, Reach Advantage, Duelist, and Dodge remain `unknown` where their
separate evidence is unavailable. Display names and archetype names are never
used as substitutes. Empty armor slots are known zero values; unresolved
equipped armor or weapon-family evidence is not.
'''
if old not in text:
    raise SystemExit("perk gear docs unavailable anchor not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

path = Path("docs/REFERENCE_SOURCES.md")
text = path.read_text(encoding="utf-8")
anchor = '''`dictionary.json` normally preserves BB-Edit as its bootstrap key set, but the pinned
vanilla source may also contribute a source-only **generic weapon** when the script
itself proves `ItemType.Weapon` (not `ItemType.Tool`) and directly supplies the
technical ID, display name, value, maximum condition, and stamina modifier needed
by the save parser. This bounded exception closes source-key coverage gaps such as
`35A5074F` (`weapon.exesword`) without promoting ambiguous base, tool, modded, or
incomplete scripts through path/name heuristics.
'''
addition = anchor + '''\nFor resolved vanilla weapons, the same pinned source also contributes optional\n`WeaponMasteryFamilies` metadata. Generation follows only exact technical\n`scripts/...` references and records the supported `IsSpecializedIn*` properties\nconsumed by reachable item/skill code. The field is a list because vanilla has\nhybrid mastery applicability; display names, categories, and filenames are not\nused to invent a family. Missing family evidence remains absent/fail-closed.\n'''
if anchor not in text:
    raise SystemExit("reference sources docs anchor not found")
path.write_text(text.replace(anchor, addition, 1), encoding="utf-8")
