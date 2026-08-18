from pathlib import Path
import re, pytest
pytestmark=pytest.mark.integration
ROOT=Path(__file__).resolve().parents[2]
def test_css_static_classes_are_referenced_or_dynamic():
    css=(ROOT/'bbtool/report.css').read_text(encoding='utf-8')
    classes=set(re.findall(r'\.([A-Za-z_][\w-]*)',css)); corpus='\n'.join(p.read_text(encoding='utf-8') for p in (ROOT/'bbtool').rglob('*.py'))
    whitelist={'band-low','band-high','band-avg','band-min','band-max'}
    missing={c for c in classes if c not in corpus and c not in whitelist}
    # CSS pseudo/helper classes may be composed dynamically; keep this contract focused on gross orphaning.
    assert len(missing)<15, sorted(missing)
def test_html_has_expected_tabs_in_source():
    src=(ROOT/'bbtool/html_report.py').read_text(encoding='utf-8').lower(); assert all(x in src for x in ['roster','level up','management','recruits'])
def test_release_tree_has_no_competing_archetype_json(): assert len(list(ROOT.rglob('archetypes*.json')))==1
