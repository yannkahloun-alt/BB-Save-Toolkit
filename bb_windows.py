#!/usr/bin/env python3
"""Windowless entry point for the installed Windows application."""
from __future__ import annotations

import multiprocessing
import os
import sys

from bbtool.app.first_run import initialize_first_run_save_default
from bbtool.app.windows_launcher import main


def _ensure_streams() -> None:
    """PyInstaller windowed executables expose no console streams."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _initialize_for_launch(argv: list[str]) -> None:
    """Apply first-run defaults only for commands that start the application."""
    command = argv[0] if argv else "open"
    if command in {"open", "background", "restart"}:
        initialize_first_run_save_default()


if __name__ == "__main__":
    _ensure_streams()
    multiprocessing.freeze_support()
    _initialize_for_launch(sys.argv[1:])
    raise SystemExit(main())
