from dataclasses import replace
import json
from pathlib import Path
import pytest
pytestmark=pytest.mark.unit
from bbtool.models import STATS
from bbtool.app.output import _public_bro_dict
from bbtool.app.config import _normalize_role

ROOT = Path(__file__).resolve().parents[2]

def test_config_unique_roles(cfg): assert len(cfg.roles)==len({r['name'] for r in cfg.roles})
def test_default_archetypes_use_calibrated_role_set(cfg):
    assert [role['name'] for role in cfg.roles] == [
        'Reach DPS', 'Nimble Frontline DPS', 'Battle Forged Frontline DPS',
        'Fat Neutral', 'Nimble Tank', 'Battle Forged Tank', 'Archer',
        'Thrower Hybrid', 'Thrower', 'Crossbow', 'Banner',
    ]
    for role in cfg.roles:
        assert sum(stat['weight'] for stat in role['stats'].values() if stat['fit']) == pytest.approx(100.0)

    reach = cfg.roles[0]
    assert reach['stats']['MAtk']['target'] == 92
    assert reach['stats']['MAtk']['baseline'] == 82
    assert reach['stats']['MAtk']['weight'] == 60
def test_default_archetype_roles_match_retained_issue_source():
    integrated = json.loads((ROOT/'config/archetypes.json').read_text(encoding='utf-8'))
    source = json.loads((ROOT/'docs/sources/issue-27-archetype-calibration.json').read_text(encoding='utf-8'))
    assert integrated['roles'] == source['roles']
def test_config_fit_stat_invariants(cfg):
    for r in cfg.roles:
        assert r['stats']
        for _s,c in r['stats'].items():
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
