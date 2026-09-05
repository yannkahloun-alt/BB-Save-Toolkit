import json
from pathlib import Path

from bbtool.app.app_server import LocalApplicationApi
from bbtool.app.archetype_catalog import ArchetypeCatalogStore
from bbtool.app.config import load_config
from bbtool.app.local_application import LocalApplication
from bbtool.app.user_state import UserStateStore


ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "http://127.0.0.1:48123"
HOST = "127.0.0.1:48123"


def _decode(response):
    return json.loads(response.body)


def test_restarted_api_exposes_revisioned_recovery_for_stale_shipped_override(tmp_path):
    config = load_config(
        ROOT / "config" / "archetypes.json",
        ROOT / "config" / "classification.json",
    )
    state_root = tmp_path / "profile"
    store = UserStateStore(state_root)

    old_catalog = ArchetypeCatalogStore(store, config.roles)
    persisted = old_catalog.set_override(
        "reach_dps",
        {"name": "Persisted Polearm Override"},
        expected_revision=0,
    )
    assert persisted.state.revision == 1
    stale_entry = next(
        entry
        for entry in store.load("archetypes").entries
        if entry.get("kind") == "override" and entry.get("id") == "reach_dps"
    )

    changed_roles = json.loads(json.dumps(config.roles))
    changed_base = next(role for role in changed_roles if role["id"] == "reach_dps")
    changed_base["name"] = f"{changed_base['name']} · shipped v2"
    changed_base["stats"]["MAtk"]["target"] += 1

    restarted_store = UserStateStore(state_root)
    application = LocalApplication(
        restarted_store,
        ArchetypeCatalogStore(restarted_store, changed_roles),
        config.classification,
    )
    api = LocalApplicationApi(application, origin=ORIGIN, token="capability")

    read = api.handle("GET", "/api/v1/archetypes", {"Host": HOST})
    assert read.status == 200
    recovery = _decode(read)["data"]
    assert recovery["revision"] == 1
    assert recovery["roles"] == []
    assert recovery["definition_hashes"] == {}
    assert recovery["provenance"] == {}
    assert recovery["user_entries"] == list(restarted_store.load("archetypes").entries)
    assert recovery["catalog_conflict"]["code"] == "shipped_user_entry_conflict"

    conflict = recovery["catalog_conflict"]["entries"]
    assert len(conflict) == 1
    assert conflict[0]["id"] == "reach_dps"
    assert conflict[0]["kind"] == "override"
    assert conflict[0]["reason"] == "base_definition_changed"
    assert conflict[0]["recovery_operation"] == "reset_base"
    assert conflict[0]["persisted_base_definition_hash"] == stale_entry["base_definition_hash"]
    assert conflict[0]["current_base_definition_hash"] != stale_entry["base_definition_hash"]

    reset = api.handle(
        "POST",
        "/api/v1/archetypes/reset-base",
        {
            "Host": HOST,
            "Origin": ORIGIN,
            "X-BBST-Session": "capability",
            "Content-Type": "application/json",
        },
        json.dumps({"id": "reach_dps", "expected_revision": recovery["revision"]}).encode(),
    )
    assert reset.status == 200
    recovered = _decode(reset)["data"]
    assert recovered["revision"] == 2
    assert "catalog_conflict" not in recovered
    assert next(role for role in recovered["roles"] if role["id"] == "reach_dps")["name"] == changed_base["name"]
    assert not any(
        entry.get("id") == "reach_dps" and entry.get("kind") in {"override", "disabled"}
        for entry in recovered["user_entries"]
    )
    assert application.catalog.load().state.revision == 2
