
import json

from bbtool.models import Brother
import bbtool.projection.trajectory as tr
import bbtool.app.output as out


def make_bro(name="A"):
    return Brother(
        Name=name,Title="",Level=5,XP=0,PerkPoints=0,PerksUsed=0,LevelPoints=0,
        AP=9,HP=70,HPStars=0,Fatigue=100,FatigueStars=0,Resolve=40,ResolveStars=0,
        Initiative=90,InitiativeStars=0,MAtk=70,MAtkStars=0,RAtk=40,RAtkStars=0,
        MDef=20,MDefStars=0,RDef=5,RDefStars=0,BackgroundID="",Background="",
        PerkIDs=[],Perks=[],TraitIDs=[],Traits=[],Injuries=[],HumanOffset=0,
        CurrentRolls={},FutureRolls={}
    )


def test_compare_fit_trajectories_win_loss_tie_paths(monkeypatch):
    bro=make_bro()
    role={"name":"x","stats":{"MAtk":{"fit":True}}}
    monkeypatch.setattr(tr,"development_rounds_to_11",lambda b:1)
    monkeypatch.setattr(tr,"_fit_stats",lambda r:["MAtk"])
    monkeypatch.setattr(tr,"_sample_coordinates",lambda samples,dimensions:[[0.1],[0.2],[0.3]])
    monkeypatch.setattr(tr,"_projection_context",lambda *a,**k:([1],None,None,None,None,None,None,None,None,None))
    seq=iter([(10,{}),(20,{}),(20,{}),(10,{}),(15,{}),(15,{})])
    monkeypatch.setattr(tr,"_simulate_one",lambda *a,**k:next(seq))
    got=tr.compare_fit_trajectories(bro,bro,role,samples=3)
    assert got["alternative_beats_primary_pct"]==33.3
    assert got["primary_beats_alternative_pct"]==33.3
    assert got["tie_pct"]==33.3
    assert got["avg_upside_when_wins_pct"]==10.0
    assert got["avg_downside_when_loses_pct"]==10.0
    assert got["sample_count"]==3


def test_compare_fit_trajectories_no_wins_or_losses(monkeypatch):
    bro=make_bro()
    role={"name":"x","stats":{"MAtk":{"fit":True}}}
    monkeypatch.setattr(tr,"_fit_stats",lambda r:["MAtk"])
    monkeypatch.setattr(tr,"_sample_coordinates",lambda samples,dimensions:[[0.1]])
    monkeypatch.setattr(tr,"_projection_context",lambda *a,**k:([1],None,None,None,None,None,None,None,None,None))
    monkeypatch.setattr(tr,"_simulate_one",lambda *a,**k:(10,{}))
    got=tr.compare_fit_trajectories(bro,bro,role,rounds=0,samples=1)
    assert got["tie_pct"]==100.0
    assert got["avg_upside_when_wins_pct"]==0.0
    assert got["avg_downside_when_loses_pct"]==0.0


def workspace(tmp_path):
    root=tmp_path/"run"; root.mkdir()
    src=tmp_path/"save.sav"; src.write_bytes(b"x")
    return out.RunWorkspace(root=root,base="save",generated_at="now",source_save=src)


def test_write_projection_validation(monkeypatch,tmp_path):
    ws=workspace(tmp_path)
    monkeypatch.setattr(out,"build_projection_validation",lambda *a:{
        "summary":{"x":1},"roll_luck_to_level11":{"A":50},"rows":[{"a":1}],
        "roll_range_violations":[]
    })
    path=out.write_projection_validation(ws,[],[],[])
    payload=json.loads(path.read_text(encoding="utf-8"))
    assert payload["_meta"]["format"]=="bbtool.projection_validation.v3"
    assert payload["summary"]=={"x":1}


def test_write_debug_bundle(tmp_path):
    ws=workspace(tmp_path)
    path=out.write_debug_bundle(
        ws,[make_bro()],[],[{"Role":"x"}],[{"Name":"A"}],[{"name":"x"}],
        {"thresholds":{}},{"dictionary":True},{"calls":1}
    )
    payload=json.loads(path.read_text(encoding="utf-8"))
    assert payload["_meta"]["format"]=="bbtool.debug_bundle.v1"
    assert payload["roster"][0]["Name"]=="A"
    assert payload["runtime"]["projection_profile"]=={"calls":1}


def test_write_html_copies_assets_and_writes_report(monkeypatch,tmp_path):
    ws=workspace(tmp_path)
    monkeypatch.setattr(out,"render_html_report",lambda *a,**k:"<html>ok</html>")
    path=out.write_html(ws,[],[],[],[],[],{})
    assert path.read_text(encoding="utf-8")=="<html>ok</html>"
    assert (ws.root/"report.css").is_file()
    assert (ws.root/"report.js").is_file()


def test_archive_workspace_includes_files(tmp_path):
    ws=workspace(tmp_path)
    (ws.root/"x.txt").write_text("x",encoding="utf-8")
    path=out.archive_workspace(ws,tmp_path)
    assert path.is_file()
