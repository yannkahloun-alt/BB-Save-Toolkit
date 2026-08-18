from pathlib import Path
import pytest
pytestmark=pytest.mark.integration
ROOT=Path(__file__).resolve().parents[2]


def test_javascript_has_all_tab_and_category_filter_functions():
    js=(ROOT/'bbtool/report.js').read_text(encoding="utf-8")
    assert 'function showTab' in js and 'function filterCategory' in js
    for tab in ('roster','levelup','management','recruits'):
        assert tab in (ROOT/'bbtool/html_report.py').read_text(encoding="utf-8")


def test_dynamic_band_classes_are_explicitly_present_or_generated():
    css=(ROOT/'bbtool/report.css').read_text(encoding="utf-8"); js=(ROOT/'bbtool/report.js').read_text(encoding="utf-8"); py=(ROOT/'bbtool/html_report.py').read_text(encoding="utf-8")
    for cls in ('band-low','band-high'):
        assert cls in css
    assert 'band-' in js or 'band-' in py
