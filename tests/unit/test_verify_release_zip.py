from __future__ import annotations

from pathlib import Path

from tools.verify_release_zip import audit_members


def valid_members() -> list[str]:
    return [
        "BB-Save-Toolkit-v3.89/README.md",
        "BB-Save-Toolkit-v3.89/config/archetypes.json",
        "BB-Save-Toolkit-v3.89/bbtool/__init__.py",
    ]


def test_release_member_audit_accepts_normal_archive_shape():
    assert audit_members(valid_members()) == []


def test_release_member_audit_rejects_save_data_case_insensitively():
    members = [*valid_members(), "BB-Save-Toolkit-v3.89/tests/private.SaV"]

    assert audit_members(members) == [
        "save data: BB-Save-Toolkit-v3.89/tests/private.SaV"
    ]


def test_tracked_save_fixtures_are_export_ignored():
    attributes = Path(".gitattributes").read_text(encoding="utf-8").splitlines()

    assert "*.sav export-ignore" in attributes
