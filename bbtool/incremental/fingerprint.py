from __future__ import annotations
import hashlib
import json
from typing import Any
from ..models import STATS

ROLE_PROJECTION_ENGINE_VERSION = 6
BROTHER_SUMMARY_ENGINE_VERSION = 5

def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

def stable_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

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


def brother_summary_fingerprint(bro, roles, classification_cfg) -> str:
    return stable_hash({
        "brother_state": brother_projection_state(bro),
        "roles": {role["name"]: role_fingerprint(role) for role in roles},
        "classification": classification_cfg,
        "engine_version": BROTHER_SUMMARY_ENGINE_VERSION,
    })


STRUCTURAL_PATH_ENGINE_VERSION = 3
ADVISOR_ENGINE_VERSION = 3


def structural_path_fingerprint(bro, roles) -> str:
    return stable_hash({
        "brother_state": brother_projection_state(bro),
        "roles": {role["name"]: role_fingerprint(role) for role in roles},
        "engine_version": STRUCTURAL_PATH_ENGINE_VERSION,
    })


def advisor_fingerprint(bro, roles) -> str:
    return stable_hash({
        "brother_state": brother_projection_state(bro),
        "roles": {role["name"]: role_fingerprint(role) for role in roles},
        "engine_version": ADVISOR_ENGINE_VERSION,
    })
