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
HEADERS = {
    "Host": HOST,
    "Origin": ORIGIN,
    "X-BBST-Session": "capability",
    "Content-Type": "application/json",
}


def _decode(response):
    return json.loads(response.body)


def test_multi_conflict_recovery_progresses_one_revision_at_a_time_and_exports(tmp_path):
    config = load_config(
        ROOT / "config" / "archetypes.json",
        ROOT / "config" / "classification.json",
    )
    state_root = tmp_path / "profile"
    store = UserStateStore(state_root)
    old_catalog = ArchetypeCatalogStore(store, config.roles)

    first = old_catalog.set_override(
        "nimble_frontline_dps",
        {"name": "Persisted Nimble Frontline Override"},
        expected_revision=0,
    )
    second = old_catalog.set_override(
        "reach_dps",
        {"name": "Persisted Reach Override"},
        expected_revision=first.state.revision,
    )
    assert second.state.revision == 2
    persisted_entries = list(store.load("archetypes").entries)

    changed_roles = json.loads(json.dumps(config.roles))
    for identity in ("nimble_frontline_dps", "reach_dps"):
        changed = next(role for role in changed_roles if role["id"] == identity)
        changed["name"] = f"{changed['name']} · shipped v2"
        changed["stats"]["MAtk"]["target"] += 1

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
    assert recovery["revision"] == 2
    assert [entry["id"] for entry in recovery["catalog_conflict"]["entries"]] == [
        "nimble_frontline_dps",
        "reach_dps",
    ]

    exported = api.handle("GET", "/api/v1/archetypes/export", {"Host": HOST})
    assert exported.status == 200
    export_document = json.loads(_decode(exported)["data"]["document"])
    assert export_document == {
        "schema": "bbtool.user-archetypes-export.v1",
        "entries": persisted_entries,
    }

    stale = api.handle(
        "POST",
        "/api/v1/archetypes/reset-base",
        HEADERS,
        json.dumps({"id": "nimble_frontline_dps", "expected_revision": 1}).encode(),
    )
    assert stale.status == 409
    assert restarted_store.load("archetypes").revision == 2

    first_reset = api.handle(
        "POST",
        "/api/v1/archetypes/reset-base",
        HEADERS,
        json.dumps({"id": "nimble_frontline_dps", "expected_revision": 2}).encode(),
    )
    assert first_reset.status == 200
    remaining = _decode(first_reset)["data"]
    assert remaining["revision"] == 3
    assert remaining["roles"] == []
    assert [entry["id"] for entry in remaining["catalog_conflict"]["entries"]] == [
        "reach_dps"
    ]
    assert not any(
        entry.get("id") == "nimble_frontline_dps"
        and entry.get("kind") in {"override", "disabled"}
        for entry in remaining["user_entries"]
    )

    second_reset = api.handle(
        "POST",
        "/api/v1/archetypes/reset-base",
        HEADERS,
        json.dumps({"id": "reach_dps", "expected_revision": 3}).encode(),
    )
    assert second_reset.status == 200
    recovered = _decode(second_reset)["data"]
    assert recovered["revision"] == 4
    assert "catalog_conflict" not in recovered
    assert {role["id"] for role in recovered["roles"]} >= {
        "nimble_frontline_dps",
        "reach_dps",
    }
    assert not any(
        entry.get("id") in {"nimble_frontline_dps", "reach_dps"}
        and entry.get("kind") in {"override", "disabled"}
        for entry in recovered["user_entries"]
    )
