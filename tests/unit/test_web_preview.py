import json
from pathlib import Path

import pytest

from bbtool.app.web_preview import (
    PreviewCatalogError, PreviewMetadata, build_web_previews,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "tests" / "fixtures" / "report_previews.json"
META = PreviewMetadata("PR #123", "a" * 40, "2026-08-30T12:34:56Z")


def test_build_web_previews_is_interactive_metadata_bound_and_presentation_only(tmp_path):
    built = build_web_previews(CATALOG, tmp_path / "site", META)
    assert [path.name for path in built] == ["standard", "level-up", "recruits"]
    for path in built:
        html = (path / "index.html").read_text(encoding="utf-8")
        assert "Render-only preview" in html
        assert "PR #123" in html
        assert "a" * 40 in html
        assert "bbtool.reference_analysis.v2" in html
        assert "2026-08-30T12:34:56Z" in html
        assert "Aldric" in html
        assert '"FutureRolls"' not in html
        assert (path / "report.css").is_file()
        assert (path / "report.js").is_file()
    levelup = (built[1] / "index.html").read_text(encoding="utf-8")
    assert 'levelup-tab-button has-levelups active" data-tab-button="levelup"' in levelup
    assert 'id="tab-levelup" class="tab-panel active"' in levelup


@pytest.mark.parametrize("field,value,message", [
    ("name", "../escape", "unsafe or duplicate name"),
    ("dataset", "../outside", "unsafe dataset path"),
    ("initial_tab", "unknown", "unsupported initial_tab"),
])
def test_build_web_previews_rejects_unsafe_catalog(tmp_path, field, value, message):
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog["scenarios"][0][field] = value
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(PreviewCatalogError, match=message):
        build_web_previews(path, tmp_path / "site", META)
