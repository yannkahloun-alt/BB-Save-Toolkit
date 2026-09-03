from dataclasses import replace
import json
from pathlib import Path
import pytest
pytestmark=pytest.mark.unit
from bbtool.models import STATS
from bbtool.app.output import _public_bro_dict
from bbtool.app.config import _normalize_role, load_config
from bbtool.build_identity import build_definition_hash, build_identity

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
    assert [{k: v for k, v in role.items() if k != 'id'} for role in integrated['roles']] == source['roles']

def test_shipped_build_ids_are_fixed(cfg):
    assert [role['id'] for role in cfg.roles] == [
        'reach_dps', 'nimble_frontline_dps', 'battle_forged_frontline_dps',
        'fat_neutral', 'nimble_tank', 'battle_forged_tank', 'archer',
        'thrower_hybrid', 'thrower', 'crossbow', 'banner',
    ]

def test_cosmetic_rename_preserves_identity_and_definition_hash(cfg):
    original = cfg.roles[0]
    renamed = {**original, 'name': 'Cosmetically Renamed'}
    assert build_identity(renamed) == build_identity(original) == 'reach_dps'
    assert build_definition_hash(renamed) == build_definition_hash(original)
    assert build_definition_hash({**original, 'id': 'replacement_id'}) == build_definition_hash(original)

def test_semantic_change_preserves_identity_and_changes_definition_hash(cfg):
    original = cfg.roles[0]
    changed = json.loads(json.dumps(original))
    changed['stats']['MAtk']['weight'] += 1
    assert build_identity(changed) == build_identity(original)
    assert build_definition_hash(changed) != build_definition_hash(original)

def _write_config(tmp_path, roles):
    targets = tmp_path/'targets.json'; classification = tmp_path/'classification.json'
    targets.write_text(json.dumps({'roles': roles}), encoding='utf-8')
    classification.write_text('{}', encoding='utf-8')
    return targets, classification

def test_duplicate_explicit_build_ids_fail(tmp_path):
    paths = _write_config(tmp_path, [{'id':'same','name':'A'}, {'id':'same','name':'B'}])
    with pytest.raises(ValueError, match=r'Duplicate archetype id\(s\): same'):
        load_config(*paths)

@pytest.mark.parametrize('invalid', [
    '', 'Uppercase', 'has-hyphen', '_leading', 'trailing_', 'double__underscore',
    '7starts_with_digit', 'space here', 7,
])
def test_invalid_explicit_build_ids_fail(tmp_path, invalid):
    paths = _write_config(tmp_path, [{'id':invalid,'name':'Role'}])
    with pytest.raises(ValueError, match=r'Role\.id must match'):
        load_config(*paths)

def test_legacy_idless_role_remains_usable_without_durable_identity(tmp_path):
    role = {'name':'Legacy Name','stats':{'MAtk':{'target':90,'baseline':80,'weight':1}}}
    cfg = load_config(*_write_config(tmp_path, [role]))
    assert cfg.roles[0]['stats']['MAtk']['fit'] is True
    assert build_identity(cfg.roles[0]) is None
    assert 'id' not in cfg.roles[0]

def test_definition_hash_ignores_engine_normalization_fields():
    raw = {'id':'test','name':'Test','stats':{'MAtk':{'target':90,'baseline':80,'weight':1}}}
    assert build_definition_hash(raw) == build_definition_hash(_normalize_role(raw))

def test_definition_hash_preserves_unknown_future_fields():
    original = {
        'id':'test', 'name':'Test',
        'stats':{'MAtk':{'target':90,'baseline':80,'weight':1}},
        'future':{'fit':1,'projected_curve':[1, 2], 'required':['b', 'a']},
    }
    changed = json.loads(json.dumps(original))
    changed['future']['fit'] = 2
    reordered = json.loads(json.dumps(original))
    reordered['future']['required'].reverse()
    assert build_definition_hash(original) != build_definition_hash(changed)
    assert build_definition_hash(original) != build_definition_hash(reordered)
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
