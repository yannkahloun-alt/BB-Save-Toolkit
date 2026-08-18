from dataclasses import replace
import pytest
pytestmark=pytest.mark.unit
from bbtool.projection.trajectory import project_fit_trajectory, project_seeded_fit_trajectory, reset_trajectory_cache
from bbtool.projection.progression import gain_range
from bbtool.projection.runtime import reset_profile_values,get_profile_values
from bbtool.models import STATS


def _first_pick(res): return tuple(res.get('trace',[{}])[0].get('picks',[])) if res.get('trace') else ()

def test_high_roll_weak_stat_can_lose_to_medium_important_stat(bro_factory,simple_role):
    role=simple_role(('HP','Fatigue','Resolve','MAtk'),weights={'HP':.1,'Fatigue':2,'Resolve':2,'MAtk':5},baselines={'HP':40,'Fatigue':50,'Resolve':20,'MAtk':40},targets={'HP':200,'Fatigue':120,'Resolve':80,'MAtk':90})
    b=bro_factory(Level=10)
    rr=[{'HP':(4,4),'Fatigue':(3,3),'Resolve':(3,3),'MAtk':(2,2)}]
    r=project_fit_trajectory(b,role,rounds=1,round_ranges=rr,samples=1,include_trace=True)
    assert 'HP' not in _first_pick(r)


def test_baseline_change_can_change_pick(bro_factory,simple_role):
    b=bro_factory(Level=10,HP=60,Fatigue=60,Resolve=60,MAtk=60)
    rr=[{s:(2,2) for s in ('HP','Fatigue','Resolve','MAtk')}]
    a=simple_role(('HP','Fatigue','Resolve','MAtk'),baselines={'HP':0,'Fatigue':0,'Resolve':0,'MAtk':59},targets={s:100 for s in ('HP','Fatigue','Resolve','MAtk')})
    c=simple_role(('HP','Fatigue','Resolve','MAtk'),baselines={'HP':59,'Fatigue':0,'Resolve':0,'MAtk':0},targets={s:100 for s in ('HP','Fatigue','Resolve','MAtk')})
    pa=_first_pick(project_fit_trajectory(b,a,rounds=1,round_ranges=rr,samples=1,include_trace=True))
    pc=_first_pick(project_fit_trajectory(b,c,rounds=1,round_ranges=rr,samples=1,include_trace=True))
    assert pa!=pc


def test_target_change_can_change_pick(bro_factory,simple_role):
    b=bro_factory(Level=10,HP=60,Fatigue=60,Resolve=60,MAtk=60)
    rr=[{s:(2,2) for s in ('HP','Fatigue','Resolve','MAtk')}]
    a=simple_role(('HP','Fatigue','Resolve','MAtk'),targets={'HP':61,'Fatigue':100,'Resolve':100,'MAtk':100},baselines={s:0 for s in ('HP','Fatigue','Resolve','MAtk')})
    c=simple_role(('HP','Fatigue','Resolve','MAtk'),targets={'HP':100,'Fatigue':61,'Resolve':100,'MAtk':100},baselines={s:0 for s in ('HP','Fatigue','Resolve','MAtk')})
    assert _first_pick(project_fit_trajectory(b,a,rounds=1,round_ranges=rr,samples=1,include_trace=True)) != _first_pick(project_fit_trajectory(b,c,rounds=1,round_ranges=rr,samples=1,include_trace=True))


def test_future_probabilistic_ranges_can_change_lookahead_without_future_oracle(bro_factory,simple_role):
    role=simple_role(('HP','Fatigue','Resolve','MAtk'),weights={'HP':1,'Fatigue':1,'Resolve':1,'MAtk':1},baselines={s:0 for s in ('HP','Fatigue','Resolve','MAtk')},targets={s:100 for s in ('HP','Fatigue','Resolve','MAtk')})
    b=bro_factory(Level=9,FutureRolls={s:[99,99] for s in STATS})
    first={s:(2,2) for s in ('HP','Fatigue','Resolve','MAtk')}
    low=[first,{'HP':(1,1),'Fatigue':(4,4),'Resolve':(4,4),'MAtk':(3,3)}]
    high=[first,{'HP':(4,4),'Fatigue':(2,2),'Resolve':(2,2),'MAtk':(1,1)}]
    r1=project_fit_trajectory(b,role,rounds=2,round_ranges=low,samples=1,include_trace=True)
    r2=project_fit_trajectory(b,role,rounds=2,round_ranges=high,samples=1,include_trace=True)
    # supplied future ranges are legitimate explicit inputs and can alter the projected final result.
    assert r1['expected_pct'] != r2['expected_pct']
    p1=_first_pick(r1)
    b2=replace(b,FutureRolls={s:[1,1] for s in STATS})
    assert _first_pick(project_fit_trajectory(b2,role,rounds=2,round_ranges=low,samples=1,include_trace=True))==p1


def test_cache_reset_returns_to_miss_and_cached_result_identical(bro_factory,simple_role):
    b=bro_factory(Level=10); role=simple_role(('MAtk','MDef','HP','Fatigue'))
    reset_trajectory_cache(); reset_profile_values()
    a=project_fit_trajectory(b,role,rounds=1,samples=16)
    p1=get_profile_values().copy()
    bres=project_fit_trajectory(b,role,rounds=1,samples=16)
    p2=get_profile_values().copy()
    assert a==bres and p2['trajectory_cache_hits']>p1['trajectory_cache_hits']
    reset_trajectory_cache(); reset_profile_values(); c=project_fit_trajectory(b,role,rounds=1,samples=16)
    assert c==a and get_profile_values()['trajectory_cache_misses']>=1


def test_seeded_trace_fit_and_choices_equal_explicit_degenerate_ranges(bro_factory,simple_role):
    role=simple_role(('MAtk','MDef','HP','Fatigue')); b=bro_factory(Level=10)
    fut={s:[gain_range(s,getattr(b,s+'Stars'))[0]] for s in STATS}; b.FutureRolls=fut
    seeded=project_seeded_fit_trajectory(b,role)
    rr=[{s:(v[0],v[0]) for s,v in fut.items()}]
    direct=project_fit_trajectory(b,role,rounds=1,round_ranges=rr,samples=1,include_trace=True)
    assert seeded['fit_pct']==direct['expected_pct']
    assert seeded['choices']==direct['trace']
