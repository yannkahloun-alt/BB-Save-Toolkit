"""Typed application operations used by the loopback HTTP adapter.

This module is the authority boundary for the local application.  HTTP code does
not read saves, mutate user-state files, or invoke analysis directly.
"""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
import threading
from typing import Any

from ..build_identity import build_definition_hash
from ..incremental.fingerprint import stable_hash
from ..models import BrotherIdentity, CampaignIdentity
from .assigned_build import AssignedBuildStore, DurableAssignedBuildResolver
from .analysis_coordinator import AnalysisCoordinator, DesiredAnalysis
from .analysis_service import AnalysisServiceRequest, SaveSource
from .archetype_catalog import (
    ArchetypeCatalogStore,
    CatalogValidationError,
    EffectiveCatalog,
    effective_catalog,
)
from .config import AnalyzerConfig
from .publication_signatures import (
    build_desired_dependency_signatures,
    dependency_signatures_are_current,
)
from .user_state import ArchetypeState, LastSuccessState, PreferencesState, UserStateStore
from .save_watcher import SaveWatcher, StableSave


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
        assigned_build_changed: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.store = store
        self.catalog = catalog
        self.classification = classification
        self.assigned_builds = AssignedBuildStore(store, catalog)
        self.coordinator = coordinator or AnalysisCoordinator()
        configure_dependency_validation = getattr(
            self.coordinator, "configure_dependency_validation", None
        )
        if callable(configure_dependency_validation):
            configure_dependency_validation(
                lambda signatures: dependency_signatures_are_current(
                    signatures,
                    catalog=self.catalog,
                    classification=self.classification,
                    assigned_builds=self.assigned_builds,
                )
            )
        self._read_save = read_save or Path.read_bytes
        self._clock = clock or (lambda: datetime.now(UTC))
        self._assigned_build_changed = assigned_build_changed
        self._persisted_generation = 0
        self._publication_warning: dict[str, Any] | None = None
        self._source_timestamps: dict[int, str] = {}
        self._invalidated_generation: int | None = None
        self._invalidation_reason: str | None = None
        self._command_lock = threading.RLock()
        self._save_watcher: SaveWatcher | None = None

    def start_save_watcher(
        self, *, monitor: bool = True, poll_interval: float = 0.25,
        stable_probes: int = 2,
    ) -> SaveWatcher:
        """Restore and watch the persisted selection; safe to drive manually in tests."""
        with self._command_lock:
            if self._save_watcher is not None:
                return self._save_watcher
            self._save_watcher = SaveWatcher(
                self._watch_selection,
                self._watch_change_detected,
                self._watch_stable,
                monitor=monitor,
                poll_interval=poll_interval,
                stable_probes=stable_probes,
                read_bytes=self._read_save,
            )
            return self._save_watcher

    def _watch_selection(self) -> tuple[str | None, bool]:
        value = self.store.load("preferences")
        return value.selected_save_path, value.auto_refresh

    def _watch_change_detected(self, reason: str) -> None:
        with self._command_lock:
            self.coordinator.mark_desired_stale()
            publication = self.coordinator.last_success
            self._invalidated_generation = (
                publication.generation if publication is not None else None
            )
            self._invalidation_reason = reason

    def _watch_stable(self, snapshot: StableSave, auto_refresh: bool) -> None:
        if not auto_refresh:
            return
        with self._command_lock:
            current = self.store.load("preferences")
            if current.selected_save_path != str(snapshot.path):
                return
            self._submit_content(snapshot.path, snapshot.content, snapshot.modified_at)

    def close(self) -> None:
        if self._save_watcher is not None:
            self._save_watcher.close()
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
        if self._save_watcher is not None:
            info["freshness"] = self._save_watcher.status()
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
        if self._save_watcher is not None:
            self._save_watcher.notify()
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
        if self._save_watcher is not None:
            self._save_watcher.notify()
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

    def _catalog_conflict_entries(
        self, state: ArchetypeState, errors: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        base = {role["id"]: role for role in self.catalog.base_roles}
        conflicts: list[dict[str, Any]] = []
        for index, entry in enumerate(state.entries):
            kind = entry.get("kind")
            identity = entry.get("id")
            if kind not in {"override", "disabled"} or not isinstance(identity, str):
                continue
            prefix = f"entries[{index}]"
            entry_errors = [error for error in errors if error.startswith(prefix)]
            if not entry_errors:
                continue
            current = base.get(identity)
            if current is None:
                reason = "shipped_definition_missing"
                current_hash = None
            elif kind == "override" and entry.get("base_definition_hash") != build_definition_hash(current):
                reason = "base_definition_changed"
                current_hash = build_definition_hash(current)
            else:
                reason = "invalid_shipped_entry"
                current_hash = build_definition_hash(current)
            conflict: dict[str, Any] = {
                "entry_index": index,
                "id": identity,
                "kind": kind,
                "reason": reason,
                "recovery_operation": "reset_base",
                "errors": entry_errors,
            }
            if kind == "override":
                conflict["persisted_base_definition_hash"] = entry.get("base_definition_hash")
                conflict["current_base_definition_hash"] = current_hash
            conflicts.append(conflict)
        return conflicts

    def effective_archetypes(self) -> dict[str, Any]:
        state = self.store.load("archetypes")
        try:
            return self._effective_catalog_payload(
                effective_catalog(self.catalog.base_roles, state)
            )
        except CatalogValidationError as exc:
            conflicts = self._catalog_conflict_entries(state, exc.errors)
            if not conflicts:
                raise
            return {
                "revision": state.revision,
                "roles": [],
                "definition_hashes": {},
                "provenance": {},
                "user_entries": list(state.entries),
                "catalog_conflict": {
                    "code": "shipped_user_entry_conflict",
                    "errors": list(exc.errors),
                    "entries": conflicts,
                },
            }

    @staticmethod
    def _assigned_identity(campaign_value: int, native_token: int) -> tuple[CampaignIdentity, BrotherIdentity]:
        campaign = CampaignIdentity(campaign_value, confidence="exact")
        brother = BrotherIdentity(campaign_value, native_token, confidence="exact")
        return campaign, brother

    def assigned_build(self, campaign_value: int, native_token: int) -> dict[str, Any]:
        campaign, brother = self._assigned_identity(campaign_value, native_token)
        return self.assigned_builds.read(campaign, brother)

    def mutate_assigned_build(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._command_lock:
            campaign = CampaignIdentity(payload["campaign_identity"], confidence="exact")
            brother = None
            if "native_entity_token" in payload:
                campaign, brother = self._assigned_identity(
                    payload["campaign_identity"], payload["native_entity_token"]
                )
            revision = payload["expected_revision"]
            if operation in {"assign", "change", "acknowledge"}:
                publication = self.coordinator.last_success
                publication_is_current = (
                    publication is not None
                    and publication.job_id == self.coordinator.desired_job_id
                    and self._invalidated_generation != publication.generation
                )
                result_identity = publication.result if publication is not None else None
                current_campaign = (
                    result_identity.campaign_identity if result_identity is not None else None
                )
                known_brothers = (
                    result_identity.brother_identities.values()
                    if result_identity is not None else ()
                )
                if (
                    not publication_is_current
                    or current_campaign is None
                    or current_campaign.confidence != "exact"
                    or current_campaign.value != campaign.value
                    or not any(
                        known.confidence == "exact" and known.value == brother.value
                        for known in known_brothers
                    )
                ):
                    raise ApplicationOperationError(
                        "identity_unavailable",
                        "assignment requires matching exact identity evidence from the current analysis",
                    )
                result = getattr(self.assigned_builds, operation)(
                    campaign, brother, payload["build_identity"],  # type: ignore[arg-type]
                    expected_revision=revision,
                )
            elif operation == "clear":
                result = self.assigned_builds.clear(
                    campaign, brother, expected_revision=revision  # type: ignore[arg-type]
                )
            elif operation == "clear_campaign":
                result = self.assigned_builds.clear_campaign(
                    campaign, expected_revision=revision
                )
            else:
                raise ApplicationOperationError(
                    "unknown_operation", "unknown assigned-build operation"
                )
            changes = result.get("changes") or (
                [result["change"]] if result.get("change") is not None else []
            )
            # The durable write is authoritative. Prevent any pre-mutation desired
            # generation from remaining current/coalescing with an explicit refresh;
            # the old publication can still supply intrinsic data while intent-aware
            # consumers expose staleness until the refreshed generation publishes.
            if changes:
                self._invalidate_publication("assigned_build_changed")
            refresh_errors = []
            if self._assigned_build_changed is not None:
                for change in changes:
                    try:
                        self._assigned_build_changed(change)
                    except Exception as exc:
                        refresh_errors.append({
                            "code": "intent_refresh_failed", "message": str(exc)
                        })
            result["invalidation"] = {
                "changes": changes,
                "affected_artifacts": [
                    "level_advisor", "company_intended_coverage", "relevant_roster_need"
                ] if changes else [],
                "status": "failed" if refresh_errors else "required" if changes else "unchanged",
            }
            if refresh_errors:
                result["invalidation"]["errors"] = refresh_errors
            return result

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
        if operation == "reset_base":
            self.catalog.reset_base_recovery(
                identity, expected_revision=revision
            )
            result_payload = self.effective_archetypes()
        else:
            if operation not in operations:
                raise ApplicationOperationError("unknown_operation", "unknown archetype operation")
            result_payload = self._effective_catalog_payload(operations[operation]())
        self._invalidate_publication("effective_archetypes_changed")
        return result_payload | {
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
        accepted = self._save_watcher.accepted if self._save_watcher is not None else None
        if self._save_watcher is not None:
            watcher_status = self._save_watcher.status()["status"]
            if watcher_status == "unavailable":
                raise ApplicationOperationError(
                    "selected_save_unavailable", "the selected save is not currently readable"
                )
            if (
                accepted is None
                or accepted.path != path
                or watcher_status == "stabilizing"
            ):
                raise ApplicationOperationError(
                    "selected_save_stabilizing", "the selected save is not yet stable"
                )
            return self._submit_content(path, accepted.content, accepted.modified_at)
        try:
            content = self._read_save(path)
            modified_at = path.stat().st_mtime
        except OSError as exc:
            raise ApplicationOperationError(
                "selected_save_unavailable", "the selected save could not be read"
            ) from exc
        return self._submit_content(path, content, modified_at)

    def _submit_content(self, path: Path, content: bytes, modified_at: float) -> dict[str, Any]:
        config: AnalyzerConfig = self.catalog.analyzer_config(self.classification)
        desired = DesiredAnalysis(
            AnalysisServiceRequest(
                source=SaveSource(content=content, name=path.name),
                roles=config.roles,
                classification=config.classification,
                assigned_build_resolver=DurableAssignedBuildResolver(
                    self.store.root, tuple(self.catalog.base_roles)
                ),
            ),
            dependency_signatures=build_desired_dependency_signatures(
                content, config.roles, config.classification, self.assigned_builds
            ),
        )
        job_id = self.coordinator.submit(desired)
        self._source_timestamps[job_id] = _utc_timestamp(modified_at)
        if self._save_watcher is not None:
            self._save_watcher.set_job_state(self.coordinator.job(job_id).status.value)
        return self.analysis_job(job_id)

    def analysis_job(self, job_id: int) -> dict[str, Any]:
        with self._command_lock:
            return self._analysis_job(job_id)

    def _analysis_job(self, job_id: int) -> dict[str, Any]:
        try:
            job = self.coordinator.job(job_id)
        except KeyError as exc:
            raise ApplicationOperationError("job_not_found", "analysis job was not found") from exc
        self._persist_publication()
        if (
            self._save_watcher is not None
            and job.id == self.coordinator.desired_job_id
        ):
            self._save_watcher.set_job_state(job.status.value)
        publication = self.coordinator.last_success
        published = publication is not None and publication.job_id == job.id
        return {
            "id": job.id,
            "status": job.status.value,
            "source_fingerprint": job.desired.source_fingerprint,
            "configuration_fingerprints": dict(job.desired.configuration_fingerprints),
            "dependency_signatures": deepcopy(job.desired.dependency_signatures),
            "artifact_signatures": (
                deepcopy(publication.artifact_signatures) if published else None
            ),
            "progress": [asdict(event) for event in job.progress],
            "error": job.error,
            "published": published,
        }

    def last_result(self) -> dict[str, Any]:
        with self._command_lock:
            return self._last_result()

    def _last_result(self) -> dict[str, Any]:
        self._persist_publication()
        desired_job_id = self.coordinator.desired_job_id
        if self._save_watcher is not None and desired_job_id is not None:
            self._save_watcher.set_job_state(
                self.coordinator.job(desired_job_id).status.value
            )
        publication = self.coordinator.last_success
        durable = self.store.load("last_success")
        if publication is None:
            freshness = (
                self._save_watcher.status()
                if self._save_watcher is not None
                else {"status": "unavailable"}
            )
            return {
                "available": False,
                "freshness": freshness,
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
            "dependency_signatures": deepcopy(
                getattr(publication, "dependency_signatures", {})
            ),
            "artifact_signatures": deepcopy(publication.artifact_signatures),
        }
        if invalidated:
            freshness["reason"] = self._invalidation_reason
        if self._save_watcher is not None:
            watcher = self._save_watcher.status()
            desired = watcher.get("desired_source_fingerprint")
            if desired is not None and desired != publication.source_fingerprint:
                freshness["status"] = "stale"
                freshness["reason"] = "selected_save_content_changed"
            elif watcher["status"] in {"detected", "stabilizing", "queued", "analyzing", "failed", "unavailable"}:
                freshness["status"] = watcher["status"]
                if "reason" in watcher:
                    freshness["reason"] = watcher["reason"]
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
