import io
import json
import zipfile

from references.update_references import build_background_dictionary


def _background_archive(files: dict[str, bytes]) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        for name, content in files.items():
            archive.writestr(
                f"source/scripts/skills/backgrounds/{name}_background.nut",
                content,
            )
    return payload.getvalue()


def test_background_stats_use_exclusive_categories_and_reconcile_scan(tmp_path):
    archive = _background_archive(
        {
            "base": (
                b'this.m.ID = "background.base";\n'
                b"this.m.HiringCost = 100;\n"
                b"this.m.DailyCost = 10;\n"
            ),
            "child": (
                b'this.inherit("scripts/skills/backgrounds/base_background");\n'
            ),
            "partial": (
                b'this.m.ID = "background.partial";\n'
                b"this.m.HiringCost = 50;\n"
            ),
            "missing_parent": (
                b'this.inherit("scripts/skills/backgrounds/absent_background");\n'
                b"this.m.HiringCost = 25;\n"
                b"this.m.DailyCost = 2;\n"
            ),
            "cycle_a": (
                b'this.inherit("scripts/skills/backgrounds/cycle_b_background");\n'
            ),
            "cycle_b": (
                b'this.inherit("scripts/skills/backgrounds/cycle_a_background");\n'
            ),
            "broken": b"\xff",
        }
    )

    stats = build_background_dictionary(
        output_path=tmp_path / "backgrounds.json",
        scripts_archive=archive,
    )

    assert stats["scripts"] == {
        "scanned": 7,
        "decoded": 6,
        "decode_failed": 1,
        "resolution_failed": 3,
    }
    # Potential references are retained independently of economy completeness.
    assert stats["backgrounds"] == 3
    assert stats["usable_background_scripts"] == 2
    assert stats["unusable_background_scripts"] == 1
    assert stats["economy_fields"] == {
        "hiring_cost": {"local": 2, "inherited": 1, "unresolved": 0},
        "daily_cost": {"local": 1, "inherited": 1, "unresolved": 1},
    }
    assert stats["identifiers"] == {"explicit": 2, "inferred": 1}

    for field in stats["economy_fields"].values():
        assert sum(field.values()) + stats["scripts"]["resolution_failed"] == 6
    assert (
        stats["scripts"]["decoded"] + stats["scripts"]["decode_failed"]
        == stats["scripts"]["scanned"]
    )
    payload = json.loads((tmp_path / "backgrounds.json").read_text(encoding="utf-8"))
    assert payload["_meta"]["format"] == "bbtool.backgrounds.v2"
    assert payload["_meta"]["source_revision"]


def test_background_root_may_inherit_from_generic_skill_hierarchy(tmp_path):
    archive = _background_archive(
        {
            "character": (
                b'this.inherit("scripts/skills/skill");\n'
                b'this.m.ID = "background.character";\n'
                b"this.m.HiringCost = 100;\n"
                b"this.m.DailyCost = 10;\n"
            ),
            "child": (
                b'this.inherit('
                b'"scripts/skills/backgrounds/character_background"'
                b");\n"
            ),
        }
    )

    output = tmp_path / "backgrounds.json"
    stats = build_background_dictionary(output_path=output, scripts_archive=archive)

    assert stats["backgrounds"] == 2
    assert stats["scripts"]["resolution_failed"] == 0


def test_potential_inputs_derive_base_ranges_and_inherit_static_rules(tmp_path):
    props = (
        ("Hitpoints", 50, 60), ("Bravery", 30, 40), ("Stamina", 90, 100),
        ("MeleeSkill", 47, 57), ("RangedSkill", 32, 42),
        ("MeleeDefense", 0, 5), ("RangedDefense", 0, 5),
        ("Initiative", 100, 110),
    )
    arrays = b"\n".join(
        f"{name} = [{lo}, {hi}],".encode() for name, lo, hi in props
    )
    zeroes = b"\n".join(f"{name} = [0, 0],".encode() for name, _, _ in props)
    archive = _background_archive({
        "character": (
            b'this.m.ID = "background.character";\nthis.m.HiringCost = 1;\n'
            b"this.m.DailyCost = 1;\n" + arrays + b"\n" + zeroes
        ),
        "parent": (
            b'this.inherit("scripts/skills/backgrounds/character_background");\n'
            b'this.m.ID = "background.parent";\nthis.m.HiringCost = 2;\n'
            b"this.m.DailyCost = 2;\n"
            b"this.m.ExcludedTalents = [this.Const.Attributes.MeleeSkill];\n"
            + b"\n".join(
                f"{name} = [{1 if name == 'MeleeSkill' else 0}, 0],".encode()
                for name, _, _ in props
            )
        ),
        "child": b'this.inherit("scripts/skills/backgrounds/parent_background");\n',
        "fixed_talents": (
            b'this.inherit("scripts/skills/backgrounds/character_background");\n'
            b'this.m.ID = "background.fixed_talents";\n'
            b"this.m.IsUntalented = true;\n" + zeroes + b"\n"
            b"local talents = this.getContainer().getActor().getTalents();\n"
            b"talents[this.Const.Attributes.RangedSkill] = 2;\n"
        ),
    })
    output = tmp_path / "backgrounds.json"
    build_background_dictionary(output_path=output, scripts_archive=archive)
    records = json.loads(output.read_text(encoding="utf-8"))["backgrounds"]
    child = next(rec for rec in records.values() if rec["Key"] == "child")
    assert child["PotentialProfile"]["stat_ranges"]["MAtk"] == [48, 57]
    assert child["PotentialProfile"]["excluded_talents"] == ["MAtk"]
    fixed = next(rec for rec in records.values() if rec["Key"] == "fixed_talents")
    assert "PotentialProfile" not in fixed
    assert fixed["PotentialUnsupportedReason"] == "talent_mutation"


def test_potential_is_retained_when_economy_is_incomplete(tmp_path):
    props = ("Hitpoints", "Bravery", "Stamina", "MeleeSkill", "RangedSkill",
             "MeleeDefense", "RangedDefense", "Initiative")
    ranges = b"\n".join(f"{name} = [0, 0],".encode() for name in props)
    archive = _background_archive({
        "character": (
            b'this.m.ID = "background.character";\n' + ranges + b"\n" + ranges
        ),
        "potential_only": (
            b'this.inherit("scripts/skills/backgrounds/character_background");\n'
            b'this.m.ID = "background.potential_only";\n' + ranges
        ),
    })
    output = tmp_path / "backgrounds.json"
    build_background_dictionary(output_path=output, scripts_archive=archive)
    records = json.loads(output.read_text(encoding="utf-8"))["backgrounds"]
    row = next(rec for rec in records.values() if rec["Key"] == "potential_only")
    assert row["PotentialProfile"]
    assert row["HiringCostBase"] is None
    assert row["DailyCostBase"] is None
