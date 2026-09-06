"""Production policy boundary for Recruitment analytical potential.

The Background × Archetype prior and recruit candidate-estimate models remain
available in ``bbtool.recruitment_prior`` for explicit research and validation.
They are intentionally disabled from normal production analysis until an
explicit later product decision re-enables them.
"""
from __future__ import annotations

from ..build_identity import build_identity

RECRUITMENT_PRIOR_DISABLED_REASON = (
    "background_archetype_prior_disabled_pending_validation"
)


def build_disabled_recruitment_analysis(
    recruits: list[dict], roles: list[dict]
) -> list[dict]:
    """Return the stable Recruitment shape without invoking potential models."""
    rows = []
    for index, recruit in enumerate(recruits):
        analyses = []
        for role in roles:
            identity = build_identity(role)
            analyses.append({
                "build_identity": identity,
                "state": "unavailable",
                "reason": (
                    "build_identity_unavailable"
                    if identity is None
                    else RECRUITMENT_PRIOR_DISABLED_REASON
                ),
                "result": None,
            })
        rows.append({
            "recruit_index": index,
            "background_save_hash": recruit.get("BackgroundSaveHash"),
            "analyses": analyses,
        })
    return rows


__all__ = [
    "RECRUITMENT_PRIOR_DISABLED_REASON",
    "build_disabled_recruitment_analysis",
]
