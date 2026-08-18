import ast, inspect
from pathlib import Path
import pytest
pytestmark=pytest.mark.unit
import bbtool.projection.trajectory as trajectory
from bbtool.models import STATS
from bbtool.html_report import classification_path_html,classification_path_metric_html,classification_path_fit_range_html,current_stat_chips,archetype_detail_body_html
ROOT=Path(__file__).resolve().parents[2]

def test_strategic_path_classes_consistent():
    p={'Label':'Base','Category':'Invest','Role':'Nimble Tank','ProjectedFitPct':88.1,'ProjectedFitLikelyMinPct':80,'ProjectedFitLikelyMaxPct':95,'ProjectedFitFullMinPct':70,'ProjectedFitFullMaxPct':105,'FitFeasibilityPct':12.3}
    assert 'class-invest' in classification_path_html(p); assert 'class-invest' in classification_path_metric_html(p,'FitFeasibilityPct'); assert 'class-invest' in classification_path_fit_range_html(p); assert 'heat' not in classification_path_metric_html(p,'FitFeasibilityPct')
def test_current_brother_details_neutral(bro_factory): assert 'important' not in current_stat_chips(bro_factory(),important_stats=set())
def test_archetype_detail_language(cfg,bro_factory):
    role=cfg.roles[0]; from bbtool.projection.planner import project_role; b=bro_factory(); row=project_role(b,role); html=archetype_detail_body_html(b,row,role); assert 'Fit development' in html and 'Level 11' in html; assert 'Projected level 11 range' not in html; assert '>EV<' not in html; assert 'Weight' in html

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
