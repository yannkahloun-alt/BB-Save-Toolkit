"""Create trusted metadata and assets from an isolated public dataset."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bbtool.app.full_preview import (
    FullPreviewMetadata, package_trusted_full_preview_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--toolkit-version", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--incremental-verified", action="store_true")
    args = parser.parse_args()
    package_trusted_full_preview_dataset(
        args.artifact,
        args.output,
        args.catalog,
        args.fixture,
        FullPreviewMetadata(
            args.source_label,
            args.source_sha,
            args.generated_at,
            args.toolkit_version,
            args.incremental_verified,
        ),
        args.destination,
    )


if __name__ == "__main__":
    main()
