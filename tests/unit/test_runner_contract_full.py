from pathlib import Path
from types import SimpleNamespace
import json

import bbtool.app.runner as runner


class FakeStep:
    instances = []

    def __init__(self, label):
        self.label = label
        self.details = []
        FakeStep.instances.append(self)

    def __enter__(self):
        return self

    def done(self, detail=""):
        self.details.append(detail)
        return 0.0


def _patch_runner(monkeypatch, tmp_path, *, reference_status, open_result=True):
    FakeStep.instances = []

    report = tmp_path / "report.html"
    report.write_text("<html></html>", encoding="utf-8")
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"archive")
    validation = tmp_path / "validation.json"
    validation.write_text(
        json.dumps({"summary": {"roll_range_violations": 0}}),
        encoding="utf-8",
    )
    debug = tmp_path / "debug.json"
    debug.write_text("{}", encoding="utf-8")
    workspace = SimpleNamespace(
        root=tmp_path,
        source_save=tmp_path / "x.sav",
        base="x",
        generated_at="now",
    )

    calls = {
        "ensure_verbose": [],
        "opened": [],
        "reference_status": [],
        "profile": [],
        "archive_calls": 0,
    }

    monkeypatch.setattr(runner, "Step", FakeStep)
    monkeypatch.setattr(
        runner,
        "ensure_references",
        lambda verbose=False: calls["ensure_verbose"].append(verbose) or dict(reference_status),
    )
    monkeypatch.setattr(runner, "print_reference_status", lambda x: calls["reference_status"].append(x))
    monkeypatch.setattr(runner, "parse_roster", lambda p, **kwargs: [SimpleNamespace()])
    monkeypatch.setattr(runner, "parse_recruits", lambda p: [SimpleNamespace(), SimpleNamespace()])
    monkeypatch.setattr(runner, "create_workspace", lambda *a: workspace)
    monkeypatch.setattr(runner, "write_raw_inputs", lambda *a: None)
    monkeypatch.setattr(
        runner,
        "load_config",
        lambda *a: SimpleNamespace(roles=[SimpleNamespace(), SimpleNamespace(), SimpleNamespace()], classification={}),
    )
    monkeypatch.setattr(runner, "configure_engine", lambda: None)
    monkeypatch.setattr(runner, "reset_profile", lambda: None)
    monkeypatch.setattr(
        runner,
        "analyze_brothers",
        lambda *a: SimpleNamespace(fits=["fit"], summaries=["summary"]),
    )
    monkeypatch.setattr(runner, "get_profile", lambda: {"project_role_calls": 7})
    monkeypatch.setattr(runner, "print_projection_profile", lambda x: calls["profile"].append(x))
    monkeypatch.setattr(runner, "write_analysis_json", lambda *a: None)
    monkeypatch.setattr(runner, "write_html", lambda *a: report)
    monkeypatch.setattr(runner, "write_projection_validation", lambda *a: validation)
    monkeypatch.setattr(runner, "write_debug_bundle", lambda *a: debug)
    def archive_workspace(*args):
        calls["archive_calls"] += 1
        return archive

    monkeypatch.setattr(runner, "archive_workspace", archive_workspace)
    monkeypatch.setattr(
        runner.webbrowser,
        "open",
        lambda uri: calls["opened"].append(uri) or open_result,
    )

    return workspace, archive, report, calls


def _opts(tmp_path, *, no_projection=False, open_report=False):
    return SimpleNamespace(
        save=tmp_path / "x.sav",
        targets=Path("targets"),
        classification=Path("classification"),
        out=tmp_path,
        no_projection=no_projection,
        open_report=open_report,
    )


def test_runner_total_timing_reference_contract_and_generated_dictionary(monkeypatch, tmp_path, capsys):
    workspace, archive, report, calls = _patch_runner(
        monkeypatch,
        tmp_path,
        reference_status={
            "generated_dictionary": True,
            "generated_backgrounds": False,
            # deliberately omit generated_perks: default must be False
        },
    )
    ticks = iter([3.0, 8.75])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(ticks))

    returned = runner.run(_opts(tmp_path))

    assert returned == (workspace, archive)
    assert calls["ensure_verbose"] == [False]
    assert calls["reference_status"] == [{
        "generated_dictionary": True,
        "generated_backgrounds": False,
    }]
    assert FakeStep.instances[0].label == "Reference dictionary"
    assert FakeStep.instances[0].details == ["generated"]

    out = capsys.readouterr().out
    assert "[DONE ] Total                            5.750s" in out
    assert f"Output: {workspace.root}" in out
    assert f"Archive: {archive}" in out
    assert f"Report: {report}" in out
    assert f"Validation: PASS — {tmp_path / 'validation.json'}" in out
    assert "SHA-256" in out
    assert "Report opening: requested=no · attempted=no · successful=unavailable" in out
    assert calls["archive_calls"] == 2


def test_runner_stops_resource_monitor_after_failure(monkeypatch, tmp_path):
    options = _opts(tmp_path, no_projection=True)
    stopped = []
    monkeypatch.setattr(runner, "start_resource_monitoring", lambda: True)
    monkeypatch.setattr(
        runner, "stop_resource_monitoring", lambda started: stopped.append(started)
    )
    monkeypatch.setattr(runner, "build_run_metadata", lambda options: {})
    monkeypatch.setattr(runner, "print_run_header", lambda metadata: None)
    monkeypatch.setattr(
        runner,
        "ensure_references",
        lambda verbose=False: (_ for _ in ()).throw(RuntimeError("reference failure")),
    )

    try:
        runner.run(options)
    except RuntimeError as exc:
        assert str(exc) == "reference failure"
    else:
        raise AssertionError("expected run failure")

    assert stopped == [True]


def test_runner_generated_background_and_perks_each_mark_generated(monkeypatch, tmp_path):
    for status in (
        {"generated_dictionary": False, "generated_backgrounds": True, "generated_perks": False},
        {"generated_dictionary": False, "generated_backgrounds": False, "generated_perks": True},
    ):
        _patch_runner(monkeypatch, tmp_path, reference_status=status)
        ticks = iter([1.0, 4.0])
        monkeypatch.setattr(runner.time, "perf_counter", lambda ticks=ticks: next(ticks))

        runner.run(_opts(tmp_path, no_projection=True))

        assert FakeStep.instances[0].details == ["generated"]


def test_runner_all_reference_flags_false_marks_cached(monkeypatch, tmp_path):
    _patch_runner(
        monkeypatch,
        tmp_path,
        reference_status={
            "generated_dictionary": False,
            "generated_backgrounds": False,
            "generated_perks": False,
        },
    )
    ticks = iter([2.0, 6.0])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(ticks))

    runner.run(_opts(tmp_path, no_projection=True))

    assert FakeStep.instances[0].details == ["cached"]


def test_runner_open_report_true_opens_and_reports_success(monkeypatch, tmp_path, capsys):
    _, _, report, calls = _patch_runner(
        monkeypatch,
        tmp_path,
        reference_status={
            "generated_dictionary": False,
            "generated_backgrounds": False,
            "generated_perks": False,
        },
        open_result=True,
    )
    ticks = iter([5.0, 9.0])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(ticks))

    runner.run(_opts(tmp_path, open_report=True))

    assert calls["opened"] == [report.resolve().as_uri()]
    out = capsys.readouterr().out
    assert f"Report: {report}" in out
    assert "Report opening: requested=yes · attempted=yes · successful=yes" in out


def test_runner_open_report_false_does_not_open_generated_report(monkeypatch, tmp_path, capsys):
    _, _, report, calls = _patch_runner(
        monkeypatch,
        tmp_path,
        reference_status={
            "generated_dictionary": False,
            "generated_backgrounds": False,
            "generated_perks": False,
        },
    )
    ticks = iter([5.0, 9.0])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(ticks))

    runner.run(_opts(tmp_path, open_report=False))

    assert calls["opened"] == []
    out = capsys.readouterr().out
    assert f"Report: {report}" in out
    assert "Report opening: requested=no · attempted=no · successful=unavailable" in out


def test_runner_open_report_requested_without_projection_has_no_report_to_open(monkeypatch, tmp_path, capsys):
    _, _, _, calls = _patch_runner(
        monkeypatch,
        tmp_path,
        reference_status={
            "generated_dictionary": False,
            "generated_backgrounds": False,
            "generated_perks": False,
        },
    )
    ticks = iter([10.0, 15.0])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(ticks))

    runner.run(_opts(tmp_path, no_projection=True, open_report=True))

    assert calls["opened"] == []
    out = capsys.readouterr().out
    assert "Report:" not in out
    assert "Report opening: requested=yes · attempted=no · successful=unavailable" in out


def test_runner_open_report_false_result_prints_no(monkeypatch, tmp_path, capsys):
    _, _, report, calls = _patch_runner(
        monkeypatch,
        tmp_path,
        reference_status={
            "generated_dictionary": False,
            "generated_backgrounds": False,
            "generated_perks": False,
        },
        open_result=False,
    )
    ticks = iter([7.0, 13.0])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(ticks))

    runner.run(_opts(tmp_path, open_report=True))

    assert calls["opened"] == [report.resolve().as_uri()]
    assert "Report opening: requested=yes · attempted=yes · successful=no" in capsys.readouterr().out


def test_runner_reports_validation_failure_and_browser_exception(monkeypatch, tmp_path, capsys):
    _, _, _, _ = _patch_runner(
        monkeypatch,
        tmp_path,
        reference_status={
            "generated_dictionary": False,
            "generated_backgrounds": False,
        },
    )
    validation = tmp_path / "validation.json"
    validation.write_text(
        json.dumps({"summary": {"roll_range_violations": 2}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "write_projection_validation", lambda *a: validation)
    monkeypatch.setattr(
        runner.webbrowser,
        "open",
        lambda uri: (_ for _ in ()).throw(RuntimeError("browser unavailable")),
    )
    ticks = iter([1.0, 2.0])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(ticks))

    runner.run(_opts(tmp_path, open_report=True))

    out = capsys.readouterr().out
    assert f"Validation: FAIL — {validation}" in out
    assert "Report opening: requested=yes · attempted=yes · successful=no" in out
    assert "error=RuntimeError: browser unavailable" in out


def test_runner_missing_generated_perks_defaults_false(monkeypatch, tmp_path):
    _patch_runner(
        monkeypatch,
        tmp_path,
        reference_status={
            "generated_dictionary": False,
            "generated_backgrounds": False,
            # deliberately omit generated_perks: default must remain False
        },
    )
    ticks = iter([2.0, 6.0])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(ticks))

    runner.run(_opts(tmp_path, no_projection=True))

    assert FakeStep.instances[0].details == ["cached"]
