
"""Top-level application workflow."""
from __future__ import annotations

import time
import webbrowser

from references.update_references import ensure_references

from ..projection import configure_engine, get_profile, reset_profile
from ..save_parser import parse_recruits, parse_roster
from .analysis import analyze_brothers
from ..incremental import IncrementalCache, find_previous_manifest, first_difference, prune_manifests, write_manifest
from .cli import CliOptions
from .config import load_config
from .console import Step, print_projection_profile, print_reference_status
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
                f"structural {incremental_cache.stats.structural_reused}/{incremental_cache.stats.structural_computed} · "
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
        step.done(validation_path.name)

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
    step.done()

    total_elapsed = time.perf_counter() - total_started
    print(f"[DONE ] Total                          {total_elapsed:>7.3f}s")
    print(f"Output: {workspace.root}")
    print(f"Archive: {archive_path}")

    if options.open_report and report_path is not None:
        opened = webbrowser.open(report_path.resolve().as_uri())
        print(f"Report: {report_path}")
        print(f"Opened: {'yes' if opened else 'no'}")

    return workspace, archive_path
