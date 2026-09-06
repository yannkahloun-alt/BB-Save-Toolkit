from pathlib import Path
from types import SimpleNamespace

from bbtool.app.analysis_coordinator import AnalysisCoordinator
from bbtool.app.archetype_catalog import ArchetypeCatalogStore
from bbtool.app.config import load_config
from bbtool.app.local_application import LocalApplication
from bbtool.app.user_state import UserStateStore
from bbtool.models import BrotherIdentity, CampaignIdentity


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


def make_application(tmp_path, *, coordinator=None, callback=None):
    config = load_config(
        ROOT / "config" / "archetypes.json",
        ROOT / "config" / "classification.json",
    )
    store = UserStateStore(tmp_path / "profile")
    return LocalApplication(
        store,
        ArchetypeCatalogStore(store, config.roles),
        config.classification,
        coordinator=coordinator,
        assigned_build_changed=callback,
    )


def test_manual_and_automatic_refresh_build_the_same_analysis_generation(tmp_path):
    backend = HoldingBackend()
    coordinator = AnalysisCoordinator(backend=backend, monitor=False)
    app = make_application(tmp_path, coordinator=coordinator)
    save = tmp_path / "same-input.sav"
    save.write_bytes(b"deterministic synthetic save bytes")

    selected = app.select_followed_save(
        str(save), expected_revision=0, auto_refresh=False
    )
    manual = app.request_analysis(
        expected_preferences_revision=selected["revision"]
    )
    manual_desired = coordinator.job(manual["id"]).desired

    coordinator.invalidate_desired()
    selected = app.select_followed_save(
        str(save), expected_revision=selected["revision"], auto_refresh=True
    )
    watcher = app.start_save_watcher(monitor=False)
    watcher.poll()
    watcher.poll()
    automatic_desired = coordinator.job(coordinator.desired_job_id).desired

    assert automatic_desired.identity == manual_desired.identity
    assert automatic_desired.source_fingerprint == manual_desired.source_fingerprint
    assert (
        automatic_desired.configuration_fingerprints
        == manual_desired.configuration_fingerprints
    )
    assert automatic_desired.dependency_signatures == manual_desired.dependency_signatures
    app.close()


def test_failed_post_write_refresh_preserves_durable_player_intent(tmp_path):
    result = SimpleNamespace(
        campaign_identity=CampaignIdentity(25809, confidence="exact"),
        brother_identities={
            "human:1": BrotherIdentity(25809, 1234, confidence="exact")
        },
    )
    publication = SimpleNamespace(generation=7, job_id=11, result=result)

    class PublishedCoordinator:
        last_success = publication
        desired_job_id = 11

        def invalidate_desired(self):
            self.desired_job_id = None

        def shutdown(self):
            pass

    def fail_refresh(_change):
        raise RuntimeError("simulated refresh failure")

    app = make_application(
        tmp_path, coordinator=PublishedCoordinator(), callback=fail_refresh
    )
    mutation = app.mutate_assigned_build(
        "assign",
        {
            "campaign_identity": 25809,
            "native_entity_token": 1234,
            "build_identity": "reach_dps",
            "expected_revision": 0,
        },
    )
    persisted = app.assigned_builds.read(
        CampaignIdentity(25809, confidence="exact"),
        BrotherIdentity(25809, 1234, confidence="exact"),
    )

    assert mutation["invalidation"]["status"] == "failed"
    assert mutation["invalidation"]["errors"][0]["code"] == "intent_refresh_failed"
    assert persisted["revision"] == 1
    assert persisted["assignment"]["status"] == "current"
    assert persisted["assignment"]["build_identity"] == "reach_dps"
    app.close()
