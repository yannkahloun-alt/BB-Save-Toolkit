#!/usr/bin/env python3
"""Windowless entry point for the installed Windows application."""
from __future__ import annotations

import multiprocessing
import os
import sys

from bbtool.app.windows_launcher import main


def _ensure_streams() -> None:
    """PyInstaller windowed executables expose no console streams."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


if __name__ == "__main__":
    _ensure_streams()
    multiprocessing.freeze_support()
    raise SystemExit(main())
