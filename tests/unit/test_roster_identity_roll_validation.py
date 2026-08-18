import bbtool.save_parser as sp


def test_find_roster_identity_rejects_star_candidate_without_roll_stream(monkeypatch):
    data = bytearray(220)

    def put_lp(offset, text):
        raw = text.encode("ascii")
        data[offset:offset + 2] = len(raw).to_bytes(2, "little")
        data[offset + 2:offset + 2 + len(raw)] = raw
        return offset + 2 + len(raw)

    q1 = put_lp(10, "Kori")
    q1 = put_lp(q1, "")
    q2 = put_lp(100, "Kurt")
    q2 = put_lp(q2, "the Wise")

    monkeypatch.setattr(sp, "f32", lambda b, q: 1.0)
    monkeypatch.setattr(sp, "u32", lambda b, q: 0)

    for q, level in ((q1, 1), (q2, 5)):
        data[q + 14] = level
        data[q + 15] = 0
        data[q + 16] = 0
        data[q + 17] = 0

    monkeypatch.setattr(sp, "parse_stars", lambda b, meta_end: {"HPStars": 1})
    monkeypatch.setattr(
        sp,
        "parse_levelup_roll_sequence",
        lambda b, meta_end: {"HP": [4]} if meta_end == q1 + 18 else None,
    )

    ident, stars, count = sp.find_roster_identity(bytes(data), 0, len(data))

    assert count == 1
    assert ident["Name"] == "Kori"
    assert ident["MetaEnd"] == q1 + 18
    assert stars == {"HPStars": 1}
