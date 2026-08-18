import pytest
import bbtool.app.analysis as an

pytestmark=pytest.mark.unit


def role(name, fitstat='MAtk'):
    return {'name':name,'stats':{fitstat:{'fit':True}},'perks':{},'perk_affinity':{},'perk_conflicts':[]}


def row(name,pct=50,feas=20):
    return {'Role':name,'ProjectedFit':pct/100,'ProjectedFitPct':pct,'FitFeasibilityPct':feas,
            'ProjectedFitLikelyMinPct':pct-5,'ProjectedFitLikelyMaxPct':pct+5,
            'ProjectedFitFullMinPct':pct-10,'ProjectedFitFullMaxPct':pct+10,
            'PerkCompatibility':'OK','MAtk':70,'MDef':20,'RAtk':40,'HP':80,'Fatigue':100,'Resolve':50,
            'ProjectedRanges':{}}


def test_role_row_fast_and_full(monkeypatch,bro_factory):
    monkeypatch.setattr(an,'project_role',lambda b,r:row(r['name'],60))
    monkeypatch.setattr(an,'project_role_fast',lambda b,r:row(r['name'],55))
    monkeypatch.setattr(an,'perk_compatibility',lambda b,r:('Good',2,['x']))
    b=bro_factory()
    assert an._role_row(b,role('A'))['ProjectedFitPct']==60
    assert an._role_row(b,role('A'),fast=True)['ProjectedFitPct']==55


def test_structural_paths_reuse_and_recompute(monkeypatch,bro_factory):
    roles=[role('A','MAtk'),role('B','HP')]
    b=bro_factory(Level=2,PerkPoints=1,Perks=[])
    monkeypatch.setattr(an,'structural_projection_perks',lambda:['Colossus'])
    monkeypatch.setattr(an,'structural_projection_perk_stats',lambda combo:{'HP'})
    monkeypatch.setattr(an,'perk_compatibility',lambda b,r:('OK',1,[]))
    monkeypatch.setattr(an,'effective_stat_profile',lambda b:({'HP':80,'MAtk':70},{}))
    monkeypatch.setattr(an,'classify_bro',lambda best,cfg:('Use','why'))
    monkeypatch.setattr(an,'advise_levelup',lambda b,rs,rows:{'ok':True})
    def rr(b,r,fast=False):
        return row(r['name'],80 if r['name']=='B' else 50)
    monkeypatch.setattr(an,'_role_row',rr)
    base=[row('A',45),row('B',46)]
    paths=an._structural_perk_paths(b,roles,{},base)
    assert len(paths)==1 and paths[0]['Perks']==['Colossus']
    assert paths[0]['Role']=='B' and paths[0]['LevelUpAdvice']=={'ok':True}


def test_structural_paths_empty_conditions(monkeypatch,bro_factory):
    monkeypatch.setattr(an,'structural_projection_perks',lambda:[])
    assert an._structural_perk_paths(bro_factory(),[],{},[])==[]
    monkeypatch.setattr(an,'structural_projection_perks',lambda:['Colossus'])
    assert an._structural_perk_paths(bro_factory(Level=11,PerkPoints=0),[],{},[])==[]


def test_select_path_and_summary(monkeypatch,bro_factory):
    monkeypatch.setattr(an,'classify_bro',lambda best,cfg:('Use','base'))
    monkeypatch.setattr(an,'fit_label',lambda fit,cfg:'Good')
    base=row('A',70)
    altrow=row('B',80)
    alt={'Perks':['Colossus'],'Label':'Colossus','Role':'B','Category':'Invest','CategoryReason':'alt',
         'BestRoleDetail':altrow,'EffectiveStats':{'HP':99}}
    selected=an._select_classification_path(base,[alt],{})
    assert selected['Label']=='Colossus'
    s=an._summary(bro_factory(),base,{}, {'HP':80}, [alt], {'advice':1})
    assert s['BestRole']=='B' and s['EffectiveStats']=={'HP':99}
    assert s['LevelUpAdvice']=={'advice':1}


def test_analyze_brothers_pipeline(monkeypatch,bro_factory):
    roles=[role('A'),role('B')]
    monkeypatch.setattr(an,'_role_row',lambda b,r:row(r['name'],70 if r['name']=='A' else 60))
    monkeypatch.setattr(an,'effective_stat_profile',lambda b:({'HP':80},{}))
    monkeypatch.setattr(an,'_structural_perk_paths',lambda *a:[])
    monkeypatch.setattr(an,'advise_levelup',lambda *a:{'x':1})
    monkeypatch.setattr(an,'_summary',lambda b,best,cfg,e,s,a:{'Name':b.Name,'BestRole':best['Role']})
    out=an.analyze_brothers([bro_factory(Name='One'),bro_factory(Name='Two')],roles,{})
    assert len(out.fits)==4 and [x['BestRole'] for x in out.summaries]==['A','A']
