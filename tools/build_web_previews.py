"""Build static report previews for CI publication."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bbtool.app.web_preview import PreviewMetadata, build_web_previews


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    built = build_web_previews(
        args.catalog,
        args.output,
        PreviewMetadata(args.source_label, args.source_sha, args.generated_at),
    )
    (args.output / "preview-context.json").write_text(
        json.dumps({"destination": args.destination}), encoding="utf-8"
    )
    print(f"Built {len(built)} render-only preview scenarios")


if __name__ == "__main__":
    main()
