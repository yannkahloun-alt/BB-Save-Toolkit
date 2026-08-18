from dataclasses import replace
import pytest
pytestmark=pytest.mark.unit
from bbtool.save_parser import ref_name
from bbtool.models import STATS


def test_reference_name_known_and_unknown():
    refs={'ABCD':{'name':'Sword'}}
    assert ref_name(refs,'abcd')=='Sword'
    assert ref_name(refs,'ffff').startswith('Unknown')


def test_brother_all_stats_and_stars_accessible_and_replace_preserves_hidden_fields(bro_factory):
    b=bro_factory(CurrentRolls={'HP':4},FutureRolls={'HP':[4,4]})
    for s in STATS:
        assert hasattr(b,s) and hasattr(b,s+'Stars')
    c=replace(b,HP=99)
    assert c.HP==99 and c.CurrentRolls==b.CurrentRolls and c.FutureRolls==b.FutureRolls
