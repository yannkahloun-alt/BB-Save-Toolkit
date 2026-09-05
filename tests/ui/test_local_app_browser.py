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


def _base_role():
    return {
        "id": "bf_tank",
        "name": "BF Tank",
        "stats": {"MDef": {"target": 35}},
    }


def _catalog(revision=0):
    role = _base_role()
    return {
        "revision": revision,
        "roles": [role],
        "definition_hashes": {"bf_tank": "sha256:base"},
        "provenance": {"bf_tank": "base"},
        "user_entries": [],
    }


def _data(value):
    return json.dumps({"data": value}, sort_keys=True).encode("utf-8")


def _error(status, code, message, details=None):
    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return status, json.dumps(payload, sort_keys=True).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _followed(self):
        selected = self.server.preferences["selected_path"]
        value = {
            "revision": self.server.preferences["revision"],
            "selected_path": selected,
            "auto_refresh": self.server.preferences["auto_refresh"],
            "available": bool(selected) and self.server.save_available,
            "freshness": {"status": self.server.followed_status},
        }
        if selected:
            value["name"] = selected.replace("\\", "/").rsplit("/", 1)[-1]
        return value

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/api/v1/session":
            self._send(200, _data({"token": self.server.session_token}))
            return
        if path == "/api/v1/followed-save":
            self._send(200, _data(self._followed()))
            return
        if path == "/api/v1/shell":
            followed = self._followed()
            shell = {
                "followed_save": {
                    "name": followed.get("name"),
                    "available": followed["available"],
                    "freshness": followed["freshness"],
                },
                "result": self.server.result,
                "analysis_health": None,
                "active_job": None,
            }
            self._send(200, _data(shell))
            return
        if path == "/api/v1/company-brother":
            self._send(200, _data({"available": False}))
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
        if path == "/app.js":
            bootstrap = b"""'use strict';
window.__localErrors = [];
window.addEventListener('error', (event) => window.__localErrors.push(String(event.error || event.message)));
window.addEventListener('unhandledrejection', (event) => window.__localErrors.push(String(event.reason)));
"""
            self._send(
                200,
                bootstrap + (STATIC / "app.js").read_bytes(),
                "text/javascript; charset=utf-8",
            )
            return
        if path in ("/level-up.js", "/recruitment.js"):
            self._send(200, b"'use strict';\n", "text/javascript; charset=utf-8")
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

        if path == "/api/v1/followed-save/select":
            if payload["expected_revision"] != self.server.preferences["revision"]:
                status, body = _error(409, "state_revision_conflict", "preferences revision conflict")
                self._send(status, body)
                return
            self.server.preferences = {
                "revision": self.server.preferences["revision"] + 1,
                "selected_path": payload["path"],
                "auto_refresh": payload.get("auto_refresh", False),
            }
            self.server.save_available = True
            self.server.followed_status = "detected"
            self.server.result = {"available": False, "freshness": {"status": "detected"}}
            self._send(200, _data(self._followed()))
            return

        if path == "/api/v1/followed-save/forget":
            if payload["expected_revision"] != self.server.preferences["revision"]:
                status, body = _error(409, "state_revision_conflict", "preferences revision conflict")
                self._send(status, body)
                return
            self.server.preferences = {
                "revision": self.server.preferences["revision"] + 1,
                "selected_path": None,
                "auto_refresh": self.server.preferences["auto_refresh"],
            }
            self.server.save_available = False
            self.server.followed_status = "unavailable"
            self.server.result = {"available": False, "freshness": {"status": "unavailable"}}
            self._send(200, _data(self._followed()))
            return

        if path == "/api/v1/analysis/jobs":
            if payload["expected_preferences_revision"] != self.server.preferences["revision"]:
                status, body = _error(409, "state_revision_conflict", "preferences revision conflict")
                self._send(status, body)
                return
            self.server.analysis_requests += 1
            self.server.followed_status = "current"
            self.server.result = {"available": True, "freshness": {"status": "current"}}
            self._send(202, _data({"id": self.server.analysis_requests, "status": "queued"}))
            return

        prefix = "/api/v1/archetypes/"
        if path.startswith(prefix):
            operation = path[len(prefix):]
            if payload["expected_revision"] != self.server.catalog["revision"]:
                status, body = _error(409, "state_revision_conflict", "catalog revision conflict")
                self._send(status, body)
                return
            catalog = json.loads(json.dumps(self.server.catalog))
            catalog["revision"] += 1
            if operation == "duplicate":
                source = next(role for role in catalog["roles"] if role["id"] == payload["id"])
                custom = json.loads(json.dumps(source))
                custom["id"] = f"custom_{catalog['revision']}"
                custom["name"] = f"{source['name']} Copy"
                catalog["roles"].append(custom)
                catalog["provenance"][custom["id"]] = "user_custom"
                catalog["definition_hashes"][custom["id"]] = "sha256:custom"
                catalog["user_entries"].append({"kind": "custom", "definition": custom})
            elif operation == "set-disabled":
                identity = payload["id"]
                catalog["user_entries"] = [
                    entry
                    for entry in catalog["user_entries"]
                    if not (entry.get("kind") == "disabled" and entry.get("id") == identity)
                ]
                if payload["disabled"]:
                    catalog["user_entries"].append({"kind": "disabled", "id": identity})
                    catalog["roles"] = [role for role in catalog["roles"] if role["id"] != identity]
                    catalog["provenance"].pop(identity, None)
                    catalog["definition_hashes"].pop(identity, None)
                elif not any(role["id"] == identity for role in catalog["roles"]):
                    base = _base_role()
                    catalog["roles"].insert(0, base)
                    catalog["provenance"][identity] = "base"
                    catalog["definition_hashes"][identity] = "sha256:base"
            elif operation == "import":
                imported = json.loads(payload["document"])
                if not payload.get("merge"):
                    catalog["user_entries"] = imported["entries"]
            else:
                status, body = _error(422, "validation_failed", f"unsupported mock operation {operation}")
                self._send(status, body)
                return
            self.server.catalog = catalog
            self.server.result = {
                "available": True,
                "freshness": {"status": "stale", "reason": "effective_archetypes_changed"},
            }
            data = catalog | {
                "freshness": {
                    "status": "stale",
                    "reason": "effective_archetypes_changed",
                    "recompute": "request_analysis",
                }
            }
            self._send(200, _data(data))
            return

        status, body = _error(404, "not_found", "endpoint not found")
        self._send(status, body)


@pytest.fixture(scope="module")
def surface_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.session_token = "local-app-test-token"
    server.preferences = {"revision": 0, "selected_path": None, "auto_refresh": False}
    server.save_available = False
    server.followed_status = "unavailable"
    server.result = {"available": False, "freshness": {"status": "unavailable"}}
    server.catalog = _catalog()
    server.posts = []
    server.analysis_requests = 0
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


def _open_dialog(driver):
    _wait(driver, "return document.getElementById('local-app-trigger') !== null")
    driver.find_element(By.ID, "local-app-trigger").click()
    _wait(driver, "return document.getElementById('local-app-dialog').open")
    _wait(driver, "return document.getElementById('local-save-summary').textContent.includes('revision')")


def _click_role_action(driver, role_text, action_text):
    return driver.execute_script(
        """
        const row = [...document.querySelectorAll('#local-archetype-list .coverage-card')]
          .find((item) => item.textContent.includes(arguments[0]));
        const button = row && [...row.querySelectorAll('button')]
          .find((item) => item.textContent === arguments[1]);
        if (!button) return false;
        button.click();
        return true;
        """,
        role_text,
        action_text,
    )


def _assert_no_js_errors(driver):
    errors = driver.execute_script("return (window.__localErrors || []).slice()")
    assert errors == []


def test_first_run_selection_reload_and_failed_refresh_are_authoritative(browser, surface_server):
    server, base_url = surface_server
    server.preferences = {"revision": 0, "selected_path": None, "auto_refresh": False}
    server.save_available = False
    server.followed_status = "unavailable"
    server.result = {"available": False, "freshness": {"status": "unavailable"}}
    server.catalog = _catalog()
    server.posts = []
    server.analysis_requests = 0

    browser.get(f"{base_url}/#company")
    _wait(browser, "return document.getElementById('local-app-flow')?.dataset.state === 'first-run'")
    assert [item.text for item in browser.find_elements(By.CSS_SELECTOR, ".primary-nav [data-workspace]")] == [
        "Company",
        "Level Up",
        "Recruitment",
    ]

    _open_dialog(browser)
    save_path = r"C:\Users\Player\Documents\Battle Brothers\savegames\company.sav"
    path_input = browser.find_element(By.ID, "local-save-path")
    path_input.clear()
    path_input.send_keys(save_path)
    browser.find_element(By.ID, "local-save-select").click()
    WebDriverWait(browser, 5).until(lambda _current: server.analysis_requests == 1)
    _wait(browser, "return document.getElementById('local-app-status').textContent.includes('analysis')")

    select_posts = [payload for path, payload in server.posts if path == "/api/v1/followed-save/select"]
    assert len(select_posts) == 1
    assert select_posts[0]["expected_revision"] == 0
    analysis_posts = [payload for path, payload in server.posts if path == "/api/v1/analysis/jobs"]
    assert len(analysis_posts) == 1
    assert analysis_posts[0]["expected_preferences_revision"] == 1

    browser.refresh()
    _open_dialog(browser)
    _wait(browser, f"return document.getElementById('local-save-path').value === {json.dumps(save_path)}")
    assert "revision 1" in browser.find_element(By.ID, "local-save-summary").text
    browser.execute_script("document.getElementById('local-app-dialog').close()")

    server.followed_status = "failed"
    server.result = {
        "available": True,
        "freshness": {"status": "failed", "reason": "analysis_failed"},
    }
    _wait(browser, "return !document.getElementById('local-app-flow').hidden && document.getElementById('local-app-flow').dataset.state === 'failed'")
    assert "previous analysis is still visible" in browser.find_element(By.ID, "local-app-flow-title").text.lower()
    assert "explicitly stale" in browser.find_element(By.ID, "local-app-flow-detail").text.lower()

    browser.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {"width": 390, "height": 900, "deviceScaleFactor": 1, "mobile": False},
    )
    _wait(browser, "return window.innerWidth === 390")
    scroll_width, client_width = browser.execute_script(
        "return [document.documentElement.scrollWidth, document.documentElement.clientWidth]"
    )
    assert scroll_width <= client_width + 1
    _assert_no_js_errors(browser)


def test_archetype_mutations_use_revisions_and_conflicts_reload_authority(browser, surface_server):
    server, base_url = surface_server
    server.preferences = {
        "revision": 1,
        "selected_path": r"C:\Users\Player\Documents\Battle Brothers\savegames\company.sav",
        "auto_refresh": False,
    }
    server.save_available = True
    server.catalog = _catalog()
    server.posts = []
    server.followed_status = "current"
    server.result = {"available": True, "freshness": {"status": "current"}}

    browser.get(f"{base_url}/#company")
    _open_dialog(browser)
    _wait(browser, "return document.querySelectorAll('#local-archetype-list .coverage-card').length === 1")

    assert _click_role_action(browser, "BF Tank", "Duplicate")
    _wait(browser, "return document.querySelectorAll('#local-archetype-list .coverage-card').length === 2")
    assert server.catalog["revision"] == 1

    server.catalog["revision"] = 2
    assert _click_role_action(browser, "BF Tank", "Disable")
    _wait(browser, "return document.getElementById('local-app-status').textContent.includes('changed elsewhere')")
    assert server.catalog["revision"] == 2

    assert _click_role_action(browser, "BF Tank", "Disable")
    _wait(browser, "return [...document.querySelectorAll('#local-archetype-list .coverage-card')].some((row) => row.textContent.includes('Disabled shipped build'))")
    assert server.catalog["revision"] == 3

    mutation_posts = [
        (path, payload)
        for path, payload in server.posts
        if path.startswith("/api/v1/archetypes/")
    ]
    assert [path for path, _payload in mutation_posts[:3]] == [
        "/api/v1/archetypes/duplicate",
        "/api/v1/archetypes/set-disabled",
        "/api/v1/archetypes/set-disabled",
    ]
    assert [payload["expected_revision"] for _path, payload in mutation_posts[:3]] == [0, 1, 2]

    browser.find_element(By.ID, "local-export").click()
    _wait(browser, "return document.getElementById('local-import-json').value.includes('bbtool.user-archetypes-export.v1')")

    browser.refresh()
    _open_dialog(browser)
    _wait(browser, "return document.querySelectorAll('#local-archetype-list .coverage-card').length === 2")
    rows = browser.find_elements(By.CSS_SELECTOR, "#local-archetype-list .coverage-card")
    assert any("BF Tank Copy" in row.text for row in rows)
    assert any("Disabled shipped build" in row.text for row in rows)
    _assert_no_js_errors(browser)
