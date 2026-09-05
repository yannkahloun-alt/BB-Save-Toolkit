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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = pytest.mark.ui

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "bbtool" / "app" / "static"


def _data(value):
    return json.dumps({"data": value}, sort_keys=True).encode("utf-8")


def _error(status, code, message):
    return status, json.dumps({"error": {"code": code, "message": message}}).encode(
        "utf-8"
    )


def _base_catalog(revision=9):
    roles = [
        {"id": "bf_tank", "name": "BF Tank", "stats": {"MDef": {"target": 35}}},
        {
            "id": "reach_dps",
            "name": "Reach DPS",
            "stats": {"MAtk": {"target": 90}},
        },
    ]
    return {
        "revision": revision,
        "roles": roles,
        "definition_hashes": {
            "bf_tank": "sha256:bf-current",
            "reach_dps": "sha256:reach-current",
        },
        "provenance": {"bf_tank": "base", "reach_dps": "base"},
        "user_entries": [],
    }


def _conflicted_catalog(revision=7):
    entries = [
        {
            "kind": "override",
            "id": "bf_tank",
            "base_definition_hash": "sha256:bf-old",
            "patch": {"name": "Old BF Tank"},
        },
        {
            "kind": "override",
            "id": "reach_dps",
            "base_definition_hash": "sha256:reach-old",
            "patch": {"name": "Old Reach DPS"},
        },
    ]
    conflicts = []
    errors = []
    for index, entry in enumerate(entries):
        error = (
            f"entries[{index}].base_definition_hash conflicts with the current "
            f"shipped definition for {entry['id']}"
        )
        errors.append(error)
        conflicts.append(
            {
                "entry_index": index,
                "id": entry["id"],
                "kind": "override",
                "reason": "base_definition_changed",
                "recovery_operation": "reset_base",
                "errors": [error],
                "persisted_base_definition_hash": entry["base_definition_hash"],
                "current_base_definition_hash": f"sha256:{entry['id']}-current",
            }
        )
    return {
        "revision": revision,
        "roles": [],
        "definition_hashes": {},
        "provenance": {},
        "user_entries": entries,
        "catalog_conflict": {
            "code": "shipped_user_entry_conflict",
            "errors": errors,
            "entries": conflicts,
        },
    }


def _brother(identity, name, assigned, best):
    return {
        "brother_id": identity,
        "brother_identity": {"confidence": "exact"},
        "snapshot": {
            "Name": name,
            "Level": 5,
            "Background": "Farmhand",
            "MAtk": 72,
            "MDef": 24,
            "Fatigue": 108,
            "Resolve": 43,
            "HP": 73,
            "Initiative": 101,
            "RAtk": 40,
            "RDef": 7,
            "Equipment": {},
            "GearFatigue": {"Total": 0},
            "Perks": [],
            "Traits": [],
            "Injuries": [],
        },
        "assigned_build": {
            "build_identity": assigned,
            "display_name": "BF Tank" if assigned == "bf_tank" else "Reach DPS",
            "status": "current",
        },
        "best_fit": {
            "role": best,
            "category": "Strong",
            "fit_pct": 82.0,
            "likely_min_pct": 77.0,
            "likely_max_pct": 87.0,
            "feasibility_pct": 68.0,
        },
        "assignment_address": None,
        "mechanical_facts": [],
        "potential": [
            {
                "build_identity": "bf_tank",
                "role": "BF Tank",
                "fit_pct": 72.0,
                "likely_min_pct": 67.0,
                "likely_max_pct": 77.0,
                "full_min_pct": 61.0,
                "full_max_pct": 82.0,
                "feasibility_pct": 54.0,
                "projected_ranges": {},
            },
            {
                "build_identity": "reach_dps",
                "role": "Reach DPS",
                "fit_pct": 82.0,
                "likely_min_pct": 77.0,
                "likely_max_pct": 87.0,
                "full_min_pct": 70.0,
                "full_max_pct": 91.0,
                "feasibility_pct": 68.0,
                "projected_ranges": {},
            },
        ],
    }


def _company_payload():
    return {
        "available": True,
        "assignment_revision": 4,
        "builds": [
            {"build_identity": "bf_tank", "display_name": "BF Tank"},
            {"build_identity": "reach_dps", "display_name": "Reach DPS"},
        ],
        "company": {
            "intent_fresh": True,
            "intrinsic_coverage": [],
            "intended_coverage": [],
        },
        "brothers": [
            _brother("bro-1", "Aldric", "bf_tank", "Reach DPS"),
            _brother("bro-2", "Beatrix", "reach_dps", "BF Tank"),
        ],
    }


def _candidate_decision(identity, name, assigned, best):
    rolls = [
        {
            "stat": stat,
            "offered_roll": roll,
            "current_value": 60 + roll,
            "stars": 2,
            "band": "high",
            "min_roll": 2,
            "max_roll": 4,
            "quality": 0.75,
            "primary": stat != "RDef",
            "runner_up": stat == "RDef",
        }
        for stat, roll in (("MAtk", 3), ("MDef", 3), ("Fatigue", 4), ("RDef", 3))
    ]
    consequence = {
        "Role": best,
        "FitBeforePct": 80.0,
        "FitAfterPct": 82.0,
        "FitDeltaPct": 2.0,
        "FitFeasibilityBeforePct": 60.0,
        "FitFeasibilityAfterPct": 64.0,
        "FitLikelyMinAfterPct": 77.0,
        "FitLikelyMaxAfterPct": 87.0,
    }
    primary = {
        "Stats": ["MAtk", "MDef", "Fatigue"],
        "Rolls": {"MAtk": 3, "MDef": 3, "Fatigue": 4},
        "AnchorFitBeforePct": 80.0,
        "AnchorFitAfterPct": 82.0,
        "FitDeltaPct": 2.0,
        "Consequences": {
            "AssignedBuild": consequence | {"Role": assigned},
            "BestFit": consequence,
        },
    }
    runner = {
        "Stats": ["MAtk", "MDef", "RDef"],
        "Rolls": {"MAtk": 3, "MDef": 3, "RDef": 3},
        "AnchorFitBeforePct": 80.0,
        "AnchorFitAfterPct": 81.0,
        "FitDeltaPct": 1.0,
        "Consequences": primary["Consequences"],
    }
    return {
        "brother_id": identity,
        "name": name,
        "level": 5,
        "background": "Farmhand",
        "assigned_build": {
            "build_identity": "bf_tank" if assigned == "BF Tank" else "reach_dps",
            "display_name": assigned,
            "status": "current",
        },
        "best_fit": {"role": best, "fit_pct": 82.0},
        "rolls": rolls,
        "primary": primary,
        "runner_up": runner,
        "gamble": None,
        "explain": {
            "pick_reasons": {"MAtk": "Highest current impact"},
            "skipped_important": [],
            "method": "Structured Advisor evidence",
        },
    }


def _level_up_payload():
    return {
        "available": True,
        "decisions": [
            _candidate_decision("bro-1", "Aldric", "BF Tank", "Reach DPS"),
            _candidate_decision("bro-2", "Beatrix", "Reach DPS", "BF Tank"),
        ],
    }


def _recruit(index, name, known):
    state = "known_evidence_estimate" if known else "prior_only"
    estimate = 71.0 if known else None
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
            "Background": "Farmhand",
            "Level": 1,
            "HireCost": 350 + index * 50,
            "DailyWage": 7 + index,
            "TryoutDone": known,
        },
        "top_potential": {
            "build_identity": "bf_tank",
            "role": "BF Tank",
            "state": state,
            "background_prior_pct": 64.0,
            "candidate_estimate_pct": estimate,
            "score_pct": estimate if known else 64.0,
        },
        "potential": [
            {
                "build_identity": "bf_tank",
                "role": "BF Tank",
                "state": state,
                "background_prior_pct": 64.0,
                "candidate_estimate_pct": estimate,
                "evidence": ["Tough"] if known else [],
            }
        ],
        "relevant_need": {
            "state": "available",
            "relevant": need,
            "matches": [need],
            "other_company_gaps": [],
        },
    }


def _recruitment_payload():
    return {
        "available": True,
        "generation": 42,
        "job_id": 42,
        "settlements": [
            {
                "settlement": "Birkhaven",
                "observation_summary": "2 candidates in current publication",
                "candidates": [
                    _recruit(0, "Cuno", False),
                    _recruit(1, "Dietrich", True),
                ],
            }
        ],
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def _send(self, status, body, content_type="application/json; charset=utf-8"):
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
        if path == "/app.js":
            bootstrap = b"""'use strict';
window.__productionBundleErrors = [];
window.addEventListener('error', (event) => window.__productionBundleErrors.push(String(event.error || event.message)));
window.addEventListener('unhandledrejection', (event) => window.__productionBundleErrors.push(String(event.reason)));
"""
            self._send(
                200,
                bootstrap
                + (STATIC / "app.js").read_bytes()
                + b"\n"
                + (STATIC / "catalog_recovery.js").read_bytes(),
                "text/javascript; charset=utf-8",
            )
            return
        if path in ("/level-up.js", "/recruitment.js"):
            self._send(
                200,
                (STATIC / path.removeprefix("/")).read_bytes(),
                "text/javascript; charset=utf-8",
            )
            return
        assets = {
            "/app.css": ("app.css", "text/css; charset=utf-8"),
            "/level-up.css": ("level-up.css", "text/css; charset=utf-8"),
            "/recruitment.css": ("recruitment.css", "text/css; charset=utf-8"),
        }
        if path in assets:
            filename, content_type = assets[path]
            self._send(200, (STATIC / filename).read_bytes(), content_type)
            return
        if path == "/api/v1/session":
            self._send(200, _data({"token": self.server.session_token}))
            return
        if path == "/api/v1/followed-save":
            self._send(200, _data(self.server.followed))
            return
        if path == "/api/v1/shell":
            self._send(
                200,
                _data(
                    {
                        "followed_save": {
                            "name": "company.sav",
                            "available": True,
                            "freshness": {"status": "current"},
                        },
                        "result": self.server.result,
                        "analysis_health": None,
                        "active_job": {
                            "id": 42,
                            "status": "completed",
                            "progress": {
                                "completed_count": 0,
                                "latest_stage": None,
                                "latest_status": None,
                            },
                        },
                    }
                ),
            )
            return
        if path == "/api/v1/company-brother":
            self._send(200, _data(self.server.company))
            return
        if path == "/api/v1/level-up":
            self._send(200, _data(self.server.level_up))
            return
        if path == "/api/v1/recruitment":
            self._send(200, _data(self.server.recruitment))
            return
        if path == "/api/v1/archetypes":
            self._send(200, _data(self.server.catalog))
            return
        if path == "/api/v1/archetypes/export":
            document = json.dumps(
                {
                    "schema": "bbtool.user-archetypes-export.v1",
                    "entries": self.server.catalog["user_entries"],
                },
                indent=2,
                sort_keys=True,
            ) + "\n"
            self._send(200, _data({"document": document}))
            return
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.headers.get("X-BBST-Session") != self.server.session_token:
            status, body = _error(403, "invalid_session", "invalid test session")
            self._send(status, body)
            return
        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size) or b"{}")
        path = self.path.split("?", 1)[0]
        self.server.posts.append((path, payload.copy()))

        if path == "/api/v1/archetypes/reset-base":
            if payload["expected_revision"] != self.server.catalog["revision"]:
                status, body = _error(409, "state_revision_conflict", "catalog revision conflict")
                self._send(status, body)
                return
            identity = payload["id"]
            catalog = json.loads(json.dumps(self.server.catalog))
            conflicts = catalog.get("catalog_conflict", {}).get("entries", [])
            if not any(item["id"] == identity for item in conflicts):
                status, body = _error(409, "catalog_conflict", "not a recoverable conflict")
                self._send(status, body)
                return
            catalog["revision"] += 1
            catalog["user_entries"] = [
                entry
                for entry in catalog["user_entries"]
                if not (
                    entry.get("id") == identity
                    and entry.get("kind") in {"override", "disabled"}
                )
            ]
            remaining = [item for item in conflicts if item["id"] != identity]
            if remaining:
                catalog["catalog_conflict"]["entries"] = remaining
                catalog["catalog_conflict"]["errors"] = [
                    error for item in remaining for error in item["errors"]
                ]
            else:
                recovered = _base_catalog(catalog["revision"])
                recovered["user_entries"] = catalog["user_entries"]
                catalog = recovered
            self.server.catalog = catalog
            self.server.result = {
                "available": True,
                "freshness": {
                    "status": "stale",
                    "reason": "effective_archetypes_changed",
                },
            }
            self._send(
                200,
                _data(
                    catalog
                    | {
                        "freshness": {
                            "status": "stale",
                            "reason": "effective_archetypes_changed",
                            "recompute": "request_analysis",
                        }
                    }
                ),
            )
            return

        if path == "/api/v1/analysis/jobs":
            if "catalog_conflict" in self.server.catalog:
                status, body = _error(
                    422,
                    "validation_failed",
                    "effective archetypes remain unavailable during recovery",
                )
                self._send(status, body)
                return
            self.server.result = {
                "available": True,
                "freshness": {"status": "current"},
            }
            self._send(202, _data({"id": 43, "status": "queued"}))
            return

        status, body = _error(404, "not_found", "endpoint not found")
        self._send(status, body)


@pytest.fixture(scope="module")
def surface_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.session_token = "production-bundle-test-token"
    server.followed = {
        "revision": 4,
        "selected_path": r"C:\Users\Player\savegames\company.sav",
        "auto_refresh": False,
        "available": True,
        "freshness": {"status": "current"},
    }
    server.result = {"available": True, "freshness": {"status": "current"}}
    server.company = _company_payload()
    server.level_up = _level_up_payload()
    server.recruitment = _recruitment_payload()
    server.catalog = _conflicted_catalog()
    server.posts = []
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


def _wait(driver, script):
    WebDriverWait(driver, 5).until(lambda current: current.execute_script(script))


def _click_workspace(driver, workspace):
    driver.find_element(By.CSS_SELECTOR, f".primary-nav [data-workspace='{workspace}']").click()
    _wait(driver, f"return location.hash === '#{workspace}'")


def test_real_local_bundle_preserves_child_surfaces_and_multi_conflict_recovery(
    browser, surface_server
):
    server, base_url = surface_server
    server.catalog = _conflicted_catalog()
    server.posts = []
    server.result = {"available": True, "freshness": {"status": "current"}}

    browser.get(f"{base_url}/#company")
    _wait(browser, "return document.querySelectorAll('.brother-row').length === 2")

    search = browser.find_element(By.ID, "roster-search")
    search.send_keys("Aldric")
    _wait(browser, "return document.querySelectorAll('.brother-row').length === 1")
    browser.find_element(By.CSS_SELECTOR, ".brother-row").click()
    _wait(browser, "return document.getElementById('brother-name').textContent === 'Aldric'")
    assert browser.find_element(By.ID, "best-fit-role").text == "Reach DPS"
    browser.find_element(By.ID, "back-to-company").click()
    _wait(browser, "return location.hash === '#company' && !document.getElementById('company-view').hidden")
    assert browser.find_element(By.ID, "roster-search").get_attribute("value") == "Aldric"
    assert len(browser.find_elements(By.CSS_SELECTOR, ".brother-row")) == 1

    _click_workspace(browser, "level-up")
    _wait(browser, "return !document.getElementById('levelup-layout').hidden && document.getElementById('levelup-brother-name').textContent === 'Aldric'")
    assert len(browser.find_elements(By.CSS_SELECTOR, "#levelup-rolls .levelup-roll")) == 4
    assert browser.find_element(By.ID, "levelup-assigned-build").text == "BF Tank"
    assert browser.find_element(By.ID, "levelup-best-fit").text == "Reach DPS"
    browser.execute_script(
        """
        const select = document.getElementById('levelup-brother-select');
        select.value = 'bro-2';
        select.dispatchEvent(new Event('change', {bubbles: true}));
        """
    )
    _wait(browser, "return document.getElementById('levelup-brother-name').textContent === 'Beatrix'")
    assert browser.find_element(By.ID, "levelup-assigned-build").text == "Reach DPS"
    assert browser.find_element(By.ID, "levelup-best-fit").text == "BF Tank"

    _click_workspace(browser, "recruitment")
    _wait(browser, "return !document.getElementById('recruitment-layout').hidden && document.querySelectorAll('.recruit-row').length === 2")
    browser.find_elements(By.CSS_SELECTOR, ".recruit-row")[1].click()
    _wait(browser, "return document.getElementById('recruit-name').textContent === 'Dietrich'")
    browser.find_element(By.ID, "recruit-shortlist-current").click()
    assert browser.find_element(By.ID, "recruit-name").text == "Dietrich"
    assert "Remove" in browser.find_element(By.ID, "recruit-shortlist-current").text

    _wait(browser, "return document.getElementById('local-app-trigger') !== null")
    browser.find_element(By.ID, "local-app-trigger").click()
    _wait(browser, "return document.getElementById('local-app-dialog').open")
    _wait(browser, "return document.querySelectorAll('[data-catalog-recovery]').length === 2")

    browser.find_element(By.ID, "local-export").click()
    _wait(browser, "return document.getElementById('local-import-json').value.includes('bf_tank') && document.getElementById('local-import-json').value.includes('reach_dps')")

    first_row = browser.find_elements(By.CSS_SELECTOR, "[data-catalog-recovery]")[0]
    first_row.find_element(By.TAG_NAME, "button").click()
    _wait(browser, "return document.querySelectorAll('[data-catalog-recovery]').length === 1")
    assert server.catalog["revision"] == 8
    remaining = browser.find_element(By.CSS_SELECTOR, "[data-catalog-recovery]")
    assert "reach_dps" in remaining.text

    remaining.find_element(By.TAG_NAME, "button").click()
    _wait(browser, "return document.querySelectorAll('[data-catalog-recovery]').length === 0")
    _wait(browser, "return document.getElementById('local-archetype-summary').textContent.includes('catalog revision 9')")
    assert server.catalog["revision"] == 9
    reset_posts = [
        payload
        for path, payload in server.posts
        if path == "/api/v1/archetypes/reset-base"
    ]
    assert reset_posts == [
        {"id": "bf_tank", "expected_revision": 7},
        {"id": "reach_dps", "expected_revision": 8},
    ]
    assert browser.execute_script("return window.__productionBundleErrors.slice()") == []
