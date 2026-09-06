import pytest
from selenium.webdriver.common.by import By

from tests.ui.test_local_app_production_bundle_browser import (
    _company_payload,
    _wait,
    browser,
    surface_server,
)

pytestmark = pytest.mark.ui


def _intrinsic(build_identity, top_fit):
    return {
        "BuildIdentity": build_identity,
        "ViableCount": 0,
        "TopFitPct": top_fit,
        "SecondFitPct": None,
    }


def _intent(build_identity):
    return {
        "BuildIdentity": build_identity,
        "AssignedCount": 0,
        "AssignedViableCount": 0,
        "FreeViableBackupCount": 0,
        "ContestedViableBackupCount": 0,
        "NeedBases": [],
        "FragilityFacts": {"NoIntent": True},
    }


def test_shared_percentage_formatter_preserves_company_null_and_numeric_zero(
    browser, surface_server
):
    server, base_url = surface_server
    company = _company_payload()
    company["company"]["intrinsic_coverage"] = [
        _intrinsic("bf_tank", None),
        _intrinsic("reach_dps", 0.0),
    ]
    company["company"]["intended_coverage"] = [
        _intent("bf_tank"),
        _intent("reach_dps"),
    ]
    server.company = company
    server.result = {"available": True, "freshness": {"status": "current"}}

    browser.get(f"{base_url}/#company")
    _wait(browser, "return document.querySelectorAll('.brother-row').length === 2")
    browser.find_element(By.CSS_SELECTOR, "[data-company-view='planning']").click()
    _wait(browser, "return document.querySelectorAll('#company-planning .coverage-card').length === 2")

    cards = browser.find_elements(By.CSS_SELECTOR, "#company-planning .coverage-card")
    null_card = next(card for card in cards if "BF Tank" in card.text)
    zero_card = next(card for card in cards if "Reach DPS" in card.text)

    assert "Top intrinsic Fit\n—" in null_card.text
    assert "Top intrinsic Fit\n0.0%" in zero_card.text
    assert "Top intrinsic Fit\n0.0%" not in null_card.text

    assert browser.execute_script(
        "return ["
        "formatPct(null), formatPct(undefined), formatPct(''), "
        "formatPct(0), formatPct(12.5), formatPct(NaN), formatPct(Infinity)"
        "]"
    ) == ["—", "—", "—", "0.0%", "12.5%", "—", "—"]
    assert browser.execute_script("return window.__productionBundleErrors") == []
