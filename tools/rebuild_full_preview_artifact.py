"""Rebuild unprivileged full-preview data with trusted publication assets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bbtool.app.full_preview import rebuild_trusted_full_preview_artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rebuild_trusted_full_preview_artifact(
        args.artifact, args.output, args.catalog,
    ), sort_keys=True))


if __name__ == "__main__":
    main()
