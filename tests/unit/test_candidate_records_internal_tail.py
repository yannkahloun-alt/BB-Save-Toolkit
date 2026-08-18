import bbtool.save_parser as sp


def test_candidate_records_filters_internal_tail_before_strict_trait_pairing(monkeypatch):
    b = bytearray(b"\x00" * 500)
    sig = 10
    b[sig + 29:sig + 34] = b"human"

    monkeypatch.setattr(
        sp, "_find_recruitment_rosters",
        lambda b: ([{"Settlement": "Town", "StartIndex": 0, "EndIndex": 1}], [sig]),
    )
    monkeypatch.setattr(sp, "_all_valid_human_offsets", lambda b: [sig + 29, 400])
    monkeypatch.setattr(sp, "try_parse_human_header", lambda b, o: {"StatsEnd": 100})
    monkeypatch.setattr(
        sp, "find_identity",
        lambda b, s, e: {"Offset": 200, "Name": "Hire", "Title": "", "Level": 2},
    )
    monkeypatch.setattr(
        sp, "find_circle_metadata",
        lambda *a, **k: {
            "CircleOffset": 120,
            "Background": "Caravan Hand",
            "BackgroundID": "BG",
            "BackgroundLevel": 2,
            "DailyCostMult": 1.0,
            "Tail": [
                {"id": "T1", "type": "trait"},
                {"id": "T2", "type": "trait"},
                {"id": "I1", "type": "internal"},
                {"id": "I2", "type": "internal"},
            ],
            "Traits": ["Deathwish", "Paranoid"],
        },
    )
    monkeypatch.setattr(sp, "_parse_tryout_done", lambda *a, **k: False)

    refs = {
        "T1": {"type": "trait"},
        "T2": {"type": "trait"},
        "I1": {"type": "internal"},
        "I2": {"type": "internal"},
    }

    got = sp._candidate_records(bytes(b), refs)

    assert len(got) == 1
    assert got[0]["_ParsedTraits"] == ["Deathwish", "Paranoid"]
