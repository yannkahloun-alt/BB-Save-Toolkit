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


def test_summary_uses_natural_best_role(monkeypatch,bro_factory):
    monkeypatch.setattr(an,'classify_bro',lambda best,cfg:('Use','base'))
    monkeypatch.setattr(an,'fit_label',lambda fit,cfg:'Good')
    base=row('A',70)
    s=an._summary(bro_factory(),base,{}, {'HP':80}, {'advice':1})
    assert s['BestRole']=='A' and s['EffectiveStats']=={'HP':80}
    assert 'ClassificationPaths' not in s
    assert 'StructuralPerkAlternatives' not in s
    assert s['LevelUpAdvice']=={'advice':1}


def test_analyze_brothers_pipeline(monkeypatch,bro_factory):
    roles=[role('A'),role('B')]
    monkeypatch.setattr(an,'_role_row',lambda b,r:row(r['name'],70 if r['name']=='A' else 60))
    monkeypatch.setattr(an,'effective_stat_profile',lambda b:({'HP':80},{}))
    monkeypatch.setattr(an,'advise_levelup',lambda *a:{'x':1})
    monkeypatch.setattr(an,'_summary',lambda b,best,cfg,e,a:{'Name':b.Name,'BestRole':best['Role']})
    out=an.analyze_brothers([bro_factory(Name='One'),bro_factory(Name='Two')],roles,{})
    assert len(out.fits)==4 and [x['BestRole'] for x in out.summaries]==['A','A']


def test_reused_summary_skips_unused_effective_stat_profile(monkeypatch, bro_factory):
    class Cache:
        def get_role_row(self, bro, role): return row(role['name'])
        def store_role_row(self, bro, role, value): pass
        def get_summary(self, bro, roles, cfg): return {'Name': bro.Name}
        def get_advisor(self, bro, roles, assigned_build=None): return {'cached': True}

    monkeypatch.setattr(
        an, 'effective_stat_profile',
        lambda bro: (_ for _ in ()).throw(AssertionError('must not be called')),
    )
    out = an.analyze_brothers([bro_factory(Name='Cached')], [role('A')], {}, Cache())
    assert out.summaries == [{
        'Name': 'Cached', 'BestRole': 'A',
        'LevelUpAdvice': {'cached': True},
    }]
