
import bbtool.levelup_advisor as adv


def fake_traj(bro, role, rounds):
    score=float(bro.MAtk+bro.MDef+bro.HP)
    return {"expected_pct":score,"full_min_pct":score-1,"full_max_pct":score+1,
            "likely_min_pct":score-1,"likely_max_pct":score+1,"feasibility_pct":50.0}


def base():
    return {"Role":"R","ProjectedFit":0.5,"ProjectedFitPct":50.0,
            "FitFeasibilityPct":0.0,"ProjectedFitLikelyMinPct":40.0}


def role():
    return {"name":"R","stats":{"MAtk":{"fit":True,"weight":2},"Fatigue":{"weight":1}}}


def test_roll_quality_degenerate_range(monkeypatch,bro_factory):
    monkeypatch.setattr(adv,"gain_range",lambda *a:(3,3))
    assert adv._roll_quality(bro_factory(),"HP",3)==1.0


def test_skipped_notes_ignores_zero_weight_noncore(bro_factory):
    r={"stats":{"HP":{"fit":False,"weight":0},"Fatigue":{"fit":False,"weight":1}}}
    rolls={"HP":adv._roll_band(bro_factory(),"HP",3),"Fatigue":adv._roll_band(bro_factory(),"Fatigue",3)}
    notes=adv._skipped_important_notes(r,{"Stats":[]},rolls)
    assert [n["Stat"] for n in notes]==["Fatigue"]
    assert "role weight 1" in notes[0]["Reason"]


def test_advisor_no_legal_combinations_returns_none(monkeypatch,bro_factory):
    monkeypatch.setattr(adv,"project_fit_trajectory",fake_traj)
    b=bro_factory(LevelPoints=1,CurrentRolls={"Foo":1,"Bar":2,"Baz":3})
    assert adv.advise_levelup(b,[role()],[base()]) is None


def test_advisor_exactly_one_combo_has_no_alternative(monkeypatch,bro_factory):
    monkeypatch.setattr(adv,"project_fit_trajectory",fake_traj)
    b=bro_factory(LevelPoints=1,CurrentRolls={"HP":4,"MAtk":3,"MDef":3})
    out=adv.advise_levelup(b,[role()],[base()])
    assert out["Alternative"] is None
    assert out["DistinctFitDecisionsEvaluated"]==1


def test_advisor_equal_expected_uses_non_gamble_comparison(monkeypatch,bro_factory):
    monkeypatch.setattr(adv,"project_fit_trajectory",lambda *a,**k:{
        "expected_pct":75.0,"full_min_pct":70.0,"full_max_pct":80.0,
        "likely_min_pct":72.0,"likely_max_pct":78.0,"feasibility_pct":20.0})
    b=bro_factory(LevelPoints=1,CurrentRolls={"HP":4,"Fatigue":3,"MAtk":3,"MDef":3})
    r=role()
    r["stats"]={stat:{"fit":True,"weight":1} for stat in ("HP","Fatigue","MAtk","MDef")}
    out=adv.advise_levelup(b,[r],[base()])
    assert out["Alternative"] is not None
    assert out["Alternative"]["Gamble"]["Samples"]==0
    assert out["Alternative"]["Gamble"]["IsGamble"] is False


def test_pick_reason_fit_neutral_role_and_unconfigured(monkeypatch,bro_factory):
    # Force equal trajectories so deterministic combo order includes HP/Fatigue/Resolve.
    monkeypatch.setattr(adv,"project_fit_trajectory",lambda *a,**k:{
        "expected_pct":75.0,"full_min_pct":70.0,"full_max_pct":80.0,
        "likely_min_pct":72.0,"likely_max_pct":78.0,"feasibility_pct":20.0})
    b=bro_factory(LevelPoints=1,CurrentRolls={"HP":4,"Fatigue":3,"Resolve":3})
    out=adv.advise_levelup(b,[role()],[base()])
    assert out["FreePickMode"] is True
    assert "Fit-neutral role stat" in out["PickReasons"]["Fatigue"]
    assert "Fit-neutral" in out["PickReasons"]["Resolve"]
