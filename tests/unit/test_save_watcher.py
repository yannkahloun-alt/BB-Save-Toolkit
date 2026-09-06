from pathlib import Path
from types import SimpleNamespace

import pytest

from bbtool.app.analysis_coordinator import AnalysisCoordinator, JobStatus
from bbtool.app.archetype_catalog import ArchetypeCatalogStore
from bbtool.app.config import load_config
from bbtool.app.local_application import ApplicationOperationError, LocalApplication
from bbtool.app.save_watcher import SaveWatcher
from bbtool.app.user_state import PreferencesState, UserStateStore


ROOT = Path(__file__).resolve().parents[2]


class HoldingHandle:
    def messages(self):
        return []

    def is_alive(self):
        return True

    def terminate(self):
        pass

    def join(self):
        pass


class HoldingBackend:
    def __init__(self):
        self.starts = []

    def start(self, job_id, request):
        self.starts.append((job_id, request))
        return HoldingHandle()


class CompletingHandle(HoldingHandle):
    def __init__(self):
        self.pending = []

    def messages(self):
        messages, self.pending = self.pending, []
        return messages

    def is_alive(self):
        return not self.pending

    def send_result(self, job_id, desired):
        self.pending.append(("result", (job_id, SimpleNamespace(
            source_fingerprint=desired.source_fingerprint,
            configuration_fingerprints=desired.configuration_fingerprints,
                        incremental_cache=SimpleNamespace(
                            publication_signatures=lambda: {}
                        ),
        ))))


class CompletingBackend(HoldingBackend):
    def start(self, job_id, request):
        handle = CompletingHandle()
        self.starts.append((job_id, request, handle))
        return handle

    @property
    def handle(self):
        return self.starts[-1][2]


def test_duplicate_events_and_same_content_replacement_coalesce(tmp_path):
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"complete-a")
    detected = []
    stable = []
    watcher = SaveWatcher(
        lambda: (str(save), True), detected.append,
        lambda snapshot, automatic: stable.append((snapshot, automatic)), monitor=False,
    )

    watcher.notify()
    watcher.notify()
    watcher.poll()
    assert watcher.status()["status"] == "stabilizing"
    watcher.poll()
    assert len(detected) == 1
    assert len(stable) == 1

    replacement = tmp_path / "replacement.tmp"
    replacement.write_bytes(b"complete-a")
    replacement.replace(save)
    watcher.poll()
    watcher.poll()

    assert len(detected) == 1
    assert len(stable) == 1
    assert watcher.status()["status"] == "queued"


def test_partial_write_must_be_reobserved_complete_before_acceptance(tmp_path):
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"old")
    stable = []
    watcher = SaveWatcher(
        lambda: (str(save), True), lambda _reason: None,
        lambda snapshot, _automatic: stable.append(snapshot.content), monitor=False,
    )
    watcher.poll()
    watcher.poll()
    assert stable == [b"old"]

    save.write_bytes(b"part")
    watcher.poll()
    save.write_bytes(b"complete-new-save")
    watcher.poll()
    assert stable == [b"old"]
    watcher.poll()

    assert stable == [b"old", b"complete-new-save"]


def test_locked_missing_and_restored_path_retains_selection(tmp_path):
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"save")
    locked = False

    def read(path):
        if locked:
            raise PermissionError("sharing violation")
        return path.read_bytes()

    stable = []
    watcher = SaveWatcher(
        lambda: (str(save), False), lambda _reason: None,
        lambda snapshot, automatic: stable.append((snapshot.content, automatic)),
        read_bytes=read, monitor=False,
    )
    watcher.poll()
    watcher.poll()
    assert stable == [(b"save", False)]
    assert watcher.status()["status"] == "detected"

    locked = True
    watcher.poll()
    assert watcher.status()["status"] == "unavailable"
    assert watcher.status()["reason"] == "selected_save_locked"
    assert watcher.accepted is not None
    locked = False
    watcher.poll()
    assert watcher.status()["status"] == "stabilizing"
    watcher.poll()
    assert watcher.status()["status"] == "detected"
    assert watcher.status()["reason"] == "refresh_available"

    save.unlink()
    watcher.poll()
    assert watcher.status()["status"] == "unavailable"
    assert watcher.status()["reason"] == "selected_save_missing"
    assert watcher.accepted.path == save
    save.write_bytes(b"restored")
    watcher.poll()
    watcher.poll()
    assert stable[-1] == (b"restored", False)


def test_local_application_restores_auto_refresh_and_delegates_coalescing(tmp_path):
    config = load_config(
        ROOT / "config" / "archetypes.json", ROOT / "config" / "classification.json"
    )
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"first")
    store = UserStateStore(tmp_path / "profile")
    store.save(
        "preferences",
        PreferencesState(selected_save_path=str(save), auto_refresh=True),
        expected_revision=0,
    )
    backend = HoldingBackend()
    coordinator = AnalysisCoordinator(backend=backend, monitor=False)
    app = LocalApplication(
        store, ArchetypeCatalogStore(store, config.roles), config.classification,
        coordinator=coordinator,
    )
    watcher = app.start_save_watcher(monitor=False)

    watcher.poll()
    assert app.last_result()["freshness"]["status"] == "stabilizing"
    watcher.poll()
    assert len(backend.starts) == 1
    first = coordinator.desired_job_id
    assert app.analysis_job(first)["status"] == "running"

    save.write_bytes(b"second")
    watcher.poll()
    assert app.last_result()["freshness"]["status"] == "stabilizing"
    watcher.poll()
    second = coordinator.desired_job_id
    assert second != first
    assert coordinator.job(first).status.value == "superseded"
    assert coordinator.job(second).status.value == "queued"

    # Duplicate probes for the same content are absorbed by the watcher and #97.
    watcher.poll()
    watcher.notify()
    watcher.poll()
    assert coordinator.desired_job_id == second
    assert len(coordinator._jobs) == 2
    app.close()


def test_notify_only_same_content_recovery_never_claims_current_without_result(tmp_path):
    config = load_config(
        ROOT / "config" / "archetypes.json", ROOT / "config" / "classification.json"
    )
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"stable")
    store = UserStateStore(tmp_path / "profile")
    store.save(
        "preferences",
        PreferencesState(selected_save_path=str(save), auto_refresh=False),
        expected_revision=0,
    )
    app = LocalApplication(
        store, ArchetypeCatalogStore(store, config.roles), config.classification,
        coordinator=AnalysisCoordinator(backend=HoldingBackend(), monitor=False),
    )
    watcher = app.start_save_watcher(monitor=False)
    watcher.poll()
    watcher.poll()
    before = app.last_result()
    assert before["available"] is False
    assert before["freshness"]["status"] == "detected"
    assert before["freshness"]["reason"] == "refresh_available"

    save.unlink()
    watcher.poll()
    unavailable = app.last_result()
    assert unavailable["available"] is False
    assert unavailable["freshness"]["status"] == "unavailable"
    assert unavailable["freshness"]["reason"] == "selected_save_missing"

    save.write_bytes(b"stable")
    watcher.poll()
    assert app.last_result()["freshness"]["status"] == "stabilizing"
    watcher.poll()
    restored = app.last_result()
    assert restored["available"] is False
    assert restored["freshness"]["status"] == "detected"
    assert restored["freshness"]["reason"] == "refresh_available"
    assert app.coordinator.desired_job_id is None
    app.close()


def test_manual_refresh_rejects_old_snapshot_while_stabilizing_or_unavailable(tmp_path):
    config = load_config(
        ROOT / "config" / "archetypes.json", ROOT / "config" / "classification.json"
    )
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"accepted")
    store = UserStateStore(tmp_path / "profile")
    store.save(
        "preferences",
        PreferencesState(selected_save_path=str(save), auto_refresh=False),
        expected_revision=0,
    )
    backend = HoldingBackend()
    app = LocalApplication(
        store, ArchetypeCatalogStore(store, config.roles), config.classification,
        coordinator=AnalysisCoordinator(backend=backend, monitor=False),
    )
    watcher = app.start_save_watcher(monitor=False)
    watcher.poll()
    watcher.poll()
    assert watcher.accepted.content == b"accepted"

    save.write_bytes(b"new-candidate")
    watcher.poll()
    with pytest.raises(ApplicationOperationError, match="not yet stable") as stabilizing:
        app.request_analysis(expected_preferences_revision=1)
    assert stabilizing.value.code == "selected_save_stabilizing"
    assert backend.starts == []

    save.unlink()
    watcher.poll()
    assert watcher.accepted.content == b"accepted"
    with pytest.raises(ApplicationOperationError, match="not currently readable") as unavailable:
        app.request_analysis(expected_preferences_revision=1)
    assert unavailable.value.code == "selected_save_unavailable"
    assert backend.starts == []
    app.close()


def test_historical_job_query_cannot_change_newer_global_watcher_state(tmp_path):
    config = load_config(
        ROOT / "config" / "archetypes.json", ROOT / "config" / "classification.json"
    )
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"first")
    store = UserStateStore(tmp_path / "profile")
    store.save(
        "preferences",
        PreferencesState(selected_save_path=str(save), auto_refresh=True),
        expected_revision=0,
    )
    backend = CompletingBackend()
    coordinator = AnalysisCoordinator(backend=backend, monitor=False)
    app = LocalApplication(
        store, ArchetypeCatalogStore(store, config.roles), config.classification,
        coordinator=coordinator,
    )
    watcher = app.start_save_watcher(monitor=False)
    watcher.poll()
    watcher.poll()
    old_id = coordinator.desired_job_id
    old_desired = coordinator.job(old_id).desired
    backend.handle.send_result(old_id, old_desired)
    coordinator.poll()
    assert coordinator.job(old_id).status == JobStatus.SUCCEEDED
    app.analysis_job(old_id)
    assert watcher.status()["status"] == "current"

    save.write_bytes(b"newest")
    watcher.poll()
    watcher.poll()
    newest_id = coordinator.desired_job_id
    assert newest_id != old_id
    assert watcher.status()["status"] == "analyzing"

    assert app.analysis_job(old_id)["status"] == "succeeded"
    assert watcher.status()["status"] == "analyzing"
    assert coordinator.desired_job_id == newest_id
    app.close()
