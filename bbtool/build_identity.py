"""Stable build identity and semantic definition hashing.

Build IDs are explicit catalog data.  An id-less role has no authoritative
durable identity; callers must never manufacture one from its display name.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re


BUILD_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_DERIVED_STAT_FIELDS = frozenset({"fit", "projected_curve"})


def validate_build_identity(value: object, *, role_name: str = "<unnamed>") -> str:
    """Return a valid explicit BuildIdentity or raise a clear error."""
    if not isinstance(value, str) or BUILD_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(
            f"{role_name}.id must match ^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
        )
    return value


def build_identity(role: dict) -> str | None:
    """Return authoritative identity only when the catalog explicitly supplies it."""
    value = role.get("id")
    if value is None:
        return None
    return validate_build_identity(value, role_name=str(role.get("name", "<unnamed>")))


def build_definition(role: dict) -> dict:
    """Return canonical semantic inputs, without identity/display/derived fields."""
    definition = deepcopy({key: value for key, value in role.items() if key not in {"id", "name"}})
    stats = definition.get("stats")
    if isinstance(stats, dict):
        for stat_definition in stats.values():
            if isinstance(stat_definition, dict):
                for field in _DERIVED_STAT_FIELDS:
                    stat_definition.pop(field, None)

    perks = definition.get("perks")
    if isinstance(perks, dict):
        for field in ("required", "recommended"):
            values = perks.get(field)
            if isinstance(values, list) and all(isinstance(value, str) for value in values):
                perks[field] = sorted(values)
    conflicts = definition.get("perk_conflicts")
    if isinstance(conflicts, list) and all(isinstance(value, str) for value in conflicts):
        definition["perk_conflicts"] = sorted(conflicts)
    return definition


def build_definition_hash(role: dict) -> str:
    """Hash the current semantic build definition using canonical JSON + SHA-256."""
    canonical = json.dumps(
        build_definition(role),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
