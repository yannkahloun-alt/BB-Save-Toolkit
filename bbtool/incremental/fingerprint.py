from __future__ import annotations
from ..models import STATS
from .dependencies import (
    ArtifactKind, ENGINE_VERSIONS, current_advisor_payload,
    stable_hash, strategic_classification_payload, validation_oracle_payload,
)

ROLE_PROJECTION_ENGINE_VERSION = ENGINE_VERSIONS[ArtifactKind.ROLE_PROJECTION]
BROTHER_SUMMARY_ENGINE_VERSION = ENGINE_VERSIONS[ArtifactKind.STRATEGIC_CLASSIFICATION]
VALIDATION_ORACLE_ENGINE_VERSION = ENGINE_VERSIONS[ArtifactKind.VALIDATION_ORACLE]

def brother_projection_state(bro) -> dict:
    return {
        "stats": {s: float(getattr(bro, s)) for s in STATS},
        "stars": {s: int(getattr(bro, s + "Stars")) for s in STATS},
        "level": int(getattr(bro, "Level", 0)),
        "level_points": int(getattr(bro, "LevelPoints", 0)),
        "perks": sorted(getattr(bro, "Perks", []) or []),
        "traits": sorted(getattr(bro, "Traits", []) or []),
        "trait_ids": sorted(getattr(bro, "TraitIDs", []) or []),
        "permanent_injury_ids": sorted(getattr(bro, "PermanentInjuryIDs", []) or []),
        "background_id": str(getattr(bro, "BackgroundID", "") or ""),
        "current_rolls": {k: int(v) for k, v in sorted((getattr(bro, "CurrentRolls", {}) or {}).items())},
    }

def brother_projection_fingerprint(bro) -> str:
    return stable_hash(brother_projection_state(bro))

def role_fingerprint(role: dict) -> str:
    return stable_hash(role)


def validation_oracle_fingerprint(bro, role: dict) -> str:
    return stable_hash(validation_oracle_payload(
        brother_projection_state(bro), role_fingerprint(role),
        ROLE_PROJECTION_ENGINE_VERSION, VALIDATION_ORACLE_ENGINE_VERSION,
    ))


def brother_summary_fingerprint(bro, roles, classification_cfg) -> str:
    return stable_hash(strategic_classification_payload(
        brother_projection_state(bro),
        {role["name"]: role_fingerprint(role) for role in roles},
        classification_cfg, BROTHER_SUMMARY_ENGINE_VERSION,
    ))


ADVISOR_ENGINE_VERSION = ENGINE_VERSIONS[ArtifactKind.LEVEL_ADVISOR]


def advisor_fingerprint(bro, roles) -> str:
    return stable_hash(current_advisor_payload(
        brother_projection_state(bro),
        {role["name"]: role_fingerprint(role) for role in roles},
        ADVISOR_ENGINE_VERSION,
    ))
