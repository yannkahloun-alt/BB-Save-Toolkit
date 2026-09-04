import json
from copy import deepcopy

import pytest

from bbtool.app.archetype_catalog import (
    ArchetypeCatalogStore,
    CatalogConflictError,
    CatalogValidationError,
    effective_catalog,
)
from bbtool.app.config import load_config
from bbtool.app.user_state import ArchetypeState, UserStateStore
from bbtool.build_identity import build_definition_hash
from bbtool.incremental.fingerprint import role_fingerprint


ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def base_roles():
    return load_config(ROOT / "config/archetypes.json", ROOT / "config/classification.json").roles


def service(tmp_path, roles=None, ids=None):
    values = iter(ids or ["custom_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"])
    return ArchetypeCatalogStore(
        UserStateStore(tmp_path / "profile"),
        roles or base_roles(),
        id_factory=lambda: next(values),
    )


def editable(role):
    value = deepcopy(role)
    for stat in value["stats"].values():
        stat.pop("fit", None)
        stat.pop("projected_curve", None)
    return value


def test_override_and_disable_survive_restart_without_changing_base(tmp_path):
    base_path = ROOT / "config/archetypes.json"
    base_bytes = base_path.read_bytes()
    roles = base_roles()
    before = deepcopy(roles)
    first = service(tmp_path, roles)
    changed = first.set_override("reach_dps", {"name": "Polearm"}, expected_revision=0)
    changed = first.set_disabled("archer", True, expected_revision=changed.state.revision)

    restarted = service(tmp_path, roles).load()
    assert restarted.roles == changed.roles
    assert next(role for role in restarted.roles if role["id"] == "reach_dps")["name"] == "Polearm"
    assert "archer" not in {role["id"] for role in restarted.roles}
    assert roles == before
    assert base_path.read_bytes() == base_bytes


def test_effective_roles_feed_analysis_and_only_changed_role_fingerprint_changes(tmp_path):
    roles = base_roles()
    catalog = service(tmp_path, roles)
    before = {role["id"]: role_fingerprint(role) for role in roles}
    changed = catalog.set_override("reach_dps", {"stats": {"MAtk": {"target": 93}}}, expected_revision=0)
    after = {role["id"]: role_fingerprint(role) for role in changed.roles}
    assert {identity for identity in before if before[identity] != after[identity]} == {"reach_dps"}
    config = catalog.analyzer_config({"invest_fit": 80})
    assert config.roles == list(changed.roles)
    assert config.classification == {"invest_fit": 80}


def test_base_upgrade_is_adopted_without_override_but_conflicts_with_stale_override(tmp_path):
    original = base_roles()
    catalog = service(tmp_path, original)
    saved = catalog.set_disabled("archer", True, expected_revision=0)
    upgraded = deepcopy(original)
    upgraded[0]["stats"]["MAtk"]["target"] += 1
    # Disabled intent remains meaningful across an unrelated base edit.
    assert "archer" not in {role["id"] for role in service(tmp_path, upgraded).load().roles}

    catalog.set_override("reach_dps", {"name": "Polearm"}, expected_revision=saved.state.revision)
    with pytest.raises(CatalogValidationError, match="base_definition_hash conflicts"):
        upgraded_catalog = service(tmp_path, upgraded)
        upgraded_catalog.load()
    reset = upgraded_catalog.reset_base("reach_dps", expected_revision=2)
    assert reset.roles[0]["stats"]["MAtk"]["target"] == 93


def test_reset_exposes_current_shipped_definition_and_enable_restores_base(tmp_path):
    catalog = service(tmp_path)
    current = catalog.set_override("reach_dps", {"name": "Polearm"}, expected_revision=0)
    current = catalog.set_disabled("reach_dps", True, expected_revision=current.state.revision)
    reset = catalog.reset_base("reach_dps", expected_revision=current.state.revision)
    role = next(role for role in reset.roles if role["id"] == "reach_dps")
    base = next(role for role in base_roles() if role["id"] == "reach_dps")
    assert role == base


def test_reset_override_preserves_disabled_choice_until_explicit_enable(tmp_path):
    catalog = service(tmp_path)
    current = catalog.set_override("reach_dps", {"name": "Polearm"}, expected_revision=0)
    current = catalog.set_disabled("reach_dps", True, expected_revision=current.state.revision)
    current = catalog.reset_override("reach_dps", expected_revision=current.state.revision)
    assert "reach_dps" not in {role["id"] for role in current.roles}
    enabled = catalog.set_disabled("reach_dps", False, expected_revision=current.state.revision)
    role = next(role for role in enabled.roles if role["id"] == "reach_dps")
    assert role["name"] == "Reach DPS"


def test_custom_duplicate_edit_delete_and_retired_id_protection(tmp_path):
    catalog = service(tmp_path, ids=["custom_aaaaaaaa", "custom_bbbbbbbb"])
    created = catalog.duplicate("reach_dps", expected_revision=0, name="My Reach")
    custom = next(role for role in created.roles if role["id"] == "custom_aaaaaaaa")
    assert build_definition_hash(custom) == build_definition_hash(
        next(role for role in created.roles if role["id"] == "reach_dps")
    )
    assert custom["name"] == "My Reach"

    definition = editable(custom)
    definition["name"] = "My Polearm"
    edited = catalog.edit_custom("custom_aaaaaaaa", definition, expected_revision=created.state.revision)
    assert next(role for role in edited.roles if role["id"] == "custom_aaaaaaaa")["name"] == "My Polearm"
    deleted = catalog.delete_custom("custom_aaaaaaaa", expected_revision=edited.state.revision)
    assert "custom_aaaaaaaa" not in {role["id"] for role in deleted.roles}
    with pytest.raises(CatalogValidationError, match="reuses a retired"):
        catalog.create_custom(definition, identity="custom_aaaaaaaa", expected_revision=deleted.state.revision)


def test_invalid_state_reports_field_paths_and_is_not_persisted(tmp_path):
    catalog = service(tmp_path)
    bad = editable(base_roles()[0])
    bad.pop("id")
    bad["stats"]["MAtk"]["weight"] = -1
    with pytest.raises(CatalogValidationError) as caught:
        catalog.create_custom(bad, identity="custom_valid", expected_revision=0)
    assert "entries[0].definition.stats.MAtk.weight must be >= 0" in caught.value.errors
    assert not catalog.store.path_for("archetypes").exists()


def test_override_rejects_engine_derived_state(tmp_path):
    catalog = service(tmp_path)
    with pytest.raises(CatalogValidationError, match="engine-derived"):
        catalog.set_override(
            "reach_dps",
            {"stats": {"MAtk": {"fit": False}}},
            expected_revision=0,
        )
    assert not catalog.store.path_for("archetypes").exists()


def test_custom_unknown_stat_fails_visibly_without_persistence(tmp_path):
    catalog = service(tmp_path)
    definition = editable(base_roles()[0])
    definition["name"] = "Invalid custom"
    definition["stats"]["Magic"] = {
        "target": 100,
        "baseline": 80,
        "weight": 10,
    }
    with pytest.raises(
        CatalogValidationError,
        match=r"entries\[0\]\.definition\.stats\.Magic is not a supported projection stat",
    ):
        catalog.create_custom(definition, identity="custom_invalid", expected_revision=0)
    assert not catalog.store.path_for("archetypes").exists()


def test_import_unknown_stat_fails_visibly_without_persistence(tmp_path):
    catalog = service(tmp_path)
    definition = editable(base_roles()[0])
    definition["id"] = "custom_imported"
    definition["name"] = "Invalid import"
    definition["stats"]["Magic"] = {
        "target": 100,
        "baseline": 80,
        "weight": 10,
    }
    payload = {
        "schema": "bbtool.user-archetypes-export.v1",
        "entries": [{"kind": "custom", "definition": definition}],
    }
    with pytest.raises(
        CatalogValidationError,
        match=r"entries\[0\]\.definition\.stats\.Magic is not a supported projection stat",
    ):
        catalog.import_json(json.dumps(payload), expected_revision=0)
    assert not catalog.store.path_for("archetypes").exists()


def test_export_replace_import_round_trip_all_user_owned_state(tmp_path):
    source = service(tmp_path / "source", ids=["custom_aaaaaaaa"])
    state = source.set_override("reach_dps", {"name": "Polearm"}, expected_revision=0)
    state = source.set_disabled("archer", True, expected_revision=state.state.revision)
    custom_def = editable(base_roles()[0])
    custom_def["name"] = "Mine"
    state = source.create_custom(custom_def, expected_revision=state.state.revision)
    exported = source.export_json()

    target = service(tmp_path / "target")
    imported = target.import_json(exported, expected_revision=0)
    assert imported.roles == state.roles
    assert json.loads(target.export_json()) == json.loads(exported)


def test_import_collision_is_explicit_and_never_remaps_identity(tmp_path):
    catalog = service(tmp_path, ids=["custom_aaaaaaaa"])
    definition = editable(base_roles()[0])
    definition["name"] = "Mine"
    state = catalog.create_custom(definition, expected_revision=0)
    payload = json.loads(catalog.export_json())
    payload["entries"][-1]["definition"]["name"] = "Different"
    with pytest.raises(CatalogConflictError, match="custom state for BuildIdentity custom_aaaaaaaa"):
        catalog.import_json(json.dumps(payload), expected_revision=state.state.revision, merge=True)
    assert catalog.load().roles == state.roles


def test_replace_import_cannot_resurrect_a_retired_custom_identity(tmp_path):
    catalog = service(tmp_path, ids=["custom_aaaaaaaa"])
    definition = editable(base_roles()[0])
    definition["name"] = "Mine"
    created = catalog.create_custom(definition, expected_revision=0)
    exported = catalog.export_json()
    deleted = catalog.delete_custom("custom_aaaaaaaa", expected_revision=created.state.revision)
    with pytest.raises(CatalogValidationError, match="reuses a retired"):
        catalog.import_json(exported, expected_revision=deleted.state.revision, merge=False)


def test_custom_id_cannot_collide_with_shipped_identity(tmp_path):
    catalog = service(tmp_path)
    definition = editable(base_roles()[0])
    definition["name"] = "Not Reach"
    with pytest.raises(CatalogValidationError, match="conflicts with a shipped BuildIdentity"):
        catalog.create_custom(definition, identity="reach_dps", expected_revision=0)


def test_explicit_legacy_import_assigns_authoritative_ids_once(tmp_path):
    catalog = service(tmp_path, ids=["custom_legacyone"])
    definition = editable(base_roles()[0])
    definition.pop("id")
    definition["name"] = "Imported legacy"
    imported = catalog.import_json(
        json.dumps({"schema": "bb-archetypes-v0.9", "roles": [definition]}),
        expected_revision=0,
    )
    assert imported.roles[-1]["id"] == "custom_legacyone"
    assert service(tmp_path).load().roles[-1]["id"] == "custom_legacyone"


def test_invalid_retired_identity_fails_with_field_path():
    state = ArchetypeState(entries=({"kind": "retired", "id": "Not Valid"},))
    with pytest.raises(CatalogValidationError) as caught:
        effective_catalog(base_roles(), state)
    assert any(error.startswith("entries[0].id:") for error in caught.value.errors)


def test_base_upgrade_cannot_reuse_retired_custom_identity(tmp_path):
    catalog = service(tmp_path, ids=["custom_aaaaaaaa"])
    definition = editable(base_roles()[0])
    definition["name"] = "Mine"
    created = catalog.create_custom(definition, expected_revision=0)
    catalog.delete_custom("custom_aaaaaaaa", expected_revision=created.state.revision)

    upgraded = deepcopy(base_roles())
    reused = editable(upgraded[0])
    reused["id"] = "custom_aaaaaaaa"
    reused["name"] = "New shipped concept"
    upgraded.append(reused)
    with pytest.raises(CatalogValidationError, match="conflicts with a shipped BuildIdentity"):
        service(tmp_path, upgraded).load()


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"kind": "custom"}, "entries[0].definition must be an object"),
        (
            {"kind": "custom", "definition": {}},
            "entries[0].definition.id is required",
        ),
    ],
)
def test_missing_custom_definition_or_id_has_precise_path(entry, message):
    state = ArchetypeState(entries=(entry,))
    with pytest.raises(CatalogValidationError, match=message.replace("[", r"\[")):
        effective_catalog(base_roles(), state)
