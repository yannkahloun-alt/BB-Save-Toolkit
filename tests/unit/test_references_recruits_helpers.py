import json
import pytest
pytestmark=pytest.mark.unit
from bbtool.save_parser import load_reference_dictionary,ref_name,_compute_daily_wage,_background_economy_entry,try_parse_human_header,find_identity,parse_stars,parse_levelup_roll_sequence

def test_reference_dictionary_core_fallback(tmp_path):
    d=tmp_path/'references'; d.mkdir(); (d/'dictionary_core.json').write_text(json.dumps({'aabb':{'name':'Sword'}})); refs=load_reference_dictionary(tmp_path); assert refs=={'AABB':{'name':'Sword'}}; assert ref_name(refs,'aabb')=='Sword'; assert ref_name(refs,'ffff')=='Unknown [FFFF]'
def test_reference_enriched_format(tmp_path):
    d=tmp_path/'references'; d.mkdir(); (d/'dictionary.json').write_text(json.dumps({'_meta':{'format':'bbtool.enriched_dictionary.v1'},'entries':{'abcd':{'name':'X'}}})); assert 'ABCD' in load_reference_dictionary(tmp_path)
def test_reference_missing_empty(tmp_path): assert load_reference_dictionary(tmp_path)=={}
def test_background_economy_unknown(): assert _background_economy_entry('X',{}) is None
def test_daily_wage_known_level_and_greedy():
    econ={'AB':{'DailyCostBase':10}}; base=_compute_daily_wage('AB',1,1.0,[],econ); greedy=_compute_daily_wage('AB',1,1.0,['Greedy'],econ); assert base==11 and greedy==12; assert _compute_daily_wage('ZZ',1,1,[],econ) is None
def test_parser_helpers_reject_truncated_noise():
    b=b'not a battle brothers record'; assert try_parse_human_header(b,0) is None; assert find_identity(b,0,len(b)) is None; assert parse_stars(b,0) is None; assert parse_levelup_roll_sequence(b,0) is None
