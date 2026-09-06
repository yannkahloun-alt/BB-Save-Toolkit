import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import threading

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = pytest.mark.ui

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "bbtool" / "app" / "static"
SETTLEMENTS = ("Birkhaven", "Weissenstadt", "Dornheim", "Eichenwald")


def _candidate(index, name, *, tryout):
    score = 60.0 + (index % 12)
    state = "known_evidence_estimate" if tryout else "prior_only"
    estimate = score if tryout else None
    evidence = ["Tough"] if tryout else []
    need = {
        "build_identity": "bf_tank",
        "role": "BF Tank",
        "need_bases": ["single_point_of_failure"],
        "assigned_viable_count": 1,
        "free_viable_backup_count": 0,
        "contested_viable_backup_count": 0,
        "candidate_plausible": True,
    }
    return {
        "recruit_index": index,
        "facts": {
            "Name": name,
            "Title": "the Long-Named Candidate" if index % 5 == 4 else "",
            "Background": "Farmhand",
            "Level": 1,
            "Settlement": SETTLEMENTS[index // 5],
            "HireCost": 300 + index * 25,
            "DailyWage": 5 + index,
            "TryoutDone": tryout,
        },
        "top_potential": {
            "build_identity": "bf_tank",
            "role": "BF Tank",
            "state": state,
            "background_prior_pct": score - 4.0,
            "candidate_estimate_pct": estimate,
            "score_pct": score if tryout else score - 4.0,
        },
        "potential_availability": {"state": "available", "reason": None},
        "potential": [
            {
                "build_identity": "bf_tank",
                "role": "BF Tank",
                "state": state,
                "background_prior_pct": score - 4.0,
                "candidate_estimate_pct": estimate,
                "evidence": evidence,
            }
        ],
        "relevant_need": {
            "state": "available",
            "reason": None,
            "upstream_reason": None,
            "relevant": need,
            "matches": [need],
            "other_company_gaps": [],
        },
    }


def _publication(job_id, prefix):
    settlements = []
    index = 0
    for settlement in SETTLEMENTS:
        candidates = []
        for ordinal in range(5):
            candidates.append(
                _candidate(
                    index,
                    f"{prefix} {settlement} {ordinal + 1}",
                    tryout=ordinal % 2 == 1,
                )
            )
            index += 1
        settlements.append(
            {
                "settlement": settlement,
                "observation_summary": f"5 candidates in publication {job_id}",
                "candidates": candidates,
            }
        )
    return {
        "available": True,
        "generation": job_id,
        "job_id": job_id,
        "settlements": settlements,
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/api/v1/recruitment":
            body = json.dumps({"data": self.server.payload}).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return
        if path == "/app.js":
            job_id = int(self.server.payload["job_id"])
            body = _bootstrap(job_id).encode("utf-8")
            self._send(200, body, "text/javascript; charset=utf-8")
            return
        if path == "/level-up.js":
            self._send(200, b"'use strict';\n", "text/javascript; charset=utf-8")
            return
        assets = {
            "/app.css": ("app.css", "text/css; charset=utf-8"),
            "/level-up.css": ("level-up.css", "text/css; charset=utf-8"),
            "/recruitment.css": ("recruitment.css", "text/css; charset=utf-8"),
            "/recruitment.js": ("recruitment.js", "text/javascript; charset=utf-8"),
        }
        if path in assets:
            filename, content_type = assets[path]
            self._send(200, (STATIC / filename).read_bytes(), content_type)
            return
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


def _bootstrap(job_id):
    return f"""'use strict';
const state = {{
  result: {{available: true, freshness: {{status: 'current'}}}},
  activeJob: {{id: {job_id}}},
}};
function node(tag, className, text) {{
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}}
function clear(element) {{
  while (element.firstChild) element.removeChild(element.firstChild);
}}
function formatPct(value, fallback = '—') {{
  if (value === null || value === undefined || value === '') return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? `${{number.toFixed(1)}}%` : fallback;
}}
function humanize(value) {{
  return String(value || '').replaceAll('_', ' ').replace(/\\b\\w/g, (letter) => letter.toUpperCase());
}}
function routeFromHash() {{
  return {{workspace: 'recruitment', brotherId: null, section: 'current'}};
}}
function freshnessFromState() {{ return state.result.freshness; }}
async function fetchData(path) {{
  const response = await fetch(path, {{cache: 'no-store', headers: {{Accept: 'application/json'}}}});
  const payload = await response.json();
  if (!response.ok || payload.error) throw new Error(payload.error?.message || 'request failed');
  return payload.data;
}}
window.__recruitmentTest = {{
  errors: [],
  setActiveJob(id) {{ state.activeJob = {{id}}; }},
}};
window.addEventListener('error', (event) => {{
  window.__recruitmentTest.errors.push(String(event.error || event.message));
}});
window.addEventListener('unhandledrejection', (event) => {{
  window.__recruitmentTest.errors.push(String(event.reason));
}});
document.addEventListener('DOMContentLoaded', () => {{
  history.replaceState(null, '', '#recruitment');
  document.querySelectorAll('[data-workspace-panel]').forEach((panel) => {{
    panel.hidden = panel.dataset.workspacePanel !== 'recruitment';
  }});
}});
"""


@pytest.fixture(scope="module")
def surface_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.payload = _publication(101, "A")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _chrome_driver_path():
    configured = os.environ.get("CHROMEWEBDRIVER")
    if configured:
        path = Path(configured)
        if path.is_dir():
            path /= "chromedriver.exe" if os.name == "nt" else "chromedriver"
        if path.is_file():
            return path
    discovered = shutil.which("chromedriver")
    return Path(discovered) if discovered else None


@pytest.fixture
def browser():
    driver_path = _chrome_driver_path()
    if driver_path is None:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("GitHub Actions browser acceptance requires the preinstalled ChromeDriver")
        pytest.skip("ChromeDriver is not installed on this developer machine")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-component-update")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--no-first-run")
    options.add_argument("--host-resolver-rules=MAP * 0.0.0.0, EXCLUDE 127.0.0.1")
    driver = webdriver.Chrome(service=Service(str(driver_path)), options=options)
    try:
        yield driver
    finally:
        driver.quit()


def _set_viewport(driver, width, height=1000):
    driver.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
    )
    WebDriverWait(driver, 5).until(
        lambda current: current.execute_script("return window.innerWidth") == width
    )


def _load_surface(driver, server, base_url, payload, width=1440):
    server.payload = payload
    _set_viewport(driver, width)
    driver.get(f"{base_url}/#recruitment")
    WebDriverWait(driver, 5).until(
        lambda current: current.execute_script(
            "return !document.getElementById('recruitment-layout').hidden "
            "&& document.querySelectorAll('.recruit-row').length === 20"
        )
    )


def _assert_no_js_errors(driver):
    errors = driver.execute_script("return window.__recruitmentTest.errors.slice()")
    assert errors == []


def _scroll_to_settlement(driver, index, expected):
    driver.execute_script(
        """
        const browser = document.getElementById('recruit-browser');
        const header = browser.querySelector('.recruit-browser-head');
        const group = browser.querySelector(`[data-settlement-index="${arguments[0]}"]`);
        const contentTop = group.getBoundingClientRect().top
          - browser.getBoundingClientRect().top + browser.scrollTop;
        const target = contentTop - header.offsetHeight + 8;
        browser.scrollTop = Math.max(0, Math.min(browser.scrollHeight - browser.clientHeight, target));
        browser.dispatchEvent(new Event('scroll'));
        """,
        index,
    )
    WebDriverWait(driver, 5).until(
        lambda current: current.execute_script(
            "return document.getElementById('recruit-current-settlement-name').textContent"
        )
        == expected
    )


def test_recruitment_runtime_interactions_and_responsive_layout(browser, surface_server):
    server, base_url = surface_server
    payload = _publication(101, "A")
    _load_surface(browser, server, base_url, payload)

    browser.execute_script(
        """
        const browser = document.getElementById('recruit-browser');
        browser.scrollTop = 350;
        browser.dispatchEvent(new Event('scroll'));
        """
    )
    before_switch = browser.execute_script(
        "return document.getElementById('recruit-browser').scrollTop"
    )
    browser.execute_script("document.querySelector('[data-recruit-index=\"1\"]').click()")
    WebDriverWait(browser, 5).until(
        lambda current: current.execute_script(
            "return document.getElementById('recruit-name').textContent"
        )
        == "A Birkhaven 2"
    )
    after_switch = browser.execute_script(
        "return document.getElementById('recruit-browser').scrollTop"
    )
    assert abs(after_switch - before_switch) <= 1

    browser.execute_script("document.getElementById('recruit-shortlist-current').click()")
    WebDriverWait(browser, 5).until(
        lambda current: current.execute_script(
            "return document.querySelectorAll('.recruit-shortlist-chip').length"
        )
        == 1
    )
    assert browser.execute_script(
        "return document.getElementById('recruit-name').textContent"
    ) == "A Birkhaven 2"
    assert abs(
        browser.execute_script("return document.getElementById('recruit-browser').scrollTop")
        - after_switch
    ) <= 1

    browser.execute_script("document.getElementById('recruit-compare-toggle').click()")
    WebDriverWait(browser, 5).until(
        lambda current: not current.execute_script(
            "return document.getElementById('recruit-compare').hidden"
        )
    )
    comparison = browser.execute_script(
        """
        return [...document.querySelectorAll('.recruit-compare-line')]
          .map((line) => [line.children[0].textContent, line.children[1].textContent]);
        """
    )
    assert ["Tryout", "Purchased"] in comparison

    for index, settlement in enumerate(SETTLEMENTS):
        _scroll_to_settlement(browser, index, settlement)
    for index in range(len(SETTLEMENTS) - 2, -1, -1):
        _scroll_to_settlement(browser, index, SETTLEMENTS[index])

    for width in (1440, 980, 390):
        _set_viewport(browser, width)
        scroll_width, client_width = browser.execute_script(
            "return [document.documentElement.scrollWidth, document.documentElement.clientWidth]"
        )
        assert scroll_width <= client_width + 1
        if width >= 980:
            visible_rows = browser.execute_script(
                """
                const box = document.getElementById('recruit-browser').getBoundingClientRect();
                return [...document.querySelectorAll('.recruit-row')].filter((row) => {
                  const rect = row.getBoundingClientRect();
                  return rect.bottom > box.top && rect.top < box.bottom;
                }).length;
                """
            )
            assert visible_rows >= 2
        else:
            assert browser.execute_script(
                "return document.getElementById('recruit-mobile-select').offsetParent !== null"
            )
        _assert_no_js_errors(browser)


def test_publication_change_clears_ordinal_scoped_decision_state(browser, surface_server):
    server, base_url = surface_server
    _load_surface(browser, server, base_url, _publication(101, "A"))

    browser.execute_script("document.querySelector('[data-recruit-index=\"1\"]').click()")
    WebDriverWait(browser, 5).until(
        lambda current: current.execute_script(
            "return document.getElementById('recruit-name').textContent"
        )
        == "A Birkhaven 2"
    )
    browser.execute_script("document.getElementById('recruit-shortlist-current').click()")
    WebDriverWait(browser, 5).until(
        lambda current: current.execute_script(
            "return document.querySelectorAll('.recruit-shortlist-chip').length"
        )
        == 1
    )
    browser.execute_script("document.getElementById('recruit-compare-toggle').click()")
    WebDriverWait(browser, 5).until(
        lambda current: not current.execute_script(
            "return document.getElementById('recruit-compare').hidden"
        )
    )

    server.payload = _publication(202, "B")
    browser.execute_script("window.__recruitmentTest.setActiveJob(202)")
    WebDriverWait(browser, 5).until(
        lambda current: current.execute_script(
            "return document.getElementById('recruit-name').textContent"
        )
        == "B Birkhaven 1"
    )

    assert browser.execute_script(
        "return document.querySelectorAll('.recruit-shortlist-chip').length"
    ) == 0
    assert browser.execute_script(
        "return document.getElementById('recruit-shortlist-chips').textContent"
    ) == "No candidates shortlisted."
    assert browser.execute_script(
        "return document.querySelector('[data-recruit-index=\"0\"]').getAttribute('aria-pressed')"
    ) == "true"
    assert browser.execute_script(
        "return document.querySelector('[data-recruit-index=\"1\"]').getAttribute('aria-pressed')"
    ) == "false"
    assert browser.execute_script("return document.getElementById('recruit-compare').hidden")
    _assert_no_js_errors(browser)



def _unavailable_publication(job_id=303):
    payload = _publication(job_id, "Unavailable")
    for settlement in payload["settlements"]:
        for candidate in settlement["candidates"]:
            candidate["top_potential"] = None
            candidate["potential_availability"] = {
                "state": "unavailable",
                "reason": "background_archetype_prior_disabled_pending_validation",
            }
            candidate["potential"] = [
                {
                    "build_identity": "bf_tank",
                    "role": "BF Tank",
                    "state": "unavailable",
                    "reason": "background_archetype_prior_disabled_pending_validation",
                    "background_prior_pct": None,
                    "candidate_estimate_pct": None,
                    "evidence": [],
                },
                {
                    "build_identity": "reach_dps",
                    "role": "Reach DPS",
                    "state": "unavailable",
                    "reason": "background_archetype_prior_disabled_pending_validation",
                    "background_prior_pct": None,
                    "candidate_estimate_pct": None,
                    "evidence": [],
                },
            ]
            candidate["relevant_need"] = {
                "state": "unavailable",
                "reason": "candidate_potential_unavailable",
                "upstream_reason": "background_archetype_prior_disabled_pending_validation",
                "relevant": None,
                "matches": [],
                "other_company_gaps": [],
            }
    first = payload["settlements"][0]["candidates"]
    first[0]["facts"]["Name"] = "Ludolf"
    first[0]["facts"]["Background"] = "Poacher"
    first[1]["facts"]["Name"] = "Ludolf"
    first[1]["facts"]["Background"] = "Hunter"
    return payload


def _partial_publication(job_id=404):
    payload = _publication(job_id, "Partial")
    candidate = payload["settlements"][0]["candidates"][0]
    candidate["top_potential"] = {
        "build_identity": "bf_tank",
        "role": "BF Tank",
        "state": "prior_only",
        "background_prior_pct": 61.0,
        "candidate_estimate_pct": None,
        "score_pct": 61.0,
    }
    candidate["potential_availability"] = {
        "state": "partial",
        "reason": "candidate_potential_partially_unavailable",
    }
    candidate["potential"] = [
        {
            "build_identity": "bf_tank",
            "role": "BF Tank",
            "state": "prior_only",
            "reason": None,
            "background_prior_pct": 61.0,
            "candidate_estimate_pct": None,
            "evidence": [],
        },
        {
            "build_identity": "reach_dps",
            "role": "Reach DPS",
            "state": "unavailable",
            "reason": "background_identity_unavailable",
            "background_prior_pct": None,
            "candidate_estimate_pct": None,
            "evidence": [],
        },
    ]
    candidate["relevant_need"] = {
        "state": "unavailable",
        "reason": "candidate_potential_incomplete",
        "upstream_reason": "candidate_potential_partially_unavailable",
        "relevant": None,
        "matches": [],
        "other_company_gaps": [],
    }
    return payload


def test_globally_unavailable_candidate_potential_is_compact_truthful_and_mobile_useful(browser, surface_server):
    server, base_url = surface_server
    _load_surface(browser, server, base_url, _unavailable_publication(), width=390)

    option_texts = browser.execute_script(
        "return [...document.getElementById('recruit-mobile-select').options].slice(0, 2).map((item) => item.textContent)"
    )
    assert "Poacher" in option_texts[0]
    assert "Hunter" in option_texts[1]
    assert all("Unavailable" not in text for text in option_texts)

    assert browser.execute_script(
        "return document.querySelectorAll('#recruit-potential .recruit-potential-row').length"
    ) == 0
    potential_text = browser.execute_script(
        "return document.getElementById('recruit-potential').textContent"
    )
    assert "Background × Archetype model is disabled pending validation" in potential_text
    assert "0.0%" not in potential_text

    evidence_text = browser.execute_script(
        "return document.getElementById('recruit-evidence').textContent"
    )
    assert "Analysis unavailable" in evidence_text
    assert "Prior-only evidence" not in evidence_text
    need_text = browser.execute_script(
        "return document.getElementById('recruit-needs').textContent"
    )
    assert "candidate potential is disabled pending validation" in need_text
    assert "Company coverage" not in need_text
    assert browser.execute_script(
        "return document.getElementById('recruit-hire-cost').textContent"
    ) == "300g"

    browser.execute_script("document.getElementById('recruit-shortlist-current').click()")
    WebDriverWait(browser, 5).until(
        lambda current: current.execute_script(
            "return document.querySelectorAll('.recruit-shortlist-chip').length"
        ) == 1
    )
    _assert_no_js_errors(browser)


def test_partial_candidate_potential_keeps_per_build_rows_and_null_percent_unknown(browser, surface_server):
    server, base_url = surface_server
    _load_surface(browser, server, base_url, _partial_publication())

    assert browser.execute_script(
        "return document.querySelectorAll('#recruit-potential .recruit-potential-row').length"
    ) == 2
    potential_text = browser.execute_script(
        "return document.getElementById('recruit-potential').textContent"
    )
    assert "61.0%" in potential_text
    assert "Unavailable" in potential_text
    assert "0.0%" not in potential_text
    assert "—" in potential_text
    need_text = browser.execute_script(
        "return document.getElementById('recruit-needs').textContent"
    )
    assert "candidate-potential evidence is incomplete" in need_text
    _assert_no_js_errors(browser)
