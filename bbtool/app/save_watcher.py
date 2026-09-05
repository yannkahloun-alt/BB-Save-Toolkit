"""Conservative polling watcher for one persisted Battle Brothers save.

The path is reopened on every probe (so atomic replacement is observed) and its
parent-directory metadata is sampled as an additional wake-up hint.  Neither
filesystem events nor timestamps are content identity: SHA-256 is authoritative.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import hashlib
import threading
from typing import Any

from .archetype_catalog import CatalogValidationError


@dataclass(frozen=True)
class StableSave:
    path: Path
    content: bytes
    fingerprint: str
    modified_at: float


class SaveWatcher:
    """Watch a selected path with deterministic, manually-drivable probes."""

    def __init__(
        self,
        selection: Callable[[], tuple[str | None, bool]],
        on_detected: Callable[[str], None],
        on_stable: Callable[[StableSave, bool], None],
        *,
        stable_probes: int = 2,
        monitor: bool = True,
        poll_interval: float = 0.25,
        read_bytes: Callable[[Path], bytes] | None = None,
    ) -> None:
        if stable_probes < 2:
            raise ValueError("stable_probes must be at least two")
        self._selection = selection
        self._on_detected = on_detected
        self._on_stable = on_stable
        self._stable_probes = stable_probes
        self._poll_interval = poll_interval
        self._read_bytes = read_bytes or Path.read_bytes
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._closed = False
        self._path: Path | None = None
        self._candidate: StableSave | None = None
        self._candidate_count = 0
        self._accepted: StableSave | None = None
        self._state = "unavailable"
        self._reason: str | None = "no_selected_save"
        self._error: str | None = None
        self._thread = None
        if monitor:
            self._thread = threading.Thread(target=self._monitor, daemon=True)
            self._thread.start()

    @property
    def accepted(self) -> StableSave | None:
        with self._lock:
            return self._accepted

    def status(self) -> dict[str, Any]:
        with self._lock:
            value: dict[str, Any] = {"status": self._state}
            if self._reason is not None:
                value["reason"] = self._reason
            if self._error is not None:
                value["message"] = self._error
            if self._accepted is not None:
                value["desired_source_fingerprint"] = self._accepted.fingerprint
            return value

    def notify(self) -> None:
        """Filesystem adapters may collapse arbitrary raw events into one wake-up."""
        self._wake.set()

    def poll(self) -> None:
        """Probe once; exposed for tests and event-loop integration."""
        stable = False
        selected, auto_refresh = self._selection()
        path = Path(selected) if selected is not None else None
        with self._lock:
            if path != self._path:
                self._path = path
                self._candidate = None
                self._candidate_count = 0
                self._accepted = None
                self._state = "unavailable" if path is None else "detected"
                self._reason = "no_selected_save" if path is None else "selection_changed"
                self._error = None
            if path is None:
                return

        try:
            # Sampling the directory as well as reopening the path is intentional:
            # games commonly write a sibling temporary file then replace the save.
            path.parent.stat()
            before = path.stat()
            if not path.is_file():
                raise FileNotFoundError(str(path))
            content = self._read_bytes(path)
            after = path.stat()
            if (
                before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
            ) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
            ):
                self._mark_unstable("changed_during_read")
                return
            fingerprint = "sha256:" + hashlib.sha256(content).hexdigest()
            snapshot = StableSave(path, content, fingerprint, after.st_mtime)
        except FileNotFoundError as exc:
            self._mark_unavailable(exc, "selected_save_missing")
            return
        except PermissionError as exc:
            self._mark_unavailable(exc, "selected_save_locked")
            return
        except OSError as exc:
            self._mark_unavailable(exc, "selected_save_unreadable")
            return

        callback = False
        with self._lock:
            if (
                self._accepted is not None
                and fingerprint == self._accepted.fingerprint
                and self._state not in {"unavailable", "stabilizing"}
            ):
                self._candidate = None
                self._candidate_count = 0
                return
            if self._candidate is None or fingerprint != self._candidate.fingerprint:
                self._candidate = snapshot
                self._candidate_count = 1
                self._state = "stabilizing"
                self._reason = "content_change_detected"
                self._error = None
                callback = True
            else:
                self._candidate = snapshot
                self._candidate_count += 1
            if self._candidate_count < self._stable_probes:
                detected = callback
            else:
                self._accepted = snapshot
                self._candidate = None
                self._candidate_count = 0
                self._state = "queued" if auto_refresh else "detected"
                self._reason = None if auto_refresh else "refresh_available"
                detected = callback
                stable = True
        if detected:
            self._on_detected("selected_save_content_changed")
        if stable:
            try:
                self._on_stable(snapshot, auto_refresh)
            except CatalogValidationError as exc:
                self._mark_catalog_conflict(exc)

    def set_job_state(self, status: str) -> None:
        with self._lock:
            if status == "running":
                self._state = "analyzing"
                self._reason = None
                self._error = None
            elif status == "failed":
                self._state = "failed"
                self._reason = "analysis_failed"
                self._error = None
            elif status == "succeeded":
                self._state = "current"
                self._reason = None
                self._error = None

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._wake.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)

    def _mark_unstable(self, reason: str) -> None:
        notify = False
        with self._lock:
            notify = self._state not in {"stabilizing", "unavailable"}
            self._candidate = None
            self._candidate_count = 0
            self._state = "stabilizing"
            self._reason = reason
        if notify:
            self._on_detected("selected_save_content_changed")

    def _mark_unavailable(self, exc: OSError, reason: str) -> None:
        notify = False
        with self._lock:
            notify = self._state != "unavailable"
            self._candidate = None
            self._candidate_count = 0
            self._state = "unavailable"
            self._reason = reason
            self._error = str(exc)
        if notify:
            self._on_detected("selected_save_unavailable")

    def _mark_catalog_conflict(self, exc: CatalogValidationError) -> None:
        with self._lock:
            self._state = "failed"
            self._reason = "archetype_catalog_conflict"
            self._error = str(exc)

    def _monitor(self) -> None:
        while True:
            self._wake.wait(self._poll_interval)
            self._wake.clear()
            with self._lock:
                if self._closed:
                    return
            self.poll()


__all__ = ["SaveWatcher", "StableSave"]
