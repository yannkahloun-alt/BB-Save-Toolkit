import json
from pathlib import Path
import threading
from types import SimpleNamespace

from bbtool.app.analysis_coordinator import AnalysisCoordinator
from bbtool.app.app_server import (
    LOOPBACK_HOST,
    MAX_REQUEST_BYTES,
    LocalApplicationApi,
    serve_local_application,
)
from bbtool.app.archetype_catalog import ArchetypeCatalogStore
from bbtool.app.config import load_config
from bbtool.app.local_application import LocalApplication
from bbtool.app.user_state import UserStateStore
from bbtool.models import BrotherIdentity, CampaignIdentity


ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "http://127.0.0.1:48123"
HOST = "127.0.0.1:48123"


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


def make_application(tmp_path, *, coordinator=None, read_save=None):
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
        read_save=read_save,
    )


def decode(response):
    return json.loads(response.body)


def headers(token="capability", *, origin=ORIGIN, host=HOST, content_type="application/json"):
    return {
        "Host": host,
        "Origin": origin,
        "X-BBST-Session": token,
        "Content-Type": content_type,
    }


def post(api, path, payload, request_headers=None):
    return api.handle(
        "POST",
        path,
        request_headers or headers(),
        json.dumps(payload).encode(),
    )


def test_health_session_and_static_shell_are_local_and_self_contained(tmp_path):
    api = LocalApplicationApi(make_application(tmp_path), origin=ORIGIN, token="capability")

    health = decode(api.handle("GET", "/api/v1/health", {"Host": HOST}))
    assert health["data"]["status"] == "ok"
    assert health["data"]["bind"] == LOOPBACK_HOST
    assert health["data"]["api_schema"] == "bbtool.local-api.v1"
    assert decode(api.handle("GET", "/api/v1/session", {"Host": HOST}))["data"] == {
        "token": "capability"
    }
    page = api.handle("GET", "/", {"Host": HOST}).body.decode()
    script = api.handle("GET", "/app.js", {"Host": HOST}).body.decode()
    assert "https://" not in page + script
    assert "http://" not in page + script


def test_hostile_cross_origin_and_missing_capability_cannot_mutate(tmp_path):
    app = make_application(tmp_path)
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    payload = {"expected_revision": 0}

    cross_origin = post(
        api, "/api/v1/followed-save/forget", payload,
        headers(origin="https://hostile.example"),
    )
    missing_token = post(
        api, "/api/v1/followed-save/forget", payload,
        headers(token=""),
    )
    form_post = post(
        api, "/api/v1/followed-save/forget", payload,
        headers(content_type="application/x-www-form-urlencoded"),
    )
    rebinding = api.handle("GET", "/api/v1/session", {"Host": "hostile.example"})

    assert (cross_origin.status, missing_token.status, form_post.status, rebinding.status) == (
        403, 403, 415, 403
    )
    assert app.store.load("preferences").revision == 0


def test_request_limits_and_exact_typed_shapes_are_enforced(tmp_path):
    api = LocalApplicationApi(make_application(tmp_path), origin=ORIGIN, token="capability")
    too_large = api.handle(
        "POST", "/api/v1/followed-save/forget", headers(), b"x" * (MAX_REQUEST_BYTES + 1)
    )
    generic = post(api, "/api/v1/followed-save/forget", {
        "expected_revision": 0, "state": {"arbitrary": "write"}
    })
    unknown = post(api, "/api/v1/archetypes/write-json", {"expected_revision": 0})
    assert too_large.status == 413
    assert generic.status == 422
    assert decode(generic)["error"]["details"]["unexpected"] == ["state"]
    assert unknown.status == 422


def test_assigned_build_typed_mutation_read_and_conflict(tmp_path):
    app = make_application(tmp_path)
    app.coordinator._last_success = SimpleNamespace(
        job_id=1,
        generation=1,
        result=SimpleNamespace(
            campaign_identity=CampaignIdentity(25809, confidence="exact"),
            brother_identities={
                "human:1": BrotherIdentity(25809, 1234, confidence="exact")
            },
        ),
    )
    app.coordinator._desired_id = 1
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    payload = {
        "campaign_identity": 25809,
        "native_entity_token": 1234,
        "build_identity": "reach_dps",
        "expected_revision": 0,
    }
    assigned = post(api, "/api/v1/assigned-builds/assign", payload)
    assert assigned.status == 200
    data = decode(assigned)["data"]
    assert data["revision"] == 1
    assert data["assignment"]["status"] == "current"
    assert data["invalidation"]["changes"][0]["input_kind"] == "assigned_build"

    read = api.handle("GET", "/api/v1/assigned-builds/25809/1234", {"Host": HOST})
    assert decode(read)["data"]["assignment"] == data["assignment"]
    conflict = post(api, "/api/v1/assigned-builds/clear", {
        "campaign_identity": 25809,
        "native_entity_token": 1234,
        "expected_revision": 0,
    })
    assert conflict.status == 409
    assert decode(conflict)["error"]["code"] == "state_revision_conflict"


def test_stale_publication_identity_cannot_authorize_assignment(tmp_path):
    app = make_application(tmp_path)
    app.coordinator._last_success = SimpleNamespace(
        job_id=1,
        generation=4,
        result=SimpleNamespace(
            campaign_identity=CampaignIdentity(25809, confidence="exact"),
            brother_identities={
                "human:1": BrotherIdentity(25809, 1234, confidence="exact")
            },
        ),
    )
    app.coordinator._desired_id = 1
    app._invalidated_generation = 4
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    response = post(api, "/api/v1/assigned-builds/assign", {
        "campaign_identity": 25809,
        "native_entity_token": 1234,
        "build_identity": "reach_dps",
        "expected_revision": 0,
    })
    assert response.status == 422
    assert decode(response)["error"]["code"] == "identity_unavailable"
    assert app.store.load("assigned_builds").revision == 0


def test_followed_save_selection_is_revision_checked_and_bounded(tmp_path):
    app = make_application(tmp_path)
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"save")

    selected = post(api, "/api/v1/followed-save/select", {
        "path": str(save), "expected_revision": 0, "auto_refresh": False
    })
    assert selected.status == 200
    assert decode(selected)["data"]["revision"] == 1
    assert decode(selected)["data"]["available"] is True

    conflict = post(api, "/api/v1/followed-save/forget", {"expected_revision": 0})
    assert conflict.status == 409
    assert decode(conflict)["error"]["code"] == "state_revision_conflict"

    invalid = post(api, "/api/v1/followed-save/select", {
        "path": str(tmp_path / "not-a-save.json"), "expected_revision": 1
    })
    assert invalid.status == 422
    assert app.store.load("preferences").selected_save_path == str(save.resolve())


def test_archetype_mutation_delegates_validation_and_returns_revision_freshness(tmp_path):
    app = make_application(tmp_path)
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    response = post(api, "/api/v1/archetypes/set-override", {
        "id": "reach_dps",
        "patch": {"name": "Polearm"},
        "expected_revision": 0,
    })
    data = decode(response)["data"]
    assert response.status == 200
    assert data["revision"] == 1
    assert data["freshness"] == {
        "status": "stale",
        "reason": "effective_archetypes_changed",
        "recompute": "request_analysis",
    }
    assert next(role for role in data["roles"] if role["id"] == "reach_dps")["name"] == "Polearm"
    assert "reach_dps" in data["definition_hashes"]

    invalid = post(api, "/api/v1/archetypes/set-override", {
        "id": "reach_dps", "patch": {"stats": {"MAtk": {"weight": -1}}},
        "expected_revision": 1,
    })
    assert invalid.status == 422
    assert decode(invalid)["error"]["details"]
    assert app.catalog.load().state.revision == 1


def test_analysis_request_only_submits_to_background_coordinator(tmp_path):
    backend = HoldingBackend()
    coordinator = AnalysisCoordinator(backend=backend, monitor=False)
    reads = []
    app = make_application(
        tmp_path,
        coordinator=coordinator,
        read_save=lambda path: reads.append(path) or b"immutable save bytes",
    )
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"unused")
    post(api, "/api/v1/followed-save/select", {
        "path": str(save), "expected_revision": 0
    })

    response = post(api, "/api/v1/analysis/jobs", {
        "expected_preferences_revision": 1
    })
    data = decode(response)["data"]
    assert response.status == 202
    assert data["status"] == "running"
    assert data["source_fingerprint"].startswith("sha256:")
    assert set(data["configuration_fingerprints"]) == {"archetypes", "classification"}
    assert reads == [save.resolve()]
    assert len(backend.starts) == 1
    assert backend.starts[0][1].source.content == b"immutable save bytes"


def test_local_analysis_request_uses_authoritative_assigned_build_resolver(tmp_path):
    backend = HoldingBackend()
    app = make_application(
        tmp_path,
        coordinator=AnalysisCoordinator(backend=backend, monitor=False),
        read_save=lambda _path: b"save",
    )
    campaign = CampaignIdentity(25809, confidence="exact")
    brother = BrotherIdentity(25809, 1234, confidence="exact")
    app.assigned_builds.assign(
        campaign, brother, "reach_dps", expected_revision=0
    )
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"unused")
    app.select_followed_save(str(save), expected_revision=0)
    app.request_analysis(expected_preferences_revision=1)

    request = backend.starts[0][1]
    resolved = request.assigned_build_resolver(campaign)
    assert resolved[brother.value]["status"] == "current"
    assert resolved[brother.value]["build_identity"] == "reach_dps"


def test_failed_job_is_structured_and_service_remains_healthy(tmp_path):
    class FailingBackend:
        def start(self, job_id, request):
            raise RuntimeError("worker unavailable")

    app = make_application(
        tmp_path,
        coordinator=AnalysisCoordinator(backend=FailingBackend(), monitor=False),
        read_save=lambda _path: b"save",
    )
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"unused")
    post(api, "/api/v1/followed-save/select", {"path": str(save), "expected_revision": 0})
    requested = post(api, "/api/v1/analysis/jobs", {"expected_preferences_revision": 1})
    job = decode(requested)["data"]
    assert job["status"] == "failed"
    assert job["error"]["code"] == "worker_start_failed"
    assert api.handle("GET", "/api/v1/health", {"Host": HOST}).status == 200
    last = decode(api.handle("GET", "/api/v1/analysis/result", {"Host": HOST}))["data"]
    assert last["available"] is False
    assert last["freshness"]["status"] == "unavailable"


def test_published_result_exposes_identity_and_persists_last_success(tmp_path):
    publication = SimpleNamespace(
        generation=3,
        job_id=7,
        source_fingerprint="sha256:source",
        configuration_fingerprints={"archetypes": "sha256:a", "classification": "sha256:c"},
        artifact_signatures={"advisor": "sha256:advisor"},
        result=SimpleNamespace(warnings=[{"code": "warning"}], public_data={"fits": []}),
    )

    class PublishedCoordinator:
        last_success = publication
        desired_job_id = 7

        def shutdown(self):
            pass

        def invalidate_desired(self):
            pass

    app = make_application(tmp_path, coordinator=PublishedCoordinator())
    result = app.last_result()
    durable = app.store.load("last_success")

    assert result["available"] is True
    assert result["freshness"]["status"] == "current"
    assert result["freshness"]["represented_source_fingerprint"] == "sha256:source"
    assert result["freshness"]["represented_configuration_fingerprints"] == {
        "archetypes": "sha256:a", "classification": "sha256:c"
    }
    assert result["freshness"]["artifact_signatures"] == {"advisor": "sha256:advisor"}
    assert durable.source_fingerprint == "sha256:source"
    assert durable.config_fingerprint.startswith("sha256:")
    assert durable.completed_at is not None


def test_successful_mutation_marks_existing_publication_stale_on_later_reads(tmp_path):
    publication = SimpleNamespace(
        generation=3,
        job_id=7,
        source_fingerprint="sha256:source",
        configuration_fingerprints={"archetypes": "sha256:a", "classification": "sha256:c"},
        artifact_signatures={},
        result=SimpleNamespace(warnings=[], public_data={"fits": []}),
    )

    class PublishedCoordinator:
        last_success = publication
        desired_job_id = 7

        def shutdown(self):
            pass

        def invalidate_desired(self):
            pass

    app = make_application(tmp_path, coordinator=PublishedCoordinator())
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    mutation = post(api, "/api/v1/archetypes/set-override", {
        "id": "reach_dps", "patch": {"name": "Polearm"}, "expected_revision": 0,
    })
    later_result = decode(
        api.handle("GET", "/api/v1/analysis/result", {"Host": HOST})
    )["data"]

    assert decode(mutation)["data"]["freshness"]["status"] == "stale"
    assert later_result["available"] is True
    assert later_result["freshness"]["status"] == "stale"
    assert later_result["freshness"]["reason"] == "effective_archetypes_changed"


def test_mutation_cancels_in_flight_pre_mutation_analysis(tmp_path):
    backend = HoldingBackend()
    coordinator = AnalysisCoordinator(backend=backend, monitor=False)
    app = make_application(
        tmp_path, coordinator=coordinator, read_save=lambda _path: b"save"
    )
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"unused")
    post(api, "/api/v1/followed-save/select", {"path": str(save), "expected_revision": 0})
    submitted = post(api, "/api/v1/analysis/jobs", {"expected_preferences_revision": 1})
    job_id = decode(submitted)["data"]["id"]

    mutation = post(api, "/api/v1/archetypes/set-override", {
        "id": "reach_dps", "patch": {"name": "Polearm"}, "expected_revision": 0,
    })

    assert mutation.status == 200
    assert coordinator.job(job_id).status.value == "cancelled"
    assert coordinator.desired_job_id is None
    assert coordinator.last_success is None


def test_snapshot_submit_and_mutation_invalidation_are_serialized(tmp_path):
    backend = HoldingBackend()
    coordinator = AnalysisCoordinator(backend=backend, monitor=False)
    read_started = threading.Event()
    release_read = threading.Event()
    mutation_finished = threading.Event()

    def blocking_read(_path):
        read_started.set()
        assert release_read.wait(2)
        return b"old snapshot"

    app = make_application(tmp_path, coordinator=coordinator, read_save=blocking_read)
    save = tmp_path / "campaign.sav"
    save.write_bytes(b"unused")
    app.select_followed_save(str(save), expected_revision=0)

    analysis_thread = threading.Thread(
        target=lambda: app.request_analysis(expected_preferences_revision=1)
    )
    mutation_thread = threading.Thread(
        target=lambda: (
            app.mutate_archetypes(
                "set_override",
                {"id": "reach_dps", "patch": {"name": "Polearm"}, "expected_revision": 0},
            ),
            mutation_finished.set(),
        )
    )
    analysis_thread.start()
    assert read_started.wait(2)
    mutation_thread.start()
    assert not mutation_finished.wait(0.05)
    release_read.set()
    analysis_thread.join(2)
    mutation_thread.join(2)

    assert mutation_finished.is_set()
    assert coordinator.job(1).status.value == "cancelled"
    assert coordinator.desired_job_id is None


def test_result_read_cannot_observe_commit_before_invalidation(tmp_path):
    publication = SimpleNamespace(
        generation=3,
        job_id=7,
        source_fingerprint="sha256:source",
        configuration_fingerprints={"archetypes": "sha256:a", "classification": "sha256:c"},
        artifact_signatures={},
        result=SimpleNamespace(warnings=[], public_data={"fits": []}),
    )

    class PublishedCoordinator:
        last_success = publication
        desired_job_id = 7

        def shutdown(self):
            pass

        def invalidate_desired(self):
            pass

    app = make_application(tmp_path, coordinator=PublishedCoordinator())
    committed = threading.Event()
    release_mutation = threading.Event()
    read_finished = threading.Event()
    original = app.catalog.set_override

    def pausing_override(*args, **kwargs):
        result = original(*args, **kwargs)
        committed.set()
        assert release_mutation.wait(2)
        return result

    app.catalog.set_override = pausing_override
    mutation_thread = threading.Thread(target=lambda: app.mutate_archetypes(
        "set_override",
        {"id": "reach_dps", "patch": {"name": "Polearm"}, "expected_revision": 0},
    ))
    observed = []
    read_thread = threading.Thread(
        target=lambda: (observed.append(app.last_result()), read_finished.set())
    )

    mutation_thread.start()
    assert committed.wait(2)
    read_thread.start()
    assert not read_finished.wait(0.05)
    release_mutation.set()
    mutation_thread.join(2)
    read_thread.join(2)

    assert read_finished.is_set()
    assert observed[0]["freshness"]["status"] == "stale"
    assert observed[0]["freshness"]["reason"] == "effective_archetypes_changed"


def test_server_bind_is_fixed_to_ipv4_loopback(monkeypatch, tmp_path):
    observed = {}

    class Server:
        def __init__(self, address, handler):
            observed["address"] = address
            self.server_address = (address[0], 45678)
            self.RequestHandlerClass = handler

        def serve_forever(self):
            return None

        def server_close(self):
            observed["closed"] = True

    monkeypatch.setattr("bbtool.app.app_server.ThreadingHTTPServer", Server)
    serve_local_application(port=0, state_root=tmp_path / "profile")

    assert observed == {"address": ("127.0.0.1", 0), "closed": True}
