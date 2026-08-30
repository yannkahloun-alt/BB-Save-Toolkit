
"""Command-line interface. No analysis logic lives here."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CliOptions:
    save: Path | None
    targets: Path
    classification: Path
    out: Path
    no_projection: bool
    open_report: bool
    full_recompute: bool = False
    verify_cache: bool = False
    cache_debug: bool = False
    render_only: Path | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only Battle Brothers save analyzer"
    )
    parser.add_argument("save", nargs="?", type=Path, help="Path to .sav")
    parser.add_argument(
        "--render-only",
        type=Path,
        metavar="DATASET",
        help="Generate a report from a public JSON dataset directory or manifest",
    )
    parser.add_argument(
        "--targets",
        type=Path,
        default=ROOT / "config" / "archetypes.json",
    )
    parser.add_argument(
        "--classification",
        type=Path,
        default=ROOT / "config" / "classification.json",
    )
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--no-projection", action="store_true")
    parser.add_argument(
        "--open-report",
        action="store_true",
        help="Open the generated HTML report in the default browser",
    )
    parser.add_argument("--full-recompute", action="store_true", help="Disable incremental role-projection reuse for this run")
    parser.add_argument("--verify-cache", action="store_true", help="Compare incremental output with an independent full recomputation")
    parser.add_argument("--cache-debug", action="store_true", help="Print incremental cache invalidation/reuse diagnostics")
    return parser


def parse_args(argv=None) -> CliOptions:
    parser = build_parser()
    ns = parser.parse_args(argv)
    if (ns.save is None) == (ns.render_only is None):
        parser.error("provide exactly one of SAVE or --render-only DATASET")
    if ns.save is not None and not ns.save.is_file():
        parser.error(f"Save not found: {ns.save}")
    if ns.render_only is not None:
        if not ns.render_only.exists():
            parser.error(f"Render dataset not found: {ns.render_only}")
        incompatible = [
            name for name, enabled in (
                ("--targets", ns.targets != ROOT / "config" / "archetypes.json"),
                ("--classification", ns.classification != ROOT / "config" / "classification.json"),
                ("--no-projection", ns.no_projection),
                ("--full-recompute", ns.full_recompute),
                ("--verify-cache", ns.verify_cache),
                ("--cache-debug", ns.cache_debug),
            ) if enabled
        ]
        if incompatible:
            parser.error(
                f"{', '.join(incompatible)} cannot be used with --render-only"
            )
    return CliOptions(
        save=ns.save,
        targets=ns.targets,
        classification=ns.classification,
        out=ns.out,
        no_projection=ns.no_projection,
        open_report=ns.open_report,
        full_recompute=ns.full_recompute,
        verify_cache=ns.verify_cache,
        cache_debug=ns.cache_debug,
        render_only=ns.render_only,
    )
