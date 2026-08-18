
import bbtool.save_parser as sp


def test_candidate_records_happy_path(monkeypatch):
    b=bytearray(b"\x00"*500)
    sig=10
    b[sig+29:sig+34]=b"human"
    monkeypatch.setattr(sp,"_find_recruitment_rosters",lambda b:(
        [{"Settlement":"Town","StartIndex":0,"EndIndex":1}],[sig]
    ))
    monkeypatch.setattr(sp,"_all_valid_human_offsets",lambda b:[sig+29,400])
    monkeypatch.setattr(sp,"try_parse_human_header",lambda b,o:{"StatsEnd":100})
    monkeypatch.setattr(sp,"find_identity",lambda b,s,e:{
        "Offset":200,"Name":"Hire","Title":"","Level":2
    })
    monkeypatch.setattr(sp,"find_circle_metadata",lambda *a,**k:{
        "CircleOffset":120,"Background":"Farmhand","BackgroundID":"ABCD",
        "BackgroundLevel":2,"DailyCostMult":1.25,
        "Tail":[{"type":"trait"},{"type":"injury"},{"type":"internal"}],
        "Traits":["Strong","Broken Nose"],
    })
    monkeypatch.setattr(sp,"_parse_tryout_done",lambda *a,**k:True)
    got=sp._candidate_records(bytes(b),{})
    assert len(got)==1
    row=got[0]
    assert row["Settlement"]=="Town"
    assert row["Name"]=="Hire"
    assert row["_ParsedTraits"]==["Strong"]
    assert row["TryoutDone"] is True
    assert row["_DailyCostMult"]==1.25


def test_candidate_records_skips_missing_human(monkeypatch):
    monkeypatch.setattr(sp,"_find_recruitment_rosters",lambda b:(
        [{"Settlement":"Town","StartIndex":0,"EndIndex":1}],[10]
    ))
    monkeypatch.setattr(sp,"_all_valid_human_offsets",lambda b:[])
    assert sp._candidate_records(b"\x00"*100,{})==[]


def test_candidate_records_skips_invalid_header_identity_or_circles(monkeypatch):
    b=bytearray(b"\x00"*500); sig=10; b[sig+29:sig+34]=b"human"
    monkeypatch.setattr(sp,"_find_recruitment_rosters",lambda b:(
        [{"Settlement":"Town","StartIndex":0,"EndIndex":1}],[sig]
    ))
    monkeypatch.setattr(sp,"_all_valid_human_offsets",lambda b:[sig+29])

    monkeypatch.setattr(sp,"try_parse_human_header",lambda *a:None)
    assert sp._candidate_records(bytes(b),{})==[]

    monkeypatch.setattr(sp,"try_parse_human_header",lambda *a:{"StatsEnd":100})
    monkeypatch.setattr(sp,"find_identity",lambda *a:None)
    assert sp._candidate_records(bytes(b),{})==[]

    monkeypatch.setattr(sp,"find_identity",lambda *a:{"Offset":200,"Name":"X","Title":"","Level":1})
    monkeypatch.setattr(sp,"find_circle_metadata",lambda *a:None)
    assert sp._candidate_records(bytes(b),{})==[]
