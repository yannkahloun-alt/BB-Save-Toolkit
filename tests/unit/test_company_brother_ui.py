import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from bbtool.app.app_server import LocalApplicationApi

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "http://127.0.0.1:48123"
HOST = "127.0.0.1:48123"


class EmptyApplication:
    def __init__(self):
        self.coordinator = SimpleNamespace(last_success=None)
        self._command_lock = threading.RLock()


def decode(response):
    return json.loads(response.body)


def test_company_brother_endpoint_is_read_only_and_handles_no_publication():
    api = LocalApplicationApi(EmptyApplication(), origin=ORIGIN, token="capability")

    response = api.handle("GET", "/api/v1/company-brother", {"Host": HOST})

    assert response.status == 200
    assert decode(response)["data"] == {"available": False}


def test_company_and_brother_structure_preserves_validated_information_architecture():
    page = (ROOT / "bbtool" / "app" / "static" / "index.html").read_text(encoding="utf-8")

    assert page.count("data-workspace=") == 3
    for workspace in ("company", "level-up", "recruitment"):
        assert f'data-workspace="{workspace}"' in page
    for subview in ("roster", "planning", "matrix"):
        assert f'data-company-view="{subview}"' in page
    for section in ("current", "gear", "mechanics", "potential", "development"):
        assert f'data-brother-section="{section}"' in page
    assert "Assigned Build · Intent" in page
    assert "Best Fit · Intrinsic analysis" in page
    assert "Alternatives" not in page
    assert 'id="brother-view"' in page
    assert 'data-workspace="brother"' not in page


def test_company_navigation_and_mutation_behavior_are_explicit_not_browser_inferred():
    js = (ROOT / "bbtool" / "app" / "static" / "app.js").read_text(encoding="utf-8")

    assert "function brotherHash" in js
    assert "state.companyReturn" in js
    assert "scrollY: window.scrollY" in js
    assert "state.companySubview = saved.subview" in js
    assert "state.companySearch = saved.search" in js
    assert "route.section" in js
    assert "fetchData('/api/v1/company-brother')" in js
    assert "'/api/v1/session'" in js
    assert "'/api/v1/analysis/jobs'" in js
    assert "`/api/v1/assigned-builds/${operation}`" in js
    assert "expected_revision: state.companyData.assignment_revision" in js
    assert "state.companyData.company.intent_fresh = false" in js
    assert "saved; refresh could not start" in js
    assert "Assigned Build was not changed" in js
    assert "innerHTML" not in js
    assert "report.js" not in js


def test_shell_polling_does_not_rebuild_brother_content_or_reset_open_detail_state():
    js = (ROOT / "bbtool" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    render_shell = js.split("function renderShell()", 1)[1].split(
        "function matchesSearch", 1
    )[0]

    assert "renderBrother" not in render_shell
    assert "updateBrotherMutationAvailability" in render_shell
    assert "loadedJobId" in js
    assert "publishedJobChanged" in js


def test_company_brother_read_model_keeps_intent_and_intrinsic_analysis_separate():
    source = (ROOT / "bbtool" / "app" / "company_brother_view.py").read_text(encoding="utf-8")

    assert 'with application._command_lock:' in source
    assert 'route_key = identity_value if isinstance(identity_value, str) else observation_id' in source
    assert '"brother_id": route_key' in source
    assert '"assigned_build": assignment' in source
    assert '"best_fit": _best_fit(summary)' in source
    assert 'application.assigned_builds.read_campaign(campaign)' in source
    assert '"intent_fresh": analyzed_assignments == live_assignments' in source
    assert '"assignment_address": address' in source
    assert '"potential": potential' in source
    assert "FutureRolls" not in source


def test_company_and_brother_responsive_contract_has_anchored_dock_and_local_overflow():
    css = (ROOT / "bbtool" / "app" / "static" / "app.css").read_text(encoding="utf-8")

    assert ".brother-dock {" in css
    assert "top: var(--app-shell-height);" in css
    assert "position: sticky;" in css
    assert "scroll-margin-top: calc(var(--app-shell-height) + 4.3rem);" in css
    assert "scroll-margin-top: calc(var(--app-shell-height) + 6.5rem);" in css
    assert ".matrix-wrap" in css and "overflow: auto;" in css
    assert "overflow-x: clip;" in css
    assert "@media (max-width: 980px)" in css
    assert "@media (max-width: 720px)" in css
    assert "@media (max-width: 420px)" in css
    assert ".roster-identity {\n    grid-column: 1 / -1;" in css
    assert ".brother-row .roster-role:nth-of-type(3)" not in css
    assert ":focus-visible" in css
