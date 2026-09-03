from pathlib import Path
from types import SimpleNamespace
import json

import pytest

import bbtool.app.runner as runner
from bbtool.models import CampaignIdentity


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
    workspace.source_save.write_bytes(b"save")

    calls = {
        "ensure_verbose": [],
        "opened": [],
        "reference_status": [],
        "profile": [],
        "archive_calls": 0,
        "archive_excludes": [],
        "archive_appends": [],
        "prune_calls": [],
        "debug_args": [],
    }

    monkeypatch.setattr(runner, "Step", FakeStep)
    monkeypatch.setattr(
        runner,
        "ensure_references",
        lambda verbose=False: calls["ensure_verbose"].append(verbose) or dict(reference_status),
    )
    monkeypatch.setattr(runner, "print_reference_status", lambda x: calls["reference_status"].append(x))
    monkeypatch.setattr(runner, "parse_roster", lambda p, **kwargs: [SimpleNamespace()])
    monkeypatch.setattr(
        runner,
        "parse_recruits",
        lambda p, diagnostics=None: [SimpleNamespace(), SimpleNamespace()],
    )
    monkeypatch.setattr(runner, "create_workspace", lambda *a: workspace)
    monkeypatch.setattr(runner, "write_raw_inputs", lambda *a: None)
    monkeypatch.setattr(
        runner,
        "load_config",
        lambda *a: SimpleNamespace(roles=[SimpleNamespace(), SimpleNamespace(), SimpleNamespace()], classification={}),
    )
    cache = SimpleNamespace(
        stats=SimpleNamespace(
            role_reused=0, role_computed=3, summary_reused=0,
            advisor_reused=0, advisor_computed=1, summary_computed=1,
        ),
        miss_reasons={},
        manifest_payload=lambda **kwargs: {},
    )
    def fake_analyze_save(request):
        status = runner.ensure_references(verbose=False)
        return SimpleNamespace(
            roster=[SimpleNamespace()],
            recruits=[SimpleNamespace(), SimpleNamespace()],
            analysis=SimpleNamespace(fits=["fit"], summaries=["summary"]),
            incremental_cache=cache,
            diagnostics={
                "parse": {"recoverable_failures": []},
                "references": status,
                "projection_profile": {"project_role_calls": 7},
                "validation_projection": {
                    "seeded_projection_calls": 3,
                    "blind_cache_lookups": 3,
                    "trajectory_cache_hits": 3,
                    "trajectory_cache_misses": 0,
                    "trajectory_seconds": 0.0,
                    "oracle_reused": 3,
                    "oracle_recomputed": 0,
                },
            },
            timings={"analysis": 0.25, "validation": 0.05, "total": 0.4},
            projection_validation={"summary": {"roll_range_violations": 0}},
        )
    monkeypatch.setattr(runner, "analyze_save", fake_analyze_save)
    monkeypatch.setattr(runner, "print_projection_profile", lambda x: calls["profile"].append(x))
    monkeypatch.setattr(runner, "write_analysis_json", lambda *a: None)
    monkeypatch.setattr(runner, "write_html", lambda *a: report)
    monkeypatch.setattr(runner, "write_projection_validation_payload", lambda *a: validation)
    monkeypatch.setattr(
        runner,
        "write_debug_bundle",
        lambda *a: calls["debug_args"].append(a) or debug,
    )
    def archive_workspace(*args, exclude=None):
        calls["archive_calls"] += 1
        calls["archive_excludes"].append(exclude)
        return archive

    monkeypatch.setattr(runner, "archive_workspace", archive_workspace)
    monkeypatch.setattr(
        runner,
        "append_file_to_archive",
        lambda *args: calls["archive_appends"].append(args),
    )
    monkeypatch.setattr(
        runner,
        "prune_outputs",
        lambda *args: calls["prune_calls"].append(args),
    )
    monkeypatch.setattr(
        runner,
        "launch_report_server",
        lambda source: calls["opened"].append(source) or open_result,
    )

    return workspace, archive, report, calls


def _opts(
    tmp_path, *, no_projection=False, open_report=False,
    measure_python_heap=False,
):
    return SimpleNamespace(
        save=tmp_path / "x.sav",
        targets=Path("targets"),
        classification=Path("classification"),
        out=tmp_path,
        no_projection=no_projection,
        open_report=open_report,
        measure_python_heap=measure_python_heap,
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
    assert FakeStep.instances[0].label == "Prepare run output"

    out = capsys.readouterr().out
    assert "[DONE ] Total                            5.750s" in out
    assert f"Output: {workspace.root}" in out
    assert f"Archive: {archive}" in out
    assert f"Report: {report}" in out
    assert f"Validation: PASS — {tmp_path / 'validation.json'}" in out
    assert "SHA-256" in out
    assert "Report opening: requested=no · attempted=no · successful=unavailable" in out
    assert calls["archive_calls"] == 1
    assert calls["archive_excludes"] == [{tmp_path / "debug.json"}]
    assert calls["archive_appends"] == [
        (tmp_path / "archive.zip", tmp_path / "debug.json", tmp_path)
    ]
    assert calls["prune_calls"] == [(tmp_path, "x", tmp_path / "archive.zip")]
    performance = calls["debug_args"][0][-1]
    assert performance["format"] == "bbtool.performance_diagnostics.v1"
    assert performance["analysis"]["role_workload"] == 3
    assert performance["analysis"]["role_computed"] == 3
    assert performance["analysis"]["summary_computed"] == 1
    assert performance["analysis"]["advisor_computed"] == 1
    assert performance["analysis"]["service_stage_seconds"]["analysis"] == 0.25
    assert performance["validation"]["oracle_reused"] == 3
    assert performance["validation"]["trajectory_cache_misses"] == 0
    assert performance["total_seconds"] == 5.75
    assert "strategic_classification" in performance["stage_seconds"]
    assert "create_run_archive" in performance["stage_seconds"]


def test_runner_scopes_manifest_lifecycle_by_campaign(monkeypatch, tmp_path):
    workspace, _, _, _ = _patch_runner(
        monkeypatch, tmp_path,
        reference_status={"generated_dictionary": False},
    )
    identity = CampaignIdentity(125, confidence="exact")
    observed = {}
    monkeypatch.setattr(runner, "parse_campaign_identity_bytes", lambda data: identity)

    def find(out, **kwargs):
        observed["find"] = (out, kwargs)
        return None, None

    monkeypatch.setattr(runner, "find_previous_manifest", find)
    monkeypatch.setattr(
        runner, "write_manifest",
        lambda run_workspace, payload: observed.setdefault(
            "write", (run_workspace, payload)
        ),
    )
    monkeypatch.setattr(
        runner, "prune_manifests",
        lambda out, **kwargs: observed.setdefault("prune", (out, kwargs)),
    )
    ticks = iter([1.0, 2.0])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(ticks))

    runner.run(_opts(tmp_path))

    assert observed["find"][1]["campaign_identity"] is identity
    assert observed["find"][1]["source_save"] == workspace.source_save
    assert observed["prune"][1]["campaign_identity"] is identity


def test_runner_does_not_prune_when_archive_generation_fails(monkeypatch, tmp_path):
    _, _, _, calls = _patch_runner(
        monkeypatch,
        tmp_path,
        reference_status={
            "generated_dictionary": False,
            "generated_backgrounds": False,
        },
    )
    monkeypatch.setattr(
        runner,
        "archive_workspace",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("archive failed")),
    )

    with pytest.raises(OSError, match="archive failed"):
        runner.run(_opts(tmp_path, no_projection=True))

    assert calls["prune_calls"] == []


def test_runner_stops_resource_monitor_after_failure(monkeypatch, tmp_path):
    options = _opts(
        tmp_path, no_projection=True, measure_python_heap=True
    )
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


def test_runner_does_not_start_heap_monitor_by_default(monkeypatch, tmp_path):
    options = _opts(tmp_path, no_projection=True)
    monkeypatch.setattr(
        runner,
        "start_resource_monitoring",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected heap tracing")),
    )
    monkeypatch.setattr(runner, "build_run_metadata", lambda options: {})
    monkeypatch.setattr(runner, "print_run_header", lambda metadata: None)
    monkeypatch.setattr(
        runner,
        "ensure_references",
        lambda verbose=False: (_ for _ in ()).throw(RuntimeError("stop")),
    )

    with pytest.raises(RuntimeError, match="stop"):
        runner.run(options)


def test_runner_generated_background_and_perks_each_mark_generated(monkeypatch, tmp_path):
    for status in (
        {"generated_dictionary": False, "generated_backgrounds": True, "generated_perks": False},
        {"generated_dictionary": False, "generated_backgrounds": False, "generated_perks": True},
    ):
        _patch_runner(monkeypatch, tmp_path, reference_status=status)
        ticks = iter([1.0, 4.0])
        monkeypatch.setattr(runner.time, "perf_counter", lambda ticks=ticks: next(ticks))

        runner.run(_opts(tmp_path, no_projection=True))

        reference_step = next(x for x in FakeStep.instances if x.label == "Reference dictionary")
        assert reference_step.details == ["generated"]


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

    reference_step = next(x for x in FakeStep.instances if x.label == "Reference dictionary")
    assert reference_step.details == ["cached"]


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

    assert calls["opened"] == [tmp_path]
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

    assert calls["opened"] == [tmp_path]
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
    monkeypatch.setattr(runner, "write_projection_validation_payload", lambda *a: validation)
    monkeypatch.setattr(
        runner,
        "launch_report_server",
        lambda source: (_ for _ in ()).throw(RuntimeError("browser unavailable")),
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

    reference_step = next(x for x in FakeStep.instances if x.label == "Reference dictionary")
    assert reference_step.details == ["cached"]
