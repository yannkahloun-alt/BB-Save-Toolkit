import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bbtool.app.app_server import LocalApplicationApi

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "http://127.0.0.1:48123"
HOST = "127.0.0.1:48123"


class ShellApplication:
    def __init__(self):
        result = SimpleNamespace(
            diagnostics={
                "run_health": {
                    "result_affecting_warnings": 1,
                    "recoverable_parsing_failures": 1,
                    "unresolved_references_relevant_to_save": 0,
                    "unresolved_backgrounds_relevant_to_save": 0,
                    "unresolved_recruit_equipment_relevant_to_save": 0,
                    "validation_roll_range_violations": 0,
                }
            }
        )
        self.coordinator = SimpleNamespace(
            last_success=SimpleNamespace(result=result),
            desired_job_id=7,
        )

    def followed_save(self):
        return {
            "revision": 2,
            "selected_path": "C:/private/quicksave.sav",
            "name": "quicksave.sav",
            "available": True,
            "freshness": {"status": "analyzing"},
        }

    def last_result(self):
        return {
            "available": True,
            "freshness": {"status": "stale", "reason": "selected_save_content_changed"},
            "warnings": [],
            "data": {"fits": []},
        }

    def analysis_job(self, job_id):
        assert job_id == 7
        return {
            "id": 7,
            "status": "running",
            "progress": [
                {"stage": "roster", "status": "completed", "elapsed_seconds": 0.1, "details": {}}
            ],
            "error": None,
            "published": False,
        }


def decode(response):
    return json.loads(response.body)


def test_shell_assets_are_fixed_local_and_expose_exact_primary_workspaces():
    api = LocalApplicationApi(ShellApplication(), origin=ORIGIN, token="capability")

    page_response = api.handle("GET", "/", {"Host": HOST})
    css_response = api.handle("GET", "/app.css", {"Host": HOST})
    js_response = api.handle("GET", "/app.js", {"Host": HOST})
    page = page_response.body.decode()
    css = css_response.body.decode()
    js = js_response.body.decode()

    assert page_response.content_type == "text/html; charset=utf-8"
    assert css_response.content_type == "text/css; charset=utf-8"
    assert js_response.content_type == "text/javascript; charset=utf-8"
    assert page.count("data-workspace=") == 3
    assert 'data-workspace="company"' in page
    assert 'data-workspace="level-up"' in page
    assert 'data-workspace="recruitment"' in page
    assert "Company | Level Up | Recruitment" not in page
    assert "Primary workspaces" in page
    assert 'href="/app.css"' in page and 'src="/app.js"' in page
    assert "https://" not in page + css + js
    assert "http://" not in page + css + js


def test_shell_navigation_freshness_health_progress_and_accessibility_are_structural():
    page = (ROOT / "bbtool" / "app" / "static" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "bbtool" / "app" / "static" / "app.css").read_text(encoding="utf-8")
    js = (ROOT / "bbtool" / "app" / "static" / "app.js").read_text(encoding="utf-8")

    assert 'class="skip-link"' in page
    assert 'role="status" aria-live="polite"' in page
    assert 'aria-label="Primary workspaces"' in page
    assert 'aria-controls="health-panel"' in page
    assert 'id="analysis-progress"' in page
    assert "aria-current" in js
    assert "history.replaceState" in js
    assert "hashchange" in js
    assert "fetchData('/api/v1/shell')" in js
    assert "current: 'Current'" in js
    assert "stale: 'Stale'" in js
    assert "analyzing: 'Analyzing'" in js
    assert "position: sticky" in css
    assert "position: fixed" not in css
    assert "overflow-x: clip" in css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in css
    assert "@media (max-width: 980px)" in css
    assert "@media (max-width: 420px)" in css
    assert ":focus-visible" in css


def test_shell_endpoint_composes_public_health_and_current_progress_without_debug_samples():
    api = LocalApplicationApi(ShellApplication(), origin=ORIGIN, token="capability")

    response = api.handle("GET", "/api/v1/shell", {"Host": HOST})
    data = decode(response)["data"]

    assert response.status == 200
    assert set(data) == {"followed_save", "result", "analysis_health", "active_job"}
    assert data["followed_save"]["name"] == "quicksave.sav"
    assert data["result"]["freshness"] == {
        "status": "stale",
        "reason": "selected_save_content_changed",
    }
    assert data["analysis_health"]["schema"] == "bbtool.analysis_health.v1"
    assert data["analysis_health"]["status"] == "degraded"
    assert data["analysis_health"]["counts"]["result_affecting_warnings"] == 1
    assert data["analysis_health"]["warning_categories"] == [
        {"code": "recoverable_parsing_failures", "count": 1}
    ]
    assert "recoverable_parsing_failure_sample" not in data["analysis_health"]
    assert data["active_job"]["id"] == 7
    assert data["active_job"]["status"] == "running"
    assert data["active_job"]["progress"][0]["stage"] == "roster"


def test_unknown_static_path_does_not_become_filesystem_access():
    api = LocalApplicationApi(ShellApplication(), origin=ORIGIN, token="capability")

    response = api.handle("GET", "/../../config/archetypes.json", {"Host": HOST})

    assert response.status == 404
    assert decode(response)["error"]["code"] == "not_found"
