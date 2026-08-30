import pytest
from bbtool.levelup_advisor import advise_levelup,_roll_band,_skipped_important_notes
from bbtool.projection.planner import project_role

pytestmark=[pytest.mark.unit, pytest.mark.coverage_slow]


def _rows(b,roles): return [project_role(b,r) for r in roles]

def test_roll_band_low_high_labels_with_star_aware_ranges(bro_factory):
    b=bro_factory(MAtkStars=3)
    # 3-star MAtk is 3..4
    assert _roll_band(b,'MAtk',3)['Label']=='MIN'
    assert _roll_band(b,'MAtk',4)['Label']=='MAX'


def test_skipped_important_stats_are_explained(bro_factory,simple_role):
    role=simple_role(('HP','Fatigue','Resolve','MAtk'))
    best={'Stats':['HP','Fatigue','Resolve']}
    rolls={s:_roll_band(bro_factory(),s,2 if s=='MAtk' else 3) for s in ('HP','Fatigue','Resolve','MAtk')}
    notes=_skipped_important_notes(role,best,rolls)
    assert any(n['Stat']=='MAtk' and 'Fit stat' in n['Reason'] for n in notes)


def test_anchor_role_is_top_role_by_role_sort_key(cfg,bro_factory):
    b=bro_factory(Level=10,LevelPoints=1,CurrentRolls={'HP':4,'Fatigue':3,'Resolve':3,'Initiative':4,'MAtk':2,'RAtk':3,'MDef':3,'RDef':3})
    rows=_rows(b,cfg.roles); advice=advise_levelup(b,cfg.roles,rows)
    from bbtool.classification import role_sort_key
    expected=sorted(rows,key=role_sort_key,reverse=True)[0]['Role']
    assert advice['AnchorRole']==expected


def test_level11_with_pending_point_evaluates_current_pick_then_no_future_rounds(cfg,bro_factory):
    b=bro_factory(Level=11,LevelPoints=1,CurrentRolls={'HP':4,'Fatigue':3,'Resolve':3,'Initiative':4,'MAtk':2,'RAtk':3,'MDef':3,'RDef':3})
    a=advise_levelup(b,cfg.roles,_rows(b,cfg.roles))
    assert a is not None and len(a['Recommended']['Stats'])==3


def test_less_than_three_rolls_returns_none(cfg,bro_factory):
    b=bro_factory(LevelPoints=1,CurrentRolls={'HP':4,'MAtk':3})
    # The advisor rejects incomplete current rolls before consuming role rows.
    assert advise_levelup(b,cfg.roles,[]) is None


def test_advisor_can_ignore_high_roll_on_saturated_stat(bro_factory,simple_role):
    role=simple_role(('HP','Fatigue','Resolve','MAtk'),weights={'HP':1,'Fatigue':2,'Resolve':2,'MAtk':5},baselines={'HP':0,'Fatigue':0,'Resolve':0,'MAtk':0},targets={'HP':60,'Fatigue':120,'Resolve':80,'MAtk':90})
    role['stats']['HP']['projected_curve']=[[0,0],[60,1],[61,1]]
    b=bro_factory(Level=10,LevelPoints=1,HP=60,Fatigue=80,Resolve=40,MAtk=60,CurrentRolls={'HP':4,'Fatigue':2,'Resolve':2,'MAtk':2})
    base={'Role':role['name'],'ProjectedFit':.5,'ProjectedFitPct':50,'FitFeasibilityPct':0,'ProjectedFitLikelyMinPct':40}
    a=advise_levelup(b,[role],[base])
    assert 'HP' not in a['Recommended']['Stats']


def test_advisor_can_invest_in_stat_still_below_baseline_for_level11_payoff(bro_factory,simple_role):
    role=simple_role(('HP','Fatigue','MAtk','MDef'),weights={'HP':1,'Fatigue':1,'MAtk':2,'MDef':8},baselines={'HP':40,'Fatigue':60,'MAtk':50,'MDef':25},targets={'HP':100,'Fatigue':130,'MAtk':90,'MDef':35})
    b=bro_factory(Level=2,LevelPoints=1,HP=80,Fatigue=100,MAtk=70,MDef=0,CurrentRolls={'HP':2,'Fatigue':2,'MAtk':1,'MDef':3})
    base={'Role':role['name'],'ProjectedFit':.5,'ProjectedFitPct':50,'FitFeasibilityPct':0,'ProjectedFitLikelyMinPct':40}
    a=advise_levelup(b,[role],[base])
    assert 'MDef' in a['Recommended']['Stats']

def test_advisor_values_recovery_while_stat_remains_below_baseline(bro_factory,simple_role):
    role=simple_role(
        ('HP','Fatigue','MAtk','MDef'),
        weights={'HP':1,'Fatigue':1,'MAtk':1,'MDef':8},
        baselines={'HP':40,'Fatigue':60,'MAtk':50,'MDef':25},
        targets={'HP':100,'Fatigue':130,'MAtk':90,'MDef':35},
    )
    b=bro_factory(
        Level=10,LevelPoints=1,HP=100,Fatigue=130,MAtk=90,MDef=20,
        CurrentRolls={'HP':4,'Fatigue':4,'MAtk':3,'MDef':3},
    )
    advice=advise_levelup(b,[role],_rows(b,[role]))
    assert 'MDef' in advice['Recommended']['Stats']
