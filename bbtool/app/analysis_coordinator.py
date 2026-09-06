"""Background process coordination for transport-independent analysis.

The coordinator owns scheduling and publication only.  Analytical semantics stay in
``analysis_service`` and dependency semantics are supplied by the caller (ultimately
the registry from issue #122).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import copy
from dataclasses import dataclass, field, replace
from enum import StrEnum
import hashlib
import multiprocessing
from queue import Empty
import threading
from typing import Any, Protocol

from ..incremental.fingerprint import stable_hash
from .analysis_service import (
    AnalysisServiceError,
    AnalysisServiceRequest,
    AnalysisServiceResult,
    ProgressEvent,
    analyze_save,
)


class JobStatus(StrEnum):
    STABILIZING = "stabilizing"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DesiredAnalysis:
    """An exact analysis request plus scoped pre-analysis dependency signatures."""

    request: AnalysisServiceRequest
    dependency_signatures: Mapping[str, Any] = field(default_factory=dict)

    @property
    def source_fingerprint(self) -> str:
        return "sha256:" + hashlib.sha256(self.request.source.content).hexdigest()

    @property
    def configuration_fingerprints(self) -> Mapping[str, str]:
        return {
            "archetypes": stable_hash(self.request.roles),
            "classification": stable_hash(self.request.classification),
        }

    @property
    def identity(self) -> tuple[Any, ...]:
        return (
            self.source_fingerprint,
            tuple(sorted(self.configuration_fingerprints.items())),
            stable_hash(self.dependency_signatures),
            self.request.options.verify_cache,
        )


@dataclass
class AnalysisJob:
    id: int
    desired: DesiredAnalysis
    status: JobStatus
    progress: list[ProgressEvent] = field(default_factory=list)
    error: dict[str, str] | None = None
    restart_count: int = 0


@dataclass(frozen=True)
class PublishedAnalysis:
    generation: int
    job_id: int
    source_fingerprint: str
    configuration_fingerprints: Mapping[str, str]
    dependency_signatures: Mapping[str, Any]
    artifact_signatures: Mapping[str, Any]
    result: AnalysisServiceResult


class WorkerHandle(Protocol):
    def messages(self) -> list[tuple[str, Any]]: ...
    def is_alive(self) -> bool: ...
    def terminate(self) -> None: ...
    def join(self) -> None: ...


class WorkerBackend(Protocol):
    def start(self, job_id: int, request: AnalysisServiceRequest) -> WorkerHandle: ...


def _worker_main(job_id: int, request: AnalysisServiceRequest, output: Any) -> None:
    def progress(event: ProgressEvent) -> None:
        output.put(("progress", (job_id, event)))

    try:
        result = analyze_save(replace(request, on_progress=progress))
        output.put(("result", (job_id, result)))
    except AnalysisServiceError as exc:
        output.put(("error", (job_id, exc.as_dict())))
    except BaseException as exc:  # worker isolation must report unexpected failures
        output.put(("error", (job_id, {
            "code": "worker_failed", "stage": "worker", "message": str(exc),
        })))


class _ProcessHandle:
    def __init__(self, process: Any, output: Any):
        self.process = process
        self.output = output

    def messages(self) -> list[tuple[str, Any]]:
        found = []
        while True:
            try:
                found.append(self.output.get_nowait())
            except Empty:
                return found

    def is_alive(self) -> bool:
        return self.process.is_alive()

    def terminate(self) -> None:
        if self.process.is_alive():
            self.process.terminate()

    def join(self) -> None:
        self.process.join(timeout=1)


class ProcessWorkerBackend:
    """Spawn one analysis worker; no CPU-heavy service work runs in the caller."""

    def __init__(self, context: Any | None = None):
        self.context = context or multiprocessing.get_context("spawn")

    def start(self, job_id: int, request: AnalysisServiceRequest) -> WorkerHandle:
        output = self.context.Queue()
        process = self.context.Process(
            target=_worker_main, args=(job_id, request, output), daemon=True
        )
        process.start()
        return _ProcessHandle(process, output)


class AnalysisCoordinator:
    """Thread-safe one-active/one-newest-pending analysis state machine."""

    def __init__(
        self,
        *,
        backend: WorkerBackend | None = None,
        signatures_are_current: Callable[[Mapping[str, Any]], bool] | None = None,
        retain_valid_artifacts: Callable[
            [PublishedAnalysis | None, Mapping[str, Any]], Mapping[str, Any]
        ] | None = None,
        max_crash_restarts: int = 1,
        monitor: bool = True,
        poll_interval: float = 0.05,
    ):
        self._backend = backend or ProcessWorkerBackend()
        self._signatures_are_current = signatures_are_current or (lambda _: True)
        self._has_explicit_signature_validator = signatures_are_current is not None
        self._retain_valid_artifacts = retain_valid_artifacts or (lambda _old, _new: {})
        self._max_crash_restarts = max_crash_restarts
        self._poll_interval = poll_interval
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._closed = False
        self._next_id = 1
        self._generation = 0
        self._desired_id: int | None = None
        self._active: AnalysisJob | None = None
        self._active_handle: WorkerHandle | None = None
        self._pending: AnalysisJob | None = None
        self._jobs: dict[int, AnalysisJob] = {}
        self._last_success: PublishedAnalysis | None = None
        self._retained_artifacts: Mapping[str, Any] = {}
        self._thread = None
        if monitor:
            self._thread = threading.Thread(target=self._monitor, daemon=True)
            self._thread.start()

    def configure_dependency_validation(
        self, signatures_are_current: Callable[[Mapping[str, Any]], bool]
    ) -> None:
        """Bind caller-owned dependency currentness unless explicitly supplied already."""
        with self._lock:
            if self._has_explicit_signature_validator:
                return
            self._signatures_are_current = signatures_are_current
            self._has_explicit_signature_validator = True

    @property
    def last_success(self) -> PublishedAnalysis | None:
        with self._lock:
            return self._last_success

    @property
    def retained_artifacts(self) -> Mapping[str, Any]:
        with self._lock:
            return dict(self._retained_artifacts)

    @property
    def desired_job_id(self) -> int | None:
        """Newest requested generation, for transport-independent freshness views."""
        with self._lock:
            return self._desired_id

    def job(self, job_id: int) -> AnalysisJob:
        with self._lock:
            return self._jobs[job_id]

    def submit(self, desired: DesiredAnalysis, *, stabilizing: bool = False) -> int:
        """Record newest desired state immediately; never waits for analysis."""
        with self._lock:
            if self._closed:
                raise RuntimeError("analysis coordinator is shut down")
            # Repeated notification for the exact desired inputs is already coalesced.
            current = self._jobs.get(self._desired_id) if self._desired_id else None
            if current is not None and current.desired.identity == desired.identity and current.status not in {
                JobStatus.FAILED, JobStatus.CANCELLED,
            }:
                return current.id
            # Lists/dicts are accepted by the analysis service. Snapshot them at the
            # scheduling boundary so caller mutation cannot change a queued job.
            request = replace(
                desired.request,
                roles=copy.deepcopy(desired.request.roles),
                classification=copy.deepcopy(desired.request.classification),
                cache=replace(
                    desired.request.cache,
                    manifest=copy.deepcopy(desired.request.cache.manifest),
                ),
                on_progress=None,
            )
            snapshot = DesiredAnalysis(
                request, copy.deepcopy(desired.dependency_signatures)
            )
            job = AnalysisJob(
                self._next_id, snapshot,
                JobStatus.STABILIZING if stabilizing else JobStatus.QUEUED,
            )
            self._next_id += 1
            self._jobs[job.id] = job
            self._desired_id = job.id
            if self._pending is not None:
                self._pending.status = JobStatus.SUPERSEDED
            if self._active is not None:
                if self._active.status == JobStatus.RUNNING:
                    self._active.status = JobStatus.SUPERSEDED
                self._pending = job
            elif stabilizing:
                self._pending = job
            else:
                self._start(job)
            self._wake.set()
            return job.id

    def mark_stable(self, job_id: int) -> None:
        """#99 may call this after proving source stability."""
        with self._lock:
            job = self._jobs[job_id]
            if job.status != JobStatus.STABILIZING or job_id != self._desired_id:
                return
            job.status = JobStatus.QUEUED
            if self._active is None:
                self._pending = None
                self._start(job)
            self._wake.set()

    def cancel(self, job_id: int) -> None:
        with self._lock:
            job = self._jobs[job_id]
            # Preserve the newest pending generation before promotion consumes
            # the pending slot.
            if self._desired_id == job_id:
                self._desired_id = (
                    None if job is self._pending
                    else self._pending.id if self._pending else None
                )
            if job is self._pending:
                job.status = JobStatus.CANCELLED
                self._pending = None
            elif job is self._active and self._active_handle is not None:
                job.status = JobStatus.CANCELLED
                self._active_handle.terminate()
                self._active_handle.join()
                self._active = None
                self._active_handle = None
                self._promote_pending()

    def invalidate_desired(self) -> None:
        """Prevent every pre-invalidation job from publishing.

        Durable application mutations call this after commit.  The next explicit
        submission establishes the new desired source/configuration generation.
        """
        with self._lock:
            self._desired_id = None
            if self._pending is not None:
                self._pending.status = JobStatus.CANCELLED
                self._pending = None
            if self._active is not None and self._active_handle is not None:
                self._active.status = JobStatus.CANCELLED
                self._active_handle.terminate()
                self._active_handle.join()
                self._active = None
                self._active_handle = None
            self._wake.set()

    def mark_desired_stale(self) -> None:
        """Prevent publication while a newer filesystem snapshot stabilizes.

        Unlike a configuration mutation, a source notification does not kill the
        active worker.  The next stable submission uses the normal newest-pending
        coalescing path; completion before then is still rejected because there is
        no current desired generation.
        """
        with self._lock:
            self._desired_id = None
            if self._pending is not None:
                self._pending.status = JobStatus.SUPERSEDED
                self._pending = None
            self._wake.set()

    def poll(self) -> None:
        """Advance worker state once; public for deterministic event-loop tests."""
        with self._lock:
            job, handle = self._active, self._active_handle
            if job is None or handle is None:
                self._promote_pending()
                return
            terminal = False
            for kind, payload in handle.messages():
                message_job_id, value = payload
                if message_job_id != job.id:
                    continue
                if kind == "progress":
                    job.progress.append(value)
                elif kind == "result":
                    terminal = True
                    self._complete(job, value)
                elif kind == "error":
                    terminal = True
                    self._fail(job, value)
            if terminal:
                handle.join()
                self._active = None
                self._active_handle = None
                self._promote_pending()
            elif not handle.is_alive():
                # multiprocessing's feeder thread may make the terminal message
                # visible only after the child has exited.
                handle.join()
                late_messages = handle.messages()
                for kind, payload in late_messages:
                    message_job_id, value = payload
                    if message_job_id != job.id:
                        continue
                    if kind == "progress":
                        job.progress.append(value)
                    elif kind == "result":
                        terminal = True
                        self._complete(job, value)
                    elif kind == "error":
                        terminal = True
                        self._fail(job, value)
                if terminal:
                    self._active = None
                    self._active_handle = None
                    self._promote_pending()
                    return
                # A process that exits without a terminal message crashed. Retry only
                # if it is still the newest desired state.
                if job.id == self._desired_id and job.restart_count < self._max_crash_restarts:
                    job.restart_count += 1
                    job.status = JobStatus.QUEUED
                    self._active = None
                    self._active_handle = None
                    self._start(job)
                else:
                    self._fail(job, {
                        "code": "worker_crashed", "stage": "worker",
                        "message": "analysis worker exited without a result",
                    })
                    self._active = None
                    self._active_handle = None
                    self._promote_pending()

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
            if self._pending is not None:
                self._pending.status = JobStatus.CANCELLED
                self._pending = None
            if self._active is not None and self._active_handle is not None:
                self._active.status = JobStatus.CANCELLED
                self._active_handle.terminate()
                self._active_handle.join()
                self._active = None
                self._active_handle = None
            self._wake.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)

    def _start(self, job: AnalysisJob) -> None:
        job.status = JobStatus.RUNNING
        self._active = job
        # User callbacks belong in the controlling process, never pickled into worker.
        try:
            self._active_handle = self._backend.start(
                job.id, replace(job.desired.request, on_progress=None)
            )
        except Exception as exc:
            self._active = None
            self._active_handle = None
            self._fail(job, {
                "code": "worker_start_failed", "stage": "worker",
                "message": str(exc),
            })

    def _complete(self, job: AnalysisJob, result: AnalysisServiceResult) -> None:
        desired = job.id == self._desired_id
        exact = (
            result.source_fingerprint == job.desired.source_fingerprint
            and result.configuration_fingerprints
            == job.desired.configuration_fingerprints
        )
        try:
            dependencies_current = self._signatures_are_current(
                job.desired.dependency_signatures
            )
        except Exception:
            dependencies_current = False
        if not (desired and exact and dependencies_current):
            job.status = JobStatus.SUPERSEDED
            return
        try:
            produced_signatures = result.incremental_cache.publication_signatures()
            if not isinstance(produced_signatures, Mapping):
                raise TypeError("publication signatures must be a mapping")
        except Exception:
            # Missing/corrupt authoritative signature evidence cannot publish as current.
            job.status = JobStatus.SUPERSEDED
            return
        self._generation += 1
        job.status = JobStatus.SUCCEEDED
        self._last_success = PublishedAnalysis(
            generation=self._generation,
            job_id=job.id,
            source_fingerprint=result.source_fingerprint,
            configuration_fingerprints=dict(result.configuration_fingerprints),
            dependency_signatures=copy.deepcopy(job.desired.dependency_signatures),
            artifact_signatures=copy.deepcopy(dict(produced_signatures)),
            result=result,
        )
        self._retained_artifacts = {}

    def _fail(self, job: AnalysisJob, error: Mapping[str, str]) -> None:
        if job.status not in {JobStatus.SUPERSEDED, JobStatus.CANCELLED}:
            job.status = JobStatus.FAILED
            job.error = dict(error)
        if job.id == self._desired_id:
            # The previous successful publication stays authoritative only for
            # independently revalidated artifacts supplied by #122's boundary.
            try:
                self._retained_artifacts = self._retain_valid_artifacts(
                    self._last_success, job.desired.dependency_signatures
                )
            except Exception:
                # Dependency validation failure is conservative: expose no old
                # artifact as current and keep the controller alive.
                self._retained_artifacts = {}

    def _promote_pending(self) -> None:
        if self._active is not None or self._pending is None:
            return
        job = self._pending
        if job.status == JobStatus.STABILIZING:
            return
        self._pending = None
        if job.status == JobStatus.QUEUED:
            self._start(job)

    def _monitor(self) -> None:
        while True:
            self._wake.wait(self._poll_interval)
            self._wake.clear()
            with self._lock:
                if self._closed:
                    return
            self.poll()


__all__ = [
    "AnalysisCoordinator", "AnalysisJob", "DesiredAnalysis", "JobStatus",
    "ProcessWorkerBackend", "PublishedAnalysis", "WorkerBackend", "WorkerHandle",
]
