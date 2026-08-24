from bbtool.models import Brother
import bbtool.app.analysis as analysis
import bbtool.app.output as output
from bbtool.html_report import bro_anchor


def make_bro(name, offset):
    return Brother(
        Name=name, Title="", Level=1, XP=0, PerkPoints=0, PerksUsed=0,
        LevelPoints=0, AP=9,
        HP=60, HPStars=0, Fatigue=100, FatigueStars=0,
        Resolve=40, ResolveStars=0, Initiative=100, InitiativeStars=0,
        MAtk=50, MAtkStars=0, RAtk=40, RAtkStars=0,
        MDef=0, MDefStars=0, RDef=0, RDefStars=0,
        BackgroundID="BG", Background="Test",
        PerkIDs=[], Perks=[], TraitIDs=[], Traits=[], Injuries=[],
        HumanOffset=offset,
    )


def test_duplicate_names_have_distinct_brother_ids():
    a = make_bro("Same", 100)
    b = make_bro("Same", 200)
    assert a.Name == b.Name
    assert a.BrotherID == "human:100"
    assert b.BrotherID == "human:200"
    assert a.BrotherID != b.BrotherID
    assert bro_anchor(a.BrotherID) != bro_anchor(b.BrotherID)


def test_public_roster_contains_brother_id():
    bro = make_bro("Display", 12345)
    row = output._public_bro_dict(bro)
    assert row["BrotherID"] == "human:12345"
    assert row["Name"] == "Display"


def test_analysis_fit_row_contains_brother_id(monkeypatch):
    bro = make_bro("Same", 314)
    role = {"name": "Role", "stats": {}}
    projection = {
        "Role": "Role", "ProjectedFit": 1.0, "ProjectedFitPct": 100.0,
        "FitFeasibilityPct": 100.0,
        "ProjectedFitLikelyMinPct": 100.0, "ProjectedFitLikelyMaxPct": 100.0,
        "ProjectedFitFullMinPct": 100.0, "ProjectedFitFullMaxPct": 100.0,
        "MAtk": 50, "MDef": 0, "RAtk": 40, "HP": 60, "Fatigue": 100, "Resolve": 40,
    }
    monkeypatch.setattr(analysis, "project_role", lambda b, r: dict(projection))
    monkeypatch.setattr(analysis, "perk_compatibility", lambda b, r: ("ok", 0.0, []))
    row = analysis._role_row(bro, role)
    assert row["BrotherID"] == "human:314"
    assert row["Name"] == "Same"
