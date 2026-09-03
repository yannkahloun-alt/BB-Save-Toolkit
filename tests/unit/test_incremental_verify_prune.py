import json
import os

from bbtool.incremental.manifest import prune_manifests
from bbtool.incremental.verify import first_difference
from bbtool.models import CampaignIdentity


def test_first_difference_points_to_exact_nested_field():
    left={"fits":[{"Role":"A","ProjectedFitPct":80.0}]}
    right={"fits":[{"Role":"A","ProjectedFitPct":81.0}]}
    assert first_difference(left,right)==(
        "$.fits[0].ProjectedFitPct",80.0,81.0
    )


def test_first_difference_none_for_equal_values():
    value={"a":[1,{"b":2}]}
    assert first_difference(value,value) is None


def test_prune_manifests_keeps_latest_for_same_campaign_only(tmp_path):
    out=tmp_path/"out"; out.mkdir()
    identity={"schema":"bbtool.campaign_identity.v1","basis":"native_campaign_id","value":7,"confidence":"exact","reason":None}
    other_identity={**identity,"value":8}
    created=[]
    for i in range(4):
        d=out/f"run{i}"; d.mkdir()
        p=d/f"run{i}-incremental-manifest.json"
        p.write_text(json.dumps({
            "schema":"bb-incremental-v2",
            "source_save_path":f"/game/save{i}.sav",
            "campaign_identity":identity,
        }),encoding="utf-8")
        os.utime(p,(100+i,100+i))
        created.append(p)
    other_dir=out/"other"; other_dir.mkdir()
    other_p=other_dir/"other-incremental-manifest.json"
    other_p.write_text(json.dumps({
        "schema":"bb-incremental-v2",
        "source_save_path":"/game/quicksave.sav",
        "campaign_identity":other_identity,
    }),encoding="utf-8")

    removed=prune_manifests(
        out,campaign_identity=CampaignIdentity(7,confidence="exact"),keep=2
    )
    assert set(removed)==set(created[:2])
    assert created[2].exists() and created[3].exists()
    assert other_p.exists()
