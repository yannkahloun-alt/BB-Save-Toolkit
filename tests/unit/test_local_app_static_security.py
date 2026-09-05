from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_local_application_additive_script_avoids_inner_html():
    js = (ROOT / "bbtool" / "app" / "static" / "catalog_recovery.js").read_text(
        encoding="utf-8"
    )

    assert "innerHTML" not in js
