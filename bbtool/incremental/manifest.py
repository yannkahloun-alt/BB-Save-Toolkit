from __future__ import annotations
import json
import os
from pathlib import Path

SCHEMA = "bb-incremental-v1"
SUFFIX = "-incremental-manifest.json"

def _load(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        return None
    return payload

def find_previous_manifest(out_root: Path, exclude_root: Path | None = None, source_save: Path | None = None):
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
        if source_save is not None:
            expected = str(source_save.resolve())
            if payload.get("source_save_path") != expected:
                continue
        return path,payload
    return None,None

def write_manifest(workspace, payload: dict) -> Path:
    path=workspace.root/f"{workspace.base}{SUFFIX}"
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False,sort_keys=True),encoding="utf-8")
    os.replace(tmp,path)
    return path


def prune_manifests(out_root: Path, *, source_save_path: str, keep: int = 10, exclude_root: Path | None = None) -> list[Path]:
    """Remove old incremental manifests only; never remove normal run outputs."""
    if keep < 1 or not out_root.exists():
        return []
    matches=[]
    for path in out_root.rglob(f"*{SUFFIX}"):
        if exclude_root is not None:
            try:
                path.relative_to(exclude_root)
                continue
            except ValueError:
                pass
        payload=_load(path)
        if payload is None or payload.get("source_save_path") != source_save_path:
            continue
        try: matches.append((path.stat().st_mtime,path))
        except OSError: continue
    removed=[]
    for _mtime,path in sorted(matches, reverse=True)[keep:]:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            pass
    return removed
