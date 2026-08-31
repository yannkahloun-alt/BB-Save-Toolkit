from dataclasses import replace
import pytest
pytestmark=[pytest.mark.unit, pytest.mark.coverage_slow]
from bbtool.levelup_advisor import advise_levelup,_roll_quality,_roll_band
from bbtool.projection.planner import project_role

def rows(b,cfg): return [project_role(b,r) for r in cfg.roles]
def current(): return {'HP':4,'Fatigue':3,'Resolve':3,'Initiative':4,'MAtk':2,'RAtk':3,'MDef':3,'RDef':3}
def test_no_current_or_no_points_none(cfg,bro_factory):
    # Both guards run before role projections are consumed.
    b=bro_factory(LevelPoints=1); assert advise_levelup(b,cfg.roles,[]) is None
    b=bro_factory(LevelPoints=0,CurrentRolls=current()); assert advise_levelup(b,cfg.roles,[]) is None
def test_advisor_evaluates_only_eligible_combinations(cfg,bro_factory):
    b=bro_factory(Level=10,LevelPoints=1,CurrentRolls=current()); a=advise_levelup(b,cfg.roles,rows(b,cfg)); eligible=a['AdvisorEligibleStats']; assert a['CombinationsEvaluated']==len(tuple(__import__('itertools').combinations(eligible,3))); assert len(a['Recommended']['Stats'])==3; assert set(a['Recommended']['Stats'])<=set(eligible); assert a['Recommended']['Stats']!=a['Alternative']['Stats']; assert a['Recommended']['AnchorFitAfterPct']>=a['Alternative']['AnchorFitAfterPct']
def test_advisor_deterministic(cfg,bro_factory):
    b=bro_factory(Level=10,LevelPoints=1,CurrentRolls=current()); a=advise_levelup(b,cfg.roles,rows(b,cfg)); c=advise_levelup(b,cfg.roles,rows(b,cfg)); assert a['Recommended']['Stats']==c['Recommended']['Stats']
def test_current_roll_change_can_change_advice(bro_factory,simple_role):
    role=simple_role(('HP','Fatigue','Resolve','RAtk'), weights={'HP':1,'Fatigue':1,'Resolve':1,'RAtk':1})
    base={'Role':role['name'],'ProjectedFit':.5,'ProjectedFitPct':50,'FitFeasibilityPct':0,'ProjectedFitLikelyMinPct':40}
    cr={'HP':4,'Fatigue':2,'Resolve':2,'RAtk':2}
    b=bro_factory(Level=10,LevelPoints=1,CurrentRolls=cr,HP=60,Fatigue=60,Resolve=60,RAtk=60)
    a=advise_levelup(b,[role],[base]); cr2=dict(cr,HP=2,RAtk=4); c=replace(b,CurrentRolls=cr2); z=advise_levelup(c,[role],[base])
    assert a['Recommended']['Stats']!=z['Recommended']['Stats']
@pytest.mark.parametrize('stat,roll,label',[('MAtk',1,'MIN'),('MAtk',2,'AVG'),('MAtk',3,'MAX'),('Initiative',3,'MIN'),('Initiative',4,'AVG'),('Initiative',5,'MAX')])
def test_roll_band_labels(bro_factory,stat,roll,label): assert _roll_band(bro_factory(),stat,roll)['Label']==label
def test_roll_quality_bounds(bro_factory): assert _roll_quality(bro_factory(),'MAtk',1)==0; assert _roll_quality(bro_factory(),'MAtk',3)==1
