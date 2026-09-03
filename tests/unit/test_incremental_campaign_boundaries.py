import os
from types import SimpleNamespace

from bbtool.app import analysis as analysis_module
from bbtool.incremental.cache import IncrementalCache
from bbtool.incremental.manifest import find_previous_manifest, write_manifest


def _run(bro, role, classification, previous=None):
    cache=IncrementalCache(previous)
    result=analysis_module.analyze_brothers([bro],[role],classification,cache)
    return result,cache,cache.manifest_payload(
        generated_at="deterministic", source_save="quicksave.sav",
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

    selected_path,selected=find_previous_manifest(out,source_save=save)
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


def test_same_path_new_campaign_selects_latest_but_rejects_changed_state(
    tmp_path,monkeypatch,bro_factory,simple_role
):
    calls=_stub_analysis(monkeypatch)
    role=simple_role(("HP","MAtk","MDef"))
    classification={"thresholds":{"Invest":{"min_projected_fit":0.8},
                                  "Use":{"min_projected_fit":0.5},
                                  "Fodder":{"min_full_max_fit":0.5}},
                    "display":{"premium_fit":0.9,"good_fit":0.7,"viable_fit":0.5}}
    campaign_a=bro_factory(Name="A",Level=11,HP=60)
    _,_,manifest_a=_run(campaign_a,role,classification)
    out=tmp_path/"out"; run_a=out/"run-a"; run_a.mkdir(parents=True)
    save=tmp_path/"quicksave.sav"; save.write_bytes(b"campaign A")
    manifest_a["source_save_path"]=str(save.resolve())
    path_a=write_manifest(SimpleNamespace(root=run_a,base="run-a"),manifest_a)
    os.utime(path_a,(100,100))
    save.write_bytes(b"campaign B")

    selected_path,selected=find_previous_manifest(out,source_save=save)
    campaign_b=bro_factory(Name="B",Level=11,HP=61)
    result_b,cache_b,_=_run(campaign_b,role,classification,selected)

    assert selected_path==path_a
    assert result_b.fits[0]["ProjectedFitPct"]==61.0
    assert cache_b.stats.role_reused==0
    assert cache_b.stats.role_computed==1
    assert cache_b.miss_reasons["brother_state_changed_or_new"]>0
    assert calls==[("A",role["name"]),("B",role["name"])]


def test_identical_state_from_unrelated_campaign_is_safe_content_reuse(
    monkeypatch,bro_factory,simple_role
):
    calls=_stub_analysis(monkeypatch)
    role=simple_role(("HP","MAtk","MDef"))
    classification={"thresholds":{"Invest":{"min_projected_fit":0.8},
                                  "Use":{"min_projected_fit":0.5},
                                  "Fodder":{"min_full_max_fit":0.5}},
                    "display":{"premium_fit":0.9,"good_fit":0.7,"viable_fit":0.5}}
    campaign_a=bro_factory(Name="Campaign A",HumanOffset=10,Level=11,HP=73)
    expected,_,manifest_a=_run(campaign_a,role,classification)
    campaign_b=bro_factory(Name="Campaign B",HumanOffset=99,Level=11,HP=73)

    reused,cache_b,_=_run(campaign_b,role,classification,manifest_a)

    assert calls==[("Campaign A",role["name"])]
    assert cache_b.stats.role_reused==1
    assert cache_b.stats.summary_reused==1
    assert reused.fits[0]["ProjectedFitPct"]==expected.fits[0]["ProjectedFitPct"]
    assert reused.fits[0]["Name"]=="Campaign B"
    assert reused.summaries[0]["Name"]=="Campaign B"
