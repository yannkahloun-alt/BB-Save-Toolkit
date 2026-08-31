from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import bbtool.app.report_server as report_server
from bbtool.app.report_server import _handler, render_served_report
from http.server import ThreadingHTTPServer
import threading


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "reference_analysis"


def test_report_server_serves_rendered_json_and_local_assets():
    root, html = render_served_report(FIXTURE)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(root, html))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(base + "/report.html") as response:
            assert response.status == 200
            assert "Aldric" in response.read().decode("utf-8")
            assert response.headers["Cache-Control"] == "no-store"
        with urlopen(base + "/report.js") as response:
            assert response.status == 200
            assert "showTab" in response.read().decode("utf-8")
        try:
            urlopen(base + "/missing")
        except HTTPError as exc:
            assert exc.code == 404
            assert exc.read() == b"Not found"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_detached_launcher_uses_absolute_application_entrypoint(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(report_server.subprocess, "Popen", lambda command, **kwargs: calls.append((command, kwargs)))
    assert report_server.launch_report_server(tmp_path)
    command, _kwargs = calls[0]
    assert Path(command[1]).is_absolute()
    assert command[2:4] == ["--serve-report", str(tmp_path.resolve())]
    assert command[4] == "--open-report"


def test_serve_report_closes_server_after_keyboard_interrupt(monkeypatch, capsys):
    calls = []

    class Server:
        server_port = 1234

        def __init__(self, address, handler):
            calls.append((address, handler))

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            calls.append("closed")

    monkeypatch.setattr(report_server, "ThreadingHTTPServer", Server)
    report_server.serve_report(FIXTURE)
    assert calls[-1] == "closed"
    assert "127.0.0.1:1234" in capsys.readouterr().out
