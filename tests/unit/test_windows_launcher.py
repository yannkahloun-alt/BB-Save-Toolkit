from __future__ import annotations

from pathlib import Path

from bbtool.app import windows_launcher as launcher


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_record_is_bounded_and_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "_runtime_directory", lambda: tmp_path)
    monkeypatch.setattr(launcher.os, "getpid", lambda: 12345)
    monkeypatch.setattr(launcher.sys, "executable", str(tmp_path / "BB-Save-Toolkit.exe"))

    launcher._write_runtime(launcher.PORT_RANGE[0])
    record = launcher._load_runtime()

    assert record == {
        "schema": launcher.RUNTIME_SCHEMA,
        "pid": 12345,
        "port": launcher.PORT_RANGE[0],
        "executable": str((tmp_path / "BB-Save-Toolkit.exe").resolve()),
        "started_at": record["started_at"],
    }


def test_running_origin_rejects_stale_record_and_scans_known_ports(monkeypatch):
    first, second = launcher.PORT_RANGE[:2]
    monkeypatch.setattr(
        launcher,
        "_load_runtime",
        lambda: {"schema": launcher.RUNTIME_SCHEMA, "pid": 1, "port": first, "executable": "x"},
    )
    monkeypatch.setattr(launcher, "_probe_port", lambda port, timeout=0.25: port == second)

    assert launcher._running_origin() == f"http://127.0.0.1:{second}"


def test_serve_skips_conflicting_port_and_uses_next_available(monkeypatch):
    first, second = launcher.PORT_RANGE[:2]
    starts = []
    runtime_ports = []
    monkeypatch.setattr(launcher, "_running_origin", lambda: None)
    monkeypatch.setattr(launcher, "_port_available", lambda port: port != first)
    monkeypatch.setattr(launcher, "_write_runtime", runtime_ports.append)
    monkeypatch.setattr(launcher, "_remove_runtime", lambda **kwargs: None)
    monkeypatch.setattr(
        launcher,
        "serve_local_application",
        lambda **kwargs: starts.append(kwargs),
    )

    assert launcher._serve(open_browser=False) == 0
    assert runtime_ports == [second]
    assert starts == [{"port": second, "open_browser": False}]


def test_open_reuses_running_instance(monkeypatch):
    origin = "http://127.0.0.1:41571"
    opened = []
    monkeypatch.setattr(launcher, "_running_origin", lambda: origin)
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    monkeypatch.setattr(
        launcher,
        "serve_local_application",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not start another server")),
    )

    assert launcher._serve(open_browser=True) == 0
    assert opened == [origin]


def test_stop_refuses_pid_whose_executable_does_not_match(monkeypatch, tmp_path):
    port = launcher.PORT_RANGE[0]
    monkeypatch.setattr(
        launcher,
        "_load_runtime",
        lambda: {
            "schema": launcher.RUNTIME_SCHEMA,
            "pid": 777,
            "port": port,
            "executable": "ignored",
        },
    )
    monkeypatch.setattr(launcher, "_probe_port", lambda value, timeout=0.25: value == port)
    monkeypatch.setattr(launcher, "_process_image", lambda pid: tmp_path / "other.exe")
    monkeypatch.setattr(launcher.sys, "executable", str(tmp_path / "BB-Save-Toolkit.exe"))
    monkeypatch.setattr(
        launcher.os,
        "kill",
        lambda *args: (_ for _ in ()).throw(AssertionError("must not terminate unrelated process")),
    )

    assert launcher._stop_running() == 4


def test_stop_refuses_healthy_instance_without_verifiable_runtime_record(monkeypatch):
    monkeypatch.setattr(launcher, "_load_runtime", lambda: None)
    monkeypatch.setattr(
        launcher,
        "_running_origin",
        lambda: f"http://127.0.0.1:{launcher.PORT_RANGE[0]}",
    )

    assert launcher._stop_running() == 9


def test_installer_contract_is_per_user_state_preserving_and_windowless():
    iss = (ROOT / "packaging" / "windows" / "BB-Save-Toolkit.iss").read_text(encoding="utf-8")
    spec = (ROOT / "packaging" / "windows" / "BB-Save-Toolkit.spec").read_text(encoding="utf-8")
    build = (ROOT / "tools" / "build_windows_installer.ps1").read_text(encoding="utf-8")
    smoke = (ROOT / "tools" / "smoke_windows_installer.ps1").read_text(encoding="utf-8")

    assert "PrivilegesRequired=lowest" in iss
    assert "MinVersion=10.0.10240" in iss
    assert "ArchitecturesAllowed=x64" in iss
    assert "{userstartup}\\BB Save Toolkit" in iss
    assert 'Parameters: "background"' in iss
    assert "/DELETEUSERDATA" in iss
    assert "{localappdata}\\BB-Save-Toolkit" in iss
    assert "ResultCode <> 0" in iss
    assert "StopExistingApplication" in iss
    assert "InitializeUninstall" in iss
    assert "Unable to stop the currently installed BB Save Toolkit process" in iss
    assert "console=False" in spec
    assert "ensure_references" in build
    assert "$generatedReferenceCaches" in build
    assert "Remove-Item -Force -ErrorAction SilentlyContinue" in build
    assert "perk_effects.json" in build
    assert "PyInstaller" in build
    assert "Second launch created a conflicting application instance" in smoke
    assert "Assert-PersistedState" in smoke
    assert "Assert-InstalledDisplayedReport" in smoke
    assert "--dump-dom" in smoke
    assert "Packaging Smoke Build" in smoke
    assert "/api/v1/archetypes/set-disabled" in smoke
    assert "Synthetic Smoke Brother" in smoke
    assert "BROTHER_SIGNATURE" in smoke
    assert "/api/v1/analysis/result" in smoke
    assert "Silent uninstall unexpectedly deleted user-owned state" in smoke
    assert "AddMinutes(5)" in smoke


def test_launcher_command_contract():
    parser = launcher.build_parser()
    assert parser.parse_args([]).command == "open"
    for command in ("open", "background", "stop", "restart", "status"):
        assert parser.parse_args([command]).command == command
