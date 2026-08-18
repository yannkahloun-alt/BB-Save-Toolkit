import pytest
pytestmark=pytest.mark.unit
from bbtool.projection.trajectory import project_fit_trajectory,reset_trajectory_cache

def test_nonambiguous_stays_512(bro_factory,simple_role):
    reset_trajectory_cache(); x=project_fit_trajectory(bro_factory(MAtk=0),simple_role(('MAtk',)),rounds=0); assert x['sample_count']==512 and not x['adaptive_refined']
def test_ambiguous_refines_to_2048(bro_factory,simple_role):
    reset_trajectory_cache(); x=project_fit_trajectory(bro_factory(MAtk=100),simple_role(('MAtk',)),rounds=0); assert x['sample_count']==2048 and x['adaptive_refined'] and x['initial_sample_count']==512
def test_refinement_deterministic(bro_factory,simple_role):
    b=bro_factory(MAtk=100); r=simple_role(('MAtk',)); reset_trajectory_cache(); a=project_fit_trajectory(b,r,rounds=0); reset_trajectory_cache(); c=project_fit_trajectory(b,r,rounds=0); assert a==c
def test_five_stat_generic_path_works(bro_factory,simple_role):
    stats=('HP','Fatigue','Resolve','MAtk','MDef'); b=bro_factory(HP=60,Fatigue=60,Resolve=60,MAtk=60,MDef=60); x=project_fit_trajectory(b,simple_role(stats),rounds=2,samples=16,include_trace=True); assert len(x['fit_stats'])==5 and all(len(t['picks'])==3 for t in x['trace'])
def test_three_stat_path_picks_all(bro_factory,simple_role):
    stats=('HP','MAtk','MDef'); x=project_fit_trajectory(bro_factory(),simple_role(stats),rounds=1,samples=1,include_trace=True); assert set(x['trace'][0]['picks'])==set(stats)

def test_refinement_preserves_method_and_fit_stat_logic(bro_factory,simple_role):
    b=bro_factory(MAtk=100); r=simple_role(('MAtk',))
    x=project_fit_trajectory(b,r,rounds=0,samples=512); y=project_fit_trajectory(b,r,rounds=0,samples=2048)
    assert x['method']==y['method']=='deterministic_low_discrepancy' and x['fit_stats']==y['fit_stats']==['MAtk']
