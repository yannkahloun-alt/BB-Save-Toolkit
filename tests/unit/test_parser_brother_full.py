import struct
import pytest
pytestmark=pytest.mark.unit
from bbtool.save_parser import (try_parse_human_header,find_identity,find_roster_identity,parse_stars,
    parse_levelup_roll_sequence,parse_roster,BROTHER_SIGNATURE)


def lp(s):
    raw=s.encode(); return struct.pack('<H',len(raw))+raw


def human_blob(ap=9, stats=(60,40,100,60,40,5,5,100), second=None):
    b=bytearray(400); b[0:5]=b'human'; off=10; b[off]=ap
    for i,v in enumerate(stats): struct.pack_into('<h',b,off+1+2*i,v)
    if second:
        off2=80; b[off2]=second[0]
        for i,v in enumerate(second[1]): struct.pack_into('<h',b,off2+1+2*i,v)
    return bytes(b)


def identity_blob(name='Alrik',title='',light=0.0,xp=1234,level=5,perk=2,used=1,points=1):
    head=lp(name)+lp(title); q=len(head); b=bytearray(head+b'\0'*80)
    struct.pack_into('<f',b,q,light); struct.pack_into('<I',b,q+4,xp)
    b[q+14]=level; b[q+15]=perk; b[q+16]=used; b[q+17]=points
    return bytes(b),q+18


def star_and_roll_tail(stars=(0,1,2,3,0,1,2,3), rolls=None, morale=0.0):
    rolls=rolls or {s:[2,3] for s in ('HP','Resolve','Fatigue','Initiative','MAtk','RAtk','MDef','RDef')}
    b=bytearray(); b+=struct.pack('<f',morale); b+=bytes([0]); b+=b'\0'*8; b+=bytes(stars)
    for s in ('HP','Resolve','Fatigue','Initiative','MAtk','RAtk','MDef','RDef'):
        vals=rolls[s]; b+=bytes([len(vals)])+bytes(vals)
    return bytes(b)


def build_record(name='Alrik',level=2,level_points=1,rolls=None,stars=(0,1,2,3,0,1,2,3)):
    sig=100; human=160; data=bytearray(b'\0'*1200)
    data[sig:sig+len(BROTHER_SIGNATURE)]=BROTHER_SIGNATURE; data[sig-19]=1
    data[human:human+5]=b'human'; apoff=human+10; data[apoff]=9
    vals=(60,40,100,60,40,5,5,100)
    for i,v in enumerate(vals): struct.pack_into('<h',data,apoff+1+2*i,v)
    ident_start=apoff+17+20
    ident,meta_rel=identity_blob(name=name,title='',level=level,points=level_points)
    data[ident_start:ident_start+len(ident)]=ident
    meta_end=ident_start+meta_rel
    tail=star_and_roll_tail(stars=stars,rolls=rolls)
    data[meta_end:meta_end+len(tail)]=tail
    return bytes(data)


def test_human_header_valid_ap_and_all_eight_stats_in_serialized_order():
    h=try_parse_human_header(human_blob(),0)
    assert h['AP']==9
    assert [h[s] for s in ('HP','Resolve','Fatigue','MAtk','RAtk','MDef','RDef','Initiative')]==[60,40,100,60,40,5,5,100]


def test_human_header_rejects_out_of_range_candidates():
    assert try_parse_human_header(human_blob(stats=(10,40,100,60,40,5,5,100)),0) is None


def test_human_header_multiple_candidates_prefers_earliest_deterministically():
    h=try_parse_human_header(human_blob(second=(8,(70,45,110,65,45,6,6,105))),0)
    assert h['AP']==9 and h['HP']==60


def test_identity_name_title_xp_level_and_points():
    ident,meta=identity_blob(name='Alrik',title='the Brave',light=0.1,xp=4321,level=7,perk=3,used=2,points=1)
    b=ident[:meta]+star_and_roll_tail()+b'\0'*20
    x,stars,count=find_roster_identity(b,0,len(b)); assert count==1
    assert (x['Name'],x['Title'],x['XP'],x['Level'],x['PerkPoints'],x['PerksUsed'],x['LevelPoints'])==('Alrik','the Brave',4321,7,3,2,1)


@pytest.mark.parametrize('kwargs',[
    {'name':'\n'}, {'level':0}, {'level':34}, {'xp':10_000_001}, {'light':float('nan')}, {'light':11.0}
])
def test_identity_rejects_invalid_name_level_xp_or_lightwound(kwargs):
    b,_=identity_blob(**kwargs); assert find_identity(b,0,len(b)) is None


def test_stars_parse_all_eight_in_save_order():
    tail=star_and_roll_tail(stars=(3,2,1,0,1,2,3,0)); x=parse_stars(tail,0)
    assert [x[k] for k in ('HPStars','ResolveStars','FatigueStars','InitiativeStars','MAtkStars','RAtkStars','MDefStars','RDefStars')]==[3,2,1,0,1,2,3,0]


def test_future_rolls_parse_all_stats_in_level_order_and_current_roll_is_first():
    order=('HP','Resolve','Fatigue','Initiative','MAtk','RAtk','MDef','RDef')
    rolls={s:[i+1,i+2] for i,s in enumerate(order)}
    # values must be <=6
    rolls={s:[1+(i%5),2+(i%5)] for i,s in enumerate(order)}
    tail=star_and_roll_tail(rolls=rolls); got=parse_levelup_roll_sequence(tail,0)
    assert got==rolls
    current={s:v[0] for s,v in got.items()}; assert current['HP']==rolls['HP'][0] and current['RDef']==rolls['RDef'][0]


def test_roll_sequence_rejects_mismatched_lengths_and_invalid_rolls():
    order=('HP','Resolve','Fatigue','Initiative','MAtk','RAtk','MDef','RDef')
    rolls={s:[2,3] for s in order}; rolls['HP']=[2]
    assert parse_levelup_roll_sequence(star_and_roll_tail(rolls=rolls),0) is None
    rolls={s:[2,3] for s in order}; rolls['HP']=[0,3]
    assert parse_levelup_roll_sequence(star_and_roll_tail(rolls=rolls),0) is None


def test_parse_roster_synthetic_record_sets_current_and_future_rolls(tmp_path):
    rolls={s:[2,3] for s in ('HP','Resolve','Fatigue','Initiative','MAtk','RAtk','MDef','RDef')}
    p=tmp_path/'save.sav'; p.write_bytes(build_record(level=2,level_points=1,rolls=rolls))
    bros=parse_roster(p); assert len(bros)==1 and bros[0].Name=='Alrik'
    assert bros[0].CurrentRolls=={s:2 for s in rolls}; assert bros[0].FutureRolls==rolls


def test_parse_roster_no_pending_points_has_empty_current_rolls(tmp_path):
    p=tmp_path/'save.sav'; p.write_bytes(build_record(level_points=0)); b=parse_roster(p)[0]; assert b.CurrentRolls=={}




def test_duplicate_brother_names_are_supported_with_brother_ids(monkeypatch,tmp_path):
    import bbtool.save_parser as sp
    p=tmp_path/'x'; p.write_bytes(b'x')
    monkeypatch.setattr(sp,'find_company_brother_human_offsets',lambda b:([10,20],{'RosterCount':2,'CompanySignatureOffsets':[1,2]}))
    monkeypatch.setattr(sp,'_find_brother_signature_offsets',lambda b:[1,2,999])
    monkeypatch.setattr(sp,'try_parse_human_header',lambda b,p:{'StatsEnd':30,'AP':9,'HP':60,'Resolve':40,'Fatigue':100,'MAtk':60,'RAtk':40,'MDef':5,'RDef':5,'Initiative':100})
    monkeypatch.setattr(sp,'find_roster_identity',lambda *a:({'Name':'Same','Title':'','Level':1,'XP':0,'PerkPoints':0,'PerksUsed':0,'LevelPoints':0,'Offset':40,'MetaEnd':50},{k:0 for k in ('HPStars','ResolveStars','FatigueStars','InitiativeStars','MAtkStars','RAtkStars','MDefStars','RDefStars')},1))
    monkeypatch.setattr(sp,'parse_levelup_roll_sequence',lambda *a:{s:[] for s in ('HP','Resolve','Fatigue','Initiative','MAtk','RAtk','MDef','RDef')})
    monkeypatch.setattr(sp,'find_circle_metadata',lambda *a:None)

    diagnostics = {"recoverable_failures": []}
    bros=sp.parse_roster(p, diagnostics=diagnostics)

    assert [b.Name for b in bros]==['Same','Same']
    assert [b.BrotherID for b in bros]==['human:10','human:20']
    assert diagnostics["recoverable_failures"] == [
        {"scope":"roster","kind":"circle_metadata_unresolved","human_offset":10,"name":"Same"},
        {"scope":"roster","kind":"circle_metadata_unresolved","human_offset":20,"name":"Same"},
    ]

def test_truncated_save_fails_with_controlled_runtime_error(tmp_path):
    p=tmp_path/'bad.sav'; p.write_bytes(BROTHER_SIGNATURE[:10])
    with pytest.raises(RuntimeError): parse_roster(p)
