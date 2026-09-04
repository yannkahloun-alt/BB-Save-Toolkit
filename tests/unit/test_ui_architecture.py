import ast
import inspect
import re
from pathlib import Path
import pytest
pytestmark=pytest.mark.unit
import bbtool.projection.trajectory as trajectory
from bbtool.models import STATS
from bbtool.html_report import best_fit_copy_control_html,best_fit_copy_text,classification_ceiling_html,classification_summary_html,classification_metric_html,classification_fit_range_html,current_stat_chips,archetype_detail_body_html,development_focus_html,target_profile_html,fit_measure_help_html,optimized_allocation_help_html
ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("role", "fit", "expected"),
    [
        ("BF Tank", 87, "BF Tank 87.0%"),
        ("Reach DPS", 92.04, "Reach DPS 92.0%"),
        ("Pure Bow Archer", 74.06, "Pure Bow Archer 74.1%"),
    ],
)
def test_best_fit_copy_text_reuses_displayed_summary_values(role, fit, expected):
    summary = {"Name": "Must Not Be Copied", "BestRole": role, "ProjectedFitPct": fit}

    assert best_fit_copy_text(summary) == expected
    assert summary["Name"] not in best_fit_copy_text(summary)


def test_best_fit_copy_control_contains_only_exact_escaped_value():
    summary = {"Name": "Ignored", "BestRole": "Tank & <Shield>", "ProjectedFitPct": 87}

    html = best_fit_copy_control_html(summary)

    assert 'data-copy-text="Tank &amp; &lt;Shield&gt; 87.0%"' in html
    assert "Ignored" not in html
    assert "Best Fit:" not in html
    assert " · " not in html and " - " not in html


def test_best_fit_copy_control_uses_shared_browser_behavior():
    source = (ROOT / "bbtool/report.js").read_text(encoding="utf-8")

    assert 'button.dataset.copyText' in source
    assert 'navigator.clipboard.writeText(value)' in source
    assert 'document.execCommand("copy")' in source

def test_strategic_result_classes_consistent():
    p={'Category':'Invest','BestRole':'Nimble Tank','ProjectedFitPct':88.1,'ProjectedFitLikelyMinPct':80,'ProjectedFitLikelyMaxPct':95,'ProjectedFitFullMinPct':70,'ProjectedFitFullMaxPct':105,'FitFeasibilityPct':12.3}
    assert 'class-invest' in classification_summary_html(p); assert 'class-invest' in classification_metric_html(p,'FitFeasibilityPct'); assert 'class-invest' in classification_fit_range_html(p); assert 'heat' not in classification_metric_html(p,'FitFeasibilityPct')


def test_fodder_trash_ceiling_explains_non_monotonic_expected_fit(cfg):
    fodder = {'ProjectedFitPct': 51.6, 'ProjectedFitFullMaxPct': 68.0}
    trash = {'ProjectedFitPct': 52.8, 'ProjectedFitFullMaxPct': 63.0}

    assert 'Full ceiling <b>68.0%</b> · can reach Use (65.0%)' in classification_ceiling_html(fodder, 'Fodder', cfg.classification)
    assert 'Full ceiling <b>63.0%</b> · below Use (65.0%)' in classification_ceiling_html(trash, 'Trash', cfg.classification)
    assert classification_ceiling_html(fodder, 'Use', cfg.classification) == ''


@pytest.mark.parametrize(
    ("fit", "relationship"),
    [
        (99.9, "below 100%"),
        (100.0, "exactly 100%"),
        (102.4, "above 100"),
    ],
)
def test_fit_measure_help_distinguishes_score_from_probability(fit, relationship):
    html = fit_measure_help_html({"ProjectedFitPct": fit, "FitFeasibilityPct": 99.6})
    assert html.startswith('<details class="fit-measure-help">')
    assert "How Fit and P(Fit≥100) differ" in html
    assert "average level-11 archetype score" in html
    assert "score, not a probability" in html
    assert "percentage of those simulated outcomes" in html
    assert relationship in html
    assert f"Fit {fit:.1f}%" in html and "P(Fit≥100) 99.6%" in html


def test_fit_measure_help_does_not_cap_above_target_fit():
    html = fit_measure_help_html({"ProjectedFitPct": 102.4, "FitFeasibilityPct": 99.6})
    assert "Fit 102.4%" in html
    assert "displayed Fit is not capped" in html


def test_optimized_allocation_help_explains_projection_policy():
    html = optimized_allocation_help_html()
    assert html.startswith('<details class="optimized-allocation-help">')
    assert "How stat allocation is optimized" in html
    assert "Only the archetype's Fit stats shown in Target Profile are eligible" in html
    assert "all eligible stats when there are three or fewer" in html
    assert "otherwise it chooses the three" in html
    assert "highest final Fit for this archetype" in html
    for influence in (
        "Talent stars",
        "baselines",
        "targets",
        "weights",
        "Fit-only ceilings",
        "permanent trait",
        "permanent-injury",
    ):
        assert influence in html
    assert "not a guaranteed outcome" in html
    assert "perks do not alter this natural-stat projection" in html
    assert "shown only in effective current stats" in html
    assert "Temporary injuries" in html
    assert "FutureRolls do not drive normal projection choices" in html


def test_current_brother_details_neutral(bro_factory): assert 'important' not in current_stat_chips(bro_factory(),important_stats=set())
def test_archetype_detail_language(cfg,bro_factory):
    role=cfg.roles[0]; from bbtool.projection.planner import project_role; b=bro_factory(); row=project_role(b,role); html=archetype_detail_body_html(b,row,role)
    assert 'FIT DEVELOPMENT — LEVEL 11 <span>(optimized stat allocation)</span>' in html
    assert '<details class="optimized-allocation-help">' in html
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
    assert '<div class="projection-compact-labels" aria-hidden="true">' in html
    for label in ('Baseline', 'Target', 'Expected'):
        assert f'<small>{label}</small>' in html
    if abs(expected - target) < 0.01:
        expected_top = re.search(r'marker-expected\" style=\"[^\"]*--label-top:([0-9]+)px', html).group(1)
        target_top = re.search(r'marker-target\" style=\"[^\"]*--label-top:([0-9]+)px', html).group(1)
        assert expected_top != target_top


def test_collapsed_projection_range_is_explicit_and_keeps_coincident_markers_legible(bro_factory):
    html = development_focus_html(
        bro_factory(RAtk=52),
        {
            'ProjectedComponents': {'RAtk': {'weight': 4}},
            'ProjectedRanges': {'RAtk': {
                'min': 92, 'max': 92, 'ev': 92,
                'baseline': 80, 'target': 92, 'weight': 4,
            }},
        },
    )

    assert '52 <em>→</em> 92' in html
    assert 'projected-range projected-range-collapsed' in html
    assert 'aria-label="Deterministic projected value: 92"' in html
    assert (
        'Deterministic projection: minimum, maximum, and expected all equal 92 '
        'under these displayed assumptions.'
    ) in html
    expected_top = re.search(r'marker-expected" style="[^"]*--label-top:([0-9]+)px', html).group(1)
    target_top = re.search(r'marker-target" style="[^"]*--label-top:([0-9]+)px', html).group(1)
    assert expected_top != target_top


def test_noncollapsed_projection_does_not_claim_deterministic_outcome(bro_factory):
    html = development_focus_html(bro_factory(MDef=13), _projection_row(expected=26.5))
    assert 'projected-range-collapsed' not in html
    assert 'Deterministic projection:' not in html


def test_target_profile_explanation_contract():
    html = target_profile_html(_projection_row(expected=26.5))
    assert html.startswith('<details class="target-profile-explainer">')
    assert ' open' not in html.split('>', 1)[0]
    for heading in ('EXPECTED', 'TARGET', 'BASELINE', 'RANGE', 'WEIGHT'):
        assert f'<strong>{heading}</strong>' in html
    assert 'RANGE (WHISKER)' not in html and 'ⓘ' not in html and 'WELCOME TOUR' not in html


def test_fit_weight_is_visually_and_semantically_connected_to_fit(bro_factory):
    html = development_focus_html(bro_factory(MDef=13), _projection_row(expected=26.5))
    assert 'class="fit-weight"' in html
    assert 'Fit Weight <b>4</b>' in html
    assert 'Importance of this stat in the Fit calculation' in html

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
