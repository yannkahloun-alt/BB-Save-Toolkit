from pathlib import Path
import pytest
from bbtool.app.config import load_config
from bbtool.models import Brother, STATS

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope='session')
def cfg():
    return load_config(ROOT/'config/archetypes.json', ROOT/'config/classification.json')

@pytest.fixture
def bro_factory():
    def make(**overrides):
        vals=dict(Name='Test',Title='',Level=1,XP=0,PerkPoints=0,PerksUsed=0,LevelPoints=0,AP=9,
                  HP=60,Fatigue=100,Resolve=40,Initiative=100,MAtk=60,RAtk=40,MDef=5,RDef=5,
                  BackgroundID='',Background='Test',PerkIDs=[],Perks=[],TraitIDs=[],Traits=[],Injuries=[],HumanOffset=0,
                  CurrentRolls={},FutureRolls={})
        for s in STATS: vals[s+'Stars']=0
        vals.update(overrides)
        return Brother(**vals)
    return make

@pytest.fixture
def simple_role():
    def make(stats=('MAtk',), weights=None, baselines=None, targets=None, name='Test Role'):
        weights=weights or {}; baselines=baselines or {}; targets=targets or {}
        out={}
        from bbtool.app.config import _fit_curve
        for s in stats:
            target=float(targets.get(s,100)); baseline=float(baselines.get(s,50))
            out[s]={'target':target,'baseline':baseline,'weight':float(weights.get(s,1)), 'fit':True,
                    'projected_curve':_fit_curve(target,baseline)}
        return {'name':name,'stats':out,'perks':{},'perk_affinity':{},'perk_conflicts':[]}
    return make
