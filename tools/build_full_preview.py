"""Package a completed approved-save run as a safe static web preview."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bbtool.app.full_preview import (
    PREVIEW_CONTEXT_SCHEMA, load_approved_save, stage_full_preview_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--toolkit-version", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--incremental-verified", action="store_true")
    args = parser.parse_args()

    fixture = load_approved_save(args.catalog, args.fixture)
    built = stage_full_preview_dataset(args.run, args.output, fixture)
    context = {
        "schema": PREVIEW_CONTEXT_SCHEMA,
        "destination": args.destination,
        "fixture": fixture.identifier,
        "save_sha256": fixture.sha256,
        "source_sha": args.source_sha,
        "source_label": args.source_label,
        "generated_at": args.generated_at,
        "toolkit_version": args.toolkit_version,
        "incremental_verified": args.incremental_verified,
    }
    (args.output / "preview-context.json").write_text(
        json.dumps(context, indent=2), encoding="utf-8"
    )
    print(f"Built full application preview: {built}")


if __name__ == "__main__":
    main()
