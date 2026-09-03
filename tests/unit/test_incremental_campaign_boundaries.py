import os
from types import SimpleNamespace

from bbtool.app import analysis as analysis_module
from bbtool.incremental.cache import IncrementalCache
from bbtool.incremental.manifest import find_previous_manifest, write_manifest
from bbtool.models import CampaignIdentity


def _run(bro, role, classification, previous=None, campaign_id=101):
    cache=IncrementalCache(previous)
    result=analysis_module.analyze_brothers([bro],[role],classification,cache)
    return result,cache,cache.manifest_payload(
        generated_at="deterministic", source_save="quicksave.sav",
        campaign_identity=CampaignIdentity(campaign_id, confidence="exact"),
        source_save_path="/campaigns/quicksave.sav",
    )


def _stub_analysis(monkeypatch):
    calls=[]

    def role_row(bro,role,fast=False):
        calls.append((bro.Name,role["name"]))
        fit=round(float(bro.HP)/100.0,2)
        return {
            "BrotherID":bro.BrotherID,"Name":bro.Name,"Level":bro.Level,
            "Background":bro.Background,"Role":role["name"],
            "ProjectedFit":fit,"ProjectedFitPct":fit*100,
            "FitFeasibilityPct":100.0,"ProjectedFitLikelyMinPct":fit*100,
            "ProjectedFitLikelyMaxPct":fit*100,"ProjectedFitFullMinPct":fit*100,
            "ProjectedFitFullMaxPct":fit*100,"PerkCompatibility":"NEUTRAL",
            "MAtk":bro.MAtk,"MDef":bro.MDef,"RAtk":bro.RAtk,"HP":bro.HP,
            "Fatigue":bro.Fatigue,"Resolve":bro.Resolve,
        }

    monkeypatch.setattr(analysis_module,"_role_row",role_row)
    monkeypatch.setattr(analysis_module,"advise_levelup",lambda *args: None)
    monkeypatch.setattr(
        analysis_module,"effective_stat_profile",
        lambda bro: ({stat:float(getattr(bro,stat)) for stat in
                      ("HP","Fatigue","Resolve","Initiative","MAtk","RAtk","MDef","RDef")},{}),
    )
    return calls


def test_immediate_identical_run_selects_manifest_and_avoids_projection_work(
    tmp_path,monkeypatch,bro_factory,simple_role
):
    calls=_stub_analysis(monkeypatch)
    bro=bro_factory(Level=11,HP=73)
    role=simple_role(("HP","MAtk","MDef"))
    classification={"thresholds":{"Invest":{"min_projected_fit":0.8},
                                  "Use":{"min_projected_fit":0.5},
                                  "Fodder":{"min_full_max_fit":0.5}},
                    "display":{"premium_fit":0.9,"good_fit":0.7,"viable_fit":0.5}}
    cold,cold_cache,manifest=_run(bro,role,classification)
    out=tmp_path/"out"; run=out/"run-a"; run.mkdir(parents=True)
    save=tmp_path/"quicksave.sav"; save.write_bytes(b"same bytes")
    manifest["source_save_path"]=str(save.resolve())
    manifest_path=write_manifest(SimpleNamespace(root=run,base="run-a"),manifest)

    selected_path,selected=find_previous_manifest(
        out, campaign_identity=CampaignIdentity(101, confidence="exact"),
        source_save=save,
    )
    warm,warm_cache,_=_run(bro,role,classification,selected)

    assert selected_path==manifest_path
    assert cold==warm
    assert calls==[(bro.Name,role["name"])]
    assert cold_cache.stats.role_computed==1
    assert warm_cache.stats.role_reused==1
    assert warm_cache.stats.role_computed==0
    assert warm_cache.stats.summary_reused==1
    assert warm_cache.stats.summary_computed==0
    assert cold_cache.miss_reasons=={"no_previous_manifest":3}
    assert not warm_cache.miss_reasons


def test_same_path_new_campaign_is_not_selected(
    tmp_path,monkeypatch,bro_factory,simple_role
):
    calls=_stub_analysis(monkeypatch)
    role=simple_role(("HP","MAtk","MDef"))
    classification={"thresholds":{"Invest":{"min_projected_fit":0.8},
                                  "Use":{"min_projected_fit":0.5},
                                  "Fodder":{"min_full_max_fit":0.5}},
                    "display":{"premium_fit":0.9,"good_fit":0.7,"viable_fit":0.5}}
    campaign_a=bro_factory(Name="A",Level=11,HP=60)
    _,_,manifest_a=_run(campaign_a,role,classification,campaign_id=101)
    out=tmp_path/"out"; run_a=out/"run-a"; run_a.mkdir(parents=True)
    save=tmp_path/"quicksave.sav"; save.write_bytes(b"campaign A")
    manifest_a["source_save_path"]=str(save.resolve())
    path_a=write_manifest(SimpleNamespace(root=run_a,base="run-a"),manifest_a)
    os.utime(path_a,(100,100))
    save.write_bytes(b"campaign B")

    selected_path,selected=find_previous_manifest(
        out, campaign_identity=CampaignIdentity(202, confidence="exact"),
        source_save=save,
    )
    campaign_b=bro_factory(Name="B",Level=11,HP=61)
    result_b,cache_b,_=_run(
        campaign_b,role,classification,selected,campaign_id=202
    )

    assert selected_path is None
    assert selected is None
    assert path_a.exists()
    assert result_b.fits[0]["ProjectedFitPct"]==61.0
    assert cache_b.stats.role_reused==0
    assert cache_b.stats.role_computed==1
    assert cache_b.miss_reasons["no_previous_manifest"]>0
    assert calls==[("A",role["name"]),("B",role["name"])]


def test_same_campaign_is_selected_across_renamed_path(tmp_path):
    out=tmp_path/"out"; run=out/"manual"; run.mkdir(parents=True)
    cache=IncrementalCache()
    identity=CampaignIdentity(101,confidence="exact")
    payload=cache.manifest_payload(
        generated_at="x",source_save="manual.sav",
        source_save_path="/old/manual.sav",campaign_identity=identity,
    )
    path=write_manifest(SimpleNamespace(root=run,base="manual"),payload)

    selected_path,selected=find_previous_manifest(
        out,campaign_identity=identity,source_save=tmp_path/"renamed.sav"
    )

    assert selected_path==path
    assert selected==payload
