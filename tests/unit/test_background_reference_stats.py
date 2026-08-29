import io
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
            "broken": b"\xff",
        }
    )

    stats = build_background_dictionary(
        output_path=tmp_path / "backgrounds.json",
        scripts_archive=archive,
    )

    assert stats["scripts"] == {
        "scanned": 4,
        "decoded": 3,
        "decode_failed": 1,
        "resolution_failed": 0,
    }
    assert stats["backgrounds"] == 2
    assert stats["usable_background_scripts"] == 2
    assert stats["unusable_background_scripts"] == 1
    assert stats["economy_fields"] == {
        "hiring_cost": {"local": 2, "inherited": 1, "unresolved": 0},
        "daily_cost": {"local": 1, "inherited": 1, "unresolved": 1},
    }
    assert stats["identifiers"] == {"explicit": 2, "inferred": 1}

    for field in stats["economy_fields"].values():
        assert sum(field.values()) + stats["scripts"]["resolution_failed"] == 3
    assert (
        stats["scripts"]["decoded"] + stats["scripts"]["decode_failed"]
        == stats["scripts"]["scanned"]
    )
