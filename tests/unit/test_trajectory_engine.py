from dataclasses import replace
import pytest
pytestmark=pytest.mark.unit
from bbtool.models import STATS
from bbtool.projection.trajectory import project_fit_trajectory, project_seeded_fit_trajectory, reset_trajectory_cache, _needs_refinement
from bbtool.projection.runtime import reset_profile_values, get_profile_values

def exact(stats, vals, rounds=1): return [{s:(vals.get(s,2),vals.get(s,2)) for s in stats} for _ in range(rounds)]

def test_zero_rounds_is_current_fit(bro_factory,simple_role):
    b=bro_factory(MAtk=100); r=simple_role(('MAtk',)); x=project_fit_trajectory(b,r,rounds=0,samples=1); assert x['expected_pct']==100
@pytest.mark.parametrize('stats',[('MAtk',),('MAtk','MDef'),('MAtk','MDef','HP'),('MAtk','MDef','HP','Fatigue')])
def test_one_to_four_fit_stats(stats,bro_factory,simple_role):
    b=bro_factory(MAtk=60,MDef=60,HP=60,Fatigue=60); r=simple_role(stats); x=project_fit_trajectory(b,r,rounds=1,samples=8); assert x['fit_stats']==[s for s in STATS if s in stats]; assert x['full_min_pct']<=x['expected_pct']<=x['full_max_pct']
def test_four_equal_stats_picks_three(bro_factory,simple_role):
    stats=('HP','Fatigue','Resolve','RAtk'); b=bro_factory(HP=60,Fatigue=60,Resolve=60,RAtk=60); r=simple_role(stats); x=project_fit_trajectory(b,r,rounds=1,round_ranges=exact(stats,{s:2 for s in stats}),samples=1,include_trace=True); assert len(x['trace'][0]['picks'])==3
def test_saturated_stat_loses_priority(bro_factory,simple_role):
    stats=('HP','Fatigue','Resolve','RAtk'); b=bro_factory(HP=120,Fatigue=60,Resolve=60,RAtk=60); r=simple_role(stats); x=project_fit_trajectory(b,r,rounds=1,round_ranges=exact(stats,{s:2 for s in stats}),samples=1,include_trace=True); assert 'HP' not in x['trace'][0]['picks']
def test_weight_changes_pick(bro_factory,simple_role):
    stats=('HP','Fatigue','Resolve','RAtk'); b=bro_factory(HP=60,Fatigue=60,Resolve=60,RAtk=60); rr=exact(stats,{'HP':2,'Fatigue':2,'Resolve':2,'RAtk':2}); r=simple_role(stats,weights={'HP':10}); x=project_fit_trajectory(b,r,rounds=1,round_ranges=rr,samples=1,include_trace=True); assert 'HP' in x['trace'][0]['picks']
def test_forced_first_combo_respected(bro_factory,simple_role):
    stats=('HP','Fatigue','Resolve','RAtk'); b=bro_factory(HP=60,Fatigue=60,Resolve=60,RAtk=60); r=simple_role(stats); forced=('HP','Fatigue','Resolve'); x=project_fit_trajectory(b,r,rounds=1,round_ranges=exact(stats,{s:2 for s in stats}),forced_first_combo=forced,samples=1,include_trace=True); assert tuple(x['trace'][0]['picks'])==forced
def test_trace_flag_does_not_change_numbers(bro_factory,simple_role):
    b=bro_factory(); r=simple_role(('MAtk','MDef','HP','Fatigue')); a=project_fit_trajectory(b,r,rounds=2,samples=32,include_trace=False); c=project_fit_trajectory(b,r,rounds=2,samples=32,include_trace=True); keys=['expected_pct','full_min_pct','full_max_pct','likely_min_pct','likely_max_pct','feasibility_pct']; assert all(a[k]==c[k] for k in keys)
def test_degenerate_single_sample_collapses(bro_factory,simple_role):
    stats=('MAtk',); b=bro_factory(MAtk=60); r=simple_role(stats); x=project_fit_trajectory(b,r,rounds=1,round_ranges=exact(stats,{'MAtk':3}),samples=1); assert len({x[k] for k in ['expected_pct','full_min_pct','full_max_pct','likely_min_pct','likely_max_pct']})==1
def test_range_invariants(bro_factory,simple_role):
    b=bro_factory(); r=simple_role(('MAtk','MDef','HP','Fatigue')); x=project_fit_trajectory(b,r,rounds=3,samples=64); assert x['full_min_pct']<=x['likely_min_pct']<=x['likely_max_pct']<=x['full_max_pct']; assert x['full_min_pct']<=x['expected_pct']<=x['full_max_pct']; assert 0<=x['feasibility_pct']<=100
def test_feasibility_extremes(bro_factory,simple_role):
    r=simple_role(('MAtk',)); assert project_fit_trajectory(bro_factory(MAtk=120),r,rounds=0,samples=1)['feasibility_pct']==100; assert project_fit_trajectory(bro_factory(MAtk=0),r,rounds=0,samples=1)['feasibility_pct']==0

def test_seeded_equals_degenerate_and_incomplete_none(bro_factory,simple_role):
    r=simple_role(('MAtk','MDef')); future={s:[2] for s in STATS}; future['MAtk']=[3]; future['MDef']=[2]; b=bro_factory(Level=10,FutureRolls=future); seeded=project_seeded_fit_trajectory(b,r); direct=project_fit_trajectory(b,r,rounds=1,round_ranges=[{'MAtk':(3,3),'MDef':(2,2)}],samples=1,include_trace=True); assert seeded['fit_pct']==direct['expected_pct']; assert seeded['choices']==direct['trace']; assert project_seeded_fit_trajectory(replace(b,FutureRolls={}),r) is None

def test_cache_hit_and_key_changes(bro_factory,simple_role):
    r=simple_role(('MAtk',)); b=bro_factory(); reset_trajectory_cache(); reset_profile_values(); project_fit_trajectory(b,r,rounds=1,samples=8); project_fit_trajectory(b,r,rounds=1,samples=8); p=get_profile_values(); assert p['trajectory_cache_hits']>=1
    assert p['trajectory_cache_miss_reasons']['missing_entry']==1
    before=p['trajectory_cache_misses']; project_fit_trajectory(replace(b,MAtk=b.MAtk+1),r,rounds=1,samples=8); updated=get_profile_values(); assert updated['trajectory_cache_misses']>before
    assert updated['trajectory_cache_miss_reasons']['fingerprint_change']==1
    assert sum(updated['trajectory_cache_miss_reasons'].values())==updated['trajectory_cache_misses']


def test_adaptive_refinement_has_reconciled_miss_reason(bro_factory, simple_role):
    reset_trajectory_cache(); reset_profile_values()
    project_fit_trajectory(bro_factory(MAtk=100), simple_role(('MAtk',)), rounds=0)
    profile = get_profile_values()
    assert profile['trajectory_adaptive_refinements'] == 1
    assert profile['trajectory_cache_miss_reasons']['refinement'] == 1
    assert sum(profile['trajectory_cache_miss_reasons'].values()) == profile['trajectory_cache_misses']


def test_new_brother_and_new_role_are_cold_cache_misses(bro_factory, simple_role):
    reset_trajectory_cache(); reset_profile_values()
    first = bro_factory(HumanOffset=1)
    project_fit_trajectory(first, simple_role(name='Duelist'), rounds=1, samples=8)
    project_fit_trajectory(first, simple_role(name='Tank'), rounds=1, samples=8)
    project_fit_trajectory(bro_factory(HumanOffset=2, MAtk=61), simple_role(name='Duelist'), rounds=1, samples=8)
    profile = get_profile_values()
    assert profile['trajectory_cache_miss_reasons']['missing_entry'] == 3
    assert profile['trajectory_cache_miss_reasons']['fingerprint_change'] == 0
    assert sum(profile['trajectory_cache_miss_reasons'].values()) == profile['trajectory_cache_misses']


def test_identical_state_cache_hit_registers_each_logical_brother(bro_factory, simple_role):
    reset_trajectory_cache(); reset_profile_values()
    role = simple_role(name='Duelist')
    project_fit_trajectory(bro_factory(HumanOffset=1), role, rounds=1, samples=8)
    project_fit_trajectory(bro_factory(HumanOffset=2), role, rounds=1, samples=8)
    project_fit_trajectory(bro_factory(HumanOffset=2, MAtk=61), role, rounds=1, samples=8)
    profile = get_profile_values()
    assert profile['trajectory_cache_hits'] == 1
    assert profile['trajectory_cache_miss_reasons']['fingerprint_change'] == 1
@pytest.mark.parametrize('change', ['stars','perk','role','rounds','ranges','samples'])
def test_cache_miss_dimensions(change,bro_factory,simple_role):
    r=simple_role(('MAtk',)); b=bro_factory(); reset_trajectory_cache(); reset_profile_values(); project_fit_trajectory(b,r,rounds=1,samples=8); before=get_profile_values()['trajectory_cache_misses']
    if change=='stars': project_fit_trajectory(replace(b,MAtkStars=1),r,rounds=1,samples=8)
    elif change=='perk': project_fit_trajectory(replace(b,Perks=['Colossus']),r,rounds=1,samples=8)
    elif change=='role': project_fit_trajectory(b,simple_role(('MAtk',),weights={'MAtk':2}),rounds=1,samples=8)
    elif change=='rounds': project_fit_trajectory(b,r,rounds=2,samples=8)
    elif change=='ranges': project_fit_trajectory(b,r,rounds=1,round_ranges=[{'MAtk':(3,3)}],samples=8)
    else: project_fit_trajectory(b,r,rounds=1,samples=9)
    assert get_profile_values()['trajectory_cache_misses']>before

def test_refinement_predicate():
    assert not _needs_refinement({'expected_pct':50,'likely_min_pct':40,'likely_max_pct':60,'full_max_pct':70,'feasibility_pct':0}); assert _needs_refinement({'expected_pct':100,'likely_min_pct':90,'likely_max_pct':110,'full_max_pct':120,'feasibility_pct':50})

@pytest.mark.parametrize('field,value', [('weight',2.0),('target',120.0),('baseline',10.0)])
def test_cache_miss_for_each_role_fit_parameter(field,value,bro_factory,simple_role):
    r=simple_role(('MAtk',)); b=bro_factory(); reset_trajectory_cache(); reset_profile_values(); project_fit_trajectory(b,r,rounds=1,samples=8); before=get_profile_values()['trajectory_cache_misses']
    changed=simple_role(('MAtk',)); changed['stats']['MAtk'][field]=value
    if field in ('target','baseline'):
        from bbtool.app.config import _fit_curve
        changed['stats']['MAtk']['projected_curve']=_fit_curve(changed['stats']['MAtk']['target'],changed['stats']['MAtk']['baseline'])
    project_fit_trajectory(b,changed,rounds=1,samples=8)
    assert get_profile_values()['trajectory_cache_misses']>before
