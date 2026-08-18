
import json
import pytest

from bbtool.models import Brother
import bbtool.projection as projection
import bbtool.projection.context as context
import bbtool.projection.planner as planner
from bbtool.app.config import _fit_curve,_normalize_role,load_config
from bbtool.app.cli import parse_args


def bro(level_points=0,current_rolls=None):
    return Brother(
        Name="B",Title="",Level=5,XP=0,PerkPoints=0,PerksUsed=0,LevelPoints=level_points,
        AP=9,HP=70,HPStars=0,Fatigue=100,FatigueStars=0,Resolve=40,ResolveStars=0,
        Initiative=90,InitiativeStars=0,MAtk=70,MAtkStars=0,RAtk=40,RAtkStars=0,
        MDef=20,MDefStars=0,RDef=5,RDefStars=0,BackgroundID="",Background="",
        PerkIDs=[],Perks=[],TraitIDs=[],Traits=[],Injuries=[],HumanOffset=0,
        CurrentRolls=current_rolls or {},FutureRolls={}
    )


def test_projection_public_reset_and_profile(monkeypatch):
    calls=[]
    monkeypatch.setattr(projection,"reset_perk_cache",lambda:calls.append("perk"))
    monkeypatch.setattr(projection,"reset_bro_context_cache",lambda:calls.append("context"))
    monkeypatch.setattr(projection,"reset_trajectory_cache",lambda:calls.append("trajectory"))
    monkeypatch.setattr(projection,"reset_profile_values",lambda:calls.append("profile"))
    monkeypatch.setattr(projection,"reset_scoring_caches",lambda:calls.append("scoring"))
    monkeypatch.setattr(projection,"get_profile_values",lambda:{"x":1})
    projection.configure_engine()
    projection.reset_profile()
    assert calls==["perk","context","trajectory","profile","scoring"]
    assert projection.get_profile()=={"x":1}


def test_fit_curve_default_baseline_and_explicit_baseline():
    a=_fit_curve(100,None)
    b=_fit_curve(100,80)
    assert a[2]==[100.0,1.0]
    assert b[1]==[80.0,0.55]


def test_normalize_role_handles_target_and_non_fit_stat():
    r=_normalize_role({"name":"x","stats":{"MAtk":{"target":90},"Initiative":{}}})
    assert r["stats"]["MAtk"]["fit"] is True
    assert r["stats"]["Initiative"]["fit"] is False


def test_load_config_rejects_missing_roles_and_bad_classification(tmp_path):
    t=tmp_path/"t.json"; c=tmp_path/"c.json"
    t.write_text(json.dumps({"roles":[]}),encoding="utf-8")
    c.write_text("{}",encoding="utf-8")
    with pytest.raises(ValueError,match="No roles"): load_config(t,c)
    t.write_text(json.dumps({"roles":[{"name":"x","stats":{}}]}),encoding="utf-8")
    c.write_text("[]",encoding="utf-8")
    with pytest.raises(ValueError,match="Invalid classification"): load_config(t,c)


def test_context_cache_reset_and_overflow(monkeypatch):
    b=bro()
    context.reset_bro_context_cache()
    monkeypatch.setattr(context,"_BRO_CONTEXT_CACHE_MAX",0)
    result=context.bro_projection_context(b)
    assert result is context._BRO_CONTEXT_CACHE[context.bro_fingerprint(b)]
    context.reset_bro_context_cache()
    assert context._BRO_CONTEXT_CACHE=={}


def test_cli_missing_save_exits(tmp_path):
    missing=tmp_path/"missing.sav"
    with pytest.raises(SystemExit):
        parse_args([str(missing)])


def test_first_round_ranges_returns_exact_roll_ranges():
    b=bro(level_points=1,current_rolls={"HP":4,"MAtk":3})
    assert planner._first_round_ranges(b)=={"HP":(4,4),"MAtk":(3,3)}
