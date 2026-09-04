"""Read-only composition model for the shared local-application shell."""
from __future__ import annotations

from typing import Any

from .health import build_public_analysis_health
from .local_application import ApplicationOperationError, LocalApplication


def build_shell_state(application: LocalApplication) -> dict[str, Any]:
    """Compose shell status without inventing a second application authority."""
    followed_save = application.followed_save()
    result = application.last_result()
    publication = application.coordinator.last_success

    analysis_health = None
    if publication is not None:
        diagnostics = getattr(publication.result, "diagnostics", {}) or {}
        analysis_health = build_public_analysis_health(
            diagnostics.get("run_health", {})
        )

    active_job = None
    desired_job_id = application.coordinator.desired_job_id
    if desired_job_id is not None:
        try:
            active_job = application.analysis_job(desired_job_id)
        except ApplicationOperationError as exc:
            if exc.code != "job_not_found":
                raise

    return {
        "followed_save": followed_save,
        "result": result,
        "analysis_health": analysis_health,
        "active_job": active_job,
    }


__all__ = ["build_shell_state"]
