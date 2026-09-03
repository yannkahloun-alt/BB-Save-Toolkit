import json
import os
from types import SimpleNamespace

import pytest

from bbtool.incremental.cache import IncrementalCache
from bbtool.incremental.manifest import find_previous_manifest, prune_manifests, write_manifest
from bbtool.models import CampaignIdentity


def _manifest(identity, *, source="quicksave.sav", path="/saves/quicksave.sav"):
    return IncrementalCache().manifest_payload(
        generated_at="x",
        source_save=source,
        source_save_path=path,
        campaign_identity=identity,
    )


def _write(out, name, payload, mtime):
    root=out/name
    root.mkdir(parents=True)
    path=write_manifest(SimpleNamespace(root=root,base=name),payload)
    os.utime(path,(mtime,mtime))
    return path


@pytest.mark.parametrize("source", ["renamed.sav", "copy.sav", "manual.sav", "quicksave.sav"])
def test_discovery_uses_campaign_not_save_path(tmp_path, source):
    identity=CampaignIdentity(44,confidence="exact")
    old=_write(tmp_path,"old",_manifest(identity,path="/old/autosave.sav"),100)

    found,payload=find_previous_manifest(
        tmp_path,campaign_identity=identity,source_save=tmp_path/source
    )

    assert found==old
    assert payload["campaign_identity"]["value"]==44


def test_discovery_chooses_newest_same_campaign_and_ignores_newer_other_campaign(tmp_path):
    wanted=CampaignIdentity(10,confidence="exact")
    older=_write(tmp_path,"older",_manifest(wanted),100)
    newest_same=_write(tmp_path,"newest-same",_manifest(wanted),200)
    _write(tmp_path,"other",_manifest(CampaignIdentity(11,confidence="exact")),300)

    found,_=find_previous_manifest(tmp_path,campaign_identity=wanted)

    assert found==newest_same
    assert found!=older


def test_same_map_seed_does_not_bridge_distinct_campaign_ids(tmp_path):
    payload=_manifest(CampaignIdentity(10,confidence="exact"))
    payload["map_seed"]="SAME-SEED"
    _write(tmp_path,"old",payload,100)

    assert find_previous_manifest(
        tmp_path,campaign_identity=CampaignIdentity(11,confidence="exact")
    )==(None,None)


@pytest.mark.parametrize(
    "identity",
    [
        None,
        CampaignIdentity(None,confidence="unavailable",reason="not_found"),
        CampaignIdentity(None,confidence="invalid",reason="ambiguous"),
    ],
)
def test_unavailable_or_invalid_current_identity_disables_history(tmp_path, identity):
    _write(tmp_path,"old",_manifest(CampaignIdentity(10,confidence="exact")),100)

    assert find_previous_manifest(tmp_path,campaign_identity=identity)==(None,None)
    assert prune_manifests(tmp_path,campaign_identity=identity,keep=1)==[]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.pop("campaign_identity"),
        lambda value: value["campaign_identity"].update(value=True),
        lambda value: value["campaign_identity"].update(value=-1),
        lambda value: value["campaign_identity"].update(confidence="invalid"),
        lambda value: value["campaign_identity"].update(reason="ambiguous"),
        lambda value: value["campaign_identity"].update(basis="map_seed"),
        lambda value: value["campaign_identity"].update(schema="unknown"),
    ],
)
def test_malformed_manifest_identity_is_not_selected(tmp_path, mutation):
    payload=_manifest(CampaignIdentity(10,confidence="exact"))
    mutation(payload)
    _write(tmp_path,"bad",payload,100)

    assert find_previous_manifest(
        tmp_path,campaign_identity=CampaignIdentity(10,confidence="exact")
    )==(None,None)


def test_schema_v1_remains_readable_but_is_not_campaign_compatible(tmp_path):
    legacy={
        "schema":"bb-incremental-v1",
        "source_save_path":"/same/quicksave.sav",
        "brothers":{},
    }
    path=_write(tmp_path,"legacy",legacy,100)

    assert IncrementalCache(json.loads(path.read_text(encoding="utf-8"))).previous
    assert find_previous_manifest(
        tmp_path,
        campaign_identity=CampaignIdentity(10,confidence="exact"),
        source_save=tmp_path/"quicksave.sav",
    )==(None,None)


def test_pruning_does_not_delete_legacy_or_malformed_manifests(tmp_path):
    identity=CampaignIdentity(10,confidence="exact")
    current=[]
    for index in range(3):
        current.append(_write(tmp_path,f"current-{index}",_manifest(identity),100+index))
    legacy=_write(tmp_path,"legacy",{"schema":"bb-incremental-v1","brothers":{}},50)
    malformed=_manifest(identity)
    malformed["campaign_identity"]["value"]="10"
    malformed_path=_write(tmp_path,"malformed",malformed,60)

    removed=prune_manifests(tmp_path,campaign_identity=identity,keep=1)

    assert set(removed)==set(current[:2])
    assert current[2].exists()
    assert legacy.exists()
    assert malformed_path.exists()


def test_pruning_counts_protected_current_manifest_toward_limit(tmp_path):
    identity=CampaignIdentity(10,confidence="exact")
    old=[]
    for index in range(3):
        old.append(_write(tmp_path,f"old-{index}",_manifest(identity),100+index))
    current_root=tmp_path/"current"
    current_root.mkdir()
    current=write_manifest(
        SimpleNamespace(root=current_root,base="current"),_manifest(identity)
    )

    removed=prune_manifests(
        tmp_path,campaign_identity=identity,keep=2,exclude_root=current_root
    )

    assert set(removed)==set(old[:2])
    assert old[2].exists()
    assert current.exists()
