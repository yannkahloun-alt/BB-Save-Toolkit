"""Content integrity helpers for reusable incremental artifacts.

Incremental dependency fingerprints prove that an artifact's inputs still match.
These helpers independently prove that the cached artifact record is the same
normalized value that the producing run stored. The hashes are not a security
boundary; missing or mismatched evidence simply makes disposable cache state
ineligible for reuse.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .dependencies import stable_hash

ARTIFACT_INTEGRITY_SCHEMA = "bbtool.incremental_artifact_integrity.v1"


def _integrity_hash(kind: str, payload: Mapping[str, Any]) -> str:
    return stable_hash({
        "schema": ARTIFACT_INTEGRITY_SCHEMA,
        "artifact_kind": kind,
        "payload": dict(payload),
    })


def sign_artifact(kind: str, payload: Mapping[str, Any]) -> dict:
    """Return a stored artifact with producer-owned normalized integrity evidence."""
    artifact = dict(payload)
    artifact["integrity"] = {
        "schema": ARTIFACT_INTEGRITY_SCHEMA,
        "hash": _integrity_hash(kind, payload),
    }
    return artifact


def integrity_status(
    kind: str,
    artifact: Mapping[str, Any],
    payload_keys: Iterable[str],
) -> str:
    """Return ``valid``, ``missing``, or ``mismatch`` for a cached artifact."""
    evidence = artifact.get("integrity")
    if (
        not isinstance(evidence, dict)
        or evidence.get("schema") != ARTIFACT_INTEGRITY_SCHEMA
        or not isinstance(evidence.get("hash"), str)
    ):
        return "missing"
    payload = {key: artifact.get(key) for key in payload_keys}
    return (
        "valid"
        if evidence["hash"] == _integrity_hash(kind, payload)
        else "mismatch"
    )
