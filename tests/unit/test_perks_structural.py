import pytest
pytestmark=pytest.mark.unit
from bbtool.models import STATS
from bbtool.projection import perks

def test_no_perk_is_raw(bro_factory):
    b=bro_factory(); assert perks.effective_stat_value(b,'HP',61)==61
@pytest.mark.parametrize('op,value,expected',[('+=',5,65),('-=',5,55),('*=',1.25,75),('/=',2,30)])
def test_arithmetic_effects(bro_factory,op,value,expected):
    b=bro_factory(); eff={'HP':[{'op':op,'value':value,'exact':True}]}; assert perks.effective_stat_value(b,'HP',60,eff)==expected
def test_effect_order(bro_factory):
    eff={'HP':[{'op':'+=','value':4},{'op':'*=','value':2}]}; assert perks.effective_stat_value(bro_factory(),'HP',60,eff)==128
def test_div_zero_ignored(bro_factory): assert perks.effective_stat_value(bro_factory(),'HP',60,{'HP':[{'op':'/=','value':0}]})==60
def test_colossus_floor(bro_factory):
    eff={'HP':[{'op':'*=','value':1.25,'property':'HitpointsMult'}]}; assert perks.effective_stat_value(bro_factory(),'HP',61,eff)==76
def test_fortified_round_positive(bro_factory):
    eff={'Resolve':[{'op':'*=','value':1.25,'property':'BraveryMult'}]}; assert perks.effective_stat_value(bro_factory(),'Resolve',42,eff)==53
def test_effective_values_matches_individual(bro_factory):
    b=bro_factory(); raw={s:getattr(b,s) for s in STATS}; vals=perks.effective_values(b,raw); assert all(vals[s]==perks.effective_stat_value(b,s,raw[s]) for s in STATS)
def test_profile_multiplier_with_real_colossus(bro_factory):
    b=bro_factory(Perks=['Colossus']); vals,mult=perks.effective_stat_profile(b); assert mult['HP']==pytest.approx(1.25); assert vals['HP']==75

def test_cache_reset_same_result():
    a=perks.structural_projection_perks(); perks.reset_perk_cache(); b=perks.structural_projection_perks(); assert a==b
def test_structural_rules():
    names=perks.structural_projection_perks(); assert 'Colossus' in names; assert 'Fortified Mind' not in names
def test_structural_stats(): assert 'HP' in perks.structural_projection_perk_stats(['Colossus'])
def test_unknown_structural_stats_empty(): assert perks.structural_projection_perk_stats(['Not A Perk'])==set()
