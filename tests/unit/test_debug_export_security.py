import json
import threading
from types import SimpleNamespace

import pytest

from bbtool.app.app_server import LocalApplicationApi


pytestmark = pytest.mark.unit
ORIGIN = "http://127.0.0.1:48123"
HOST = "127.0.0.1:48123"


def test_debug_export_preserves_existing_host_rebinding_guard(monkeypatch):
    app = SimpleNamespace(
        coordinator=SimpleNamespace(last_success=SimpleNamespace(generation=3)),
        _command_lock=threading.RLock(),
    )
    api = LocalApplicationApi(app, origin=ORIGIN, token="capability")
    called = []
    monkeypatch.setattr(
        "bbtool.app.app_server.build_debug_export",
        lambda *_args, **_kwargs: called.append(True) or (b"zip", "debug.zip"),
    )

    hostile = api.handle(
        "GET",
        "/api/v1/debug-export",
        {"Host": "hostile.example"},
    )

    assert hostile.status == 403
    assert json.loads(hostile.body)["error"]["code"] == "invalid_host"
    assert called == []

    allowed = api.handle("GET", "/api/v1/debug-export", {"Host": HOST})
    assert allowed.status == 200
    assert allowed.content_type == "application/zip"
    assert called == [True]
