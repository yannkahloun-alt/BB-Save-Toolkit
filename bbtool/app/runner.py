
"""Top-level application workflow."""
from __future__ import annotations

import json
import time
import webbrowser

from references.update_references import ensure_references

from ..projection import configure_engine, get_profile, reset_profile
from ..save_parser import parse_recruits, parse_roster
from .analysis import analyze_brothers
from ..incremental import IncrementalCache, find_previous_manifest, first_difference, prune_manifests, write_manifest
from .cli import CliOptions
from .config import load_config
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
    write_analysis_json,
    write_debug_bundle,
    write_projection_validation,
    write_html,
    write_raw_inputs,
)


def run(options: CliOptions) -> tuple:
    total_started = time.perf_counter()

    step = Step("Reference dictionary")
    step.__enter__()
    reference_status = ensure_references(verbose=False)
    print_reference_status(reference_status)
    generated = (
        reference_status["generated_dictionary"]
        or reference_status["generated_backgrounds"]
        or reference_status.get("generated_perks", False)
        or reference_status.get("generated_traits", False)
        or reference_status.get("generated_permanent_injuries", False)
    )
    step.done("generated" if generated else "cached")

    step = Step("Parse roster")
    step.__enter__()
    bros = parse_roster(options.save)
    step.done(f"{len(bros)} brothers")

    step = Step("Parse recruits")
    step.__enter__()
    recruits = parse_recruits(options.save)
    step.done(f"{len(recruits)} candidates")

    step = Step("Prepare run output")
    step.__enter__()
    workspace = create_workspace(options.save, options.out)
    write_raw_inputs(workspace, bros, recruits)
    step.done()

    report_path = None
    validation_path = None

    if not options.no_projection:
        step = Step("Load configuration")
        step.__enter__()
        config = load_config(options.targets, options.classification)
        configure_engine()
        step.done()

        full_recompute = bool(getattr(options, "full_recompute", False))
        verify_cache = bool(getattr(options, "verify_cache", False))
        previous_path, previous_manifest = (None, None)
        if not full_recompute:
            previous_path, previous_manifest = find_previous_manifest(options.out, exclude_root=workspace.root, source_save=options.save)
        incremental_cache = IncrementalCache(previous_manifest, enabled=not full_recompute, previous_path=previous_path)

        reset_profile()
        step = Step("Strategic classification")
        step.__enter__()
        analysis = analyze_brothers(
            bros, config.roles, config.classification, incremental_cache
        )
        step.done(
            f"{len(bros)} brothers × {len(config.roles)} archetypes · "
            f"reused {incremental_cache.stats.role_reused} · "
            f"computed {incremental_cache.stats.role_computed} · "
            f"summaries reused {incremental_cache.stats.summary_reused}"
        )
        projection_profile = get_profile()
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

        if verify_cache and not full_recompute:
            verify_step = Step("Verify incremental cache")
            verify_step.__enter__()
            clean = analyze_brothers(bros, config.roles, config.classification, None)
            diff = first_difference(
                {"fits": analysis.fits, "summaries": analysis.summaries},
                {"fits": clean.fits, "summaries": clean.summaries},
            )
            if diff is not None:
                path, incremental_value, full_value = diff
                raise RuntimeError(
                    "Incremental cache verification failed at "
                    f"{path}: incremental={incremental_value!r} full={full_value!r}"
                )
            verify_step.done("incremental == full")

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
        )
        step.done(debug_path.name)

    step = Step("Create run archive")
    step.__enter__()
    archive_path = archive_workspace(workspace, options.out)
    archive_size = archive_path.stat().st_size
    archive_sha256 = sha256_file(archive_path)
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
            open_succeeded = bool(webbrowser.open(report_path.resolve().as_uri()))
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

    return workspace, archive_path
