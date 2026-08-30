"""Smoke tests for the shared test harness itself.

These tests deliberately avoid Battle Brothers business assertions.  Their job is
only to prove that pytest can import the package and load the shipped config from
a clean checkout / extracted release.
"""
from pathlib import Path

import pytest

from bbtool.app.config import load_config


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_package_and_config_are_loadable():
    cfg = load_config(ROOT / "config/archetypes.json", ROOT / "config/classification.json")
    assert cfg.roles


def test_slow_selector_includes_coverage_slow_tests():
    script = (ROOT / "run_tests.ps1").read_text(encoding="utf-8")

    assert '"slow or coverage_slow"' in script
