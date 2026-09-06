"""Static release-archive contract checks.

Usage: python tools/verify_release_zip.py path.zip
"""
from __future__ import annotations

from pathlib import PurePosixPath
import sys
import zipfile


FORBIDDEN_PARTS = {"__pycache__", ".pytest_cache"}


def audit_members(names):
    issues = []
    for name in names:
        path = PurePosixPath(name)
        if any(part in FORBIDDEN_PARTS for part in path.parts) or path.suffix == ".pyc":
            issues.append(f"cache artifact: {name}")
        if path.suffix.lower() == ".sav":
            issues.append(f"save data: {name}")

    archetypes = [
        name
        for name in names
        if PurePosixPath(name).name.startswith("archetypes")
        and PurePosixPath(name).suffix == ".json"
    ]
    if len(archetypes) != 1 or PurePosixPath(archetypes[0]).name != "archetypes.json":
        issues.append(f"archetype configs: {archetypes}")
    return issues


def audit_zip(path):
    with zipfile.ZipFile(path) as archive:
        return audit_members(archive.namelist())


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        print("Usage: python tools/verify_release_zip.py <release.zip>")
        return 2
    issues = audit_zip(argv[0])
    if issues:
        print("\n".join(issues))
        return 1
    print("release archive OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
