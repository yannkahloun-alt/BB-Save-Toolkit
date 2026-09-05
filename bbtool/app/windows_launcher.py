"""Windows installed-application launcher for the loopback local app."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser

from .app_server import API_SCHEMA, LOOPBACK_HOST, serve_local_application

RUNTIME_SCHEMA = "bbtool.windows-runtime.v1"
PORT_RANGE = tuple(range(41571, 41580))
MUTEX_NAME = r"Local\BBSaveToolkit.Application"
_RUNTIME_DIRECTORY = "BB-Save-Toolkit"
_RUNTIME_FILE = "runtime.json"
_LOG_FILE = "launcher.log"


def _runtime_directory() -> Path:
    return Path(tempfile.gettempdir()) / _RUNTIME_DIRECTORY


def _runtime_file() -> Path:
    return _runtime_directory() / _RUNTIME_FILE


def _log_event(event: str, detail: str = "") -> None:
    """Write bounded launcher diagnostics without save paths or user state."""
    try:
        root = _runtime_directory()
        root.mkdir(parents=True, exist_ok=True)
        clean = " ".join(str(detail).splitlines())[:1000]
        with (root / _LOG_FILE).open("a", encoding="utf-8") as handle:
            handle.write(f"{int(time.time())} {event} {clean}\n")
    except OSError:
        pass


def _write_runtime(port: int) -> None:
    root = _runtime_directory()
    root.mkdir(parents=True, exist_ok=True)
    target = _runtime_file()
    temp = target.with_suffix(".tmp")
    payload = {
        "schema": RUNTIME_SCHEMA,
        "pid": os.getpid(),
        "port": port,
        "executable": str(Path(sys.executable).resolve()),
        "started_at": int(time.time()),
    }
    temp.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(temp, target)


def _load_runtime() -> dict[str, object] | None:
    try:
        raw = json.loads(_runtime_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or raw.get("schema") != RUNTIME_SCHEMA:
        return None
    pid = raw.get("pid")
    port = raw.get("port")
    executable = raw.get("executable")
    if (
        isinstance(pid, bool)
        or not isinstance(pid, int)
        or pid <= 0
        or isinstance(port, bool)
        or not isinstance(port, int)
        or port not in PORT_RANGE
        or not isinstance(executable, str)
        or not executable
    ):
        return None
    return raw


def _remove_runtime(*, expected_pid: int | None = None) -> None:
    record = _load_runtime()
    if expected_pid is not None and record is not None and record.get("pid") != expected_pid:
        return
    try:
        _runtime_file().unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _probe_port(port: int, *, timeout: float = 0.25) -> bool:
    origin = f"http://{LOOPBACK_HOST}:{port}"
    request = urllib.request.Request(f"{origin}/api/v1/health", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
    except (
        OSError,
        TimeoutError,
        urllib.error.URLError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return False
    data = payload.get("data") if isinstance(payload, dict) else None
    return bool(
        isinstance(data, dict)
        and data.get("status") == "ok"
        and data.get("api_schema") == API_SCHEMA
        and data.get("bind") == LOOPBACK_HOST
    )


def _running_origin() -> str | None:
    record = _load_runtime()
    checked: set[int] = set()
    if record is not None:
        port = int(record["port"])
        checked.add(port)
        if _probe_port(port):
            return f"http://{LOOPBACK_HOST}:{port}"
    for port in PORT_RANGE:
        if port in checked:
            continue
        if _probe_port(port):
            return f"http://{LOOPBACK_HOST}:{port}"
    return None


def _wait_for_origin(timeout: float = 5.0) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        origin = _running_origin()
        if origin is not None:
            return origin
        time.sleep(0.1)
    return None


def _port_available(port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((LOOPBACK_HOST, port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def _kernel32():
    if sys.platform != "win32":
        return None
    return ctypes.WinDLL("kernel32", use_last_error=True)


@contextmanager
def _single_instance_mutex():
    kernel = _kernel32()
    if kernel is None:
        yield True
        return
    kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.ReleaseMutex.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateMutexW(None, True, MUTEX_NAME)
    if not handle:
        raise OSError(ctypes.get_last_error(), "unable to create application mutex")
    already_exists = ctypes.get_last_error() == 183
    if already_exists:
        kernel.CloseHandle(handle)
        yield False
        return
    try:
        yield True
    finally:
        kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def _process_image(pid: int) -> Path | None:
    kernel = _kernel32()
    if kernel is None:
        return None
    process_query_limited_information = 0x1000
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return Path(buffer.value).resolve()
    finally:
        kernel.CloseHandle(handle)


def _same_executable(path: Path | None) -> bool:
    if path is None:
        return False
    expected = os.path.normcase(str(Path(sys.executable).resolve()))
    actual = os.path.normcase(str(path))
    return actual == expected


def _stop_running() -> int:
    record = _load_runtime()
    if record is None:
        return 0
    pid = int(record["pid"])
    port = int(record["port"])
    if not _probe_port(port):
        _remove_runtime(expected_pid=pid)
        return 0
    if not _same_executable(_process_image(pid)):
        _log_event("stop_refused", "runtime PID executable did not match launcher")
        return 4
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        _log_event("stop_failed", type(exc).__name__)
        return 5
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if not _probe_port(port):
            _remove_runtime(expected_pid=pid)
            return 0
        time.sleep(0.1)
    _log_event("stop_timeout", f"pid={pid} port={port}")
    return 6


def _serve(*, open_browser: bool) -> int:
    existing = _running_origin()
    if existing is not None:
        if open_browser:
            webbrowser.open(existing)
        return 0
    with _single_instance_mutex() as acquired:
        if not acquired:
            existing = _wait_for_origin()
            if existing is None:
                _log_event("duplicate_without_server")
                return 7
            if open_browser:
                webbrowser.open(existing)
            return 0
        existing = _running_origin()
        if existing is not None:
            if open_browser:
                webbrowser.open(existing)
            return 0
        for port in PORT_RANGE:
            if not _port_available(port):
                continue
            _write_runtime(port)
            try:
                _log_event("server_start", f"pid={os.getpid()} port={port}")
                serve_local_application(port=port, open_browser=open_browser)
                return 0
            except OSError:
                _remove_runtime(expected_pid=os.getpid())
                continue
            finally:
                _remove_runtime(expected_pid=os.getpid())
        _log_event("port_exhausted")
        return 8


def _require_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("the installed launcher is supported only on Windows")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "command",
        nargs="?",
        default="open",
        choices=("open", "background", "stop", "restart", "status"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        _require_windows()
        command = build_parser().parse_args(argv).command
        if command == "stop":
            return _stop_running()
        if command == "status":
            return 0 if _running_origin() is not None else 1
        if command == "restart":
            stopped = _stop_running()
            if stopped != 0:
                return stopped
            return _serve(open_browser=True)
        return _serve(open_browser=command == "open")
    except BaseException as exc:
        _log_event("launcher_error", f"{type(exc).__name__}: {exc}")
        return 10


__all__ = [
    "MUTEX_NAME",
    "PORT_RANGE",
    "RUNTIME_SCHEMA",
    "build_parser",
    "main",
]
