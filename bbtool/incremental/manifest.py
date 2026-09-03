from __future__ import annotations
import json
import os
from pathlib import Path

from ..models import CampaignIdentity

SCHEMA = "bb-incremental-v2"
LEGACY_SCHEMA = "bb-incremental-v1"
CAMPAIGN_IDENTITY_SCHEMA = "bbtool.campaign_identity.v1"
SUFFIX = "-incremental-manifest.json"

def _load(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("schema") not in {
        SCHEMA, LEGACY_SCHEMA
    }:
        return None
    return payload


def campaign_identity_payload(identity: CampaignIdentity | None) -> dict:
    """Serialize campaign evidence without inventing a fallback identity."""
    if not isinstance(identity, CampaignIdentity):
        identity = CampaignIdentity(None, confidence="unavailable", reason="not_provided")
    return {
        "schema": CAMPAIGN_IDENTITY_SCHEMA,
        "basis": identity.basis,
        "value": identity.value,
        "confidence": identity.confidence,
        "reason": identity.reason,
    }


def _exact_campaign_value(value) -> int | None:
    if not isinstance(value, dict):
        return None
    raw = value.get("value")
    if (
        value.get("schema") != CAMPAIGN_IDENTITY_SCHEMA
        or value.get("basis") != "native_campaign_id"
        or value.get("confidence") != "exact"
        or value.get("reason") is not None
        or isinstance(raw, bool)
        or not isinstance(raw, int)
        or not 0 <= raw <= 2_147_483_647
    ):
        return None
    return raw


def _requested_campaign_value(identity: CampaignIdentity | None) -> int | None:
    if not isinstance(identity, CampaignIdentity):
        return None
    return _exact_campaign_value(campaign_identity_payload(identity))


def find_previous_manifest(
    out_root: Path,
    *,
    campaign_identity: CampaignIdentity | None,
    exclude_root: Path | None = None,
    source_save: Path | None = None,
):
    """Find the newest v2 manifest in the exact native campaign namespace.

    ``source_save`` is accepted as optional provenance/lookup context only. It
    never substitutes for missing native campaign identity.
    """
    expected = _requested_campaign_value(campaign_identity)
    if expected is None:
        return None, None
    if not out_root.exists(): return None, None
    candidates=[]
    for path in out_root.rglob(f"*{SUFFIX}"):
        if exclude_root is not None:
            try:
                path.relative_to(exclude_root); continue
            except ValueError: pass
        try: candidates.append((path.stat().st_mtime, path))
        except OSError: continue
    for _mtime,path in sorted(candidates, reverse=True):
        payload=_load(path)
        if payload is None:
            continue
        if payload.get("schema") != SCHEMA:
            continue
        if _exact_campaign_value(payload.get("campaign_identity")) != expected:
            continue
        return path,payload
    return None,None

def write_manifest(workspace, payload: dict) -> Path:
    path=workspace.root/f"{workspace.base}{SUFFIX}"
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False,sort_keys=True),encoding="utf-8")
    os.replace(tmp,path)
    return path


def prune_manifests(
    out_root: Path,
    *,
    campaign_identity: CampaignIdentity | None,
    keep: int = 10,
    exclude_root: Path | None = None,
) -> list[Path]:
    """Remove old incremental manifests only; never remove normal run outputs."""
    expected = _requested_campaign_value(campaign_identity)
    if keep < 1 or expected is None or not out_root.exists():
        return []
    matches=[]
    for path in out_root.rglob(f"*{SUFFIX}"):
        protected = False
        if exclude_root is not None:
            try:
                path.relative_to(exclude_root)
                protected = True
            except ValueError:
                pass
        payload=_load(path)
        if (
            payload is None
            or payload.get("schema") != SCHEMA
            or _exact_campaign_value(payload.get("campaign_identity")) != expected
        ):
            continue
        try: matches.append((path.stat().st_mtime,path,protected))
        except OSError: continue
    retained = {path for _mtime,path,protected in matches if protected}
    for _mtime,path,protected in sorted(matches, reverse=True):
        if not protected and len(retained) < keep:
            retained.add(path)
    removed=[]
    for _mtime,path,_protected in sorted(matches, reverse=True):
        if path in retained:
            continue
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            pass
    return removed
