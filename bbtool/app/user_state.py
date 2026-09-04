"""Versioned, durable per-user application state.

This module owns persistence mechanics only.  Domain features receive bounded,
typed files; generated reports and caches are deliberately outside this root.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid


APPLICATION_DIRECTORY = "BB-Save-Toolkit"
LAYOUT_SCHEMA = "bbtool.user-state-layout.v1"
FEATURE_SCHEMA_VERSION = 1


class UserStateError(RuntimeError):
    """Base class for visible durable-state failures."""


class CorruptStateError(UserStateError):
    pass


class IncompatibleStateError(UserStateError):
    pass


class MigrationError(UserStateError):
    pass


class StateConflictError(UserStateError):
    pass


class StateLockError(UserStateError):
    pass


class StateValidationError(UserStateError):
    pass


def resolve_user_state_root(*, override: Path | None = None) -> Path:
    """Resolve the application data root without creating it.

    ``override`` is the supported test/portable-mode injection point.
    """
    if override is not None:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(
            Path.home() / ".local" / "share"
        )
    return (Path(base) / APPLICATION_DIRECTORY).resolve()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _require_exact_keys(payload: Mapping, required: set[str], where: str) -> None:
    actual = set(payload)
    if actual != required:
        missing = sorted(required - actual)
        extra = sorted(actual - required)
        raise StateValidationError(
            f"{where} has invalid fields (missing={missing}, extra={extra})"
        )


def _require_revision(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StateValidationError(f"{where}.revision must be a non-negative integer")
    return value


def _require_text(value: object, where: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value:
        raise StateValidationError(f"{where} must be a non-empty string")
    return value


@dataclass(frozen=True)
class RootMetadata:
    schema: str = LAYOUT_SCHEMA
    schema_version: int = FEATURE_SCHEMA_VERSION
    revision: int = 0
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class PreferencesState:
    schema: str = "bbtool.preferences.v1"
    schema_version: int = FEATURE_SCHEMA_VERSION
    revision: int = 0
    selected_save_path: str | None = None
    auto_refresh: bool = False


@dataclass(frozen=True)
class ArchetypeState:
    """Reserved durable catalog container; #96 owns entry semantics."""

    schema: str = "bbtool.user-archetypes.v1"
    schema_version: int = FEATURE_SCHEMA_VERSION
    revision: int = 0
    entries: tuple[dict, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LastSuccessState:
    schema: str = "bbtool.last-success.v1"
    schema_version: int = FEATURE_SCHEMA_VERSION
    revision: int = 0
    source_fingerprint: str | None = None
    config_fingerprint: str | None = None
    source_timestamp: str | None = None
    completed_at: str | None = None


@dataclass(frozen=True)
class AssignedBuildRecord:
    brother_identity: str
    build_identity: str
    assigned_definition_hash: str


@dataclass(frozen=True)
class AssignedBuildCampaign:
    campaign_identity: int
    assignments: tuple[AssignedBuildRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AssignedBuildState:
    schema: str = "bbtool.assigned-builds.v1"
    schema_version: int = FEATURE_SCHEMA_VERSION
    revision: int = 0
    campaigns: tuple[AssignedBuildCampaign, ...] = field(default_factory=tuple)


def _validate_metadata(payload: Mapping) -> RootMetadata:
    where = "metadata"
    _require_exact_keys(
        payload,
        {"schema", "schema_version", "revision", "created_at", "updated_at"},
        where,
    )
    if payload["schema"] != LAYOUT_SCHEMA or payload["schema_version"] != 1:
        raise IncompatibleStateError("unsupported user-state layout schema")
    revision = _require_revision(payload["revision"], where)
    created = _require_text(payload["created_at"], f"{where}.created_at", optional=True)
    updated = _require_text(payload["updated_at"], f"{where}.updated_at", optional=True)
    return RootMetadata(revision=revision, created_at=created, updated_at=updated)


def _validate_preferences(payload: Mapping) -> PreferencesState:
    where = "preferences"
    _require_exact_keys(
        payload,
        {"schema", "schema_version", "revision", "selected_save_path", "auto_refresh"},
        where,
    )
    if payload["schema"] != PreferencesState.schema:
        raise IncompatibleStateError("unsupported preferences schema")
    if payload["schema_version"] != 1:
        raise IncompatibleStateError("unsupported preferences schema version")
    revision = _require_revision(payload["revision"], where)
    selected = _require_text(
        payload["selected_save_path"], f"{where}.selected_save_path", optional=True
    )
    if not isinstance(payload["auto_refresh"], bool):
        raise StateValidationError("preferences.auto_refresh must be boolean")
    return PreferencesState(
        revision=revision,
        selected_save_path=selected,
        auto_refresh=payload["auto_refresh"],
    )


def _validate_archetypes(payload: Mapping) -> ArchetypeState:
    where = "user archetypes"
    _require_exact_keys(
        payload, {"schema", "schema_version", "revision", "entries"}, where
    )
    if payload["schema"] != ArchetypeState.schema or payload["schema_version"] != 1:
        raise IncompatibleStateError("unsupported user-archetypes schema")
    revision = _require_revision(payload["revision"], where)
    entries = payload["entries"]
    if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
        raise StateValidationError("user archetype entries must be JSON objects")
    return ArchetypeState(revision=revision, entries=tuple(entries))


def _validate_last_success(payload: Mapping) -> LastSuccessState:
    where = "last success"
    keys = {
        "schema", "schema_version", "revision", "source_fingerprint",
        "config_fingerprint", "source_timestamp", "completed_at",
    }
    _require_exact_keys(payload, keys, where)
    if payload["schema"] != LastSuccessState.schema or payload["schema_version"] != 1:
        raise IncompatibleStateError("unsupported last-success schema")
    revision = _require_revision(payload["revision"], where)
    values = {
        key: _require_text(payload[key], f"{where}.{key}", optional=True)
        for key in (
            "source_fingerprint", "config_fingerprint", "source_timestamp", "completed_at"
        )
    }
    return LastSuccessState(revision=revision, **values)


def _validate_assigned_builds(payload: Mapping) -> AssignedBuildState:
    from ..build_identity import validate_build_identity

    where = "assigned builds"
    _require_exact_keys(
        payload, {"schema", "schema_version", "revision", "campaigns"}, where
    )
    if payload["schema"] != AssignedBuildState.schema or payload["schema_version"] != 1:
        raise IncompatibleStateError("unsupported assigned-builds schema")
    revision = _require_revision(payload["revision"], where)
    campaigns = payload["campaigns"]
    if not isinstance(campaigns, list) or len(campaigns) > 1024:
        raise StateValidationError("assigned builds.campaigns must be an array of at most 1024 items")
    seen_campaigns: set[int] = set()
    total_assignments = 0
    normalized = []
    for campaign_index, campaign in enumerate(campaigns):
        path = f"assigned builds.campaigns[{campaign_index}]"
        if not isinstance(campaign, Mapping):
            raise StateValidationError(f"{path} must be an object")
        _require_exact_keys(campaign, {"campaign_identity", "assignments"}, path)
        identity = campaign["campaign_identity"]
        if isinstance(identity, bool) or not isinstance(identity, int) or not 0 <= identity <= 2_147_483_647:
            raise StateValidationError(f"{path}.campaign_identity must be a non-negative signed 32-bit integer")
        if identity in seen_campaigns:
            raise StateValidationError(f"{path}.campaign_identity is duplicated")
        seen_campaigns.add(identity)
        assignments = campaign["assignments"]
        if not isinstance(assignments, list) or len(assignments) > 10000:
            raise StateValidationError(f"{path}.assignments must be an array of at most 10000 items")
        total_assignments += len(assignments)
        if total_assignments > 10000:
            raise StateValidationError("assigned builds must contain at most 10000 assignments")
        seen_brothers: set[str] = set()
        records = []
        prefix = f"campaign:{identity}/entity:"
        for assignment_index, assignment in enumerate(assignments):
            item_path = f"{path}.assignments[{assignment_index}]"
            if not isinstance(assignment, Mapping):
                raise StateValidationError(f"{item_path} must be an object")
            _require_exact_keys(
                assignment,
                {"brother_identity", "build_identity", "assigned_definition_hash"},
                item_path,
            )
            brother = assignment["brother_identity"]
            if not isinstance(brother, str) or not brother.startswith(prefix):
                raise StateValidationError(f"{item_path}.brother_identity is outside its campaign namespace")
            token = brother[len(prefix):]
            if (
                not token.isascii()
                or not token.isdigit()
                or not 1 <= int(token) <= 0xFFFFFFFF
                or token != str(int(token))
            ):
                raise StateValidationError(f"{item_path}.brother_identity is malformed")
            if brother in seen_brothers:
                raise StateValidationError(f"{item_path}.brother_identity is duplicated")
            seen_brothers.add(brother)
            try:
                build = validate_build_identity(assignment["build_identity"])
            except ValueError as exc:
                raise StateValidationError(f"{item_path}.build_identity is invalid: {exc}") from exc
            definition_hash = assignment["assigned_definition_hash"]
            if (
                not isinstance(definition_hash, str)
                or len(definition_hash) != 71
                or not definition_hash.startswith("sha256:")
                or any(character not in "0123456789abcdef" for character in definition_hash[7:])
            ):
                raise StateValidationError(f"{item_path}.assigned_definition_hash is invalid")
            records.append(AssignedBuildRecord(brother, build, definition_hash))
        normalized.append(AssignedBuildCampaign(
            identity, tuple(sorted(records, key=lambda item: item.brother_identity))
        ))
    return AssignedBuildState(
        revision=revision,
        campaigns=tuple(sorted(normalized, key=lambda item: item.campaign_identity)),
    )


def _migrate_preferences_v0(payload: dict) -> dict:
    _require_exact_keys(
        payload,
        {"schema", "schema_version", "revision", "selected_save", "auto_refresh"},
        "preferences v0",
    )
    if payload["schema"] != "bbtool.preferences.v0":
        raise StateValidationError("preferences v0 has an unsupported schema")
    return {
        "schema": "bbtool.preferences.v1",
        "schema_version": 1,
        "revision": payload["revision"],
        "selected_save_path": payload["selected_save"],
        "auto_refresh": payload["auto_refresh"],
    }


@dataclass(frozen=True)
class _Feature:
    relative_path: Path
    default_factory: Callable[[], object]
    validator: Callable[[Mapping], object]
    migrations: Mapping[int, Callable[[dict], dict]] = field(default_factory=dict)


FEATURES = {
    "metadata": _Feature(Path("metadata.json"), RootMetadata, _validate_metadata),
    "preferences": _Feature(
        Path("preferences.json"), PreferencesState, _validate_preferences,
        migrations={0: _migrate_preferences_v0},
    ),
    "archetypes": _Feature(
        Path("archetypes/catalog-state.json"), ArchetypeState, _validate_archetypes
    ),
    "last_success": _Feature(
        Path("last-success.json"), LastSuccessState, _validate_last_success
    ),
    "assigned_builds": _Feature(
        Path("assigned-builds.json"), AssignedBuildState, _validate_assigned_builds
    ),
}


def _json_payload(value: object) -> dict:
    payload = asdict(value)
    if isinstance(value, ArchetypeState):
        payload["entries"] = list(value.entries)
    return payload


def _serialized(payload: Mapping) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


@contextmanager
def _exclusive_lock(path: Path, timeout: float) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    deadline = time.monotonic() + timeout
    locked = False
    try:
        while not locked:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    if handle.tell() == handle.seek(0, os.SEEK_END):
                        handle.write(b"\0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise StateLockError(
                        f"timed out acquiring state lock {path}"
                    ) from exc
                time.sleep(0.01)
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        with suppress(FileNotFoundError):
            temporary.unlink()


class UserStateStore:
    """Persistence authority for bounded application-state features."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        clock: Callable[[], str] = _utc_now,
        lock_timeout: float = 5.0,
    ) -> None:
        self.root = resolve_user_state_root(override=root)
        self._clock = clock
        self._lock_timeout = lock_timeout

    def path_for(self, feature: str) -> Path:
        try:
            return self.root / FEATURES[feature].relative_path
        except KeyError as exc:
            raise ValueError(f"unknown state feature: {feature}") from exc

    def _lock_path(self, feature: str) -> Path:
        path = self.path_for(feature)
        return path.with_name(f".{path.name}.lock")

    def _revision_path(self, feature: str) -> Path:
        path = self.path_for(feature)
        return path.with_name(f".{path.name}.revision")

    def _revision_mirror_path(self, feature: str) -> Path:
        path = self.path_for(feature)
        return path.with_name(f".{path.name}.revision.bak")

    @staticmethod
    def _read_revision_copy(path: Path) -> int | None:
        if not path.exists():
            return None
        try:
            value = int(path.read_text(encoding="ascii"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise CorruptStateError(f"revision copy {path} is corrupt") from exc
        if value < 0:
            raise CorruptStateError(f"revision copy {path} is corrupt")
        return value

    def _write_revision_highwater(self, feature: str, revision: int) -> None:
        data = f"{revision}\n".encode("ascii")
        _atomic_write(self._revision_mirror_path(feature), data)
        _atomic_write(self._revision_path(feature), data)

    def _revision_highwater(
        self,
        feature: str,
        *,
        recover: bool = False,
        fallback_revision: int | None = None,
        repair: bool = True,
    ) -> int:
        copies = []
        failures = []
        for path in (
            self._revision_path(feature), self._revision_mirror_path(feature)
        ):
            try:
                value = self._read_revision_copy(path)
            except CorruptStateError as exc:
                failures.append(exc)
            else:
                if value is not None:
                    copies.append(value)
        if not copies:
            if failures or (recover and fallback_revision is None):
                raise CorruptStateError(
                    f"{feature} revision high-watermark copies are unusable"
                ) from (failures[0] if failures else None)
            if recover:
                if repair:
                    self._write_revision_highwater(feature, fallback_revision)
                return fallback_revision
            return 0
        if failures or len(copies) != 2 or len(set(copies)) != 1:
            if not recover:
                raise CorruptStateError(
                    f"{feature} revision high-watermark copies disagree or are corrupt"
                ) from (failures[0] if failures else None)
            highwater = max(
                copies + (
                    [fallback_revision] if fallback_revision is not None else []
                )
            )
            if repair:
                self._write_revision_highwater(feature, highwater)
            return highwater
        return copies[0]

    def _decode(self, feature: str, raw: bytes, *, migrate: bool) -> tuple[object, bool]:
        spec = FEATURES[feature]
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CorruptStateError(f"{feature} state is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise CorruptStateError(f"{feature} state must be a JSON object")
        version = payload.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise CorruptStateError(f"{feature} state has no valid schema_version")
        if version > FEATURE_SCHEMA_VERSION:
            raise IncompatibleStateError(
                f"{feature} schema version {version} is newer than supported version 1"
            )
        changed = False
        while version < FEATURE_SCHEMA_VERSION:
            migration = spec.migrations.get(version)
            if migration is None:
                raise IncompatibleStateError(
                    f"no {feature} migration from schema version {version}"
                )
            if not migrate:
                raise IncompatibleStateError(f"{feature} state requires migration")
            try:
                payload = migration(dict(payload))
            except Exception as exc:
                raise MigrationError(
                    f"{feature} migration from version {version} failed"
                ) from exc
            next_version = payload.get("schema_version")
            if next_version != version + 1:
                raise MigrationError(f"{feature} migration did not advance exactly one version")
            version = next_version
            changed = True
        try:
            return spec.validator(payload), changed
        except IncompatibleStateError:
            raise
        except StateValidationError as exc:
            raise CorruptStateError(f"{feature} state failed validation: {exc}") from exc

    def load(self, feature: str, *, migrate: bool = True) -> object:
        spec = FEATURES[feature]
        path = self.path_for(feature)
        with _exclusive_lock(self._lock_path(feature), self._lock_timeout):
            if not path.exists():
                if self._revision_highwater(feature) != 0:
                    raise CorruptStateError(
                        f"{feature} payload is missing but revision state remains"
                    )
                return spec.default_factory()
            raw = path.read_bytes()
            value, changed = self._decode(feature, raw, migrate=migrate)
            if changed:
                value = replace(
                    value,
                    revision=max(
                        value.revision, self._revision_highwater(feature)
                    ) + 1,
                )
                self._write_locked(
                    feature, path, raw, _serialized(_json_payload(value))
                )
            return value

    def _write_locked(
        self,
        feature: str,
        path: Path,
        previous: bytes | None,
        replacement: bytes,
        *,
        known_highwater: int | None = None,
    ) -> None:
        if previous is not None:
            _atomic_write(path.with_suffix(path.suffix + ".bak"), previous)
        revision = json.loads(replacement)["revision"]
        highwater = (
            self._revision_highwater(feature)
            if known_highwater is None
            else known_highwater
        )
        if revision < highwater:
            raise StateConflictError(
                f"{feature} revision {revision} is below high-watermark {highwater}"
            )
        self._write_revision_highwater(feature, revision)
        _atomic_write(path, replacement)

    def save(self, feature: str, value: object, *, expected_revision: int) -> object:
        spec = FEATURES[feature]
        path = self.path_for(feature)
        with _exclusive_lock(self._lock_path(feature), self._lock_timeout):
            previous = path.read_bytes() if path.exists() else None
            if previous is None:
                if self._revision_highwater(feature) != 0:
                    raise CorruptStateError(
                        f"{feature} payload is missing but revision state remains"
                    )
                current = spec.default_factory()
            else:
                current, changed = self._decode(feature, previous, migrate=False)
                if changed:  # pragma: no cover - migrate=False cannot produce this
                    raise AssertionError("unexpected migration")
            current_revision = current.revision
            if expected_revision != current_revision:
                raise StateConflictError(
                    f"{feature} revision conflict: expected {expected_revision}, "
                    f"found {current_revision}"
                )
            candidate = replace(
                value,
                revision=max(
                    current_revision, self._revision_highwater(feature)
                ) + 1,
            )
            validated, _ = self._decode(
                feature, _serialized(_json_payload(candidate)), migrate=False
            )
            self._write_locked(
                feature, path, previous, _serialized(_json_payload(validated))
            )
        if feature != "metadata":
            self._touch_metadata()
        return validated

    def assert_revision(self, feature: str, *, expected_revision: int) -> object:
        """Return current typed state only if its revision matches under lock."""
        spec = FEATURES[feature]
        path = self.path_for(feature)
        with _exclusive_lock(self._lock_path(feature), self._lock_timeout):
            if not path.exists():
                if self._revision_highwater(feature) != 0:
                    raise CorruptStateError(
                        f"{feature} payload is missing but revision state remains"
                    )
                current = spec.default_factory()
            else:
                current, changed = self._decode(
                    feature, path.read_bytes(), migrate=False
                )
                if changed:  # pragma: no cover - migrate=False cannot produce this
                    raise AssertionError("unexpected migration")
            if current.revision != expected_revision:
                raise StateConflictError(
                    f"{feature} revision conflict: expected {expected_revision}, "
                    f"found {current.revision}"
                )
            return current

    def _touch_metadata(self) -> None:
        path = self.path_for("metadata")
        with _exclusive_lock(self._lock_path("metadata"), self._lock_timeout):
            previous = path.read_bytes() if path.exists() else None
            if previous is None:
                metadata = RootMetadata()
            else:
                metadata, _ = self._decode("metadata", previous, migrate=False)
            now = self._clock()
            updated = replace(
                metadata,
                revision=max(
                    metadata.revision, self._revision_highwater("metadata")
                ) + 1,
                created_at=metadata.created_at or now,
                updated_at=now,
            )
            self._write_locked(
                "metadata", path, previous, _serialized(_json_payload(updated))
            )

    @contextmanager
    def _all_feature_locks(self) -> Iterator[None]:
        with ExitStack() as stack:
            for feature in sorted(FEATURES):
                stack.enter_context(
                    _exclusive_lock(self._lock_path(feature), self._lock_timeout)
                )
            yield

    def recover_from_backup(self, feature: str) -> object:
        path = self.path_for(feature)
        backup = path.with_suffix(path.suffix + ".bak")
        with _exclusive_lock(self._lock_path(feature), self._lock_timeout):
            if not backup.exists():
                raise UserStateError(f"no recovery backup exists for {feature}")
            raw = backup.read_bytes()
            value, _ = self._decode(feature, raw, migrate=True)
            recovered = replace(
                value,
                revision=max(
                    value.revision,
                    self._revision_highwater(feature, recover=True),
                ) + 1,
            )
            self._write_revision_highwater(feature, recovered.revision)
            _atomic_write(path, _serialized(_json_payload(recovered)))
            return recovered

    def reset_feature(self, feature: str, *, expected_revision: int) -> None:
        spec = FEATURES[feature]
        path = self.path_for(feature)
        with _exclusive_lock(self._lock_path(feature), self._lock_timeout):
            if not path.exists():
                if expected_revision != 0:
                    raise StateConflictError(f"{feature} revision conflict")
                previous = None
                current_revision = 0
            else:
                previous = path.read_bytes()
                current, _ = self._decode(feature, previous, migrate=False)
                current_revision = current.revision
                if current_revision != expected_revision:
                    raise StateConflictError(f"{feature} revision conflict")
            reset = replace(
                spec.default_factory(),
                revision=max(
                    current_revision,
                    self._revision_highwater(
                        feature,
                        recover=True,
                        fallback_revision=current_revision,
                    ),
                ) + 1,
            )
            self._write_locked(
                feature, path, previous, _serialized(_json_payload(reset))
            )

    def backup(self, destination: Path) -> Path:
        destination = Path(destination).resolve()
        if destination == self.root or self.root in destination.parents:
            raise UserStateError("backup destination must be outside UserStateRoot")
        if destination.exists():
            raise FileExistsError(destination)
        with self._all_feature_locks():
            for feature in FEATURES:
                path = self.path_for(feature)
                backup = path.with_suffix(path.suffix + ".bak")
                if not path.exists():
                    if (
                        backup.exists()
                        or self._revision_path(feature).exists()
                        or self._revision_mirror_path(feature).exists()
                    ):
                        raise CorruptStateError(
                            f"cannot back up degraded {feature} state"
                        )
                    continue
                current, _ = self._decode(
                    feature, path.read_bytes(), migrate=False
                )
                if self._revision_highwater(feature) != current.revision:
                    raise CorruptStateError(
                        f"cannot back up inconsistent {feature} revisions"
                    )
            destination.mkdir(parents=True)
            if self.root.exists():
                for path in self.root.rglob("*"):
                    if (
                        path.is_symlink()
                        or not path.is_file()
                        or path.name.endswith((".lock", ".tmp"))
                    ):
                        continue
                    target = destination / path.relative_to(self.root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
        return destination

    def restore(self, source: Path) -> None:
        source = Path(source).resolve()
        if not source.is_dir():
            raise UserStateError("restore source must be a state backup directory")
        staged: dict[str, object | None] = {}
        for feature, spec in FEATURES.items():
            path = source / spec.relative_path
            if path.exists():
                raw = path.read_bytes()
                value, _ = self._decode(feature, raw, migrate=True)
                source_version = json.loads(raw)["schema_version"]
                source_revisions = (
                    path.with_name(f".{path.name}.revision"),
                    path.with_name(f".{path.name}.revision.bak"),
                )
                present = [item for item in source_revisions if item.exists()]
                if source_version == FEATURE_SCHEMA_VERSION and not present:
                    raise CorruptStateError(
                        f"restore source has missing {feature} revision state"
                    )
                if present and len(present) != 2:
                    raise CorruptStateError(
                        f"restore source has incomplete {feature} revision state"
                    )
                if present:
                    revisions = [
                        self._read_revision_copy(item) for item in source_revisions
                    ]
                    if len(set(revisions)) != 1 or revisions[0] != value.revision:
                        raise CorruptStateError(
                            f"restore source has inconsistent {feature} revisions"
                        )
                staged[feature] = value
            else:
                source_backup = path.with_suffix(path.suffix + ".bak")
                source_revision = path.with_name(f".{path.name}.revision")
                source_revision_mirror = path.with_name(
                    f".{path.name}.revision.bak"
                )
                if any(item.exists() for item in (
                    source_backup, source_revision, source_revision_mirror
                )):
                    raise CorruptStateError(
                        f"restore source has degraded {feature} state"
                    )
                staged[feature] = None
        additional = {}
        recognized = {spec.relative_path for spec in FEATURES.values()}
        for path in source.rglob("*"):
            if (
                path.is_symlink()
                or not path.is_file()
                or path.name.endswith((".lock", ".tmp"))
            ):
                continue
            relative = path.relative_to(source)
            if (
                relative not in recognized
                and not path.name.endswith((".bak", ".revision"))
            ):
                target = self.root / relative
                if target.is_symlink():
                    raise UserStateError(
                        f"restore target must not be a symbolic link: {target}"
                    )
                additional[relative] = (
                    path.read_bytes(), target.read_bytes() if target.exists() else None
                )
        with self._all_feature_locks():
            local_revisions = {}
            local_highwaters = {}
            local_previous = {}
            for feature in FEATURES:
                path = self.path_for(feature)
                previous = path.read_bytes() if path.exists() else None
                local_previous[feature] = previous
                if previous is None:
                    current_revision = 0
                else:
                    current, _ = self._decode(
                        feature, previous, migrate=False
                    )
                    current_revision = current.revision
                local_revisions[feature] = current_revision
                local_highwaters[feature] = self._revision_highwater(
                    feature,
                    recover=True,
                    fallback_revision=current_revision,
                    repair=False,
                )
            for feature, restored in staged.items():
                spec = FEATURES[feature]
                path = self.path_for(feature)
                previous = local_previous[feature]
                current_revision = local_revisions[feature]
                value = restored if restored is not None else spec.default_factory()
                value = replace(
                    value,
                    revision=max(
                        value.revision,
                        current_revision,
                        local_highwaters[feature],
                    ) + 1,
                )
                self._write_locked(
                    feature,
                    path,
                    previous,
                    _serialized(_json_payload(value)),
                    known_highwater=local_highwaters[feature],
                )
            for relative, (raw, previous) in additional.items():
                target = self.root / relative
                if previous is not None:
                    _atomic_write(
                        target.with_suffix(target.suffix + ".bak"), previous
                    )
                _atomic_write(target, raw)

    def reset_all(self) -> None:
        """Explicitly reset known payloads while preserving revision tombstones."""
        with self._all_feature_locks():
            plans = {}
            for feature, spec in FEATURES.items():
                path = self.path_for(feature)
                if path.exists():
                    previous = path.read_bytes()
                    current, _ = self._decode(feature, previous, migrate=False)
                    current_revision = current.revision
                else:
                    previous = None
                    current_revision = 0
                highwater = self._revision_highwater(
                    feature,
                    recover=True,
                    fallback_revision=current_revision,
                    repair=False,
                )
                plans[feature] = (
                    spec, path, previous, current_revision, highwater
                )

            controlled = set()
            for feature in FEATURES:
                path = self.path_for(feature)
                controlled.update({
                    path,
                    path.with_suffix(path.suffix + ".bak"),
                    self._lock_path(feature),
                    self._revision_path(feature),
                    self._revision_mirror_path(feature),
                })
            additional = {}
            if self.root.exists():
                for path in self.root.rglob("*"):
                    if (
                        path.is_symlink()
                        or not path.is_file()
                        or path in controlled
                        or path.name.endswith((".bak", ".lock", ".tmp"))
                    ):
                        continue
                    additional[path] = path.read_bytes()

            for feature, plan in plans.items():
                spec, path, previous, current_revision, highwater = plan
                reset = replace(
                    spec.default_factory(),
                    revision=max(current_revision, highwater) + 1,
                )
                self._write_locked(
                    feature,
                    path,
                    previous,
                    _serialized(_json_payload(reset)),
                    known_highwater=highwater,
                )
            for path, previous in additional.items():
                _atomic_write(path.with_suffix(path.suffix + ".bak"), previous)
                path.unlink()


__all__ = [
    "APPLICATION_DIRECTORY", "LAYOUT_SCHEMA", "ArchetypeState",
    "AssignedBuildCampaign", "AssignedBuildRecord", "AssignedBuildState",
    "CorruptStateError", "IncompatibleStateError", "LastSuccessState",
    "MigrationError", "PreferencesState", "RootMetadata", "StateConflictError",
    "StateLockError", "StateValidationError", "UserStateError", "UserStateStore",
    "resolve_user_state_root",
]
