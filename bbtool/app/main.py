"""Application entry point."""
from __future__ import annotations

from .cli import parse_args


def main(argv=None) -> None:
    options = parse_args(argv)
    if options.render_only is not None:
        from .render_only import run_render_only
        run_render_only(options)
    else:
        from .runner import run
        run(options)
