"""Application entry point."""
from __future__ import annotations

from .cli import parse_args
from .runner import run


def main(argv=None) -> None:
    run(parse_args(argv))
