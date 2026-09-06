from __future__ import annotations

from contextlib import contextmanager
import ctypes
import json
from pathlib import Path

import pytest

from bbtool.app import first_run
from bbtool.app import windows_launcher as launcher


class FakeCall:
    def __init__(self, callback):
        self.callback = callback
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.callback(*args)


class FakeResponse:
    def __init__(self, *, status=200, payload=b"{}"):
        self.status = status
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def runtime_record(port: int | None = None, pid: int = 777):
    return {
        "schema": launcher.RUNTIME_SCHEMA,
        "pid": pid,
        "port": port or launcher.PORT_RANGE[0],
        "executable": "launcher.exe",
    }


def test_log_event_flattens_bounds_and_tolerates_io_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "_runtime_directory", lambda: tmp_path)
    monkeypatch.setattr(launcher.time, "time", lambda: 123.9)
    launcher._log_event("event", "one\ntwo " + "x" * 1200)
    logged = (tmp_path / "launcher.log").read_text(encoding="utf-8")
    assert logged.startswith("123 event one two ")
    assert "\n" not in logged[:-1]
    assert len(logged.split("event ", 1)[1].rstrip("\n")) == 1000

    monkeypatch.setattr(
        launcher,
        "_runtime_directory",
        lambda: (_ for _ in ()).throw(OSError("blocked")),
    )
    launcher._log_event("ignored", "safe")


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"schema": "wrong", "pid": 1, "port": launcher.PORT_RANGE[0], "executable": "x"},
        {"schema": launcher.RUNTIME_SCHEMA, "pid": True, "port": launcher.PORT_RANGE[0], "executable": "x"},
        {"schema": launcher.RUNTIME_SCHEMA, "pid": "1", "port": launcher.PORT_RANGE[0], "executable": "x"},
        {"schema": launcher.RUNTIME_SCHEMA, "pid": 0, "port": launcher.PORT_RANGE[0], "executable": "x"},
        {"schema": launcher.RUNTIME_SCHEMA, "pid": 1, "port": True, "executable": "x"},
        {"schema": launcher.RUNTIME_SCHEMA, "pid": 1, "port": "41571", "executable": "x"},
        {"schema": launcher.RUNTIME_SCHEMA, "pid": 1, "port": 1, "executable": "x"},
        {"schema": launcher.RUNTIME_SCHEMA, "pid": 1, "port": launcher.PORT_RANGE[0], "executable": 3},
        {"schema": launcher.RUNTIME_SCHEMA, "pid": 1, "port": launcher.PORT_RANGE[0], "executable": ""},
    ],
)
def test_load_runtime_rejects_malformed_records(tmp_path, monkeypatch, payload):
    target = tmp_path / "runtime.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(launcher, "_runtime_file", lambda: target)
    assert launcher._load_runtime() is None


def test_load_runtime_rejects_missing_and_invalid_json(tmp_path, monkeypatch):
    target = tmp_path / "runtime.json"
    monkeypatch.setattr(launcher, "_runtime_file", lambda: target)
    assert launcher._load_runtime() is None
    target.write_text("{", encoding="utf-8")
    assert launcher._load_runtime() is None


def test_remove_runtime_honors_expected_pid_and_tolerates_unlink_errors(tmp_path, monkeypatch):
    target = tmp_path / "runtime.json"
    target.write_text("x", encoding="utf-8")
    monkeypatch.setattr(launcher, "_runtime_file", lambda: target)
    monkeypatch.setattr(launcher, "_load_runtime", lambda: runtime_record(pid=7))
    launcher._remove_runtime(expected_pid=8)
    assert target.exists()
    launcher._remove_runtime(expected_pid=7)
    assert not target.exists()
    launcher._remove_runtime(expected_pid=7)

    class BadPath:
        def unlink(self):
            raise OSError("blocked")

    monkeypatch.setattr(launcher, "_runtime_file", lambda: BadPath())
    launcher._remove_runtime()


def test_probe_port_requires_exact_health_contract(monkeypatch):
    port = launcher.PORT_RANGE[0]
    valid = {
        "data": {
            "status": "ok",
            "api_schema": launcher.API_SCHEMA,
            "bind": launcher.LOOPBACK_HOST,
        }
    }
    monkeypatch.setattr(
        launcher.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(payload=json.dumps(valid).encode()),
    )
    assert launcher._probe_port(port)

    monkeypatch.setattr(
        launcher.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(status=503),
    )
    assert not launcher._probe_port(port)

    for payload in (b"not-json", json.dumps({"data": {"status": "wrong"}}).encode(), b"[]"):
        monkeypatch.setattr(
            launcher.urllib.request,
            "urlopen",
            lambda *_args, _payload=payload, **_kwargs: FakeResponse(payload=_payload),
        )
        assert not launcher._probe_port(port)

    monkeypatch.setattr(
        launcher.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    assert not launcher._probe_port(port)


def test_running_origin_prefers_valid_runtime_record(monkeypatch):
    port = launcher.PORT_RANGE[0]
    monkeypatch.setattr(launcher, "_load_runtime", lambda: runtime_record(port))
    probes = []
    monkeypatch.setattr(launcher, "_probe_port", lambda value, **_kwargs: probes.append(value) or True)
    assert launcher._running_origin() == f"http://{launcher.LOOPBACK_HOST}:{port}"
    assert probes == [port]


def test_wait_for_origin_success_and_timeout(monkeypatch):
    values = iter([None, "http://127.0.0.1:41571"])
    monkeypatch.setattr(launcher, "_running_origin", lambda: next(values))
    monkeypatch.setattr(launcher.time, "sleep", lambda _seconds: None)
    assert launcher._wait_for_origin(timeout=1) == "http://127.0.0.1:41571"

    times = iter([0.0, 0.1, 2.0])
    monkeypatch.setattr(launcher.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(launcher, "_running_origin", lambda: None)
    assert launcher._wait_for_origin(timeout=1) is None


def test_port_available_closes_socket_on_success_and_failure(monkeypatch):
    events = []

    class Probe:
        def __init__(self, fail):
            self.fail = fail

        def bind(self, address):
            events.append(("bind", address))
            if self.fail:
                raise OSError("used")

        def close(self):
            events.append(("close", self.fail))

    probes = iter([Probe(False), Probe(True)])
    monkeypatch.setattr(launcher.socket, "socket", lambda *_args: next(probes))
    assert launcher._port_available(41571) is True
    assert launcher._port_available(41572) is False
    assert events[-1] == ("close", True)


def test_kernel32_platform_boundary(monkeypatch):
    monkeypatch.setattr(launcher.sys, "platform", "linux")
    assert launcher._kernel32() is None
    sentinel = object()
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher.ctypes, "WinDLL", lambda *args, **kwargs: sentinel, raising=False)
    assert launcher._kernel32() is sentinel


def test_single_instance_mutex_non_windows_create_failure_duplicate_and_release(monkeypatch):
    monkeypatch.setattr(launcher, "_kernel32", lambda: None)
    with launcher._single_instance_mutex() as acquired:
        assert acquired is True

    events = []

    class Kernel:
        pass

    kernel = Kernel()
    kernel.CreateMutexW = FakeCall(lambda *_args: 0)
    kernel.ReleaseMutex = FakeCall(lambda handle: events.append(("release", handle)) or 1)
    kernel.CloseHandle = FakeCall(lambda handle: events.append(("close", handle)) or 1)
    monkeypatch.setattr(launcher, "_kernel32", lambda: kernel)
    monkeypatch.setattr(launcher.ctypes, "get_last_error", lambda: 5)
    with pytest.raises(OSError, match="unable to create application mutex"):
        with launcher._single_instance_mutex():
            pass

    kernel.CreateMutexW = FakeCall(lambda *_args: 11)
    monkeypatch.setattr(launcher.ctypes, "get_last_error", lambda: 183)
    with launcher._single_instance_mutex() as acquired:
        assert acquired is False
    assert events == [("close", 11)]

    events.clear()
    monkeypatch.setattr(launcher.ctypes, "get_last_error", lambda: 0)
    with launcher._single_instance_mutex() as acquired:
        assert acquired is True
    assert events == [("release", 11), ("close", 11)]


def test_process_image_handles_platform_open_query_and_success(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "_kernel32", lambda: None)
    assert launcher._process_image(1) is None

    events = []

    class Kernel:
        pass

    kernel = Kernel()
    kernel.OpenProcess = FakeCall(lambda *_args: 0)
    kernel.QueryFullProcessImageNameW = FakeCall(lambda *_args: 0)
    kernel.CloseHandle = FakeCall(lambda handle: events.append(handle) or 1)
    monkeypatch.setattr(launcher, "_kernel32", lambda: kernel)
    assert launcher._process_image(2) is None

    kernel.OpenProcess = FakeCall(lambda *_args: 22)
    assert launcher._process_image(3) is None
    assert events == [22]

    expected = tmp_path / "BB-Save-Toolkit.exe"

    def query(_handle, _flags, buffer, _size):
        buffer.value = str(expected)
        return 1

    kernel.QueryFullProcessImageNameW = FakeCall(query)
    assert launcher._process_image(4) == expected.resolve()
    assert events == [22, 22]


def test_same_executable_requires_exact_normalized_path(tmp_path, monkeypatch):
    expected = tmp_path / "App.exe"
    monkeypatch.setattr(launcher.sys, "executable", str(expected))
    assert not launcher._same_executable(None)
    assert launcher._same_executable(expected.resolve())
    assert not launcher._same_executable(tmp_path / "Other.exe")


def test_stop_stale_runtime_kill_failure_success_and_timeout(monkeypatch, tmp_path):
    port = launcher.PORT_RANGE[0]
    record = runtime_record(port)
    removed = []
    monkeypatch.setattr(launcher, "_load_runtime", lambda: record)
    monkeypatch.setattr(launcher, "_remove_runtime", lambda **kwargs: removed.append(kwargs))
    monkeypatch.setattr(launcher, "_process_image", lambda _pid: tmp_path / "App.exe")
    monkeypatch.setattr(launcher, "_same_executable", lambda _path: True)

    monkeypatch.setattr(launcher, "_probe_port", lambda _port: False)
    assert launcher._stop_running() == 0
    assert removed == [{"expected_pid": 777}]

    monkeypatch.setattr(launcher, "_probe_port", lambda _port: True)
    monkeypatch.setattr(launcher.os, "kill", lambda *_args: (_ for _ in ()).throw(OSError("denied")))
    assert launcher._stop_running() == 5

    probes = iter([True, False])
    monkeypatch.setattr(launcher, "_probe_port", lambda _port: next(probes))
    monkeypatch.setattr(launcher.os, "kill", lambda *_args: None)
    monkeypatch.setattr(launcher.time, "sleep", lambda _seconds: None)
    assert launcher._stop_running() == 0

    monkeypatch.setattr(launcher, "_probe_port", lambda _port: True)
    times = iter([0.0, 1.0, 6.0])
    monkeypatch.setattr(launcher.time, "monotonic", lambda: next(times))
    assert launcher._stop_running() == 6


def test_stop_no_record_no_server_is_success(monkeypatch):
    monkeypatch.setattr(launcher, "_load_runtime", lambda: None)
    monkeypatch.setattr(launcher, "_running_origin", lambda: None)
    assert launcher._stop_running() == 0


def test_serve_duplicate_mutex_paths_and_port_exhaustion(monkeypatch):
    monkeypatch.setattr(launcher, "_running_origin", lambda: None)
    opened = []
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)

    @contextmanager
    def duplicate():
        yield False

    monkeypatch.setattr(launcher, "_single_instance_mutex", duplicate)
    monkeypatch.setattr(launcher, "_wait_for_origin", lambda: None)
    assert launcher._serve(open_browser=True) == 7

    monkeypatch.setattr(launcher, "_wait_for_origin", lambda: "http://127.0.0.1:41571")
    assert launcher._serve(open_browser=True) == 0
    assert opened == ["http://127.0.0.1:41571"]

    @contextmanager
    def acquired():
        yield True

    monkeypatch.setattr(launcher, "_single_instance_mutex", acquired)
    monkeypatch.setattr(launcher, "_running_origin", lambda: None)
    monkeypatch.setattr(launcher, "_port_available", lambda _port: False)
    assert launcher._serve(open_browser=False) == 8


def test_serve_rechecks_after_mutex_and_recovers_from_bind_race(monkeypatch):
    origins = iter([None, "http://127.0.0.1:41572"])
    monkeypatch.setattr(launcher, "_running_origin", lambda: next(origins))

    @contextmanager
    def acquired():
        yield True

    monkeypatch.setattr(launcher, "_single_instance_mutex", acquired)
    opened = []
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    assert launcher._serve(open_browser=True) == 0
    assert opened == ["http://127.0.0.1:41572"]

    monkeypatch.setattr(launcher, "_running_origin", lambda: None)
    available = set(launcher.PORT_RANGE[:2])
    monkeypatch.setattr(launcher, "_port_available", lambda port: port in available)
    written = []
    removed = []
    monkeypatch.setattr(launcher, "_write_runtime", written.append)
    monkeypatch.setattr(launcher, "_remove_runtime", lambda **kwargs: removed.append(kwargs))
    calls = []

    def serve(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise OSError("bind race")

    monkeypatch.setattr(launcher, "serve_local_application", serve)
    monkeypatch.setattr(launcher.os, "getpid", lambda: 44)
    assert launcher._serve(open_browser=False) == 0
    assert written == list(launcher.PORT_RANGE[:2])
    assert len(removed) >= 2


def test_require_windows_and_main_command_dispatch(monkeypatch):
    monkeypatch.setattr(launcher.sys, "platform", "linux")
    assert launcher.main(["status"]) == 10
    with pytest.raises(RuntimeError):
        launcher._require_windows()

    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher, "_stop_running", lambda: 4)
    assert launcher.main(["stop"]) == 4
    assert launcher.main(["restart"]) == 4

    monkeypatch.setattr(launcher, "_running_origin", lambda: None)
    assert launcher.main(["status"]) == 1
    monkeypatch.setattr(launcher, "_running_origin", lambda: "http://127.0.0.1:41571")
    assert launcher.main(["status"]) == 0

    served = []
    monkeypatch.setattr(launcher, "_stop_running", lambda: 0)
    monkeypatch.setattr(launcher, "_serve", lambda **kwargs: served.append(kwargs) or 0)
    assert launcher.main(["restart"]) == 0
    assert launcher.main(["open"]) == 0
    assert launcher.main(["background"]) == 0
    assert served == [
        {"open_browser": True},
        {"open_browser": True},
        {"open_browser": False},
    ]


def test_resolve_windows_documents_platform_dll_failure_api_failure_and_success(tmp_path, monkeypatch):
    monkeypatch.setattr(first_run.sys, "platform", "linux")
    assert first_run.resolve_windows_documents() is None

    monkeypatch.setattr(first_run.sys, "platform", "win32")
    monkeypatch.setattr(
        first_run.ctypes,
        "WinDLL",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("missing")),
        raising=False,
    )
    assert first_run.resolve_windows_documents() is None

    freed = []

    class Shell:
        pass

    class Ole:
        pass

    shell = Shell()
    ole = Ole()
    shell.SHGetKnownFolderPath = FakeCall(lambda *_args: 1)
    ole.CoTaskMemFree = FakeCall(lambda pointer: freed.append(pointer.value))
    dlls = iter([shell, ole])
    monkeypatch.setattr(first_run.ctypes, "WinDLL", lambda *_args, **_kwargs: next(dlls), raising=False)
    assert first_run.resolve_windows_documents() is None
    assert freed == []

    allocated = ctypes.create_unicode_buffer(str(tmp_path / "OneDrive" / "Documents"))
    address = ctypes.addressof(allocated)

    def resolve(_folder, _flags, _token, out_pointer):
        ctypes.cast(out_pointer, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.c_void_p(address)
        return 0

    shell.SHGetKnownFolderPath = FakeCall(resolve)
    dlls = iter([shell, ole])
    monkeypatch.setattr(first_run.ctypes, "WinDLL", lambda *_args, **_kwargs: next(dlls), raising=False)
    assert first_run.resolve_windows_documents() == tmp_path / "OneDrive" / "Documents"
    assert freed[-1] == address


def test_first_run_without_documents_and_late_state_conflict_preserves_winner(tmp_path, monkeypatch):
    state_root = tmp_path / "state"
    assert first_run.initialize_first_run_save_default(
        state_root=state_root,
        documents_resolver=lambda: None,
    ) is None

    store = first_run.UserStateStore(state_root)
    chosen = tmp_path / "winner.sav"
    original_save = first_run.UserStateStore.save
    called = False

    def racing_save(self, feature, value, *, expected_revision):
        nonlocal called
        if not called:
            called = True
            other = first_run.UserStateStore(state_root)
            original_save(
                other,
                "preferences",
                first_run.PreferencesState(selected_save_path=str(chosen)),
                expected_revision=0,
            )
        return original_save(self, feature, value, expected_revision=expected_revision)

    monkeypatch.setattr(first_run.UserStateStore, "save", racing_save)
    result = first_run.initialize_first_run_save_default(
        state_root=state_root,
        documents_resolver=lambda: tmp_path / "Documents",
    )
    assert result == chosen
    assert store.load("preferences").selected_save_path == str(chosen)
