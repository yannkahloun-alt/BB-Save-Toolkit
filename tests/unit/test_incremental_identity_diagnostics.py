from bbtool.incremental.identity import future_roll_suffix_shift, progression_evidence


def test_future_roll_suffix_shift_detects_common_level_consumption(bro_factory):
    previous = bro_factory(FutureRolls={
        "HP":[4,4,4], "Fatigue":[3,4,3], "Resolve":[2,3,2],
        "Initiative":[4,5,4], "MAtk":[2,3,1], "RAtk":[3,4,2],
        "MDef":[2,3,2], "RDef":[2,2,3],
    })
    current = bro_factory(FutureRolls={
        "HP":[4,4], "Fatigue":[4,3], "Resolve":[3,2],
        "Initiative":[5,4], "MAtk":[3,1], "RAtk":[4,2],
        "MDef":[3,2], "RDef":[2,3],
    })
    assert future_roll_suffix_shift(previous, current) == 1


def test_future_roll_suffix_shift_rejects_inconsistent_stats(bro_factory):
    previous = bro_factory(FutureRolls={"HP":[4,4,4], "MAtk":[1,2,3]})
    current = bro_factory(FutureRolls={"HP":[4,4], "MAtk":[9,3]})
    assert future_roll_suffix_shift(previous, current) is None


def test_progression_evidence_is_name_and_offset_independent(bro_factory):
    rolls={"MAtk":[1,2,3]}
    a=bro_factory(Name="Old", HumanOffset=1, FutureRolls=rolls)
    b=bro_factory(Name="New", HumanOffset=999, FutureRolls=rolls)
    assert progression_evidence(a)==progression_evidence(b)
