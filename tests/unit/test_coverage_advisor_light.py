import pytest
import bbtool.levelup_advisor as adv

pytestmark = pytest.mark.unit


def _role(name='Anchor'):
    return {
        'name': name,
        'stats': {
            'MAtk': {'fit': True, 'weight': 5.0},
            'MDef': {'fit': True, 'weight': 4.0},
            'HP': {'fit': True, 'weight': 2.0},
            'Fatigue': {'fit': True, 'weight': 1.0},
        },
        'perks': {}, 'perk_affinity': {}, 'perk_conflicts': [],
    }


def _base(role='Anchor'):
    return {'Role': role, 'ProjectedFit': .5, 'ProjectedFitPct': 50.0,
            'FitFeasibilityPct': 25.0, 'ProjectedFitLikelyMinPct': 40.0}


def _rolls():
    return {'HP':4,'Fatigue':4,'Resolve':4,'Initiative':5,'MAtk':3,'RAtk':3,'MDef':3,'RDef':3}


def fake_trajectory(bro, role, rounds):
    # Deterministic cheap surrogate: current values drive the ranking.
    score = bro.MAtk * 3 + bro.MDef * 2 + bro.HP * .2 + bro.Fatigue * .05
    return {'expected_pct':score, 'full_min_pct':score-10, 'full_max_pct':score+10,
            'likely_min_pct':score-5, 'likely_max_pct':score+5,
            'feasibility_pct':min(100.0, score)}


def test_roll_quality_and_band_all_branches(bro_factory):
    b=bro_factory()
    assert adv._roll_quality(b,'MAtk',1)==0.0
    assert adv._roll_quality(b,'MAtk',3)==1.0
    assert adv._roll_band(b,'MAtk',1)['Label']=='MIN'
    assert adv._roll_band(b,'MAtk',2)['Label']=='AVG'
    assert adv._roll_band(b,'MAtk',3)['Label']=='MAX'
    # Initiative range 3..5 gives LOW/HIGH around average 4 with out-of-range values.
    assert adv._roll_band(b,'Initiative',3)['Label']=='MIN'
    assert adv._roll_band(b,'Initiative',5)['Label']=='MAX'
    # Force a wider range to hit LOW/HIGH explicitly.
    orig=adv.gain_range
    adv.gain_range=lambda stat, stars:(1,5)
    try:
        assert adv._roll_band(b,'HP',2)['Label']=='LOW'
        assert adv._roll_band(b,'HP',4)['Label']=='HIGH'
    finally:
        adv.gain_range=orig


def test_skipped_notes_filters_sorts_and_explains(bro_factory):
    b=bro_factory()
    role=_role()
    best={'Stats':['MAtk','Fatigue','Resolve']}
    all_rolls={s:adv._roll_band(b,s,v) for s,v in _rolls().items()}
    notes=adv._skipped_important_notes(role,best,all_rolls)
    assert [n['Stat'] for n in notes][:2] == ['MDef','HP']
    assert all('current +' in n['Reason'] for n in notes)
    assert not any(n['Stat']=='RAtk' for n in notes)


def test_advisor_fast_path_full_payload_and_no_gamble(monkeypatch,bro_factory):
    monkeypatch.setattr(adv,'project_fit_trajectory',fake_trajectory)
    monkeypatch.setattr(adv,'compare_fit_trajectories',lambda *a,**k:{'alternative_beats_primary_pct':0.0,'tie_pct':0.0,'primary_beats_alternative_pct':100.0,'mean_delta_pct':-1.0,'avg_upside_when_wins_pct':0.0,'max_upside_pct':0.0,'avg_downside_when_loses_pct':1.0,'max_downside_pct':1.0,'sample_count':512})
    b=bro_factory(Level=10,LevelPoints=1,CurrentRolls=_rolls())
    out=adv.advise_levelup(b,[_role()],[_base()])
    assert out['AnchorRole']=='Anchor'
    assert len(out['Recommended']['Stats'])==3
    assert out['CombinationsEvaluated']==4
    assert out['DistinctFitDecisionsEvaluated']==2
    assert set(out['PickReasons'])==set(out['Recommended']['Stats'])
    assert set(out['AllRolls'])==set(_rolls())
    assert out['Alternative'] is not None
    assert out['Alternative']['Gamble']['Samples']==512


def test_zero_weight_max_roll_is_excluded_from_role_recommendations(monkeypatch,bro_factory):
    monkeypatch.setattr(adv,'project_fit_trajectory',fake_trajectory)
    monkeypatch.setattr(adv,'compare_fit_trajectories',lambda *a,**k:{'alternative_beats_primary_pct':0.0,'tie_pct':0.0,'primary_beats_alternative_pct':100.0,'mean_delta_pct':-1.0,'avg_upside_when_wins_pct':0.0,'max_upside_pct':0.0,'avg_downside_when_loses_pct':1.0,'max_downside_pct':1.0,'sample_count':512})
    role=_role()
    role['stats']['Initiative']={'fit':True,'weight':0.0}
    b=bro_factory(
        Level=10,LevelPoints=1,InitiativeStars=3,
        CurrentRolls=_rolls(),
    )
    out=adv.advise_levelup(b,[role],[_base()])
    assert 'Initiative' not in out['Recommended']['Stats']
    assert 'Initiative' not in out['Alternative']['Stats']
    assert out['AdvisorExcludedStats']['Initiative']=='role weight 0'
    assert out['AdvisorEligibleStats']==['HP','Fatigue','MAtk','MDef']
    assert out['CombinationsEvaluated']==4


def test_positive_weight_initiative_remains_eligible(monkeypatch,bro_factory):
    monkeypatch.setattr(adv,'project_fit_trajectory',fake_trajectory)
    monkeypatch.setattr(adv,'compare_fit_trajectories',lambda *a,**k:{'alternative_beats_primary_pct':0.0,'tie_pct':0.0,'primary_beats_alternative_pct':100.0,'mean_delta_pct':-1.0,'avg_upside_when_wins_pct':0.0,'max_upside_pct':0.0,'avg_downside_when_loses_pct':1.0,'max_downside_pct':1.0,'sample_count':512})
    role=_role()
    role['stats']['Initiative']={'fit':True,'weight':9.0}
    out=adv.advise_levelup(
        bro_factory(Level=10,LevelPoints=1,CurrentRolls=_rolls()),
        [role],[_base()],
    )
    assert 'Initiative' in out['AdvisorEligibleStats']


def test_fewer_than_three_fit_stats_reports_free_picks(monkeypatch,bro_factory):
    monkeypatch.setattr(adv,'project_fit_trajectory',fake_trajectory)
    role=_role()
    role['stats']={
        'MAtk':{'fit':True,'weight':5.0},
        'Initiative':{'fit':True,'weight':0.0},
    }
    out=adv.advise_levelup(
        bro_factory(Level=10,LevelPoints=1,CurrentRolls=_rolls()),
        [role],[_base()],
    )
    assert out['FreePickMode'] is True
    assert out['AdvisorEligibleStats']==['MAtk']
    assert set(out['FreePickStats'])==set(out['Recommended']['Stats'])-{'MAtk'}
    assert 'Initiative' in out['FreePickCandidates']


def test_advisor_gamble_refines_512_to_2048(monkeypatch,bro_factory):
    monkeypatch.setattr(adv,'project_fit_trajectory',fake_trajectory)
    calls=[]
    def compare(a,b,role,rounds,samples):
        calls.append(samples)
        return {'alternative_beats_primary_pct': 2.0, 'tie_pct':1.0,
                'primary_beats_alternative_pct':97.0, 'mean_delta_pct':-1.0,
                'avg_upside_when_wins_pct':2.0,'max_upside_pct':3.0,
                'avg_downside_when_loses_pct':1.0,'max_downside_pct':2.0,
                'sample_count':samples}
    monkeypatch.setattr(adv,'compare_fit_trajectories',compare)
    b=bro_factory(Level=10,LevelPoints=1,CurrentRolls=_rolls())
    out=adv.advise_levelup(b,[_role()],[_base()])
    assert calls==[512,2048]
    assert out['Alternative']['Gamble']['IsGamble'] is True
    assert out['Alternative']['Gamble']['Samples']==2048


def test_advisor_early_returns(monkeypatch,bro_factory):
    monkeypatch.setattr(adv,'project_fit_trajectory',fake_trajectory)
    assert adv.advise_levelup(bro_factory(LevelPoints=0,CurrentRolls=_rolls()),[_role()],[_base()]) is None
    assert adv.advise_levelup(bro_factory(LevelPoints=1,CurrentRolls={'HP':4,'MAtk':3}),[_role()],[_base()]) is None
