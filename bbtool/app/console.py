
"""Console tracing and structured runtime diagnostics."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path


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
    if status.get("schema"):
        print(
            "        reference status            "
            f"{status['schema']} · cache {status['cache_directory']}"
        )
        print(
            "        reference schemas           "
            + " · ".join(
                f"{name}={value}"
                for name, value in status.get("reference_schemas", {}).items()
            )
        )
        print(
            "        reference fallback          "
            + ("used" if status.get("fallback_used") else "none")
        )
        for name, source in status.get("download_sources", {}).items():
            if name == "vanilla_scripts":
                continue
            revision = source.get(
                "immutable_revision", source.get("selected_revision", "unknown")
            )
            requested_url = source.get("requested_url", source.get("url", "unknown"))
            upstream = source.get("upstream_source")
            print(
                f"        reference source {name:<11}"
                f"network · ref {revision} · "
                f"{format_bytes(source['size_bytes'])} · "
                f"SHA-256 {source['sha256']} · {requested_url}"
                + (f" · upstream {upstream}" if upstream else "")
            )
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
        revision = scripts.get(
            "immutable_revision", scripts.get("selected_revision", "unknown")
        )
        print(
            "        vanilla scripts download    "
            f"{scripts['archive_bytes'] / (1024 * 1024):.2f} MiB · "
            f"{scripts['seconds']:.3f}s · "
            f"{scripts.get('source', 'network')} · "
            f"ref {revision}"
        )
        if scripts.get("sha256"):
            requested_url = scripts.get("requested_url", scripts.get("url", "unknown"))
            upstream = scripts.get("upstream_source")
            print(
                "        vanilla scripts provenance  "
                f"{requested_url} · SHA-256 {scripts['sha256']}"
                + (f" · upstream {upstream}" if upstream else "")
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
        scripts = bs["scripts"]
        hiring = bs["economy_fields"]["hiring_cost"]
        daily = bs["economy_fields"]["daily_cost"]
        identifiers = bs["identifiers"]
        print(
            "        backgrounds.json            "
            f"{bs['backgrounds']} entries from "
            f"{bs['usable_background_scripts']} usable scripts · "
            f"{bs['unusable_background_scripts']} unusable / "
            f"{scripts['decoded']} decoded"
        )
        print(
            "        hiring cost origin          "
            f"local={hiring['local']} · inherited={hiring['inherited']} · "
            f"unresolved={hiring['unresolved']}"
        )
        print(
            "        daily cost origin           "
            f"local={daily['local']} · inherited={daily['inherited']} · "
            f"unresolved={daily['unresolved']}"
        )
        print(
            "        background identifiers      "
            f"explicit={identifiers['explicit']} · "
            f"inferred={identifiers['inferred']}"
        )
        print(
            "        background script scan      "
            f"scanned={scripts['scanned']} · decoded={scripts['decoded']} · "
            f"decode failed={scripts['decode_failed']} · "
            f"resolution failed={scripts['resolution_failed']} · "
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

    final_cache = status.get("final_cache", {})
    if final_cache:
        print("        reference cache final state")
        for name, info in final_cache.items():
            print(
                f"          {name}: {info['source']} · "
                f"{'valid' if info['valid'] else 'invalid'} · "
                f"{format_bytes(info['size'])} · {info['path']}"
            )


def print_projection_profile(profile: dict) -> None:
    print(f"        base role matrix          {profile.get('base_matrix_s', 0.0):>7.3f}s")
    print(f"        Level-Up Advisor          {profile.get('advisor_s', 0.0):>7.3f}s")
    print(f"        summary assembly          {profile.get('summary_s', 0.0):>7.3f}s")
    print(f"        Fit trajectories*         {profile.get('trajectory_s', 0.0):>7.3f}s")
    print(
        "        trajectory cache          "
        f"{profile.get('trajectory_cache_hits', 0)} hits · "
        f"{profile.get('trajectory_cache_misses', 0)} misses · "
        f"{profile.get('trajectory_adaptive_refinements', 0)} refined"
    )
    miss_reasons = profile.get("trajectory_cache_miss_reasons", {})
    if miss_reasons:
        print(
            "        trajectory miss reasons   "
            + " · ".join(f"{name}={count}" for name, count in sorted(miss_reasons.items()))
        )
    print(f"        full projections          {profile.get('full_projection_calls', 0):>7}")
    print(f"        fast projections          {profile.get('fast_projection_calls', 0):>7}")
    print(f"        projection calls          {profile['project_role_calls']:>7}")
    slowest = profile.get("slowest_projections", ())
    if slowest:
        print("        slowest projections")
        for item in slowest[:5]:
            print(
                f"          {item['seconds']:.3f}s · {item['brother']} · "
                f"{item['archetype']} · {item['kind']} · "
                f"{item.get('structural_alternatives', 0)} structural alternatives"
            )
    brother_totals = profile.get("brother_projection_s", {})
    if brother_totals:
        name, seconds = max(brother_totals.items(), key=lambda item: item[1])
        print(f"        slowest brother            {seconds:.3f}s · {name}")
    archetype_totals = profile.get("archetype_projection_s", {})
    if archetype_totals:
        name, seconds = max(archetype_totals.items(), key=lambda item: item[1])
        print(f"        slowest archetype          {seconds:.3f}s · {name}")
    print("        * internal subcomponent; included in base role matrix and advisor wall time")
