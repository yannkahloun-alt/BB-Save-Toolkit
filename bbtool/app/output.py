"""Creation of reproducible analysis run folders and archives."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from ..formatting import component_summary
from ..html_report import render_report_launcher
from ..models import STATS
from ..perk_gear import perk_gear_facts
from ..projection import (
    development_rounds_to_11,
    gain_range,
    project_fit_trajectory,
    project_seeded_fit_trajectory,
)
from .health import build_public_analysis_health
from .target_presentation import (
    DATASET_SCHEMA as TARGET_DATASET_SCHEMA,
    build_target_presentation,
)
from ..incremental.dependencies import stable_hash as dependency_stable_hash

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MAX_RETAINED_OUTPUTS = 10


@dataclass(frozen=True)
class RunWorkspace:
    root: Path
    base: str
    generated_at: str
    source_save: Path


def create_workspace(save: Path, out_root: Path) -> RunWorkspace:
    out_root.mkdir(parents=True, exist_ok=True)
    run_dt = datetime.now().astimezone()
    stamp = run_dt.strftime("%Y%m%d-%H%M%S")
    generated_at = run_dt.isoformat(timespec="seconds")
    base = f"{save.stem}-{stamp}"
    root = out_root / base
    root.mkdir(parents=True, exist_ok=False)
    return RunWorkspace(
        root=root,
        base=base,
        generated_at=generated_at,
        source_save=save,
    )


def public_brother_data(bro) -> dict:
    """Serialize only information the normal analysis is allowed to consume.

    FutureRolls are hidden save-state ground truth and belong exclusively in the
    projection-validation artifact. CurrentRolls remain public because they are
    the rolls currently shown to the player and are consumed by the Advisor.
    """
    data = asdict(bro)
    data["BrotherID"] = bro.BrotherID
    preserved_facts = getattr(bro, "PerkGearFacts", None)
    data["PerkGearFacts"] = (
        preserved_facts if preserved_facts is not None else perk_gear_facts(bro)
    )
    data.pop("FutureRolls", None)
    # Native identity is available at the typed application-service boundary.
    # Keep the public report-v1 dataset free of durable campaign-local tokens.
    data.pop("NativeEntityToken", None)
    return data


_public_bro_dict = public_brother_data


def write_raw_inputs(workspace: RunWorkspace, bros, recruits) -> None:
    save_copy = (
        workspace.root
        / f"{workspace.base}{workspace.source_save.suffix}"
    )
    shutil.copy2(workspace.source_save, save_copy)

    (workspace.root / f"{workspace.base}-roster.json").write_text(
        json.dumps([public_brother_data(bro) for bro in bros], indent=2),
        encoding="utf-8",
    )
    (workspace.root / f"{workspace.base}-recruits.json").write_text(
        json.dumps(recruits, indent=2),
        encoding="utf-8",
    )


def _decorate_fit_rows(fits: list[dict]) -> None:
    for row in fits:
        row["ProjectedComponentSummary"] = component_summary(row["ProjectedComponents"])
        row["ProjectedRangeSummary"] = "; ".join(
            f"{stat}:{value['min']}-{value['max']} (EV {value['ev']})"
            for stat, value in row.get("ProjectedRanges", {}).items()
        )

def write_analysis_json(
    workspace: RunWorkspace,
    fits: list[dict],
    summaries: list[dict],
) -> None:
    _decorate_fit_rows(fits)
    (workspace.root / f"{workspace.base}-role-fit.json").write_text(
        json.dumps(fits, indent=2),
        encoding="utf-8",
    )
    (
        workspace.root
        / f"{workspace.base}-classification.json"
    ).write_text(
        json.dumps(summaries, indent=2),
        encoding="utf-8",
    )


REPORT_DATASET_SCHEMA = "bbtool.reference_analysis.v2"


def _write_public_json(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def write_report_dataset(
    workspace: RunWorkspace,
    bros,
    recruits,
    fits: list[dict],
    summaries: list[dict],
    roles: list[dict],
    class_cfg: dict,
    analysis_health: dict | None = None,
    presentation_context: dict | None = None,
    presentation_payload: dict | None = None,
) -> Path:
    """Write the versioned public JSON contract consumed by report serving."""
    analysis_health = analysis_health or build_public_analysis_health({})
    payloads = {
        "roster": [_public_bro_dict(bro) for bro in bros],
        "recruits": recruits,
        "role_fit": fits,
        "classification": summaries,
        "archetypes": {"roles": roles},
        "classification_config": class_cfg,
        "analysis_health": analysis_health,
    }
    files = {}
    for label, payload in payloads.items():
        path = workspace.root / f"{workspace.base}-{label.replace('_', '-')}.json"
        _write_public_json(path, payload)
        files[label] = {
            "path": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    schema = REPORT_DATASET_SCHEMA
    if presentation_context is not None or presentation_payload is not None:
        artifact_hashes = {key: value["sha256"] for key, value in files.items()}
        if presentation_context is not None:
            context = {"summaries": summaries, **presentation_context}
            presentation = build_target_presentation(
                bros=bros, recruits=recruits, roles=roles,
                analysis_health=analysis_health,
                artifact_hashes=artifact_hashes,
                **context,
            )
        else:
            presentation = deepcopy(presentation_payload)
            provenance = presentation["publication"]["provenance"]
            provenance["artifact_hashes"] = dict(sorted(artifact_hashes.items()))
            presentation["publication"]["coherence_signature"] = \
                dependency_stable_hash(provenance)
        path = workspace.root / f"{workspace.base}-target-presentation.json"
        _write_public_json(path, presentation)
        files["presentation"] = {
            "path": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        schema = TARGET_DATASET_SCHEMA
    manifest = {
        "schema": schema,
        "purpose": "versioned public inputs for the interactive report",
        "source": workspace.source_save.name,
        "generated_at": workspace.generated_at,
        "files": files,
    }
    manifest_path = workspace.root / "manifest.json"
    _write_public_json(manifest_path, manifest)
    return manifest_path



def _blind_projection_for_validation(bro, role) -> dict:
    """Return the exact blind trajectory distribution used by classification.

    Current visible level-up rolls are fixed exactly as they are in planner.py;
    hidden future rolls are deliberately not supplied here. In normal runs this
    resolves to the trajectory cache populated during Strategic Classification.
    """
    current = getattr(bro, "CurrentRolls", {}) or {}
    first_round_ranges = None
    if int(getattr(bro, "LevelPoints", 0)) > 0 and current:
        first_round_ranges = {stat: (int(value), int(value)) for stat, value in current.items()}
    return project_fit_trajectory(
        bro, role, rounds=development_rounds_to_11(bro),
        first_round_ranges=first_round_ranges,
    )


def _discrete_sum_distribution(lo: int, hi: int, rounds: int) -> dict[int, int]:
    """Exact count distribution for the sum of ``rounds`` uniform integer rolls."""
    dist = {0: 1}
    for _ in range(rounds):
        nxt = defaultdict(int)
        for subtotal, count in dist.items():
            for roll in range(lo, hi + 1):
                nxt[subtotal + roll] += count
        dist = dict(nxt)
    return dist


def _midrank_from_counts(dist: dict, actual) -> float | None:
    total = sum(dist.values())
    if not total:
        return None
    below = sum(count for value, count in dist.items() if value < actual)
    equal = dist.get(actual, 0)
    return round(100.0 * (below + 0.5 * equal) / total, 1)


def _roll_luck_to_level11(bro) -> dict:
    """Rank the serialized real roll sequence against vanilla roll RNG.

    This is oracle-only validation data.  Per-stat ranks use the exact discrete
    distribution of the cumulative rolls remaining through level 11.
    """
    rounds = development_rounds_to_11(bro)
    sequences = getattr(bro, "FutureRolls", {}) or {}
    by_stat = {}
    for stat in STATS:
        values = tuple(int(v) for v in sequences.get(stat, ())[:rounds])
        if len(values) != rounds:
            continue
        lo, hi = gain_range(stat, int(getattr(bro, stat + "Stars")))
        actual_sum = sum(values)
        dist = _discrete_sum_distribution(lo, hi, rounds)
        by_stat[stat] = {
            "PercentilePct": _midrank_from_counts(dist, actual_sum),
            "ActualSum": actual_sum,
            "ExpectedSum": round(rounds * (lo + hi) / 2.0, 1),
            "MinSum": rounds * lo,
            "MaxSum": rounds * hi,
            "RollRange": [lo, hi],
            "Rolls": list(values),
        }
    return {"Rounds": rounds, "ByStat": by_stat}


def _role_relevant_roll_rank(role: dict, roll_luck: dict) -> float | None:
    """Fit-weighted rank of the raw level-11 roll luck relevant to a role.

    This intentionally stays separate from the Fit simulator: it is the weighted
    average of the exact per-stat cumulative-roll percentiles, using the role's
    Fit weights.  It measures raw RNG quality, before pick competition, targets,
    perk transforms, or Fit curves can change the outcome.
    """
    stats = role.get("stats", {}) or {}
    by_stat = roll_luck.get("ByStat", {}) or {}
    weighted = []
    for stat, spec in stats.items():
        if spec.get("fit") is False:
            continue
        entry = by_stat.get(stat)
        if not entry or entry.get("PercentilePct") is None:
            return None
        weight = float(spec.get("weight", 1.0))
        weighted.append((weight, float(entry["PercentilePct"])))
    total_weight = sum(weight for weight, _ in weighted)
    if total_weight <= 0:
        return None
    return round(sum(weight * pct for weight, pct in weighted) / total_weight, 1)


def _empirical_percentile(outcomes, realized: float) -> tuple[float | None, int]:
    """Mid-rank percentile of a real Fit inside the blind simulated distribution."""
    values = tuple(float(v) for v in (outcomes or ()))
    n = len(values)
    if not n:
        return None, 0
    eps = 1e-12
    below = sum(v < realized - eps for v in values)
    equal = sum(abs(v - realized) <= eps for v in values)
    percentile = 100.0 * (below + 0.5 * equal) / n
    return round(percentile, 1), n


def build_projection_validation(
    bros, fits: list[dict], roles: list[dict], validation_oracle_lookup=None,
    validation_oracle_store=None,
) -> dict:
    """Compare probabilistic Fit projections with rolls serialized in the save.

    This diagnostic is intentionally excluded from classification/advisor inputs.
    """
    bro_by_id = {bro.BrotherID: bro for bro in bros}
    bros_by_name = {}
    for bro in bros:
        bros_by_name.setdefault(bro.Name, []).append(bro)
    role_by_name = {role["name"]: role for role in roles}
    rows = []
    roll_range_violations = []
    oracle_reused = 0
    oracle_recomputed = 0
    roll_luck_by_object = {id(bro): _roll_luck_to_level11(bro) for bro in bros}
    roll_luck_by_bro = {bro.BrotherID: roll_luck_by_object[id(bro)] for bro in bros}
    for bro in bros:
        rounds = development_rounds_to_11(bro)
        for stat, values in (getattr(bro, "FutureRolls", {}) or {}).items():
            lo, hi = gain_range(stat, int(getattr(bro, stat + "Stars")))
            for idx, value in enumerate(values[:rounds]):
                if not lo <= int(value) <= hi:
                    roll_range_violations.append({
                        "BrotherID": bro.BrotherID, "Name": bro.Name, "Stat": stat, "Round": idx + 1,
                        "Roll": int(value), "ExpectedRange": [lo, hi],
                    })

    for projected in fits:
        projected_id = projected.get("BrotherID")
        bro = bro_by_id.get(projected_id)
        if bro is None and projected_id is None:
            legacy_matches = bros_by_name.get(projected.get("Name"), [])
            bro = legacy_matches[0] if len(legacy_matches) == 1 else None
        role = role_by_name.get(projected.get("Role"))
        if bro is None or role is None:
            continue
        actual = project_seeded_fit_trajectory(bro, role)
        if actual is None:
            continue
        expected = float(projected.get("ProjectedFitPct", projected.get("ProjectedFit", 0.0)))
        likely_min = float(projected.get("ProjectedFitLikelyMinPct", expected))
        likely_max = float(projected.get("ProjectedFitLikelyMaxPct", expected))
        full_min = float(projected.get("ProjectedFitFullMinPct", expected))
        full_max = float(projected.get("ProjectedFitFullMaxPct", expected))
        realized = float(actual["fit_pct"])
        blind = validation_oracle_lookup(bro, role) if validation_oracle_lookup else None
        if blind is None:
            blind = _blind_projection_for_validation(bro, role)
            oracle_recomputed += 1
            if validation_oracle_store is not None:
                validation_oracle_store(bro, role, blind)
        else:
            oracle_reused += 1
        actual_percentile, percentile_samples = _empirical_percentile(
            blind.get("_outcomes_pct"), realized
        )
        rows.append({
            "BrotherID": bro.BrotherID, "Name": bro.Name, "Role": role["name"],
            "ExpectedFitPct": round(expected, 1),
            "SeededFitPct": round(realized, 1),
            "DeltaVsExpectedPct": round(realized - expected, 1),
            "ActualPercentilePct": actual_percentile,
            "ActualPercentileSampleCount": percentile_samples,
            "RelevantRollRankPct": _role_relevant_roll_rank(
                role, roll_luck_by_object[id(bro)]
            ),
            "LikelyRangePct": [round(likely_min, 1), round(likely_max, 1)],
            "FullRangePct": [round(full_min, 1), round(full_max, 1)],
            "InsideLikelyRange": likely_min - 1e-9 <= realized <= likely_max + 1e-9,
            "InsideFullRange": full_min - 1e-9 <= realized <= full_max + 1e-9,
            "SeededReached100": realized >= 100.0 - 1e-9,
            "ProjectedFeasibilityPct": projected.get("FitFeasibilityPct"),
            "Rounds": actual["rounds"],
            "Choices": actual["choices"],
        })
    n = len(rows)
    return {
        "purpose": "validation only; contains hidden future save rolls; never used by classification or advisor",
        "roll_luck_to_level11": roll_luck_by_bro,
        "rows": rows,
        "summary": {
            "comparisons": n,
            "oracle_reused": oracle_reused,
            "oracle_recomputed": oracle_recomputed,
            "inside_likely": sum(bool(r["InsideLikelyRange"]) for r in rows),
            "inside_likely_pct": round(100.0 * sum(bool(r["InsideLikelyRange"]) for r in rows) / n, 1) if n else None,
            "inside_full": sum(bool(r["InsideFullRange"]) for r in rows),
            "inside_full_pct": round(100.0 * sum(bool(r["InsideFullRange"]) for r in rows) / n, 1) if n else None,
            "mean_abs_delta_vs_expected": round(sum(abs(float(r["DeltaVsExpectedPct"])) for r in rows) / n, 2) if n else None,
            "max_abs_delta_vs_expected": round(max((abs(float(r["DeltaVsExpectedPct"])) for r in rows), default=0.0), 2) if n else None,
            "actual_percentile_mean": round(sum(float(r["ActualPercentilePct"]) for r in rows if r["ActualPercentilePct"] is not None) / sum(r["ActualPercentilePct"] is not None for r in rows), 1) if any(r["ActualPercentilePct"] is not None for r in rows) else None,
            "relevant_roll_rank_mean": round(sum(float(r["RelevantRollRankPct"]) for r in rows if r["RelevantRollRankPct"] is not None) / sum(r["RelevantRollRankPct"] is not None for r in rows), 1) if any(r["RelevantRollRankPct"] is not None for r in rows) else None,
            "roll_range_violations": len(roll_range_violations),
        },
        "roll_range_violations": roll_range_violations,
    }


def write_projection_validation(
    workspace: RunWorkspace,
    bros,
    fits: list[dict],
    roles: list[dict],
) -> Path:
    """Write the quarantined seeded-future validation artifact.

    This is the only JSON output allowed to expose FutureRolls / seeded choices.
    """
    validation = build_projection_validation(bros, fits, roles)
    return write_projection_validation_payload(workspace, validation)


def write_projection_validation_payload(
    workspace: RunWorkspace,
    validation: dict,
) -> Path:
    """Write validation data already computed by the analysis service."""
    payload = {
        "_meta": {
            "format": "bbtool.projection_validation.v3",
            "generated_at": workspace.generated_at,
            "source_save": workspace.source_save.name,
            "purpose": "projection calibration against hidden serialized future rolls",
            "warning": "validation-only oracle data; never feed into classification or advisor",
        },
        "summary": validation["summary"],
        "roll_luck_to_level11": validation["roll_luck_to_level11"],
        "rows": validation["rows"],
        "roll_range_violations": validation["roll_range_violations"],
    }
    path = workspace.root / f"{workspace.base}-projection-validation.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return path


def write_debug_bundle(
    workspace: RunWorkspace,
    bros,
    recruits,
    fits: list[dict],
    summaries: list[dict],
    roles: list[dict],
    classification_cfg: dict,
    reference_status: dict,
    projection_profile: dict,
    run_health: dict | None = None,
    run_metadata: dict | None = None,
    performance_diagnostics: dict | None = None,
) -> Path:
    """
    Single-file support bundle intended to be dropped into ChatGPT instead of
    the whole run ZIP. It contains the raw roster/recruit data, analysis JSON,
    active configuration, and runtime/reference diagnostics.
    """
    payload = {
        "_meta": {
            "format": "bbtool.debug_bundle.v1",
            "generated_at": workspace.generated_at,
            "source_save": workspace.source_save.name,
            "purpose": "single-file diagnostic bundle",
        },
        "roster": [_public_bro_dict(bro) for bro in bros],
        "recruits": recruits,
        "role_fit": fits,
        "classification": summaries,
        "config": {
            "archetypes": roles,
            "classification": classification_cfg,
        },
        "runtime": {
            "run_metadata": run_metadata or {},
            "references": reference_status,
            "projection_profile": projection_profile,
            "run_health": run_health or {},
            "performance": performance_diagnostics or {},
        },
    }

    path = workspace.root / f"{workspace.base}-debug.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return path


def finalize_debug_bundle_metadata(
    path: Path,
    run_metadata: dict,
    performance_diagnostics: dict | None = None,
) -> None:
    """Persist runtime data that is only complete near the end of the run."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    runtime = payload.setdefault("runtime", {})
    runtime["run_metadata"] = run_metadata
    if performance_diagnostics is not None:
        runtime["performance"] = performance_diagnostics
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def write_performance_diagnostics(
    workspace: RunWorkspace,
    performance_diagnostics: dict,
) -> Path:
    """Write the final small timing record appended after measured ZIP work."""
    path = workspace.root / f"{workspace.base}-performance.json"
    path.write_text(
        json.dumps(performance_diagnostics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path



def write_html(
    workspace: RunWorkspace,
    bros,
    recruits,
    fits: list[dict],
    summaries: list[dict],
    roles: list[dict],
    class_cfg: dict,
    analysis_health: dict | None = None,
    presentation_context: dict | None = None,
    presentation_payload: dict | None = None,
) -> Path:
    write_report_dataset(
        workspace, bros, recruits, fits, summaries, roles, class_cfg,
        analysis_health, presentation_context, presentation_payload,
    )
    shutil.copy2(PACKAGE_ROOT / "report.css", workspace.root / "report.css")
    shutil.copy2(PACKAGE_ROOT / "report.js", workspace.root / "report.js")

    report_path = workspace.root / f"{workspace.base}-report.html"
    report_path.write_text(
        render_report_launcher(workspace.source_save, workspace.generated_at),
        encoding="utf-8",
    )
    return report_path


def archive_workspace(
    workspace: RunWorkspace,
    out_root: Path,
    *,
    exclude: set[Path] | None = None,
) -> Path:
    archive_path = out_root / f"{workspace.base}.zip"
    excluded = {path.resolve() for path in (exclude or set())}
    with zipfile.ZipFile(
        archive_path, "w", zipfile.ZIP_DEFLATED
    ) as archive:
        for item in workspace.root.rglob("*"):
            if item.is_file() and item.resolve() not in excluded:
                archive.write(item, item.relative_to(out_root))
    return archive_path


def append_file_to_archive(
    archive_path: Path,
    item: Path,
    out_root: Path,
) -> None:
    """Append one late-finalized file without rebuilding the completed archive."""
    with zipfile.ZipFile(archive_path, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.write(item, item.relative_to(out_root))


def prune_outputs(
    output_directory: Path,
    source_stem: str,
    current_output: Path,
    *,
    max_outputs: int = MAX_RETAINED_OUTPUTS,
) -> list[Path]:
    """Delete obsolete generated archives for one save without touching other files."""
    if max_outputs < 1:
        raise ValueError("max_outputs must be at least 1")

    output_directory = output_directory.resolve()
    current_output = current_output.resolve()
    pattern = re.compile(
        rf"^{re.escape(source_stem)}-(\d{{8}})-(\d{{6}})\.zip$"
    )
    candidates = []
    for path in output_directory.iterdir():
        if not path.is_file() or path.parent.resolve() != output_directory:
            continue
        match = pattern.fullmatch(path.name)
        if match is None:
            continue
        try:
            stamp = datetime.strptime(
                "".join(match.groups()), "%Y%m%d%H%M%S"
            )
        except ValueError:
            stamp = datetime.fromtimestamp(path.stat().st_mtime)
        candidates.append((stamp, path.name, path))

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    retained = {current_output}
    for _, _, path in candidates:
        if len(retained) >= max_outputs:
            break
        if path != current_output:
            retained.add(path)
    deleted = []
    for _, _, path in candidates:
        if path in retained:
            continue
        try:
            path.unlink()
        except OSError as exc:
            print(f"Warning: unable to delete obsolete output {path}: {exc}")
        else:
            deleted.append(path)
    return deleted
