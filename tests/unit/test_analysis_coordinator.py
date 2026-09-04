from types import SimpleNamespace

from bbtool.app.analysis_coordinator import (
    AnalysisCoordinator,
    DesiredAnalysis,
    JobStatus,
    ProcessWorkerBackend,
)
from bbtool.app.analysis_service import (
    AnalysisServiceOptions,
    AnalysisServiceRequest,
    CompatibleCacheContext,
    ProgressEvent,
    SaveSource,
)


def desired(label, *, artifact="intrinsic:v1"):
    return DesiredAnalysis(
        AnalysisServiceRequest(
            source=SaveSource(label.encode(), f"{label}.sav"),
            roles=[{"id": "role", "name": "Role", "stats": {}}],
            classification={"label": label},
        ),
        {"intrinsic": artifact},
    )


def result_for(item):
    return SimpleNamespace(
        source_fingerprint=item.source_fingerprint,
        configuration_fingerprints=item.configuration_fingerprints,
    )


class Handle:
    def __init__(self):
        self.pending = []
        self.alive = True
        self.terminated = False

    def messages(self):
        messages, self.pending = self.pending, []
        return messages

    def send(self, kind, job_id, value):
        self.pending.append((kind, (job_id, value)))
        if kind in {"result", "error"}:
            self.alive = False

    def crash(self):
        self.alive = False

    def is_alive(self):
        return self.alive

    def terminate(self):
        self.terminated = True
        self.alive = False

    def join(self):
        pass


class Backend:
    def __init__(self):
        self.starts = []

    def start(self, job_id, request):
        handle = Handle()
        self.starts.append((job_id, request, handle))
        return handle

    @property
    def handle(self):
        return self.starts[-1][2]


class FailingBackend:
    def start(self, job_id, request):
        raise OSError("cannot spawn")


def coordinator(backend, **kwargs):
    return AnalysisCoordinator(backend=backend, monitor=False, **kwargs)


def test_rapid_changes_keep_one_active_and_only_newest_pending():
    backend = Backend()
    service = coordinator(backend)
    first, middle, newest = desired("first"), desired("middle"), desired("newest")

    first_id = service.submit(first)
    middle_id = service.submit(middle)
    newest_id = service.submit(newest)

    assert len(backend.starts) == 1
    assert service.job(first_id).status == JobStatus.SUPERSEDED
    assert service.job(middle_id).status == JobStatus.SUPERSEDED
    backend.handle.send("result", first_id, result_for(first))
    service.poll()
    assert [entry[0] for entry in backend.starts] == [first_id, newest_id]


def test_stale_completion_never_publishes_over_newer_desired_state():
    backend = Backend()
    service = coordinator(backend)
    old, new = desired("old"), desired("new")
    old_id = service.submit(old)
    new_id = service.submit(new)
    backend.handle.send("result", old_id, result_for(old))

    service.poll()

    assert service.last_success is None
    assert service.job(old_id).status == JobStatus.SUPERSEDED
    backend.handle.send("result", new_id, result_for(new))
    service.poll()
    assert service.last_success.job_id == new_id


def test_result_with_wrong_exact_fingerprint_is_rejected():
    backend = Backend()
    service = coordinator(backend)
    item = desired("wanted")
    job_id = service.submit(item)
    wrong = result_for(desired("other"))
    backend.handle.send("result", job_id, wrong)

    service.poll()

    assert service.last_success is None
    assert service.job(job_id).status == JobStatus.SUPERSEDED


def test_dependency_validity_callback_prevents_publication_after_external_change():
    backend = Backend()
    current = {"intrinsic": "intrinsic:v1"}
    service = coordinator(
        backend, signatures_are_current=lambda signatures: signatures == current
    )
    item = desired("save")
    job_id = service.submit(item)
    current["intrinsic"] = "intrinsic:v2"
    backend.handle.send("result", job_id, result_for(item))

    service.poll()

    assert service.last_success is None
    assert service.job(job_id).status == JobStatus.SUPERSEDED


def test_failure_preserves_last_success_and_only_retains_revalidated_artifacts():
    backend = Backend()
    retained_calls = []

    def retain(previous, signatures):
        retained_calls.append((previous.job_id, signatures))
        return {"intrinsic": previous.result}

    service = coordinator(backend, retain_valid_artifacts=retain)
    good = desired("good")
    good_id = service.submit(good)
    backend.handle.send("result", good_id, result_for(good))
    service.poll()
    failed = desired("failed", artifact="intrinsic:v1")
    failed_id = service.submit(failed)
    backend.handle.send("error", failed_id, {
        "code": "analysis_failed", "stage": "analysis", "message": "boom"
    })

    service.poll()

    assert service.last_success.job_id == good_id
    assert service.job(failed_id).status == JobStatus.FAILED
    assert service.retained_artifacts == {"intrinsic": service.last_success.result}
    assert retained_calls == [(good_id, failed.artifact_signatures)]


def test_worker_crash_restarts_newest_job_then_degrades_cleanly():
    backend = Backend()
    service = coordinator(backend, max_crash_restarts=1)
    item = desired("save")
    job_id = service.submit(item)
    backend.handle.crash()
    service.poll()

    assert len(backend.starts) == 2
    assert service.job(job_id).status == JobStatus.RUNNING
    assert service.job(job_id).restart_count == 1
    backend.handle.crash()
    service.poll()
    assert service.job(job_id).status == JobStatus.FAILED
    assert service.job(job_id).error["code"] == "worker_crashed"


def test_superseded_crash_does_not_restart_and_promotes_pending():
    backend = Backend()
    service = coordinator(backend)
    old_id = service.submit(desired("old"))
    new_id = service.submit(desired("new"))
    backend.handle.crash()

    service.poll()

    assert [entry[0] for entry in backend.starts] == [old_id, new_id]


def test_cancellation_terminates_active_and_promotes_pending():
    backend = Backend()
    service = coordinator(backend)
    first_id = service.submit(desired("first"))
    first_handle = backend.handle
    second_id = service.submit(desired("second"))

    service.cancel(first_id)

    assert first_handle.terminated
    assert service.job(first_id).status == JobStatus.CANCELLED
    assert backend.starts[-1][0] == second_id
    second = service.job(second_id).desired
    backend.handle.send("result", second_id, result_for(second))
    service.poll()
    assert service.last_success.job_id == second_id


def test_stabilizing_and_progress_are_explicit_without_running_analysis():
    backend = Backend()
    service = coordinator(backend)
    item = desired("save")
    job_id = service.submit(item, stabilizing=True)
    assert backend.starts == []
    assert service.job(job_id).status == JobStatus.STABILIZING

    service.mark_stable(job_id)
    event = ProgressEvent("analysis", "working", 0.0, {"done": 1})
    backend.handle.send("progress", job_id, event)
    service.poll()

    assert service.job(job_id).status == JobStatus.RUNNING
    assert service.job(job_id).progress == [event]


def test_shutdown_cancels_pending_and_terminates_worker():
    backend = Backend()
    service = coordinator(backend)
    active_id = service.submit(desired("active"))
    active_handle = backend.handle
    pending_id = service.submit(desired("pending"))

    service.shutdown()

    assert active_handle.terminated
    assert service.job(active_id).status == JobStatus.CANCELLED
    assert service.job(pending_id).status == JobStatus.CANCELLED


def test_duplicate_desired_notification_is_coalesced():
    backend = Backend()
    service = coordinator(backend)
    item = desired("same")
    first = service.submit(item)
    second = service.submit(item)
    assert first == second
    assert len(backend.starts) == 1


def test_scheduled_inputs_are_snapshotted_against_caller_mutation():
    backend = Backend()
    service = coordinator(backend)
    base = desired("save")
    manifest = {"brothers": {"one": {"roles": {}}}}
    item = DesiredAnalysis(
        replace_request(base.request, cache=CompatibleCacheContext(manifest=manifest)),
        base.artifact_signatures,
    )
    expected = item.identity
    job_id = service.submit(item)
    item.request.roles[0]["name"] = "Mutated"
    item.request.classification["label"] = "mutated"
    manifest["brothers"]["one"]["roles"]["new"] = {}

    assert service.job(job_id).desired.identity == expected
    assert backend.starts[0][1].roles[0]["name"] == "Role"
    assert backend.starts[0][1].cache.manifest["brothers"]["one"]["roles"] == {}


def replace_request(request, **changes):
    from dataclasses import replace

    return replace(request, **changes)


def test_behavior_affecting_options_do_not_coalesce():
    backend = Backend()
    service = coordinator(backend)
    first = desired("save")
    second = DesiredAnalysis(
        replace_request(
            first.request, options=AnalysisServiceOptions(verify_cache=True)
        ),
        first.artifact_signatures,
    )

    first_id = service.submit(first)
    second_id = service.submit(second)

    assert first_id != second_id
    assert service.job(first_id).status == JobStatus.SUPERSEDED


def test_worker_start_failure_is_contained_by_coordinator():
    service = coordinator(FailingBackend())
    job_id = service.submit(desired("save"))
    assert service.job(job_id).status == JobStatus.FAILED
    assert service.job(job_id).error["code"] == "worker_start_failed"


def test_dependency_callback_failure_fails_closed_without_controller_failure():
    backend = Backend()

    def broken(_signatures):
        raise RuntimeError("registry unavailable")

    service = coordinator(backend, signatures_are_current=broken)
    item = desired("save")
    job_id = service.submit(item)
    backend.handle.send("result", job_id, result_for(item))
    service.poll()
    assert service.job(job_id).status == JobStatus.SUPERSEDED
    assert service.last_success is None


def test_production_backend_spawns_process_without_calling_analysis_inline():
    calls = []

    class Queue:
        def get_nowait(self):
            raise __import__("queue").Empty

    class Process:
        def __init__(self, *, target, args, daemon):
            calls.append((target, args, daemon))

        def start(self):
            calls.append("started")

        def is_alive(self):
            return True

    context = SimpleNamespace(Queue=Queue, Process=Process)
    item = desired("save")
    handle = ProcessWorkerBackend(context).start(7, item.request)

    assert calls[-1] == "started"
    target, args, daemon = calls[0]
    assert target.__name__ == "_worker_main"
    assert args[0:2] == (7, item.request)
    assert daemon is True
    assert handle.is_alive()
