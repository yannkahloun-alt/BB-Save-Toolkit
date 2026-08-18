from dataclasses import replace
import json
import pytest
pytestmark=pytest.mark.unit
from bbtool.models import STATS
from bbtool.app.output import _public_bro_dict
from bbtool.app.config import _normalize_role

def test_config_unique_roles(cfg): assert len(cfg.roles)==len({r['name'] for r in cfg.roles})
def test_config_fit_stat_invariants(cfg):
    for r in cfg.roles:
        assert r['stats']
        for s,c in r['stats'].items():
            if c.get('fit'):
                assert {'target','baseline','weight','projected_curve'}<=c.keys(); assert c['baseline']<=c['target']; assert c['weight']>0
                ys=[p[1] for p in c['projected_curve']]; assert ys==sorted(ys)
def test_classification_threshold_order(cfg):
    t=cfg.classification['thresholds']; assert t['Invest']['min_projected_fit']>t['Use']['min_projected_fit']>=t['Fodder']['min_full_max_fit']
def test_five_stat_role_normalizes():
    role={'name':'Five','stats':{s:{'target':100,'baseline':50,'weight':1} for s in STATS[:5]}}; n=_normalize_role(role); assert sum(c['fit'] for c in n['stats'].values())==5
def test_brother_defaults_and_replace(bro_factory):
    b=bro_factory(); assert b.CurrentRolls=={} and b.FutureRolls=={}; assert all(hasattr(b,s) and hasattr(b,s+'Stars') for s in STATS); c=replace(b,MAtk=99); assert c.MAtk==99 and c.Name==b.Name
def test_public_serialization_hides_future_keeps_current(bro_factory):
    b=bro_factory(CurrentRolls={'MAtk':3},FutureRolls={'MAtk':[3]}); d=_public_bro_dict(b); assert 'FutureRolls' not in d and d['CurrentRolls']=={'MAtk':3}
def test_public_dict_json_finite(bro_factory):
    text=json.dumps(_public_bro_dict(bro_factory())); assert 'NaN' not in text and 'Infinity' not in text
