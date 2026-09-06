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
    return json.dumps({"data": value, "error": None}, sort_keys=True).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def _send(self, status, body, content_type="application/json; charset=utf-8", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/app.js":
            bootstrap = b"""'use strict';
window.__localErrors = [];
window.addEventListener('error', (event) => window.__localErrors.push(String(event.error || event.message)));
window.addEventListener('unhandledrejection', (event) => window.__localErrors.push(String(event.reason)));
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
        if path == "/api/v1/session":
            self._send(200, _data({"token": self.server.session_token}))
            return
        if path == "/api/v1/shell":
            self._send(
                200,
                _data({
                    "followed_save": {
                        "name": "quicksave.sav",
                        "available": True,
                        "freshness": self.server.result["freshness"],
                    },
                    "result": self.server.result,
                    "analysis_health": None,
                    "active_job": None,
                }),
            )
            return
        if path == "/api/v1/followed-save":
            self._send(200, _data({
                "revision": 1,
                "selected_path": r"C:\Users\Player\Documents\Battle Brothers\savegames\quicksave.sav",
                "auto_refresh": True,
                "available": True,
                "name": "quicksave.sav",
                "freshness": self.server.result["freshness"],
            }))
            return
        if path == "/api/v1/archetypes":
            self._send(200, _data({
                "revision": 0,
                "roles": [],
                "definition_hashes": {},
                "provenance": {},
                "user_entries": [],
            }))
            return
        if path == "/api/v1/company-brother":
            self._send(200, _data({"available": False}))
            return
        if path == "/api/v1/debug-export":
            token = self.headers.get("X-BBST-Session")
            self.server.debug_export_requests.append(token)
            if token != self.server.session_token:
                self._send(
                    403,
                    json.dumps({
                        "data": None,
                        "error": {"code": "invalid_session", "message": "invalid session"},
                    }).encode("utf-8"),
                )
                return
            body = b"PK\x03\x04debug-json-zip"
            self._send(
                200,
                body,
                "application/zip",
                {"Content-Disposition": 'attachment; filename="BB-Save-Toolkit-debug-json-generation-7.zip"'},
            )
            return
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


@pytest.fixture(scope="module")
def debug_surface_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.session_token = "debug-export-browser-token"
    server.result = {"available": False, "freshness": {"status": "unavailable"}}
    server.debug_export_requests = []
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


def test_debug_export_control_tracks_publication_and_downloads_with_session(browser, debug_surface_server):
    server, base_url = debug_surface_server
    server.result = {"available": False, "freshness": {"status": "unavailable"}}
    server.debug_export_requests = []

    browser.get(f"{base_url}/#company")
    wait = WebDriverWait(browser, 5)
    wait.until(lambda current: current.find_element(By.ID, "debug-export-button"))
    button = browser.find_element(By.ID, "debug-export-button")
    assert not button.is_enabled()
    assert server.debug_export_requests == []

    browser.execute_script(
        """
        window.__debugDownloadClicks = [];
        const originalClick = HTMLAnchorElement.prototype.click;
        HTMLAnchorElement.prototype.click = function () {
          if (this.download) {
            window.__debugDownloadClicks.push({download: this.download, href: this.href});
            return;
          }
          return originalClick.call(this);
        };
        """
    )

    server.result = {"available": True, "freshness": {"status": "current"}}
    wait.until(lambda current: current.find_element(By.ID, "debug-export-button").is_enabled())
    browser.find_element(By.ID, "debug-export-button").click()

    wait.until(lambda _current: len(server.debug_export_requests) == 1)
    wait.until(
        lambda current: current.execute_script(
            "return (window.__debugDownloadClicks || []).length === 1"
        )
    )
    download = browser.execute_script("return window.__debugDownloadClicks[0]")

    assert server.debug_export_requests == [server.session_token]
    assert download["download"] == "BB-Save-Toolkit-debug-json-generation-7.zip"
    assert download["href"].startswith("blob:")
    assert browser.find_element(By.ID, "debug-export-button").get_attribute("title") == "Debug JSON downloaded"
    assert browser.execute_script("return (window.__localErrors || []).slice()") == []
