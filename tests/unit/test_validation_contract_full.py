import pytest
pytestmark=pytest.mark.unit
from bbtool.app import output
from bbtool.models import STATS


def test_empirical_percentile_512_and_2048_sample_counts():
    for n in (512,2048):
        pct,count=output._empirical_percentile(list(range(n)), n//2)
        assert count==n and pct is not None


def test_inside_likely_and_full_boundaries_are_inclusive(monkeypatch,bro_factory,simple_role):
    role=simple_role(('MAtk',)); b=bro_factory(Level=11,FutureRolls={s:[] for s in STATS})
    monkeypatch.setattr(output,'project_seeded_fit_trajectory',lambda b,r:{'fit_pct':50.0,'rounds':0,'choices':[]})
    monkeypatch.setattr(output,'_blind_projection_for_validation',lambda b,r:{'_outcomes_pct':(50.0,)})
    fit={'Name':b.Name,'Role':role['name'],'ProjectedFitPct':50,'ProjectedFitLikelyMinPct':50,'ProjectedFitLikelyMaxPct':50,'ProjectedFitFullMinPct':50,'ProjectedFitFullMaxPct':50,'FitFeasibilityPct':0}
    row=output.build_projection_validation([b],[fit],[role])['rows'][0]
    assert row['InsideLikelyRange'] and row['InsideFullRange']


def test_seeded_reached_100_boundary(monkeypatch,bro_factory,simple_role):
    role=simple_role(('MAtk',)); b=bro_factory(Level=11,FutureRolls={s:[] for s in STATS})
    monkeypatch.setattr(output,'project_seeded_fit_trajectory',lambda b,r:{'fit_pct':100.0,'rounds':0,'choices':[]})
    monkeypatch.setattr(output,'_blind_projection_for_validation',lambda b,r:{'_outcomes_pct':(100.0,)})
    fit={'Name':b.Name,'Role':role['name'],'ProjectedFitPct':100,'ProjectedFitLikelyMinPct':99,'ProjectedFitLikelyMaxPct':101,'ProjectedFitFullMinPct':98,'ProjectedFitFullMaxPct':102,'FitFeasibilityPct':50}
    assert output.build_projection_validation([b],[fit],[role])['rows'][0]['SeededReached100']


def test_validation_summary_exact_aggregates(monkeypatch,bro_factory,simple_role):
    role=simple_role(('MAtk',)); bros=[bro_factory(Name='A',Level=11,FutureRolls={s:[] for s in STATS}),bro_factory(Name='B',Level=11,FutureRolls={s:[] for s in STATS})]
    vals=iter([40.0,60.0]); monkeypatch.setattr(output,'project_seeded_fit_trajectory',lambda b,r:{'fit_pct':next(vals),'rounds':0,'choices':[]})
    monkeypatch.setattr(output,'_blind_projection_for_validation',lambda b,r:{'_outcomes_pct':tuple(range(101))})
    fits=[{'Name':x.Name,'Role':role['name'],'ProjectedFitPct':50,'ProjectedFitLikelyMinPct':45,'ProjectedFitLikelyMaxPct':55,'ProjectedFitFullMinPct':30,'ProjectedFitFullMaxPct':70,'FitFeasibilityPct':0} for x in bros]
    s=output.build_projection_validation(bros,fits,[role])['summary']
    assert s['comparisons']==2 and s['inside_likely']==0 and s['inside_full']==2 and s['mean_abs_delta_vs_expected']==10 and s['max_abs_delta_vs_expected']==10


def test_validation_summary_contains_every_required_metric(monkeypatch,bro_factory,simple_role):
    role=simple_role(('MAtk',)); b=bro_factory(Level=11,FutureRolls={s:[] for s in STATS})
    monkeypatch.setattr(output,'project_seeded_fit_trajectory',lambda b,r:{'fit_pct':50,'rounds':0,'choices':[]})
    monkeypatch.setattr(output,'_blind_projection_for_validation',lambda b,r:{'_outcomes_pct':(40,50,60)})
    fit={'Name':b.Name,'Role':role['name'],'ProjectedFitPct':50,'ProjectedFitLikelyMinPct':45,'ProjectedFitLikelyMaxPct':55,'ProjectedFitFullMinPct':40,'ProjectedFitFullMaxPct':60,'FitFeasibilityPct':0}
    s=output.build_projection_validation([b],[fit],[role])['summary']
    required={'comparisons','inside_likely','inside_likely_pct','inside_full','inside_full_pct','mean_abs_delta_vs_expected','max_abs_delta_vs_expected','actual_percentile_mean','relevant_roll_rank_mean','roll_range_violations'}
    assert required<=s.keys()


def test_luck_high_maps_to_high_actual_percentile_and_low_to_low_in_controlled_validation(monkeypatch,bro_factory,simple_role):
    role=simple_role(('MAtk',)); role['stats']['MAtk']['weight']=5
    bros=[bro_factory(Name='Hi',Level=10,MAtkStars=0,FutureRolls={s:[3] for s in STATS}),bro_factory(Name='Lo',Level=10,MAtkStars=0,FutureRolls={s:[1] for s in STATS})]
    vals={'Hi':90.0,'Lo':10.0}; monkeypatch.setattr(output,'project_seeded_fit_trajectory',lambda b,r:{'fit_pct':vals[b.Name],'rounds':1,'choices':[]})
    monkeypatch.setattr(output,'_blind_projection_for_validation',lambda b,r:{'_outcomes_pct':tuple(range(101))})
    fits=[{'Name':b.Name,'Role':role['name'],'ProjectedFitPct':50,'ProjectedFitLikelyMinPct':5,'ProjectedFitLikelyMaxPct':95,'ProjectedFitFullMinPct':0,'ProjectedFitFullMaxPct':100,'FitFeasibilityPct':0} for b in bros]
    rows={r['Name']:r for r in output.build_projection_validation(bros,fits,[role])['rows']}
    assert rows['Hi']['RelevantRollRankPct']>50 and rows['Hi']['ActualPercentilePct']>50
    assert rows['Lo']['RelevantRollRankPct']<50 and rows['Lo']['ActualPercentilePct']<50
