import pytest
pytestmark=[pytest.mark.unit, pytest.mark.coverage_slow]
import bbtool.app.analysis as an


def test_structural_paths_call_same_advisor_function_for_simulated_state(monkeypatch,cfg,bro_factory):
    calls=[]
    def fake(bro,roles,rows):
        calls.append(tuple(bro.Perks)); return {'marker':tuple(bro.Perks)}
    monkeypatch.setattr(an,'advise_levelup',fake)
    b=bro_factory(PerkPoints=1,Level=2)
    base=[an._role_row(b,r,fast=True) for r in cfg.roles]
    paths=an._structural_perk_paths(b,cfg.roles,cfg.classification,base)
    col=next(p for p in paths if p['Perks']==['Colossus'])
    assert ('Colossus',) in calls and col['LevelUpAdvice']['marker']==('Colossus',)


def test_base_and_colossus_advice_can_differ_when_effective_state_differs(monkeypatch,cfg,bro_factory):
    def fake(bro,roles,rows): return {'Recommended':{'Stats':['HP'] if 'Colossus' not in bro.Perks else ['MAtk']}}
    monkeypatch.setattr(an,'advise_levelup',fake)
    b=bro_factory(PerkPoints=1,Level=2)
    base=fake(b,cfg.roles,[])
    rows=[an._role_row(b,r,fast=True) for r in cfg.roles]
    col=next(p for p in an._structural_perk_paths(b,cfg.roles,cfg.classification,rows) if p['Perks']==['Colossus'])
    assert base['Recommended']['Stats']!=col['LevelUpAdvice']['Recommended']['Stats']


def test_structural_path_can_win_classification_over_base():
    cfg={'thresholds':{'Invest':{'min_projected_fit':.9},'Use':{'min_projected_fit':.7},'Fodder':{'min_full_max_fit':.6}}}
    base={'Role':'A','ProjectedFit':.65,'ProjectedFitPct':65,'ProjectedFitFullMaxPct':65,'FitFeasibilityPct':0,'ProjectedFitLikelyMinPct':60}
    alt_detail={'Role':'B','ProjectedFit':.75,'ProjectedFitPct':75,'ProjectedFitFullMaxPct':80,'FitFeasibilityPct':0,'ProjectedFitLikelyMinPct':70}
    alt={'Perks':['Colossus'],'Label':'Colossus','Role':'B','Category':'Use','CategoryReason':'x','BestRoleDetail':alt_detail}
    selected=an._select_classification_path(base,[alt],cfg)
    assert selected['Label']=='Colossus'
