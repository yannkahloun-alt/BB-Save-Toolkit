import pytest
pytestmark=pytest.mark.unit
from bbtool.projection import perks
from bbtool.models import STATS


def test_effect_unknown_stat_is_ignored(bro_factory):
    b=bro_factory()
    effects={s:[] for s in STATS}; effects['NotAStat']=[{'op':'+=','value':99}]
    assert perks.effective_stat_value(b,'HP',60,effects)==60


def test_unknown_perk_is_ignored(bro_factory):
    b=bro_factory(Perks=['Definitely Missing'])
    assert perks.effective_stat_value(b,'HP',60)==60

def test_conditional_and_non_exact_effects_are_ignored(monkeypatch,bro_factory):
    reg={'X':{'Name':'X','Effects':[{'stat':'HP','op':'+=','value':9,'exact':True,'conditional':True},{'stat':'HP','op':'+=','value':11,'exact':False,'conditional':False}]}}
    monkeypatch.setattr(perks,'_load_perk_effects',lambda:reg)
    b=bro_factory(Perks=['X'])
    assert perks.effective_stat_value(b,'HP',60)==60
