from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import bbtool.app.cli as cli


def test_cli_root_is_repository_root():
    expected = Path(cli.__file__).resolve().parents[2]
    assert expected == cli.ROOT
    assert (cli.ROOT / "bbtool").is_dir()
    assert (cli.ROOT / "config").is_dir()


def test_cli_options_are_frozen():
    options = cli.CliOptions(
        save=Path("save.sav"),
        targets=Path("targets.json"),
        classification=Path("classification.json"),
        out=Path("output"),
        no_projection=False,
        open_report=False,
    )
    with pytest.raises(FrozenInstanceError):
        options.open_report = True
