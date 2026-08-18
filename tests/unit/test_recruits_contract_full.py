import struct
import pytest
pytestmark=pytest.mark.unit
import bbtool.save_parser as sp


def lp(s):
    r=s.encode(); return struct.pack('<H',len(r))+r


def test_settlement_reference_resolves_unique_registry_entry():
    ref=123456; b=b'xxxx'+struct.pack('<I',ref)+lp('Hagenau')+lp('A sufficiently long settlement description')+b'zz'
    assert sp._resolve_settlement_reference(b,ref)=='Hagenau'


def test_settlement_reference_ambiguous_or_missing_is_none():
    ref=42; rec=struct.pack('<I',ref)+lp('Town')+lp('A sufficiently long description')
    rec2=struct.pack('<I',ref)+lp('Keep')+lp('Another sufficiently long description')
    assert sp._resolve_settlement_reference(rec+b'xx'+rec2,ref) is None
    assert sp._resolve_settlement_reference(b'abc',ref) is None


def test_tryout_done_true_false_and_missing():
    prefix=b'\xff'+b'\0'*28
    assert sp._parse_tryout_done(prefix+b'\x01',0,30,0) is True
    assert sp._parse_tryout_done(prefix+b'\x00',0,30,0) is False
    assert sp._parse_tryout_done(b'none',0,4,0) is None


def test_hire_cost_known_background_and_equipment():
    econ={'AB':{'HiringCostBase':500,'DailyCostBase':10}}
    assert sp._compute_hire_cost('AB',1,100,econ)==630
    assert sp._compute_hire_cost('XX',1,100,econ) is None
    assert sp._compute_hire_cost('AB',1,None,econ) is None


def test_daily_wage_known_unknown_and_greedy():
    econ={'AB':{'HiringCostBase':500,'DailyCostBase':10}}
    plain=sp._compute_daily_wage('AB',1,1.0,[],econ)
    greedy=sp._compute_daily_wage('AB',1,1.0,['Greedy'],econ)
    assert plain==11 and greedy>plain and sp._compute_daily_wage('XX',1,1,[],econ) is None


def test_equipment_value_resolved_unknown_and_exact_circle_boundary():
    header={'StatsEnd':0} # p=6, pouches at6, count at7, item starts8
    meta={'AABBCCDD':{'SerializedLength':5,'Value':100}}
    b=bytearray(b'\0'*20); b[6]=0; b[7]=1; b[8]=0; b[9:13]=bytes.fromhex('AABBCCDD')
    assert sp._parse_recruit_equipment_value(bytes(b),header,13,meta)==100
    assert sp._parse_recruit_equipment_value(bytes(b),header,13,{}) is None
    assert sp._parse_recruit_equipment_value(bytes(b),header,14,meta) is None


def test_parse_recruits_public_fields_tryout_traits_and_costs(monkeypatch,tmp_path):
    p=tmp_path/'save'; p.write_bytes(b'abc')
    recs=[{'Settlement':'Town','Name':'A','Title':'','Background':'Farmhand','_BackgroundID':'BG','Level':2,'_BackgroundLevel':2,'TryoutDone':True,'_ParsedTraits':['Greedy'],'_DailyCostMult':1.0,'_Header':{'StatsEnd':0},'_CircleOffset':0},
          {'Settlement':'Keep','Name':'B','Title':'x','Background':'Unknown','_BackgroundID':'BG','Level':1,'_BackgroundLevel':1,'TryoutDone':False,'_ParsedTraits':['Brave'],'_DailyCostMult':1.0,'_Header':{'StatsEnd':0},'_CircleOffset':0}]
    monkeypatch.setattr(sp,'_candidate_records',lambda b,refs:recs)
    monkeypatch.setattr(sp,'load_reference_dictionary',lambda p:{})
    monkeypatch.setattr(sp,'_load_background_economy',lambda p:{'BG':{'HiringCostBase':500,'DailyCostBase':10}})
    monkeypatch.setattr(sp,'_load_item_economy',lambda p:{})
    monkeypatch.setattr(sp,'_parse_recruit_equipment_value',lambda *a:100)
    out=sp.parse_recruits(p)
    assert [x['Settlement'] for x in out]==['Town','Keep']
    assert out[0]['Traits']==['Greedy'] and out[1]['Traits']==[]
    assert out[0]['HireCost'] is not None and out[0]['DailyWage'] is not None


def test_incomplete_candidate_is_rejected_by_candidate_records(monkeypatch):
    # No recruitment roster/signature => no candidate escapes the parser.
    monkeypatch.setattr(sp,'_find_recruitment_rosters',lambda b:([],[]))
    assert sp._candidate_records(b'incomplete',{})==[]


def test_multiple_settlement_recruitment_rosters_are_detected():
    b=bytearray(b'\0'*1400); sigs=[100,300,500,700]
    for p in sigs:b[p:p+len(sp.BROTHER_SIGNATURE)]=sp.BROTHER_SIGNATURE
    b[sigs[0]-19]=1  # one company brother
    ref1,ref2=111,222
    struct.pack_into('<I',b,sigs[1]-23,ref1); struct.pack_into('<H',b,sigs[1]-19,2)
    struct.pack_into('<I',b,sigs[3]-23,ref2); struct.pack_into('<H',b,sigs[3]-19,1)
    reg=900
    for ref,name in ((ref1,'Town'),(ref2,'Keep')):
        payload=struct.pack('<I',ref)+lp(name)+lp('A sufficiently long settlement description')
        b[reg:reg+len(payload)]=payload; reg+=len(payload)+10
    rosters,found=sp._find_recruitment_rosters(bytes(b))
    assert found==sigs and [(r['Settlement'],r['Count']) for r in rosters]==[('Town',2),('Keep',1)]
