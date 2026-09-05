from copy import deepcopy
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from bbtool.app.analysis_coordinator import AnalysisCoordinator, JobStatus
from bbtool.app.archetype_catalog import ArchetypeCatalogStore
from bbtool.app.config import load_config
from bbtool.app.local_application import LocalApplication
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


class CompletingHandle(HoldingHandle):
    def __init__(self):
        self.pending = []

    def messages(self):
        messages, self.pending = self.pending, []
        return messages

    def is_alive(self):
        return not self.pending

    def send_result(self, job_id, desired):
        self.pending.append(
            (
                "result",
                (
                    job_id,
                    SimpleNamespace(
                        source_fingerprint=desired.source_fingerprint,
                        configuration_fingerprints=desired.configuration_fingerprints,
                    ),
                ),
            )
        )


class CompletingBackend:
    def __init__(self):
        self.starts = []
        self._condition = threading.Condition()

    def start(self, job_id, request):
        handle = CompletingHandle()
        with self._condition:
            self.starts.append((job_id, request, handle))
            self._condition.notify_all()
        return handle

    @property
    def handle(self):
        return self.starts[-1][2]

    def wait_for_starts(self, count):
        with self._condition:
            return self._condition.wait_for(lambda: len(self.starts) >= count, timeout=2)


class ObservedReader:
    def __init__(self):
        self.count = 0
        self._condition = threading.Condition()

    def __call__(self, path):
        content = path.read_bytes()
        with self._condition:
            self.count += 1
            self._condition.notify_all()
        return content

    def wait_for_reads(self, count):
        with self._condition:
            return self._condition.wait_for(lambda: self.count >= count, timeout=2)


def test_restarted_auto_refresh_catalog_conflict_keeps_watcher_alive_after_recovery(tmp_path):
    config = load_config(
        ROOT / "config" / "archetypes.json",
        ROOT / "config" / "classification.json",
    )
    state_root = tmp_path / "profile"
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"before-upgrade")

    store = UserStateStore(state_root)
    store.save(
        "preferences",
        PreferencesState(selected_save_path=str(save), auto_refresh=True),
        expected_revision=0,
    )
    old_catalog = ArchetypeCatalogStore(store, config.roles)
    old_catalog.set_override(
        "reach_dps",
        {"name": "Persisted Polearm Override"},
        expected_revision=0,
    )

    changed_roles = deepcopy(config.roles)
    changed_base = next(role for role in changed_roles if role["id"] == "reach_dps")
    changed_base["stats"]["MAtk"]["target"] += 1

    restarted_store = UserStateStore(state_root)
    backend = CompletingBackend()
    coordinator = AnalysisCoordinator(backend=backend, monitor=False)
    reader = ObservedReader()
    application = LocalApplication(
        restarted_store,
        ArchetypeCatalogStore(restarted_store, changed_roles),
        config.classification,
        coordinator=coordinator,
        read_save=reader,
    )
    watcher = application.start_save_watcher(monitor=True, poll_interval=0.01)

    try:
        # Two stable probes reach the stale catalog callback; a third probe proves
        # that the production monitor loop survived the callback failure.
        assert reader.wait_for_reads(3)
        failed = watcher.status()
        assert failed["status"] == "failed"
        assert failed["reason"] == "archetype_catalog_conflict"
        assert (
            "base_definition_hash conflicts with the current shipped definition"
            in failed["message"]
        )
        assert backend.starts == []

        conflict = application.effective_archetypes()
        assert conflict["catalog_conflict"]["code"] == "shipped_user_entry_conflict"
        recovered = application.mutate_archetypes(
            "reset_base",
            {"id": "reach_dps", "expected_revision": conflict["revision"]},
        )
        assert "catalog_conflict" not in recovered

        requested = application.request_analysis(expected_preferences_revision=1)
        first_job_id = requested["id"]
        assert len(backend.starts) == 1
        first_desired = coordinator.job(first_job_id).desired
        backend.handle.send_result(first_job_id, first_desired)
        coordinator.poll()
        assert coordinator.job(first_job_id).status == JobStatus.SUCCEEDED
        application.analysis_job(first_job_id)
        current = watcher.status()
        assert current["status"] == "current"
        assert "reason" not in current
        assert "message" not in current

        save.write_bytes(b"after-recovery-change")
        watcher.notify()
        assert backend.wait_for_starts(2)
        second_job_id = coordinator.desired_job_id
        assert second_job_id is not None
        assert second_job_id != first_job_id
        assert backend.starts[-1][1].source.content == b"after-recovery-change"
        assert watcher.accepted is not None
        assert watcher.accepted.content == b"after-recovery-change"
    finally:
        application.close()


def test_save_watcher_still_propagates_unrelated_stable_callback_errors(tmp_path):
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"stable")

    def fail(_snapshot, _auto_refresh):
        raise RuntimeError("programming error")

    watcher = SaveWatcher(
        lambda: (str(save), True),
        lambda _reason: None,
        fail,
        monitor=False,
    )
    watcher.poll()
    with pytest.raises(RuntimeError, match="programming error"):
        watcher.poll()
