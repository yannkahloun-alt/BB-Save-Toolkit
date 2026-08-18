import pytest
pytestmark=pytest.mark.unit
from bbtool.projection.planner import project_role,project_role_fast
from bbtool.classification import fit_label,classify_bro,perk_compatibility,role_sort_key

def test_project_role_fields_all_roles(cfg,bro_factory):
    b=bro_factory()
    required={'Role','ProjectedFit','ProjectedFitPct','ProjectedFitLikelyMinPct','ProjectedFitLikelyMaxPct','ProjectedFitFullMinPct','ProjectedFitFullMaxPct','FitFeasibilityPct','ProjectedComponents','ProjectedRanges'}
    for r in cfg.roles: assert required<=project_role(b,r).keys()
def test_fast_exact_subset_all_roles(cfg,bro_factory):
    b=bro_factory()
    for r in cfg.roles:
        f=project_role(b,r); q=project_role_fast(b,r); assert all(f[k]==v for k,v in q.items())
@pytest.mark.parametrize('score,label',[(.95,'PREMIUM'),(.949,'GOOD'),(.82,'GOOD'),(.819,'VIABLE'),(.68,'VIABLE'),(.679,'LOW')])
def test_fit_label_thresholds(cfg,score,label): assert fit_label(score,cfg.classification)==label
@pytest.mark.parametrize('pf,full,cat',[(.95,95,'Invest'),(.949,95,'Use'),(.65,65,'Use'),(.649,65,'Fodder'),(.1,64.9,'Trash')])
def test_classify_boundaries(cfg,pf,full,cat):
    row={'ProjectedFit':pf,'ProjectedFitPct':pf*100,'ProjectedFitFullMaxPct':full}; assert classify_bro(row,cfg.classification)[0]==cat
def test_perk_compatibility_conflict_and_affinity(bro_factory):
    role={'perk_conflicts':['Battle Forged'],'perk_affinity':{'Nimble':4,'Dodge':2}}
    assert perk_compatibility(bro_factory(Perks=['Battle Forged']),role)[0]=='CONFLICT'; assert perk_compatibility(bro_factory(Perks=['Nimble','Dodge']),role)[:2]==('HIGH',6)
def test_role_sort_conflict_penalty_and_determinism():
    a={'ProjectedFit':.8,'ProjectedFitPct':80,'FitFeasibilityPct':50,'ProjectedFitLikelyMinPct':70}; b=dict(a); b['PerkCompatibility']='CONFLICT'; assert role_sort_key(a)>role_sort_key(b); assert role_sort_key(a)==role_sort_key(dict(a))
