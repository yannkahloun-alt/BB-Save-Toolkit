"""Application entry point."""
from __future__ import annotations

from .cli import parse_args


def main(argv=None) -> None:
    options = parse_args(argv)
    if options.serve_app:
        from .app_server import serve_local_application
        serve_local_application(port=options.app_port, open_browser=options.open_report)
    elif options.serve_report is not None:
        from .report_server import serve_report
        serve_report(options.serve_report, open_browser=options.open_report)
    elif options.render_only is not None:
        from .render_only import run_render_only
        run_render_only(options)
    else:
        from .runner import run
        run(options)
