
"""Console tracing and structured runtime diagnostics."""
from __future__ import annotations

import hashlib
from pathlib import Path
import time


class Step:
    def __init__(self, label: str):
        self.label = label
        self.started = 0.0

    def __enter__(self):
        print(f"[START] {self.label}")
        self.started = time.perf_counter()
        return self

    def done(self, detail: str = ""):
        elapsed = time.perf_counter() - self.started
        suffix = f" — {detail}" if detail else ""
        print(f"[DONE ] {self.label:<30} {elapsed:>7.3f}s{suffix}")
        return elapsed

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.done()
        return False


def format_bytes(size: int) -> str:
    """Format an exact byte count compactly while retaining the exact value."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB ({size} B)"
    return f"{size / (1024 * 1024):.2f} MiB ({size} B)"


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a generated artifact without loading it all."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_generated_files(root: Path) -> None:
    """Print deterministic paths and sizes for the completed run directory."""
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        print(f"File: {path} — {format_bytes(path.stat().st_size)}")


def print_reference_status(status: dict) -> None:
    initial = status["initial_cache"]
    print(
        "        cache at start              "
        f"dictionary={'yes' if initial['dictionary']['exists'] else 'no'} · "
        f"backgrounds={'yes' if initial['backgrounds']['exists'] else 'no'} · "
        f"perks={'yes' if initial['perks']['exists'] else 'no'} · "
        f"traits={'yes' if initial.get('traits', {}).get('exists') else 'no'} · "
        f"perm injuries={'yes' if initial.get('permanent_injuries', {}).get('exists') else 'no'}"
    )

    scripts = status.get("scripts_download_stats")
    if scripts:
        print(
            "        vanilla scripts download    "
            f"{scripts['archive_bytes'] / (1024 * 1024):.2f} MiB · "
            f"{scripts['seconds']:.3f}s"
        )
        print(
            "        vanilla scripts archive     "
            f"{scripts['members']} files · {scripts['nut_files']} .nut · "
            f"{scripts['item_scripts']} item scripts · "
            f"{scripts['background_scripts']} background scripts"
        )

    ds = status.get("dictionary_stats")
    if ds:
        print(
            "        dictionary.json            "
            f"{ds['dictionary_ids']} / {ds['dictionary_ids']} BB-Edit IDs retained · "
            f"{ds['output_bytes'] / 1024:.1f} KiB"
        )
        print(
            "        equipment enrichment        "
            f"{ds['equipment_like']} equipment-like · {ds['with_value']} values · "
            f"{ds['unresolved']} unresolved · {ds['coverage_pct']:.1f}%"
        )
        print(
            "        item key matching           "
            f"{ds['exact_hash_matches']} exact script-hash matches · "
            f"{ds['exact_hash_with_value']} with resolved Value"
        )
        print(
            "        source value resolution     "
            f"{ds['source_value_resolved']} / {ds['source_scripts']} scripts · "
            f"{ds['source_value_local']} local · "
            f"{ds['source_value_inherited']} inherited · "
            f"{ds['source_value_unresolved']} unresolved"
        )
        print(
            "        dictionary generation       "
            f"BB-Edit dl {ds['bbedit_download_seconds']:.3f}s · "
            f"parse {ds['source_parse_seconds']:.3f}s · "
            f"join {ds['join_seconds']:.3f}s · "
            f"write {ds['write_seconds']:.3f}s"
        )
        if ds["unresolved_sample"]:
            print(
                "        unresolved item sample      "
                + ", ".join(ds["unresolved_sample"][:10])
            )

    bs = status.get("background_stats")
    if bs:
        print(
            "        backgrounds.json            "
            f"{bs['backgrounds']} resolved / "
            f"{bs['scanned_background_scripts']} scanned"
        )
        print(
            "        background inheritance      "
            f"hire={bs['inherited_hiring_cost']} · "
            f"daily={bs['inherited_daily_cost']} · "
            f"inferred id={bs['inferred_id']}"
        )
        print(
            "        background unresolved       "
            f"hire={bs['missing_hiring_cost']} · "
            f"daily={bs['missing_daily_cost']} · "
            f"parse {bs['parse_seconds']:.3f}s"
        )

    ps = status.get("perk_stats")
    if ps:
        print(
            "        perk_effects.json           "
            f"{ps['perks']} perks · {ps['stat_modifying']} core-stat modifiers · "
            f"{ps['exact_stat_modifying']} exact · "
            f"{ps['conditional_stat_modifying']} conditional"
        )
        print(
            "        perk effect parsing         "
            f"{ps['parse_seconds']:.3f}s · {ps['output_bytes'] / 1024:.1f} KiB"
        )

    ts = status.get("trait_stats")
    if ts:
        print(
            "        trait_effects.json          "
            f"{ts['traits']} traits · {ts['stat_modifying']} core-stat modifiers · "
            f"{ts['exact_stat_modifying']} exact · "
            f"{ts['conditional_stat_modifying']} conditional"
        )
        print(
            "        trait effect parsing        "
            f"{ts['parse_seconds']:.3f}s · {ts['output_bytes'] / 1024:.1f} KiB"
        )


    pis = status.get("permanent_injury_stats")
    if pis:
        print(
            "        permanent injury effects    "
            f"{pis['injuries']} injuries · {pis['stat_modifying']} core-stat modifiers · "
            f"{pis['exact_stat_modifying']} exact · "
            f"{pis['conditional_stat_modifying']} conditional"
        )
        print(
            "        permanent injury parsing    "
            f"{pis['parse_seconds']:.3f}s · {pis['output_bytes'] / 1024:.1f} KiB"
        )


def print_projection_profile(profile: dict) -> None:
    print(f"        base role matrix          {profile.get('base_matrix_s', 0.0):>7.3f}s")
    print(f"        structural paths          {profile.get('structural_paths_s', 0.0):>7.3f}s")
    print(f"        Level-Up Advisor          {profile.get('advisor_s', 0.0):>7.3f}s")
    print(f"        summary assembly          {profile.get('summary_s', 0.0):>7.3f}s")
    print(f"        Fit trajectories*         {profile.get('trajectory_s', 0.0):>7.3f}s")
    print(
        "        trajectory cache          "
        f"{profile.get('trajectory_cache_hits', 0)} hits · "
        f"{profile.get('trajectory_cache_misses', 0)} misses · "
        f"{profile.get('trajectory_adaptive_refinements', 0)} refined"
    )
    print(f"        full projections          {profile.get('full_projection_calls', 0):>7}")
    print(f"        fast projections          {profile.get('fast_projection_calls', 0):>7}")
    print(f"        projection calls          {profile['project_role_calls']:>7}")
    print("        * internal subcomponent; included in base/structural path wall time")
