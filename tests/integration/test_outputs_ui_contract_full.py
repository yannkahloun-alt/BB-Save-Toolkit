import json
import re
import pytest
pytestmark=[pytest.mark.integration, pytest.mark.coverage_slow]
from bbtool.app.output import create_workspace,write_raw_inputs,write_analysis_json,write_debug_bundle,write_projection_validation
from bbtool.app.analysis import analyze_brothers
from bbtool.html_report import render_html_report
from bbtool.models import STATS


def _future(b,rounds=0): return {s:[2]*rounds for s in STATS}

def test_normal_json_outputs_hide_future_and_validation_exposes_oracle(tmp_path,cfg,bro_factory):
    save=tmp_path/'autosave.sav'; save.write_bytes(b'x'); ws=create_workspace(save,tmp_path/'out')
    b=bro_factory(Level=11,FutureRolls=_future(None,0)); result=analyze_brothers([b],cfg.roles,cfg.classification)
    write_raw_inputs(ws,[b],[]); write_analysis_json(ws,result.fits,result.summaries)
    debug=write_debug_bundle(ws,[b],[],result.fits,result.summaries,cfg.roles,cfg.classification,{}, {})
    validation=write_projection_validation(ws,[b],result.fits,cfg.roles)
    for p in (ws.root/f'{ws.base}-roster.json',debug): assert 'FutureRolls' not in p.read_text(encoding="utf-8")
    assert 'validation-only' in validation.read_text(encoding="utf-8") or 'validation' in validation.read_text(encoding="utf-8")
    for p in ws.root.glob('*.json'):
        obj=json.loads(p.read_text(encoding="utf-8")); assert obj is not None
        assert 'NaN' not in p.read_text(encoding="utf-8") and 'Infinity' not in p.read_text(encoding="utf-8")
    assert ws.generated_at and ws.base.startswith('autosave-')


def test_rendered_html_strategic_and_brother_contracts(tmp_path,cfg,bro_factory):
    b=bro_factory(Name='UIBro',Level=2,LevelPoints=1,CurrentRolls={'HP':4,'Fatigue':3,'Resolve':3,'Initiative':4,'MAtk':2,'RAtk':3,'MDef':3,'RDef':3})
    result=analyze_brothers([b],cfg.roles,cfg.classification)
    html=render_html_report(tmp_path/'x.sav',[b],result.fits,result.summaries,cfg.roles,cfg.classification,'2026-01-01T00:00:00',[])
    assert html.count('selected-path-row')==1
    assert 'rowspan=' in html and 'P5–P95' in html and 'P10–P90' not in html
    assert 'strategy-paths' in html and 'strategy-fit-range' in html
    assert 'heat1' not in ''.join(re.findall(r'<div class="classification-path-metric[^>]*>',html))
    assert 'CURRENT BROTHER DETAILS' in html
    current=html.split('CURRENT BROTHER DETAILS',1)[1].split('ARCHETYPE DETAILS',1)[0]
    assert ' important' not in current
    assert 'EFFECTIVE CURRENT STATS' in html and 'FIT DEVELOPMENT — LEVEL 11' in html and 'optimized stat allocation' in html
    rendered_archetypes = len(result.fits) + sum(
        len(summary.get('StructuralPerkAlternatives', []))
        for summary in result.summaries
    )
    assert 'TARGET PROFILE' in html and html.count('target-profile-chevron') == rendered_archetypes
    assert 'Baseline (minimum useful)' in html and 'Target (desired)' in html and 'Expected (projection)' in html
    assert 'Projected level 11 range' not in html and '>EV<' not in html and 'Weight' in html
    assert 'class-icon' in html
    class_sets = (set(value.split()) for value in re.findall(r'class="([^"]*)"', html))
    assert any({'role-card', 'retained-role'} <= classes for classes in class_sets)


def test_levelup_tab_visibility_and_summary_advice_is_rendered(tmp_path,cfg,bro_factory):
    b=bro_factory(Name='L',Level=10,LevelPoints=1,CurrentRolls={'HP':4,'Fatigue':3,'Resolve':3,'Initiative':4,'MAtk':2,'RAtk':3,'MDef':3,'RDef':3})
    result=analyze_brothers([b],cfg.roles,cfg.classification)
    html=render_html_report(tmp_path/'x',[b],result.fits,result.summaries,cfg.roles,cfg.classification,'',[])
    assert 'data-tab-panel="levelup"' in html and 'Recommended line' in html and result.summaries[0]['LevelUpAdvice']['AnchorRole'] in html
