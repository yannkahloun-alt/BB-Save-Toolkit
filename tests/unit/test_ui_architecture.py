import ast
import inspect
import re
from pathlib import Path
import pytest
pytestmark=pytest.mark.unit
import bbtool.projection.trajectory as trajectory
from bbtool.models import STATS
from bbtool.html_report import classification_path_html,classification_path_metric_html,classification_path_fit_range_html,current_stat_chips,archetype_detail_body_html,development_focus_html,target_profile_html
ROOT=Path(__file__).resolve().parents[2]

def test_strategic_path_classes_consistent():
    p={'Label':'Base','Category':'Invest','Role':'Nimble Tank','ProjectedFitPct':88.1,'ProjectedFitLikelyMinPct':80,'ProjectedFitLikelyMaxPct':95,'ProjectedFitFullMinPct':70,'ProjectedFitFullMaxPct':105,'FitFeasibilityPct':12.3}
    assert 'class-invest' in classification_path_html(p); assert 'class-invest' in classification_path_metric_html(p,'FitFeasibilityPct'); assert 'class-invest' in classification_path_fit_range_html(p); assert 'heat' not in classification_path_metric_html(p,'FitFeasibilityPct')
def test_current_brother_details_neutral(bro_factory): assert 'important' not in current_stat_chips(bro_factory(),important_stats=set())
def test_archetype_detail_language(cfg,bro_factory):
    role=cfg.roles[0]; from bbtool.projection.planner import project_role; b=bro_factory(); row=project_role(b,role); html=archetype_detail_body_html(b,row,role)
    assert 'FIT DEVELOPMENT — LEVEL 11 <span>(optimized stat allocation)</span>' in html
    assert 'TARGET PROFILE' in html and 'EFFECTIVE CURRENT STATS' in html
    assert 'Projected level 11 range' not in html and '>EV<' not in html and 'Weight' in html
    assert 'with optimal rolls' not in html and 'vs Target' not in html
    assert html.count('target-profile-chevron') == 1
    assert html.count('projection-marker marker-baseline') == len(row['ProjectedRanges'])
    assert html.count('projection-marker marker-target') == len(row['ProjectedRanges'])
    assert html.count('projection-marker marker-expected') == len(row['ProjectedRanges'])


def _projection_row(*, expected, baseline=32, target=42, low=13, high=37):
    return {
        'ProjectedComponents': {'MDef': {'weight': 4}},
        'ProjectedRanges': {'MDef': {
            'min': low, 'max': high, 'ev': expected,
            'baseline': baseline, 'target': target, 'weight': 4,
        }},
    }


@pytest.mark.parametrize(('expected','target'), [(26.5,42), (37,42), (42.001,42), (47,42), (44,44)])
def test_projection_markers_share_live_numeric_axis(bro_factory, expected, target):
    html = development_focus_html(bro_factory(MDef=13), _projection_row(expected=expected, target=target))
    positions = {
        kind: float(re.search(rf'marker-{kind}\" style=\"left:([0-9.]+)%', html).group(1))
        for kind in ('baseline', 'target', 'expected')
    }
    values = {'baseline': 32, 'target': target, 'expected': expected}
    assert sorted(positions, key=positions.get) == sorted(values, key=values.get)
    assert 'projected-range' in html
    assert '<small class="focus-level">' not in html
    if abs(expected - target) < 0.01:
        expected_top = re.search(r'marker-expected\" style=\"[^\"]*--label-top:([0-9]+)px', html).group(1)
        target_top = re.search(r'marker-target\" style=\"[^\"]*--label-top:([0-9]+)px', html).group(1)
        assert expected_top != target_top


def test_target_profile_explanation_contract():
    html = target_profile_html(_projection_row(expected=26.5))
    assert html.startswith('<details class="target-profile-explainer">')
    assert ' open' not in html.split('>', 1)[0]
    for heading in ('EXPECTED', 'TARGET', 'BASELINE', 'RANGE', 'WEIGHT'):
        assert f'<strong>{heading}</strong>' in html
    assert 'RANGE (WHISKER)' not in html and 'ⓘ' not in html and 'WELCOME TOUR' not in html

def test_single_advisor_definition():
    tree=ast.parse((ROOT/'bbtool/levelup_advisor.py').read_text(encoding="utf-8")); assert sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=='advise_levelup' for n in ast.walk(tree))==1
def test_single_trajectory_definition():
    tree=ast.parse((ROOT/'bbtool/projection/trajectory.py').read_text(encoding="utf-8")); assert sum(isinstance(n,ast.FunctionDef) and n.name=='project_fit_trajectory' for n in ast.walk(tree))==1
def test_seeded_calls_shared_engine(): assert 'project_fit_trajectory(' in inspect.getsource(trajectory.project_seeded_fit_trajectory)
def test_advisor_never_mentions_future_rolls(): assert 'FutureRolls' not in (ROOT/'bbtool/levelup_advisor.py').read_text(encoding="utf-8")
def test_classification_never_mentions_future_rolls(): assert 'FutureRolls' not in (ROOT/'bbtool/classification.py').read_text(encoding="utf-8")
def test_no_monte_carlo_in_active_code_docs():
    bad=[]
    for p in list((ROOT/'bbtool').rglob('*.py'))+list((ROOT/'docs').rglob('*.md')):
        if 'monte-carlo' in p.read_text(encoding='utf-8').lower(): bad.append(str(p))
    assert not bad
def test_single_archetype_config(): assert [p.name for p in (ROOT/'config').glob('*archetype*.json')]==['archetypes.json']

def test_html_levelup_renderer_does_not_call_or_import_advisor():
    src=(ROOT/'bbtool/html_report.py').read_text(encoding="utf-8")
    assert 'advise_levelup' not in src

def test_effective_raw_only_when_value_differs(bro_factory):
    b=bro_factory(HP=60)
    same=current_stat_chips(b,effective={'HP':60,**{s:getattr(b,s) for s in STATS if s!='HP'}})
    diff=current_stat_chips(b,effective={'HP':75,**{s:getattr(b,s) for s in STATS if s!='HP'}})
    assert 'raw 60' not in same and 'raw 60' in diff
