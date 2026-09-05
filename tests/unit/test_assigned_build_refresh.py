from pathlib import Path
from types import SimpleNamespace

import pytest

from bbtool.app.analysis_coordinator import AnalysisCoordinator
from bbtool.app.archetype_catalog import ArchetypeCatalogStore
from bbtool.app.config import load_config
from bbtool.app.local_application import LocalApplication
from bbtool.app.user_state import UserStateStore
from bbtool.models import BrotherIdentity, CampaignIdentity

pytestmark = pytest.mark.unit

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


def test_assigned_build_change_invalidates_old_desired_generation_and_refreshes(tmp_path):
    cfg = load_config(
        ROOT / "config" / "archetypes.json",
        ROOT / "config" / "classification.json",
    )
    backend = HoldingBackend()
    coordinator = AnalysisCoordinator(backend=backend, monitor=False)
    store = UserStateStore(tmp_path / "profile")
    app = LocalApplication(
        store,
        ArchetypeCatalogStore(store, cfg.roles),
        cfg.classification,
        coordinator=coordinator,
        read_save=lambda _path: b"save",
    )
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"unused")
    app.select_followed_save(str(save), expected_revision=0)

    campaign = CampaignIdentity(25809, confidence="exact")
    brother = BrotherIdentity(25809, 1234, confidence="exact")
    coordinator._last_success = SimpleNamespace(
        job_id=41,
        generation=7,
        result=SimpleNamespace(
            campaign_identity=campaign,
            brother_identities={"human:1": brother},
        ),
    )
    coordinator._desired_id = 41
    app._invalidated_generation = None

    mutation = app.mutate_assigned_build(
        "assign",
        {
            "campaign_identity": 25809,
            "native_entity_token": 1234,
            "build_identity": "reach_dps",
            "expected_revision": 0,
        },
    )

    assert mutation["assignment"]["status"] == "current"
    assert mutation["invalidation"]["affected_artifacts"] == [
        "level_advisor",
        "company_intended_coverage",
        "relevant_roster_need",
    ]
    assert coordinator.desired_job_id is None
    assert app._invalidated_generation == 7
    assert app._invalidation_reason == "assigned_build_changed"

    refreshed = app.request_analysis(expected_preferences_revision=1)

    assert refreshed["status"] == "running"
    assert coordinator.desired_job_id == refreshed["id"]
    assert len(backend.starts) == 1
    scheduled = backend.starts[0][1]
    resolved = scheduled.assigned_build_resolver(campaign)
    assert resolved[brother.value]["status"] == "current"
    assert resolved[brother.value]["build_identity"] == "reach_dps"
