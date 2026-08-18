import pytest
pytestmark=pytest.mark.unit
from bbtool.app.output import _discrete_sum_distribution,_midrank_from_counts,_empirical_percentile,_roll_luck_to_level11,_role_relevant_roll_rank
from bbtool.models import STATS
@pytest.mark.parametrize('lo,hi,rounds,total',[(1,3,1,3),(1,3,2,9),(2,4,2,9),(3,5,10,3**10)])
def test_distribution_counts(lo,hi,rounds,total): assert sum(_discrete_sum_distribution(lo,hi,rounds).values())==total
def test_midrank_min_mid_max():
    d=_discrete_sum_distribution(1,3,2); assert _midrank_from_counts(d,2)<50; assert _midrank_from_counts(d,4)==50; assert _midrank_from_counts(d,6)>50
def test_deterministic_distribution_midrank(): assert _midrank_from_counts(_discrete_sum_distribution(3,3,5),15)==50
def test_empirical_percentile_edges_ties_empty():
    assert _empirical_percentile([],1)==(None,0); assert _empirical_percentile([1,2,3],0)[0]==0; assert _empirical_percentile([1,2,3],4)[0]==100; assert _empirical_percentile([1,2,2,3],2)[0]==50

def test_relevant_rank_weights_and_ignores_nonfit(bro_factory):
    fut={s:[2] for s in STATS}; fut['MAtk']=[3]; fut['MDef']=[1]; b=bro_factory(Level=10,FutureRolls=fut); luck=_roll_luck_to_level11(b)
    role={'stats':{'MAtk':{'fit':True,'weight':3,'target':999,'baseline':-999},'MDef':{'fit':True,'weight':1},'HP':{'fit':False,'weight':999}}}; assert _role_relevant_roll_rank(role,luck)==pytest.approx(round((83.3*3+16.7)/4,1))
def test_relevant_rank_none_without_relevant_stats(): assert _role_relevant_roll_rank({'stats':{}},{'ByStat':{}}) is None
