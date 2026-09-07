import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from tests.ui.test_recruitment_browser import (
    _assert_no_js_errors,
    _load_surface,
    _publication,
)

pytest_plugins = ["tests.ui.test_recruitment_browser"]
pytestmark = pytest.mark.ui


def _economics_payload():
    payload = _publication(303, "Economy")
    candidates = payload["settlements"][0]["candidates"]

    candidates[0]["facts"]["HireCost"] = None
    candidates[0]["facts"]["DailyWage"] = None

    candidates[1]["facts"]["HireCost"] = 0
    candidates[1]["facts"]["DailyWage"] = 0

    candidates[2]["facts"]["HireCost"] = 425
    candidates[2]["facts"]["DailyWage"] = 9

    candidates[3]["facts"].pop("HireCost")
    candidates[3]["facts"]["DailyWage"] = "Infinity"
    return payload


def _select_candidate(browser, index, expected_name):
    browser.execute_script(
        "document.querySelector(`[data-recruit-index=\"${arguments[0]}\"]`).click()",
        index,
    )
    WebDriverWait(browser, 5).until(
        lambda current: current.find_element(By.ID, "recruit-name").text == expected_name
    )


def test_recruitment_economics_preserve_unknown_zero_and_positive_values(
    browser, surface_server
):
    server, base_url = surface_server
    payload = _economics_payload()
    _load_surface(browser, server, base_url, payload)

    unknown_row = browser.find_element(By.CSS_SELECTOR, '[data-recruit-index="0"]')
    assert unknown_row.find_element(By.CSS_SELECTOR, ".recruit-row-cost").text == "—"
    assert "—/day" in unknown_row.text
    assert "0g" not in unknown_row.text

    unknown_option = browser.find_element(
        By.CSS_SELECTOR, '#recruit-mobile-select option[value="0"]'
    )
    unknown_option_text = unknown_option.get_attribute("textContent")
    assert unknown_option_text.endswith(" · —")
    assert "0g" not in unknown_option_text

    assert browser.find_element(By.ID, "recruit-hire-cost").text == "—"
    assert browser.find_element(By.ID, "recruit-daily-wage").text == "—"

    browser.find_element(By.ID, "recruit-shortlist-current").click()
    WebDriverWait(browser, 5).until(
        lambda current: len(
            current.find_elements(By.CSS_SELECTOR, ".recruit-shortlist-chip")
        )
        == 1
    )
    chip = browser.find_element(By.CSS_SELECTOR, ".recruit-shortlist-chip").text
    assert chip.endswith(" · —")
    assert "0g" not in chip

    browser.find_element(By.ID, "recruit-compare-toggle").click()
    WebDriverWait(browser, 5).until(
        lambda current: not current.find_element(By.ID, "recruit-compare").get_attribute(
            "hidden"
        )
    )
    comparison = browser.execute_script(
        """
        return [...document.querySelectorAll('.recruit-compare-line')]
          .map((line) => [line.children[0].textContent, line.children[1].textContent]);
        """
    )
    assert ["Economics", "— · —/day"] in comparison

    _select_candidate(browser, 1, "Economy Birkhaven 2")
    assert browser.find_element(By.ID, "recruit-hire-cost").text == "0g"
    assert browser.find_element(By.ID, "recruit-daily-wage").text == "0g"

    _select_candidate(browser, 2, "Economy Birkhaven 3")
    assert browser.find_element(By.ID, "recruit-hire-cost").text == "425g"
    assert browser.find_element(By.ID, "recruit-daily-wage").text == "9g"

    _select_candidate(browser, 3, "Economy Birkhaven 4")
    assert browser.find_element(By.ID, "recruit-hire-cost").text == "—"
    assert browser.find_element(By.ID, "recruit-daily-wage").text == "—"

    _assert_no_js_errors(browser)
