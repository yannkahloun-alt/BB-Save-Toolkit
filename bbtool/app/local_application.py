"""Typed application operations used by the loopback HTTP adapter.

This module is the authority boundary for the local application.  HTTP code does
not read saves, mutate user-state files, or invoke analysis directly.
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
import threading
from typing import Any

from ..incremental.fingerprint import stable_hash
from .analysis_coordinator import AnalysisCoordinator, DesiredAnalysis
from .analysis_service import AnalysisServiceRequest, SaveSource
from .archetype_catalog import ArchetypeCatalogStore, EffectiveCatalog
from .config import AnalyzerConfig
from .user_state import LastSuccessState, PreferencesState, UserStateStore


class ApplicationOperationError(RuntimeError):
    """A stable application failure suitable for transport adapters."""

    def __init__(self, code: str, message: str, *, details: Any = None) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)

    def as_dict(self) -> dict[str, Any]:
        value = {"code": self.code, "message": self.message}
        if self.details is not None:
            value["details"] = self.details
        return value


def _utc_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


class LocalApplication:
    """Explicit read and mutation API for the interactive local application."""

    def __init__(
        self,
        store: UserStateStore,
        catalog: ArchetypeCatalogStore,
        classification: dict,
        *,
        coordinator: AnalysisCoordinator | None = None,
        read_save: Callable[[Path], bytes] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.catalog = catalog
        self.classification = classification
        self.coordinator = coordinator or AnalysisCoordinator()
        self._read_save = read_save or Path.read_bytes
        self._clock = clock or (lambda: datetime.now(UTC))
        self._persisted_generation = 0
        self._publication_warning: dict[str, Any] | None = None
        self._source_timestamps: dict[int, str] = {}
        self._invalidated_generation: int | None = None
        self._invalidation_reason: str | None = None
        self._command_lock = threading.RLock()

    def close(self) -> None:
        self.coordinator.shutdown()

    def followed_save(self) -> dict[str, Any]:
        preferences = self.store.load("preferences")
        selected = preferences.selected_save_path
        info: dict[str, Any] = {
            "revision": preferences.revision,
            "selected_path": selected,
            "auto_refresh": preferences.auto_refresh,
            "available": False,
        }
        if selected is not None:
            path = Path(selected)
            try:
                stat = path.stat()
                info.update({
                    "available": path.is_file(),
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "modified_at": _utc_timestamp(stat.st_mtime),
                })
            except OSError as exc:
                info["warning"] = {
                    "code": "selected_save_unavailable",
                    "message": str(exc),
                }
        return info

    def select_followed_save(
        self, path_value: str, *, expected_revision: int, auto_refresh: bool | None = None
    ) -> dict[str, Any]:
        with self._command_lock:
            return self._select_followed_save(
                path_value,
                expected_revision=expected_revision,
                auto_refresh=auto_refresh,
            )

    def _select_followed_save(
        self, path_value: str, *, expected_revision: int, auto_refresh: bool | None
    ) -> dict[str, Any]:
        if not isinstance(path_value, str) or not path_value.strip():
            raise ApplicationOperationError("invalid_save_path", "path must be a non-empty string")
        path = Path(path_value).expanduser().resolve()
        if path.suffix.lower() != ".sav" or not path.is_file():
            raise ApplicationOperationError(
                "invalid_save_path", "selected save must be an existing .sav file"
            )
        current = self.store.load("preferences")
        saved = self.store.save(
            "preferences",
            PreferencesState(
                selected_save_path=str(path),
                auto_refresh=current.auto_refresh if auto_refresh is None else auto_refresh,
            ),
            expected_revision=expected_revision,
        )
        self._invalidate_publication("selected_save_changed")
        return self.followed_save() | {
            "revision": saved.revision,
            "freshness": {"status": "stale", "reason": "selected_save_changed"},
        }

    def forget_followed_save(self, *, expected_revision: int) -> dict[str, Any]:
        with self._command_lock:
            return self._forget_followed_save(expected_revision=expected_revision)

    def _forget_followed_save(self, *, expected_revision: int) -> dict[str, Any]:
        current = self.store.load("preferences")
        saved = self.store.save(
            "preferences",
            PreferencesState(selected_save_path=None, auto_refresh=current.auto_refresh),
            expected_revision=expected_revision,
        )
        self._invalidate_publication("selected_save_forgotten")
        return self.followed_save() | {
            "revision": saved.revision,
            "freshness": {"status": "unavailable", "reason": "selected_save_forgotten"},
        }

    @staticmethod
    def _catalog_payload(value: EffectiveCatalog) -> dict[str, Any]:
        return {
            "revision": value.state.revision,
            "roles": list(value.roles),
            "definition_hashes": value.definition_hashes,
        }

    def _effective_catalog_payload(self, value: EffectiveCatalog) -> dict[str, Any]:
        custom_ids = {
            entry["definition"]["id"] for entry in value.state.entries
            if entry.get("kind") == "custom"
        }
        override_ids = {
            entry["id"] for entry in value.state.entries
            if entry.get("kind") == "override"
        }
        provenance = {
            role["id"]: (
                "user_custom" if role["id"] in custom_ids
                else "base_with_user_override" if role["id"] in override_ids
                else "base"
            )
            for role in value.roles
        }
        return self._catalog_payload(value) | {
            "provenance": provenance,
            "user_entries": list(value.state.entries),
        }

    def effective_archetypes(self) -> dict[str, Any]:
        return self._effective_catalog_payload(self.catalog.load())

    def mutate_archetypes(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._command_lock:
            return self._mutate_archetypes(operation, payload)

    def _mutate_archetypes(
        self, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        revision = payload["expected_revision"]
        identity = payload.get("id")
        operations = {
            "set_override": lambda: self.catalog.set_override(
                identity, payload["patch"], expected_revision=revision
            ),
            "set_disabled": lambda: self.catalog.set_disabled(
                identity, payload["disabled"], expected_revision=revision
            ),
            "reset_base": lambda: self.catalog.reset_base(identity, expected_revision=revision),
            "reset_override": lambda: self.catalog.reset_override(identity, expected_revision=revision),
            "create_custom": lambda: self.catalog.create_custom(
                payload["definition"], expected_revision=revision
            ),
            "edit_custom": lambda: self.catalog.edit_custom(
                identity, payload["definition"], expected_revision=revision
            ),
            "duplicate": lambda: self.catalog.duplicate(
                identity, expected_revision=revision, name=payload.get("name")
            ),
            "delete_custom": lambda: self.catalog.delete_custom(
                identity, expected_revision=revision
            ),
            "import": lambda: self.catalog.import_json(
                payload["document"], expected_revision=revision, merge=payload.get("merge", False)
            ),
        }
        if operation not in operations:
            raise ApplicationOperationError("unknown_operation", "unknown archetype operation")
        result = operations[operation]()
        self._invalidate_publication("effective_archetypes_changed")
        return self._effective_catalog_payload(result) | {
            "freshness": {
                "status": "stale",
                "reason": "effective_archetypes_changed",
                "recompute": "request_analysis",
            }
        }

    def export_archetypes(self) -> dict[str, Any]:
        return {"document": self.catalog.export_json()}

    def request_analysis(self, *, expected_preferences_revision: int) -> dict[str, Any]:
        with self._command_lock:
            return self._request_analysis(
                expected_preferences_revision=expected_preferences_revision
            )

    def _request_analysis(self, *, expected_preferences_revision: int) -> dict[str, Any]:
        preferences = self.store.load("preferences")
        if preferences.revision != expected_preferences_revision:
            from .user_state import StateConflictError

            raise StateConflictError(
                "preferences revision conflict: expected "
                f"{expected_preferences_revision}, found {preferences.revision}"
            )
        if preferences.selected_save_path is None:
            raise ApplicationOperationError("no_selected_save", "no save is currently selected")
        path = Path(preferences.selected_save_path)
        try:
            content = self._read_save(path)
        except OSError as exc:
            raise ApplicationOperationError(
                "selected_save_unavailable", "the selected save could not be read"
            ) from exc
        config: AnalyzerConfig = self.catalog.analyzer_config(self.classification)
        desired = DesiredAnalysis(
            AnalysisServiceRequest(
                source=SaveSource(content=content, name=path.name),
                roles=config.roles,
                classification=config.classification,
            )
        )
        job_id = self.coordinator.submit(desired)
        with suppress(OSError):
            self._source_timestamps[job_id] = _utc_timestamp(path.stat().st_mtime)
        return self.analysis_job(job_id)

    def analysis_job(self, job_id: int) -> dict[str, Any]:
        try:
            job = self.coordinator.job(job_id)
        except KeyError as exc:
            raise ApplicationOperationError("job_not_found", "analysis job was not found") from exc
        self._persist_publication()
        return {
            "id": job.id,
            "status": job.status.value,
            "source_fingerprint": job.desired.source_fingerprint,
            "configuration_fingerprints": dict(job.desired.configuration_fingerprints),
            "artifact_signatures": dict(job.desired.artifact_signatures),
            "progress": [asdict(event) for event in job.progress],
            "error": job.error,
            "published": (
                self.coordinator.last_success is not None
                and self.coordinator.last_success.job_id == job.id
            ),
        }

    def last_result(self) -> dict[str, Any]:
        self._persist_publication()
        publication = self.coordinator.last_success
        durable = self.store.load("last_success")
        if publication is None:
            return {
                "available": False,
                "freshness": {"status": "unavailable"},
                "last_success": asdict(durable),
                "warning": self._publication_warning,
            }
        result = publication.result
        invalidated = self._invalidated_generation == publication.generation
        freshness = {
            "status": (
                "current"
                if publication.job_id == self.coordinator.desired_job_id and not invalidated
                else "stale"
            ),
            "generation": publication.generation,
            "represented_source_fingerprint": publication.source_fingerprint,
            "represented_configuration_fingerprints": dict(publication.configuration_fingerprints),
            "artifact_signatures": dict(publication.artifact_signatures),
        }
        if invalidated:
            freshness["reason"] = self._invalidation_reason
        return {
            "available": True,
            "freshness": freshness,
            "warnings": result.warnings,
            "data": result.public_data,
            "warning": self._publication_warning,
        }

    def _invalidate_publication(self, reason: str) -> None:
        self.coordinator.invalidate_desired()
        publication = self.coordinator.last_success
        self._invalidated_generation = (
            publication.generation if publication is not None else None
        )
        self._invalidation_reason = reason

    def _persist_publication(self) -> None:
        publication = self.coordinator.last_success
        if publication is None or publication.generation <= self._persisted_generation:
            return
        current = self.store.load("last_success")
        config_fingerprint = stable_hash(dict(publication.configuration_fingerprints))
        try:
            self.store.save(
                "last_success",
                LastSuccessState(
                    source_fingerprint=publication.source_fingerprint,
                    config_fingerprint=config_fingerprint,
                    source_timestamp=self._source_timestamps.get(publication.job_id),
                    completed_at=self._clock().isoformat(),
                ),
                expected_revision=current.revision,
            )
            self._persisted_generation = publication.generation
            self._publication_warning = None
        except Exception as exc:
            self._publication_warning = {
                "code": "last_success_persistence_failed",
                "message": str(exc),
            }


__all__ = ["ApplicationOperationError", "LocalApplication"]
