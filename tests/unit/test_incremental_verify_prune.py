import json
import os
import time
from pathlib import Path

from bbtool.incremental.manifest import prune_manifests
from bbtool.incremental.verify import first_difference


def test_first_difference_points_to_exact_nested_field():
    left={"fits":[{"Role":"A","ProjectedFitPct":80.0}]}
    right={"fits":[{"Role":"A","ProjectedFitPct":81.0}]}
    assert first_difference(left,right)==(
        "$.fits[0].ProjectedFitPct",80.0,81.0
    )


def test_first_difference_none_for_equal_values():
    value={"a":[1,{"b":2}]}
    assert first_difference(value,value) is None


def test_prune_manifests_keeps_latest_for_same_save_only(tmp_path):
    out=tmp_path/"out"; out.mkdir()
    source="/game/quicksave.sav"
    other="/game/other.sav"
    created=[]
    for i in range(4):
        d=out/f"run{i}"; d.mkdir()
        p=d/f"run{i}-incremental-manifest.json"
        p.write_text(json.dumps({
            "schema":"bb-incremental-v1",
            "source_save_path":source,
        }),encoding="utf-8")
        os.utime(p,(100+i,100+i))
        created.append(p)
    other_dir=out/"other"; other_dir.mkdir()
    other_p=other_dir/"other-incremental-manifest.json"
    other_p.write_text(json.dumps({
        "schema":"bb-incremental-v1",
        "source_save_path":other,
    }),encoding="utf-8")

    removed=prune_manifests(out,source_save_path=source,keep=2)
    assert set(removed)==set(created[:2])
    assert created[2].exists() and created[3].exists()
    assert other_p.exists()
