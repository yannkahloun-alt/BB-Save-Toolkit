from dataclasses import replace
import pytest
pytestmark=pytest.mark.unit
from bbtool.app.output import _roll_luck_to_level11,_role_relevant_roll_rank


def test_roll_luck_respects_stars_and_remaining_rounds(bro_factory):
    b=bro_factory(Level=10,MAtkStars=0,FutureRolls={'MAtk':[3]})
    a=_roll_luck_to_level11(b)['ByStat']['MAtk']
    c=replace(b,MAtkStars=3,FutureRolls={'MAtk':[3]})
    z=_roll_luck_to_level11(c)['ByStat']['MAtk']
    assert a['RollRange']!=z['RollRange']
    b2=bro_factory(Level=9,MAtkStars=0,FutureRolls={'MAtk':[3,3]})
    assert _roll_luck_to_level11(b2)['Rounds']==2


def test_relevant_rank_ignores_target_baseline_and_perks_and_levelup_choices():
    luck={'ByStat':{'MAtk':{'PercentilePct':90},'MDef':{'PercentilePct':10}}}
    base={'name':'X','stats':{'MAtk':{'fit':True,'weight':2,'target':90,'baseline':50},'MDef':{'fit':True,'weight':1,'target':35,'baseline':10}},'perks':{}}
    changed={'name':'X','stats':{'MAtk':{'fit':True,'weight':2,'target':999,'baseline':-999},'MDef':{'fit':True,'weight':1,'target':1,'baseline':0}},'perks':{'Colossus':True},'levelup_choice':['HP']}
    assert _role_relevant_roll_rank(base,luck)==_role_relevant_roll_rank(changed,luck)


def test_relevant_rank_favorable_and_unfavorable_examples():
    high={'ByStat':{'MAtk':{'PercentilePct':90}}}; low={'ByStat':{'MAtk':{'PercentilePct':10}}}; role={'stats':{'MAtk':{'fit':True,'weight':5}}}
    assert _role_relevant_roll_rank(role,high)==90 and _role_relevant_roll_rank(role,low)==10
