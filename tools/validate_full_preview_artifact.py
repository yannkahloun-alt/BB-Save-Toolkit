"""Validate an unprivileged full-preview artifact before publication."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bbtool.app.full_preview import validate_full_preview_artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate_full_preview_artifact(args.artifact), sort_keys=True))


if __name__ == "__main__":
    main()
