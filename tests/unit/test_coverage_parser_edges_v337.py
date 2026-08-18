
import struct
import pytest
import bbtool.save_parser as sp


def star_blob(count=0, txt_len=None, stars=None, truncate=False):
    b=bytearray()
    b+=struct.pack("<f",0.0)
    b+=bytes([count])
    if count:
        b+=b"\x00"
        if txt_len is None: txt_len=0
        b+=struct.pack("<H",txt_len)
        b+=b"x"*min(txt_len,4)
        b+=b"\x00"*4
    b+=b"\x00"*8
    b+=bytes(stars or [0]*8)
    if truncate:
        b=b[:6]
    return bytes(b)


def test_parse_stars_rejects_excessive_circle_count():
    assert sp.parse_stars(star_blob(count=33),0) is None


def test_parse_stars_rejects_excessive_text_length():
    assert sp.parse_stars(star_blob(count=1,txt_len=1025),0) is None


def test_parse_stars_rejects_short_or_bad_star_values():
    assert sp.parse_stars(star_blob(truncate=True),0) is None
    assert sp.parse_stars(star_blob(stars=[0,0,0,0,0,0,0,4]),0) is None


def test_parse_levelup_roll_sequence_rejects_bad_metadata():
    b=bytearray()
    b+=struct.pack("<f",0.0)+bytes([33])
    assert sp.parse_levelup_roll_sequence(bytes(b),0) is None

    b=bytearray()
    b+=struct.pack("<f",0.0)+bytes([1])+b"\x00"+struct.pack("<H",1025)
    assert sp.parse_levelup_roll_sequence(bytes(b),0) is None


def test_all_valid_human_offsets_filters_invalid(monkeypatch):
    b=b"xxhuman---human---"
    monkeypatch.setattr(sp,"try_parse_human_header",lambda b,o: o==2)
    assert sp._all_valid_human_offsets(b)==[2]


def test_find_company_human_offsets_error_paths(monkeypatch):
    monkeypatch.setattr(sp,"_find_brother_signature_offsets",lambda b:[])
    with pytest.raises(RuntimeError,match="signature was not found"):
        sp.find_company_brother_human_offsets(b"x"*100)

    monkeypatch.setattr(sp,"_find_brother_signature_offsets",lambda b:[10])
    with pytest.raises(RuntimeError,match="too early"):
        sp.find_company_brother_human_offsets(b"x"*100)

    monkeypatch.setattr(sp,"_find_brother_signature_offsets",lambda b:[30])
    b=bytearray(b"x"*100); b[11]=0
    with pytest.raises(RuntimeError,match="Invalid company roster count"):
        sp.find_company_brother_human_offsets(bytes(b))

    monkeypatch.setattr(sp,"_find_brother_signature_offsets",lambda b:[30])
    b=bytearray(b"x"*100); b[11]=2
    with pytest.raises(RuntimeError,match="only 1 brother signatures"):
        sp.find_company_brother_human_offsets(bytes(b))


def test_find_company_human_offsets_missing_and_invalid_human(monkeypatch):
    monkeypatch.setattr(sp,"_find_brother_signature_offsets",lambda b:[30])
    b=bytearray(b"x"*200); b[11]=1
    with pytest.raises(RuntimeError,match="Could not locate"):
        sp.find_company_brother_human_offsets(bytes(b))

    b[59:64]=b"human"
    monkeypatch.setattr(sp,"try_parse_human_header",lambda *a:None)
    with pytest.raises(RuntimeError,match="Invalid human header"):
        sp.find_company_brother_human_offsets(bytes(b))


def test_find_company_human_offsets_success(monkeypatch):
    monkeypatch.setattr(sp,"_find_brother_signature_offsets",lambda b:[30])
    b=bytearray(b"x"*200); b[11]=1; b[59:64]=b"human"
    monkeypatch.setattr(sp,"try_parse_human_header",lambda *a:{"ok":1})
    offsets,dbg=sp.find_company_brother_human_offsets(bytes(b))
    assert offsets==[59]
    assert dbg["RosterCount"]==1


def test_find_recruitment_rosters_no_signatures(monkeypatch):
    monkeypatch.setattr(sp,"_find_brother_signature_offsets",lambda b:[])
    assert sp._find_recruitment_rosters(b"")==([],[])


def test_find_recruitment_rosters_skip_invalid_candidates(monkeypatch):
    # first signature is company; second begins possible recruitment roster
    sigs=[30,80,130]
    monkeypatch.setattr(sp,"_find_brother_signature_offsets",lambda b:sigs)
    b=bytearray(b"\x00"*200); b[11]=1
    # candidate count zero at second sig => skip, then zero at third => skip
    rosters,got=sp._find_recruitment_rosters(bytes(b))
    assert rosters==[] and got==sigs


def test_find_recruitment_rosters_success(monkeypatch):
    sigs=[30,80]
    monkeypatch.setattr(sp,"_find_brother_signature_offsets",lambda b:sigs)
    b=bytearray(b"\x00"*200); b[11]=1
    struct.pack_into("<I",b,57,1234)
    struct.pack_into("<H",b,61,1)
    monkeypatch.setattr(sp,"_resolve_settlement_reference",lambda b,ref:"Town")
    rosters,got=sp._find_recruitment_rosters(bytes(b))
    assert rosters[0]["Settlement"]=="Town"
    assert rosters[0]["Count"]==1


def test_find_recruitment_rosters_unresolved_settlement(monkeypatch):
    sigs=[30,80]
    monkeypatch.setattr(sp,"_find_brother_signature_offsets",lambda b:sigs)
    b=bytearray(b"\x00"*200); b[11]=1
    struct.pack_into("<I",b,57,1234); struct.pack_into("<H",b,61,1)
    monkeypatch.setattr(sp,"_resolve_settlement_reference",lambda *a:None)
    rosters,_=sp._find_recruitment_rosters(bytes(b))
    assert rosters==[]
