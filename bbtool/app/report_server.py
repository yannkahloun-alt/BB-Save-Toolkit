"""Loopback-only HTTP delivery for reports backed by adjacent public JSON."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.parse
import webbrowser

from ..html_report import render_html_report
from .render_only import RenderDatasetError, load_render_dataset

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
APP_ENTRYPOINT = PACKAGE_ROOT.parent / "bb_analyze.py"


def render_served_report(source: Path) -> tuple[Path, str]:
    """Validate ``source`` and render solely from its public JSON contract."""
    dataset = load_render_dataset(source)
    source_name = dataset.manifest.get("source") or dataset.root.name or "report"
    generated_at = str(dataset.manifest.get("generated_at") or "")
    html = render_html_report(
        Path(source_name), dataset.bros, dataset.fits, dataset.summaries,
        dataset.roles, dataset.classification, generated_at=generated_at,
        recruits=dataset.recruits, analysis_health=dataset.analysis_health,
    )
    return dataset.root, html


def _handler(root: Path, html: str):
    class ReportHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if path in ("/", "/report.html"):
                self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))
                return
            assets = {
                "/report.css": ("text/css; charset=utf-8", "report.css"),
                "/report.js": ("text/javascript; charset=utf-8", "report.js"),
            }
            asset = assets.get(path)
            asset_path = None if asset is None else root / asset[1]
            if asset_path is not None and not asset_path.is_file():
                asset_path = PACKAGE_ROOT / asset[1]
            if asset is None or asset_path is None or not asset_path.is_file():
                self._send(404, "text/plain; charset=utf-8", b"Not found")
                return
            self._send(200, asset[0], asset_path.read_bytes())

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    return ReportHandler


def serve_report(source: Path, *, open_browser: bool = False) -> None:
    """Serve a validated report on loopback until interrupted by the user."""
    try:
        root, html = render_served_report(source)
    except RenderDatasetError as exc:
        raise SystemExit(str(exc)) from exc
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(root, html))
    url = f"http://127.0.0.1:{server.server_port}/report.html"
    print(f"Report server: {url}")
    print("Press Ctrl+C to stop the local report server.")
    if open_browser:
        threading.Timer(0.1, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def launch_report_server(source: Path) -> bool:
    """Start a detached loopback server that opens the report in a browser."""
    command = [
        sys.executable, str(APP_ENTRYPOINT), "--serve-report",
        str(source.resolve()), "--open-report",
    ]
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
              "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)
    return True


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Serve a BB Toolkit report locally")
    parser.add_argument("source", type=Path)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args(argv)
    serve_report(args.source, open_browser=args.open_browser)


if __name__ == "__main__":
    main()
