
import json
import struct
from pathlib import Path
import pytest

from bbtool.models import Brother
import bbtool.save_parser as sp
import bbtool.html_report as hr


def make_bro(name="Test Bro", level_points=0, current_rolls=None):
    return Brother(
        Name=name, Title="", Level=5, XP=1000, PerkPoints=0, PerksUsed=0, LevelPoints=level_points,
        AP=9, HP=70, HPStars=1, Fatigue=100, FatigueStars=2, Resolve=45, ResolveStars=0,
        Initiative=90, InitiativeStars=0, MAtk=70, MAtkStars=2, RAtk=40, RAtkStars=0,
        MDef=20, MDefStars=1, RDef=5, RDefStars=0, BackgroundID="BEEF", Background="Farmhand",
        PerkIDs=[], Perks=[], TraitIDs=[], Traits=[], Injuries=[], HumanOffset=0,
        CurrentRolls=current_rolls or {}, FutureRolls={}
    )


def base_role():
    return {
        "name": "Frontliner",
        "stats": {
            "HP": {"weight": 1, "target": 90},
            "MAtk": {"weight": 2, "target": 90},
            "MDef": {"weight": 2, "target": 35},
        },
    }


def base_fit(name="Test Bro"):
    return {
        "Name": name, "Role": "Frontliner",
        "ProjectedFit": 0.9, "ProjectedFitPct": 90.0,
        "ProjectedFitLikelyMinPct": 80.0, "ProjectedFitLikelyMaxPct": 100.0,
        "ProjectedFitFullMinPct": 70.0, "ProjectedFitFullMaxPct": 110.0,
        "FitFeasibilityPct": 40.0,
        "ProjectedComponents": {
            "HP": {"weight": 1}, "MAtk": {"weight": 2}, "MDef": {"weight": 2},
        },
        "ProjectedRanges": {
            "HP": {"p5": 80, "p95": 90, "min": 75, "max": 95, "ev": 85,
                   "baseline": 70, "target": 90, "weight": 1},
            "MAtk": {"p5": 80, "p95": 90, "min": 75, "max": 95, "ev": 85,
                     "baseline": 80, "target": 90, "weight": 2},
            "MDef": {"p5": 28, "p95": 35, "min": 25, "max": 38, "ev": 32,
                     "baseline": 25, "target": 35, "weight": 2},
        },
    }


def base_summary(name="Test Bro"):
    return {
        "Name": name, "Category": "Use", "BestRole": "Frontliner",
        "ProjectedFit": 0.9, "ProjectedFitPct": 90.0,
        "ProjectedFitLikelyMinPct": 80.0, "ProjectedFitLikelyMaxPct": 100.0,
        "ProjectedFitFullMinPct": 70.0, "ProjectedFitFullMaxPct": 110.0,
        "FitFeasibilityPct": 40.0, "ClassificationPaths": [],
        "SelectedClassificationPath": {}, "StructuralPerkAlternatives": [],
        "EffectiveStats": {},
    }


def class_cfg():
    return {
        "display": {"premium_fit": 1.1, "good_fit": 1.0, "viable_fit": 0.8},
        "thresholds": {
            "Invest": {"min_projected_fit": 1.0},
            "Use": {"min_projected_fit": 0.8},
            "Fodder": {"min_full_max_fit": 0.8},
        },
    }


def test_load_background_economy_valid_and_invalid(tmp_path):
    refs=tmp_path/"references"; refs.mkdir()
    p=refs/"backgrounds.json"
    p.write_text(json.dumps({"abcd":{"HiringCostBase":100,"DailyCostBase":7,"Script":"x"}}),encoding="utf-8")
    got=sp._load_background_economy(tmp_path)
    assert got["ABCD"]["HiringCostBase"]==100
    p.write_text("[]",encoding="utf-8")
    with pytest.raises(RuntimeError,match="invalid"): sp._load_background_economy(tmp_path)
    p.unlink()
    with pytest.raises(RuntimeError,match="missing"): sp._load_background_economy(tmp_path)


def test_load_item_economy_filters_unresolved_and_validates_format(tmp_path):
    refs=tmp_path/"references"; refs.mkdir()
    p=refs/"dictionary.json"
    p.write_text(json.dumps({"_meta":{"format":"bbtool.enriched_dictionary.v1"},"entries":{
        "abcd":{"Value":250,"SerializedLength":12,"name":"Sword","slot":"weapon"},
        "skip":{"Value":None,"SerializedLength":12},
        "skip2":{"Value":20,"SerializedLength":0},
    }}),encoding="utf-8")
    got=sp._load_item_economy(tmp_path)
    assert list(got)==["ABCD"] and got["ABCD"]["Value"]==250
    p.write_text("{}",encoding="utf-8")
    with pytest.raises(RuntimeError,match="not enriched"): sp._load_item_economy(tmp_path)


@pytest.mark.parametrize("typ,extra",[
    ("injury",14),("training",38),("knowledge",13),("learning",3),
    ("trait",1),("perk",1),("internal",1),("potion-effect",1),("permanentInjury",1),
])
def test_parse_tail_entries_known_types(typ, extra):
    item=bytes.fromhex("01020304")
    b=item+b"\x00"*extra
    refs={"01020304":{"type":typ}}
    got=sp._parse_tail_entries(b,0,1,len(b),refs,{})
    assert got==[{"id":"01020304","type":typ,"extra":extra}]


def test_parse_tail_entries_unknown_backtracks_memo_and_failures():
    item=bytes.fromhex("01020304")
    b=item+b"\x00"*14
    memo={}
    got=sp._parse_tail_entries(b,0,1,len(b),{},memo)
    assert got[0]["type"]=="unknown" and got[0]["extra"]==14
    assert sp._parse_tail_entries(b,0,1,len(b),{},memo) is got
    assert sp._parse_tail_entries(b,0,0,0,{}, {})==[]
    assert sp._parse_tail_entries(b,0,0,1,{}, {}) is None
    assert sp._parse_tail_entries(b,0,1,3,{}, {}) is None


def _lp(text):
    raw=text.encode("utf-8")
    return struct.pack("<H",len(raw))+raw


def test_find_circle_metadata_minimal_valid_and_no_background():
    refs={
        "A1B2C3D4":{"type":"background","name":"Farmhand"},
        "01020304":{"type":"perk","name":"Colossus"},
    }
    stats_end=0
    block=bytearray()
    block+=struct.pack("<H",2)
    block+=bytes.fromhex("01020304")+b"\x00"
    block+=bytes.fromhex("A1B2C3D4")+b"\x00"
    block+=_lp("desc")+_lp("templ")
    block+=bytes([1,0])
    block+=struct.pack("<f",1.0)
    identity=len(block)
    got=sp.find_circle_metadata(bytes(block),stats_end,identity,refs)
    assert got["Background"]=="Farmhand"
    assert got["Perks"]==["Colossus"]
    assert got["Traits"]==[]
    assert sp.find_circle_metadata(bytes(block),0,identity,{}) is None


def test_html_helpers_cover_edges():
    assert "left:0.00%" in hr.fit_uncertainty_track({
        "ProjectedFitPct":-20,"ProjectedFitLikelyMinPct":150,"ProjectedFitLikelyMaxPct":-5
    })
    assert hr.public_value(None)=="—"
    assert hr.structural_detail_html(make_bro(),{"BestRoleDetail":None},[base_role()],{})==""
    assert "role-card" in hr.structural_detail_html(make_bro(),{
        "BestRoleDetail":base_fit(),"Role":"Frontliner","Label":"Colossus","Category":"Use",
        "EffectiveStats":{}
    },[base_role()],{})

    fodder_fit = base_fit()
    fodder_fit.update(ProjectedFit=0.516, ProjectedFitPct=51.6, ProjectedFitFullMaxPct=68.0)
    fodder_card = hr.structural_detail_html(make_bro(), {
        "BestRoleDetail":fodder_fit,"Role":"Frontliner","Label":"Base","Category":"Fodder",
        "EffectiveStats":{}
    },[base_role()],{"thresholds":{"Fodder":{"min_full_max_fit":0.65}}})
    assert 'Full ceiling <b>68.0%</b> · can reach Use (65.0%)' in fodder_card


@pytest.mark.parametrize("value,expected",[
    (110,"heat5"),(100,"heat5"),(90,"heat5"),(80,"heat4"),(70,"heat4")
])
def test_heat_bands(value,expected):
    assert hr.heat(value)==expected


def test_pretty_html_indents_void_self_closing_and_closing_tags():
    src="<html><body><div><span>x</span><br><img src='x'/></div></body></html>"
    out=hr.pretty_html(src)
    assert out.endswith("\n")
    assert "\n  <body>" in out
    assert "<br>" in out and "<img" in out


def test_recruit_rendering_all_tryout_states_and_grouping():
    recs=[
        {"Settlement":"A","Name":"One","Title":"","Level":1,"Background":"Beggar","Traits":[],"TryoutDone":True,"HireCost":100,"DailyWage":5},
        {"Settlement":"A","Name":"Two","Title":"X","Level":2,"Background":"Farmhand","Traits":["Strong"],"TryoutDone":False,"HireCost":200,"DailyWage":8},
        {"Settlement":"B","Name":"Three","Title":None,"Level":None,"Background":None,"Traits":[],"TryoutDone":None,"HireCost":None,"DailyWage":None},
    ]
    rows=hr.recruit_table_rows(recs)
    assert "traits-revealed" in rows and "traits-hidden" in rows and "traits-unknown" in rows
    panels=hr.recruit_settlement_panels(recs)
    assert panels.count("settlement-panel")>=2 and "2 candidates" in panels and "1 candidate" in panels


def test_render_html_report_minimal_full_document():
    b=make_bro()
    fit=base_fit()
    summary=base_summary()
    html=hr.render_html_report(Path("my save.sav"),[b],[fit],[summary],[base_role()],class_cfg(),generated_at="now")
    assert "my save — Battle Brothers Report" in html
    assert 'data-tab-panel="roster"' in html
    assert 'data-tab-panel="management"' in html
    assert 'data-tab-panel="recruits"' in html
    assert "No level-ups are currently available." in html
    assert "Frontliner" in html


def test_render_html_report_levelup_and_structural_path(monkeypatch):
    b=make_bro(level_points=1,current_rolls={"HP":3,"MAtk":3,"MDef":2})
    fit=base_fit()
    summary=base_summary()
    summary["ClassificationPaths"]=[
        {"Label":"Base","Role":"Frontliner","Category":"Use","ProjectedFitPct":90,
         "ProjectedFitLikelyMinPct":80,"ProjectedFitLikelyMaxPct":100,
         "ProjectedFitFullMinPct":70,"ProjectedFitFullMaxPct":110,"FitFeasibilityPct":40}
    ]
    summary["SelectedClassificationPath"]=summary["ClassificationPaths"][0].copy()
    summary["StructuralPerkAlternatives"]=[{
        "Label":"Colossus","Role":"Frontliner","Category":"Use",
        "ProjectedFitPct":95,"FitFeasibilityPct":50,"BestRoleDetail":base_fit(),"EffectiveStats":{}
    }]
    monkeypatch.setattr(hr,"levelup_bro_panel",lambda *a,**k:"<div>LEVELUP PANEL</div>")
    html=hr.render_html_report(Path("x.sav"),[b],[fit],[summary],[base_role()],class_cfg(),recruits=[
        {"Settlement":"Town","Name":"Hire","Title":"","Level":1,"Background":"Beggar","Traits":[],"TryoutDone":False,"HireCost":100,"DailyWage":5}
    ])
    assert "LEVELUP PANEL" in html
    assert "COLOSSUS" in html
    assert "selected-path-row" in html
    assert "Hire" in html
