
"""Top-level application workflow."""
from __future__ import annotations

import json
from pathlib import Path
import time

from references.update_references import ensure_references

from ..save_parser import parse_recruits, parse_roster
from .analysis_service import (
    AnalysisServiceOptions,
    AnalysisServiceRequest,
    CompatibleCacheContext,
    SaveSource,
    analyze_save,
)
from ..incremental import find_previous_manifest, prune_manifests, write_manifest
from .cli import CliOptions
from .config import load_config
from .health import build_run_health, print_run_health
from .report_server import launch_report_server
from .telemetry import (
    build_run_metadata,
    print_resource_summary,
    print_run_header,
    refresh_resources,
    start_resource_monitoring,
    stop_resource_monitoring,
)
from .console import (
    Step,
    format_bytes,
    print_generated_files,
    print_projection_profile,
    print_reference_status,
    sha256_file,
)
from .output import (
    archive_workspace,
    create_workspace,
    finalize_debug_bundle_metadata,
    prune_outputs,
    write_analysis_json,
    write_debug_bundle,
    write_projection_validation,
    write_html,
    write_raw_inputs,
)


def run(options: CliOptions) -> tuple:
    resource_monitor_started = start_resource_monitoring()
    try:
        return _run(options, resource_monitor_started)
    finally:
        stop_resource_monitoring(resource_monitor_started)


def _run(options: CliOptions, resource_monitor_started: bool) -> tuple:
    total_started = time.perf_counter()
    run_metadata = build_run_metadata(options)
    print_run_header(run_metadata)

    step = Step("Prepare run output")
    step.__enter__()
    workspace = create_workspace(options.save, options.out)
    step.done()

    report_path = None
    validation_path = None
    validation_payload = None
    incremental_cache = None
    projection_profile = {}
    debug_path = None

    if not options.no_projection:
        step = Step("Load configuration")
        step.__enter__()
        config = load_config(options.targets, options.classification)
        step.done()

        full_recompute = bool(getattr(options, "full_recompute", False))
        verify_cache = bool(getattr(options, "verify_cache", False))
        previous_path, previous_manifest = (None, None)
        if not full_recompute:
            previous_path, previous_manifest = find_previous_manifest(options.out, exclude_root=workspace.root, source_save=options.save)
        step = Step("Strategic classification")
        step.__enter__()
        service_result = analyze_save(
            AnalysisServiceRequest(
                source=SaveSource(
                    Path(options.save).read_bytes(), Path(options.save).name
                ),
                roles=config.roles,
                classification=config.classification,
                options=AnalysisServiceOptions(verify_cache=verify_cache),
                cache=CompatibleCacheContext(
                    manifest=previous_manifest,
                    previous_path=previous_path,
                    enabled=not full_recompute,
                ),
            )
        )
        bros = service_result.roster
        recruits = service_result.recruits
        analysis = service_result.analysis
        incremental_cache = service_result.incremental_cache
        parse_diagnostics = service_result.diagnostics["parse"]
        reference_status = service_result.diagnostics["references"]
        write_raw_inputs(workspace, bros, recruits)
        print_reference_status(reference_status)
        step.done(
            f"{len(bros)} brothers × {len(config.roles)} archetypes · "
            f"reused {incremental_cache.stats.role_reused} · "
            f"computed {incremental_cache.stats.role_computed} · "
            f"summaries reused {incremental_cache.stats.summary_reused}"
        )
        projection_profile = service_result.diagnostics["projection_profile"]
        print_projection_profile(projection_profile)
        if bool(getattr(options, "cache_debug", False)):
            print(
                "        incremental artifacts      "
                f"roles {incremental_cache.stats.role_reused} reused/{incremental_cache.stats.role_computed} computed · "
                f"advisor {incremental_cache.stats.advisor_reused}/{incremental_cache.stats.advisor_computed} · "
                f"summary {incremental_cache.stats.summary_reused}/{incremental_cache.stats.summary_computed}"
            )
            if incremental_cache.miss_reasons:
                print(
                    "        cache miss reasons         "
                    + " · ".join(
                        f"{name}={count}"
                        for name, count in sorted(incremental_cache.miss_reasons.items())
                    )
                )

        write_manifest(
            workspace,
            incremental_cache.manifest_payload(
                generated_at=workspace.generated_at,
                source_save=workspace.source_save.name,
                source_save_path=str(workspace.source_save.resolve()),
            ),
        )
        prune_manifests(
            options.out,
            source_save_path=str(workspace.source_save.resolve()),
            keep=10,
            exclude_root=workspace.root,
        )

        step = Step("Write analysis outputs")
        step.__enter__()
        write_analysis_json(
            workspace,
            analysis.fits,
            analysis.summaries,
        )
        step.done()

        step = Step("Generate HTML report")
        step.__enter__()
        report_path = write_html(
            workspace,
            bros,
            recruits,
            analysis.fits,
            analysis.summaries,
            config.roles,
            config.classification,
        )
        step.done()

        step = Step("Write projection validation")
        step.__enter__()
        validation_path = write_projection_validation(
            workspace,
            bros,
            analysis.fits,
            config.roles,
        )
        validation_payload = json.loads(validation_path.read_text(encoding="utf-8"))
        validation_passed = not validation_payload.get("summary", {}).get(
            "roll_range_violations", 0
        )
        step.done(
            f"{'PASS' if validation_passed else 'FAIL'} — {validation_path}"
        )

        run_health = build_run_health(
            bros,
            recruits,
            reference_status,
            parse_diagnostics=parse_diagnostics,
            incremental_cache=incremental_cache,
            validation_payload=validation_payload,
        )
        refresh_resources(run_metadata)

        step = Step("Write debug bundle")
        step.__enter__()
        debug_path = write_debug_bundle(
            workspace,
            bros,
            recruits,
            analysis.fits,
            analysis.summaries,
            config.roles,
            config.classification,
            reference_status,
            projection_profile,
            run_health,
            run_metadata,
        )
        step.done(debug_path.name)

    if options.no_projection:
        step = Step("Reference dictionary")
        step.__enter__()
        reference_status = ensure_references(verbose=False)
        generated = any(
            value
            for key, value in reference_status.items()
            if key.startswith("generated_")
        )
        step.done("generated" if generated else "cached")
        parse_diagnostics = {"recoverable_failures": []}
        bros = parse_roster(options.save, diagnostics=parse_diagnostics)
        recruits = parse_recruits(options.save, diagnostics=parse_diagnostics)
        write_raw_inputs(workspace, bros, recruits)
        run_health = build_run_health(
            bros,
            recruits,
            reference_status,
            parse_diagnostics=parse_diagnostics,
        )

    step = Step("Create run archive")
    step.__enter__()
    archive_path = archive_workspace(workspace, options.out)
    refresh_resources(run_metadata)
    stop_resource_monitoring(resource_monitor_started)
    if debug_path is not None:
        finalize_debug_bundle_metadata(debug_path, run_metadata)
        # Rebuild so the archive contains the final, post-archive measurement.
        archive_path = archive_workspace(workspace, options.out)
    archive_size = archive_path.stat().st_size
    archive_sha256 = sha256_file(archive_path)
    prune_outputs(options.out, workspace.source_save.stem, archive_path)
    step.done(f"{format_bytes(archive_size)} — SHA-256 {archive_sha256}")

    total_elapsed = time.perf_counter() - total_started
    print(f"[DONE ] Total                          {total_elapsed:>7.3f}s")
    print(f"Output: {workspace.root}")
    print_generated_files(workspace.root)
    if report_path is not None:
        print(f"Report: {report_path}")
    if validation_path is not None:
        print(f"Validation: {'PASS' if validation_passed else 'FAIL'} — {validation_path}")
    print(
        f"Archive: {archive_path} — {format_bytes(archive_size)} — "
        f"SHA-256 {archive_sha256}"
    )

    open_requested = bool(options.open_report)
    open_attempted = False
    open_succeeded = None
    open_error = None
    if options.open_report and report_path is not None:
        open_attempted = True
        try:
            open_succeeded = bool(launch_report_server(workspace.root))
        except Exception as exc:  # Browser integration must not hide completed outputs.
            open_succeeded = False
            open_error = f"{type(exc).__name__}: {exc}"
    success = "yes" if open_succeeded else "no" if open_succeeded is False else "unavailable"
    print(
        "Report opening: "
        f"requested={'yes' if open_requested else 'no'} · "
        f"attempted={'yes' if open_attempted else 'no'} · successful={success}"
        + (f" · error={open_error}" if open_error else "")
    )
    print_run_health(run_health, debug_path.name if debug_path else None)
    print_resource_summary(run_metadata)

    return workspace, archive_path
