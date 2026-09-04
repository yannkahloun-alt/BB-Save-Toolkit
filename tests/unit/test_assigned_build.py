from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from bbtool.app.assigned_build import AssignedBuildStore, AssignedBuildValidationError
from bbtool.app.archetype_catalog import ArchetypeCatalogStore
from bbtool.app.config import load_config
from bbtool.app.local_application import LocalApplication
from bbtool.app.user_state import (
    AssignedBuildCampaign,
    AssignedBuildRecord,
    AssignedBuildState,
    CorruptStateError,
    StateConflictError,
    UserStateStore,
)
from bbtool.models import BrotherIdentity, CampaignIdentity


ROOT = Path(__file__).resolve().parents[2]


def roles():
    return load_config(
        ROOT / "config/archetypes.json", ROOT / "config/classification.json"
    ).roles


def identities(campaign=25809, token=1234):
    return (
        CampaignIdentity(campaign, confidence="exact"),
        BrotherIdentity(campaign, token, confidence="exact"),
    )


def service(tmp_path, base=None):
    state = UserStateStore(tmp_path / "profile")
    return AssignedBuildStore(state, ArchetypeCatalogStore(state, base or roles()))


def test_assignment_survives_restart_and_rename_is_cosmetic(tmp_path):
    campaign, brother = identities()
    original = roles()
    assigned = service(tmp_path, original).assign(
        campaign, brother, "reach_dps", expected_revision=0
    )
    assert assigned["revision"] == 1
    assert assigned["assignment"]["status"] == "current"

    renamed = deepcopy(original)
    next(role for role in renamed if role["id"] == "reach_dps")["name"] = "Polearm"
    restarted = service(tmp_path, renamed).read(campaign, brother)
    assert restarted["assignment"]["status"] == "current"
    assert restarted["assignment"]["display_name"] == "Polearm"
    assert restarted["assignment"]["assigned_definition_hash"] == assigned["assignment"]["assigned_definition_hash"]


def test_redefinition_is_visible_until_explicit_reassignment_acknowledges_hash(tmp_path):
    campaign, brother = identities()
    original = roles()
    first = service(tmp_path, original).assign(campaign, brother, "reach_dps", expected_revision=0)
    changed = deepcopy(original)
    next(role for role in changed if role["id"] == "reach_dps")["stats"]["MAtk"]["target"] += 1
    updated = service(tmp_path, changed)
    unresolved = updated.read(campaign, brother)
    assert unresolved["assignment"]["status"] == "definition_changed"
    assert unresolved["assignment"]["assigned_definition_hash"] != unresolved["assignment"]["current_definition_hash"]

    acknowledged = updated.acknowledge(
        campaign, brother, "reach_dps", expected_revision=first["revision"]
    )
    assert acknowledged["assignment"]["status"] == "current"
    assert acknowledged["assignment"]["assigned_definition_hash"] == unresolved["assignment"]["current_definition_hash"]


def test_removed_build_is_preserved_as_missing_and_remains_clearable(tmp_path):
    campaign, brother = identities()
    original = roles()
    first = service(tmp_path, original).assign(campaign, brother, "reach_dps", expected_revision=0)
    removed = [role for role in original if role["id"] != "reach_dps"]
    restarted = service(tmp_path, removed)
    assert restarted.read(campaign, brother)["assignment"]["status"] == "missing"
    cleared = restarted.clear(campaign, brother, expected_revision=first["revision"])
    assert cleared["assignment"]["status"] == "unassigned"


def test_retired_custom_build_is_preserved_as_deprecated(tmp_path):
    campaign, brother = identities()
    state = UserStateStore(tmp_path / "profile")
    catalog = ArchetypeCatalogStore(state, roles(), id_factory=lambda: "custom_one")
    definition = deepcopy(roles()[0])
    definition.pop("id")
    for stat in definition["stats"].values():
        stat.pop("fit", None)
        stat.pop("projected_curve", None)
    definition["name"] = "Mine"
    created = catalog.create_custom(definition, expected_revision=0)
    assigned = AssignedBuildStore(state, catalog).assign(
        campaign, brother, "custom_one", expected_revision=0
    )
    catalog.delete_custom("custom_one", expected_revision=created.state.revision)
    assert AssignedBuildStore(state, catalog).read(campaign, brother)["assignment"]["status"] == "deprecated"
    assert assigned["assignment"]["status"] == "current"


def test_stale_writes_and_nonexact_or_cross_campaign_identity_fail(tmp_path):
    campaign, brother = identities()
    assigned = service(tmp_path)
    assigned.assign(campaign, brother, "reach_dps", expected_revision=0)
    with pytest.raises(StateConflictError):
        assigned.change(campaign, brother, "banner", expected_revision=0)
    with pytest.raises(AssignedBuildValidationError, match="CampaignIdentity must be exact"):
        assigned.read(CampaignIdentity(None, confidence="unavailable"), brother)
    with pytest.raises(AssignedBuildValidationError, match="BrotherIdentity must be exact"):
        assigned.read(
            campaign,
            BrotherIdentity(25809, None, confidence="invalid", reason="ambiguous"),
        )
    with pytest.raises(AssignedBuildValidationError, match="outside"):
        assigned.read(campaign, BrotherIdentity(99, 1234, confidence="exact"))


def test_clear_absent_is_idempotent_and_emits_no_change(tmp_path):
    campaign, brother = identities()
    result = service(tmp_path).clear(campaign, brother, expected_revision=0)
    assert result == {
        "revision": 0,
        "assignment": {
            "status": "unassigned", "build_identity": None,
            "assigned_definition_hash": None, "current_definition_hash": None,
            "display_name": None,
        },
        "change": None,
    }


@pytest.mark.parametrize(
    "brother_values",
    [
        ("campaign:25809/entity:001234",),
        ("campaign:25809/entity:1234", "campaign:25809/entity:001234"),
    ],
)
def test_noncanonical_brother_token_aliases_are_rejected(tmp_path, brother_values):
    state = UserStateStore(tmp_path / "profile")
    records = tuple(
        AssignedBuildRecord(
            brother_identity=value,
            build_identity="reach_dps",
            assigned_definition_hash="sha256:" + "0" * 64,
        )
        for value in brother_values
    )
    with pytest.raises(CorruptStateError, match="brother_identity is malformed"):
        state.save(
            "assigned_builds",
            AssignedBuildState(
                campaigns=(AssignedBuildCampaign(25809, records),)
            ),
            expected_revision=0,
        )
    assert not state.path_for("assigned_builds").exists()


@pytest.mark.parametrize("operation", ["clear", "clear_campaign"])
def test_noop_clear_rechecks_revision_atomically_after_stale_load(
    tmp_path, monkeypatch, operation
):
    campaign, brother = identities()
    assigned = service(tmp_path)
    assigned.assign(campaign, brother, "reach_dps", expected_revision=0)
    real_load = assigned.store.load
    calls = 0

    def stale_once(feature, *, migrate=True):
        nonlocal calls
        if feature == "assigned_builds" and calls == 0:
            calls += 1
            return AssignedBuildState()
        return real_load(feature, migrate=migrate)

    monkeypatch.setattr(assigned.store, "load", stale_once)
    with pytest.raises(StateConflictError, match="expected 0, found 1"):
        if operation == "clear":
            assigned.clear(campaign, identities(token=9999)[1], expected_revision=0)
        else:
            assigned.clear_campaign(identities(campaign=9999)[0], expected_revision=0)


def test_change_metadata_is_normalized_and_analysis_inputs_are_untouched(tmp_path):
    campaign, brother = identities()
    source_roles = roles()
    before = deepcopy(source_roles)
    result = service(tmp_path, source_roles).assign(
        campaign, brother, "reach_dps", expected_revision=0
    )
    change = result["change"]
    assert change["input_kind"] == "assigned_build"
    assert change["campaign_identity"] == 25809
    assert change["brother_identity"] == "campaign:25809/entity:1234"
    assert change["authoritative_revision"] == 1
    assert change["old"]["status"] == "unassigned"
    assert change["new"]["status"] == "current"
    assert source_roles == before


def test_downstream_notification_failure_does_not_roll_back_commit(tmp_path):
    campaign, brother = identities()
    config = load_config(
        ROOT / "config/archetypes.json", ROOT / "config/classification.json"
    )
    state = UserStateStore(tmp_path / "profile")

    def fail(_change):
        raise RuntimeError("refresh failed")

    application = LocalApplication(
        state, ArchetypeCatalogStore(state, config.roles), config.classification,
        assigned_build_changed=fail,
    )
    application.coordinator._last_success = SimpleNamespace(
        job_id=1,
        generation=1,
        result=SimpleNamespace(
            campaign_identity=campaign,
            brother_identities={"human:1": brother},
        ),
    )
    application.coordinator._desired_id = 1
    result = application.mutate_assigned_build("assign", {
        "campaign_identity": 25809, "native_entity_token": 1234,
        "build_identity": "reach_dps", "expected_revision": 0,
    })
    assert result["revision"] == 1
    assert result["invalidation"]["status"] == "failed"
    assert application.assigned_build(25809, 1234)["assignment"]["status"] == "current"
    application.close()
