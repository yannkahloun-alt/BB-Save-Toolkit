"""Effective archetype catalogs backed by durable user-owned intent.

The shipped catalog is an immutable input.  Only sparse base overrides,
disabled base IDs, complete custom definitions, and retired custom IDs are
written through :mod:`bbtool.app.user_state`.
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass

from ..build_identity import (
    build_definition_hash,
    build_identity,
    validate_build_identity,
)
from ..models import STATS
from .config import AnalyzerConfig, _normalize_role
from .user_state import ArchetypeState, StateValidationError, UserStateStore

EXPORT_SCHEMA = "bbtool.user-archetypes-export.v1"
LEGACY_IMPORT_SCHEMAS = frozenset({"bb-archetypes-v0.9"})
_ENTRY_KINDS = frozenset({"override", "disabled", "custom", "retired"})


class CatalogValidationError(StateValidationError):
    """A deterministic collection of field-level catalog errors."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(sorted(set(errors)))
        super().__init__("; ".join(self.errors))


class CatalogConflictError(StateValidationError):
    """User intent cannot be applied without an explicit decision."""


@dataclass(frozen=True)
class EffectiveCatalog:
    roles: tuple[dict, ...]
    state: ArchetypeState

    @property
    def definition_hashes(self) -> dict[str, str]:
        """Per-build semantic signatures for targeted dependency consumers."""
        return {role["id"]: build_definition_hash(role) for role in self.roles}


def _validate_role(
    role: object,
    path: str,
    *,
    require_id: bool = True,
    allow_derived: bool = False,
) -> dict:
    errors: list[str] = []
    if not isinstance(role, dict):
        raise CatalogValidationError([f"{path} must be an object"])
    allowed = {"id", "name", "stats", "perks", "perk_affinity", "perk_conflicts"}
    extra = sorted(set(role) - allowed)
    errors.extend(f"{path}.{field} is not supported" for field in extra)
    if require_id and "id" not in role:
        errors.append(f"{path}.id is required")
    try:
        identity = build_identity(role)
    except ValueError as exc:
        errors.append(f"{path}.id: {exc}")
        identity = None
    if require_id and identity is None:
        errors.append(f"{path}.id must be an authoritative BuildIdentity")
    if not isinstance(role.get("name"), str) or not role.get("name", "").strip():
        errors.append(f"{path}.name must be a non-empty string")
    stats = role.get("stats")
    if not isinstance(stats, dict) or not stats:
        errors.append(f"{path}.stats must be a non-empty object")
    else:
        for stat, definition in sorted(stats.items()):
            stat_path = f"{path}.stats.{stat}"
            if not isinstance(stat, str) or not stat:
                errors.append(f"{path}.stats keys must be non-empty strings")
                continue
            if stat not in STATS:
                errors.append(
                    f"{stat_path} is not a supported projection stat; expected one of {list(STATS)}"
                )
                continue
            if not isinstance(definition, dict):
                errors.append(f"{stat_path} must be an object")
                continue
            allowed_stat_fields = {"target", "baseline", "weight", "ceiling"}
            if allow_derived:
                allowed_stat_fields.update({"fit", "projected_curve"})
            unexpected = sorted(set(definition) - allowed_stat_fields)
            errors.extend(
                f"{stat_path}.{field} is not supported" for field in unexpected
            )
            for field in ("target", "baseline", "weight"):
                value = definition.get(field)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    errors.append(f"{stat_path}.{field} must be finite numeric")
            ceiling = definition.get("ceiling")
            if ceiling is not None and (
                isinstance(ceiling, bool)
                or not isinstance(ceiling, (int, float))
                or not math.isfinite(ceiling)
            ):
                errors.append(f"{stat_path}.ceiling must be finite numeric")
            if (
                isinstance(definition.get("weight"), (int, float))
                and not isinstance(definition.get("weight"), bool)
                and definition["weight"] < 0
            ):
                errors.append(f"{stat_path}.weight must be >= 0")
            if (
                all(
                    isinstance(definition.get(key), (int, float))
                    and not isinstance(definition.get(key), bool)
                    for key in ("baseline", "target")
                )
                and definition["baseline"] > definition["target"]
            ):
                errors.append(f"{stat_path}.baseline must be <= target")
            if (
                isinstance(ceiling, (int, float))
                and not isinstance(ceiling, bool)
                and isinstance(definition.get("target"), (int, float))
                and ceiling < definition["target"]
            ):
                errors.append(f"{stat_path}.ceiling must be >= target")
    perks = role.get("perks")
    if not isinstance(perks, dict) or set(perks) != {"required", "recommended"}:
        errors.append(f"{path}.perks must contain exactly required and recommended")
    else:
        for field in ("required", "recommended"):
            values = perks[field]
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value for value in values
            ):
                errors.append(
                    f"{path}.perks.{field} must be an array of non-empty strings"
                )
            elif len(values) != len(set(values)):
                errors.append(f"{path}.perks.{field} must not contain duplicates")
    affinity = role.get("perk_affinity")
    if not isinstance(affinity, dict) or any(
        not isinstance(key, str)
        or not key
        or isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for key, value in affinity.items()
    ):
        errors.append(
            f"{path}.perk_affinity must map non-empty strings to finite numbers"
        )
    conflicts = role.get("perk_conflicts")
    if not isinstance(conflicts, list) or any(
        not isinstance(value, str) or not value for value in conflicts
    ):
        errors.append(f"{path}.perk_conflicts must be an array of non-empty strings")
    elif len(conflicts) != len(set(conflicts)):
        errors.append(f"{path}.perk_conflicts must not contain duplicates")
    if errors:
        raise CatalogValidationError(errors)
    try:
        return _normalize_role(role)
    except ValueError as exc:
        raise CatalogValidationError([f"{path}: {exc}"]) from exc


def _merge_patch(base: dict, patch: Mapping) -> dict:
    result = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = _merge_patch(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _base_index(base_roles: list[dict] | tuple[dict, ...]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    errors: list[str] = []
    for index, role in enumerate(base_roles):
        try:
            normalized = _validate_role(
                role, f"base.roles[{index}]", allow_derived=True
            )
        except CatalogValidationError as exc:
            errors.extend(exc.errors)
            continue
        identity = build_identity(normalized)
        if identity in indexed:
            errors.append(f"base.roles[{index}].id duplicates {identity}")
        else:
            indexed[identity] = normalized
    if errors:
        raise CatalogValidationError(errors)
    return indexed


def effective_catalog(
    base_roles: list[dict] | tuple[dict, ...], state: ArchetypeState
) -> EffectiveCatalog:
    """Validate and deterministically merge immutable base plus user state."""
    base = _base_index(base_roles)
    overrides: dict[str, dict] = {}
    disabled: set[str] = set()
    customs: list[dict] = []
    retired: set[str] = set()
    seen: set[tuple[str, str]] = set()
    errors: list[str] = []
    for index, entry in enumerate(state.entries):
        path = f"entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{path} must be an object")
            continue
        kind = entry.get("kind")
        if kind not in _ENTRY_KINDS:
            errors.append(f"{path}.kind must be one of {sorted(_ENTRY_KINDS)}")
            continue
        if kind == "custom" and not isinstance(entry.get("definition"), dict):
            errors.append(f"{path}.definition must be an object")
            continue
        identity = (
            entry.get("id")
            if kind != "custom"
            else entry.get("definition", {}).get("id")
            if isinstance(entry.get("definition"), dict)
            else None
        )
        if not isinstance(identity, str):
            identity_path = (
                f"{path}.definition.id" if kind == "custom" else f"{path}.id"
            )
            errors.append(f"{identity_path} is required")
            continue
        marker = (kind, identity)
        if marker in seen:
            errors.append(f"{path} duplicates {kind} state for {identity}")
            continue
        seen.add(marker)
        expected = {"kind", "id"}
        if kind == "override":
            expected = {"kind", "id", "base_definition_hash", "patch"}
        elif kind == "custom":
            expected = {"kind", "definition"}
        extra = sorted(set(entry) - expected)
        missing = sorted(expected - set(entry))
        errors.extend(f"{path}.{field} is not supported" for field in extra)
        errors.extend(f"{path}.{field} is required" for field in missing)
        if kind in {"override", "disabled"} and identity not in base:
            errors.append(f"{path}.id {identity!r} is absent from the shipped catalog")
        if kind == "override" and identity in base:
            if entry.get("base_definition_hash") != build_definition_hash(
                base[identity]
            ):
                errors.append(
                    f"{path}.base_definition_hash conflicts with the current shipped definition for {identity}"
                )
            patch = entry.get("patch")
            if not isinstance(patch, dict) or not patch:
                errors.append(f"{path}.patch must be a non-empty object")
            elif "id" in patch:
                errors.append(f"{path}.patch.id cannot change BuildIdentity")
            else:
                patch_stats = patch.get("stats", {})
                if isinstance(patch_stats, dict):
                    for stat, definition in patch_stats.items():
                        if isinstance(definition, dict):
                            for field in ("fit", "projected_curve"):
                                if field in definition:
                                    errors.append(
                                        f"{path}.patch.stats.{stat}.{field} is engine-derived and cannot be persisted"
                                    )
                try:
                    overrides[identity] = _validate_role(
                        _merge_patch(base[identity], patch),
                        f"{path}.patch",
                        allow_derived=True,
                    )
                except CatalogValidationError as exc:
                    errors.extend(exc.errors)
        elif kind == "disabled":
            disabled.add(identity)
        elif kind == "custom":
            try:
                custom = _validate_role(entry.get("definition"), f"{path}.definition")
                customs.append(custom)
            except CatalogValidationError as exc:
                errors.extend(exc.errors)
        elif kind == "retired":
            try:
                validate_build_identity(identity, role_name=path)
            except ValueError as exc:
                errors.append(f"{path}.id: {exc}")
            if identity in base:
                errors.append(
                    f"{path}.id {identity!r} conflicts with a shipped BuildIdentity"
                )
            retired.add(identity)
    custom_ids = [build_identity(role) for role in customs]
    for identity in custom_ids:
        if identity in base:
            errors.append(
                f"custom id {identity!r} conflicts with a shipped BuildIdentity"
            )
        if identity in retired:
            errors.append(f"custom id {identity!r} reuses a retired BuildIdentity")
    if len(custom_ids) != len(set(custom_ids)):
        errors.append("custom BuildIdentity values must be unique")
    effective = [
        overrides.get(identity, role)
        for identity, role in base.items()
        if identity not in disabled
    ] + customs
    names = [role["name"] for role in effective]
    if len(names) != len(set(names)):
        errors.append(
            "effective display names must be unique for report-v1 compatibility"
        )
    if not effective:
        errors.append("effective catalog must contain at least one archetype")
    if errors:
        raise CatalogValidationError(errors)
    return EffectiveCatalog(tuple(deepcopy(effective)), state)


def _recoverable_shipped_conflict_indexes(
    state: ArchetypeState, errors: tuple[str, ...]
) -> set[int]:
    """Return shipped-entry conflicts that may be reset one revision at a time."""
    indexes: set[int] = set()
    matched: set[str] = set()
    for index, entry in enumerate(state.entries):
        if not isinstance(entry, dict) or entry.get("kind") not in {
            "override",
            "disabled",
        }:
            continue
        prefix = f"entries[{index}]"
        entry_errors = {error for error in errors if error.startswith(prefix)}
        if entry_errors:
            indexes.add(index)
            matched.update(entry_errors)
    unmatched = set(errors) - matched
    if unmatched - {"effective display names must be unique for report-v1 compatibility"}:
        return set()
    return indexes


class ArchetypeCatalogStore:
    """Domain operations over the #95 durable-state substrate."""

    def __init__(
        self,
        store: UserStateStore,
        base_roles: list[dict] | tuple[dict, ...],
        *,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.base_roles = tuple(deepcopy(base_roles))
        self._id_factory = id_factory or (lambda: "custom_" + uuid.uuid4().hex)
        _base_index(self.base_roles)

    def load(self) -> EffectiveCatalog:
        return effective_catalog(self.base_roles, self.store.load("archetypes"))

    def analyzer_config(self, classification: dict) -> AnalyzerConfig:
        """Return the existing analysis boundary's normalized effective input."""
        return AnalyzerConfig(
            roles=list(self.load().roles), classification=deepcopy(classification)
        )

    def _save(self, entries: list[dict], revision: int) -> EffectiveCatalog:
        candidate = ArchetypeState(entries=tuple(deepcopy(entries)))
        effective_catalog(self.base_roles, candidate)
        saved = self.store.save("archetypes", candidate, expected_revision=revision)
        return effective_catalog(self.base_roles, saved)

    def set_override(
        self, identity: str, patch: dict, *, expected_revision: int
    ) -> EffectiveCatalog:
        current = self.load().state
        base = _base_index(self.base_roles)
        if identity not in base:
            raise CatalogConflictError(
                f"cannot override unknown shipped BuildIdentity {identity}"
            )
        entries = [
            entry
            for entry in current.entries
            if not (entry.get("kind") == "override" and entry.get("id") == identity)
        ]
        entries.append(
            {
                "kind": "override",
                "id": identity,
                "base_definition_hash": build_definition_hash(base[identity]),
                "patch": deepcopy(patch),
            }
        )
        return self._save(entries, expected_revision)

    def set_disabled(
        self, identity: str, disabled: bool, *, expected_revision: int
    ) -> EffectiveCatalog:
        current = self.load().state
        if identity not in _base_index(self.base_roles):
            raise CatalogConflictError(
                f"cannot disable unknown shipped BuildIdentity {identity}"
            )
        entries = [
            entry
            for entry in current.entries
            if not (entry.get("kind") == "disabled" and entry.get("id") == identity)
        ]
        if disabled:
            entries.append({"kind": "disabled", "id": identity})
        return self._save(entries, expected_revision)

    def reset_base(self, identity: str, *, expected_revision: int) -> EffectiveCatalog:
        # Reset is the recovery path for a stale override after a base upgrade,
        # so it must be able to inspect valid durable syntax without first
        # applying the now-conflicting effective catalog.
        current = self.store.load("archetypes")
        entries = [
            entry
            for entry in current.entries
            if not (
                entry.get("id") == identity
                and entry.get("kind") in {"override", "disabled"}
            )
        ]
        return self._save(entries, expected_revision)

    def reset_base_recovery(
        self, identity: str, *, expected_revision: int
    ) -> ArchetypeState:
        """Reset one explicit shipped conflict, even while other conflicts remain."""
        current = self.store.load("archetypes")
        try:
            effective_catalog(self.base_roles, current)
        except CatalogValidationError as exc:
            indexes = _recoverable_shipped_conflict_indexes(current, exc.errors)
            requested = {
                index
                for index in indexes
                if current.entries[index].get("id") == identity
            }
            if requested:
                entries = [
                    deepcopy(entry)
                    for index, entry in enumerate(current.entries)
                    if not (
                        index in requested
                        or (
                            entry.get("id") == identity
                            and entry.get("kind") in {"override", "disabled"}
                        )
                    )
                ]
                candidate = ArchetypeState(entries=tuple(entries))
                try:
                    effective_catalog(self.base_roles, candidate)
                except CatalogValidationError as remaining:
                    if not _recoverable_shipped_conflict_indexes(
                        candidate, remaining.errors
                    ):
                        raise
                return self.store.save(
                    "archetypes",
                    candidate,
                    expected_revision=expected_revision,
                )
        return self.reset_base(
            identity, expected_revision=expected_revision
        ).state

    def reset_override(
        self, identity: str, *, expected_revision: int
    ) -> EffectiveCatalog:
        """Remove only a base patch, preserving a separate disabled choice."""
        current = self.store.load("archetypes")
        entries = [
            entry
            for entry in current.entries
            if not (entry.get("kind") == "override" and entry.get("id") == identity)
        ]
        return self._save(entries, expected_revision)

    def create_custom(
        self, definition: dict, *, expected_revision: int, identity: str | None = None
    ) -> EffectiveCatalog:
        current = self.load().state
        role = deepcopy(definition)
        role["id"] = identity or self._id_factory()
        entries = list(current.entries) + [{"kind": "custom", "definition": role}]
        return self._save(entries, expected_revision)

    def edit_custom(
        self, identity: str, definition: dict, *, expected_revision: int
    ) -> EffectiveCatalog:
        current = self.load().state
        replacement = deepcopy(definition)
        replacement["id"] = identity
        found = False
        entries = []
        for entry in current.entries:
            if (
                entry.get("kind") == "custom"
                and entry.get("definition", {}).get("id") == identity
            ):
                entries.append({"kind": "custom", "definition": replacement})
                found = True
            else:
                entries.append(entry)
        if not found:
            raise CatalogConflictError(f"unknown custom BuildIdentity {identity}")
        return self._save(entries, expected_revision)

    def duplicate(
        self, identity: str, *, expected_revision: int, name: str | None = None
    ) -> EffectiveCatalog:
        catalog = self.load()
        source = next((role for role in catalog.roles if role["id"] == identity), None)
        if source is None:
            raise CatalogConflictError(
                f"cannot duplicate unavailable BuildIdentity {identity}"
            )
        definition = deepcopy(source)
        definition.pop("id", None)
        for stat in definition["stats"].values():
            stat.pop("fit", None)
            stat.pop("projected_curve", None)
        definition["name"] = name or f"{definition['name']} Copy"
        return self.create_custom(definition, expected_revision=expected_revision)

    def delete_custom(
        self, identity: str, *, expected_revision: int
    ) -> EffectiveCatalog:
        current = self.load().state
        entries = [
            entry
            for entry in current.entries
            if not (
                entry.get("kind") == "custom"
                and entry.get("definition", {}).get("id") == identity
            )
        ]
        if len(entries) == len(current.entries):
            raise CatalogConflictError(f"unknown custom BuildIdentity {identity}")
        entries.append({"kind": "retired", "id": identity})
        return self._save(entries, expected_revision)

    def export_json(self) -> str:
        state = self.store.load("archetypes")
        payload = {"schema": EXPORT_SCHEMA, "entries": list(state.entries)}
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def import_json(
        self, raw: str, *, expected_revision: int, merge: bool = False
    ) -> EffectiveCatalog:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CatalogValidationError(
                [f"import is not valid JSON: {exc.msg}"]
            ) from exc
        if not isinstance(payload, dict):
            raise CatalogValidationError(["import root must be an object"])
        schema = payload.get("schema")
        if schema == EXPORT_SCHEMA:
            if set(payload) != {"schema", "entries"} or not isinstance(
                payload.get("entries"), list
            ):
                raise CatalogValidationError(
                    [
                        f"{EXPORT_SCHEMA} import must contain exactly schema and an entries array"
                    ]
                )
            incoming = payload["entries"]
        elif isinstance(schema, str) and schema in LEGACY_IMPORT_SCHEMAS:
            if not isinstance(payload.get("roles"), list):
                raise CatalogValidationError(
                    [f"legacy import schema {schema} must contain a roles array"]
                )
            # Explicit import is the one supported transition from an id-less
            # legacy analysis catalog to authoritative managed custom builds.
            incoming = []
            for index, source in enumerate(payload["roles"]):
                if not isinstance(source, dict):
                    raise CatalogValidationError([f"roles[{index}] must be an object"])
                definition = deepcopy(source)
                definition.setdefault("id", self._id_factory())
                incoming.append({"kind": "custom", "definition": definition})
        else:
            raise CatalogValidationError(
                [
                    f"unsupported archetype import schema {schema!r}; expected {EXPORT_SCHEMA} or one of {sorted(LEGACY_IMPORT_SCHEMAS)}"
                ]
            )
        if not merge:
            # Replacement may discard editable state, but local retired-ID
            # tombstones are monotonic identity history and cannot be erased
            # by importing an older file.
            current = self.store.load("archetypes")
            retired = [
                entry for entry in current.entries if entry.get("kind") == "retired"
            ]
            incoming_keys = {
                (entry.get("kind"), entry.get("id"))
                for entry in incoming
                if isinstance(entry, dict)
            }
            incoming = list(incoming) + [
                entry
                for entry in retired
                if (entry.get("kind"), entry.get("id")) not in incoming_keys
            ]
            return self._save(incoming, expected_revision)
        current = self.load().state
        entries = list(current.entries)
        keys: dict[tuple[str, str], dict] = {}
        for entry in entries:
            identity = (
                entry.get("definition", {}).get("id")
                if entry.get("kind") == "custom"
                else entry.get("id")
            )
            keys[(entry.get("kind"), identity)] = entry
        for entry in incoming:
            identity = (
                entry.get("definition", {}).get("id")
                if isinstance(entry, dict) and entry.get("kind") == "custom"
                else entry.get("id")
                if isinstance(entry, dict)
                else None
            )
            key = (
                (entry.get("kind"), identity)
                if isinstance(entry, dict)
                else (None, None)
            )
            if key in keys and keys[key] != entry:
                raise CatalogConflictError(
                    f"import conflicts with existing {key[0]} state for BuildIdentity {identity}"
                )
            if key not in keys:
                entries.append(entry)
                keys[key] = entry
        return self._save(entries, expected_revision)


__all__ = [
    "EXPORT_SCHEMA",
    "LEGACY_IMPORT_SCHEMAS",
    "ArchetypeCatalogStore",
    "CatalogConflictError",
    "CatalogValidationError",
    "EffectiveCatalog",
    "effective_catalog",
]
