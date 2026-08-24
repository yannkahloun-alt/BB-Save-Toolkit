import bbtool.app.console as console


def _full_status():
    return {
        "initial_cache": {
            "dictionary": {"exists": False},
            "backgrounds": {"exists": True},
            "perks": {"exists": False},
        },
        "scripts_download_stats": {
            "archive_bytes": (100 * 1024 * 1024) + (512 * 1024),
            "seconds": 0.125,
            "members": 11,
            "nut_files": 7,
            "item_scripts": 5,
            "background_scripts": 3,
        },
        "dictionary_stats": {
            "dictionary_ids": 12,
            "output_bytes": (100 * 1024) + 512,
            "equipment_like": 8,
            "with_value": 6,
            "unresolved": 2,
            "coverage_pct": 75.5,
            "exact_hash_matches": 7,
            "exact_hash_with_value": 5,
            "source_value_resolved": 9,
            "source_scripts": 10,
            "source_value_local": 6,
            "source_value_inherited": 3,
            "source_value_unresolved": 1,
            "bbedit_download_seconds": 0.111,
            "source_parse_seconds": 0.222,
            "join_seconds": 0.033,
            "write_seconds": 0.044,
            "unresolved_sample": [f"U{i}" for i in range(12)],
        },
        "background_stats": {
            "backgrounds": 4,
            "scanned_background_scripts": 9,
            "inherited_hiring_cost": 2,
            "inherited_daily_cost": 3,
            "inferred_id": 1,
            "missing_hiring_cost": 5,
            "missing_daily_cost": 6,
            "parse_seconds": 0.555,
        },
        "perk_stats": {
            "perks": 13,
            "stat_modifying": 8,
            "exact_stat_modifying": 5,
            "conditional_stat_modifying": 3,
            "parse_seconds": 0.666,
            "output_bytes": (200 * 1024) + 512,
        },
    }


def test_step_done_returns_real_elapsed_and_formats_detail(capsys, monkeypatch):
    values = iter([3.0, 8.75])
    monkeypatch.setattr(console.time, "perf_counter", lambda: next(values))

    step = console.Step("Long task")
    assert step.started == 0.0
    assert step.__enter__() is step
    elapsed = step.done("phase complete")

    assert elapsed == 5.75
    out = capsys.readouterr().out
    assert "[START] Long task" in out
    assert "[DONE ] Long task" in out
    assert "5.750s" in out
    assert "— phase complete" in out


def test_step_context_manager_calls_done_only_on_success(capsys, monkeypatch):
    values = iter([20.0, 21.25])
    monkeypatch.setattr(console.time, "perf_counter", lambda: next(values))

    with console.Step("Context task"):
        pass

    out = capsys.readouterr().out
    assert "[START] Context task" in out
    assert "[DONE ] Context task" in out
    assert "1.250s" in out


def test_print_reference_status_full_contract(capsys):
    console.print_reference_status(_full_status())
    out = capsys.readouterr().out

    expected_fragments = [
        "dictionary=no · backgrounds=yes · perks=no",
        "100.50 MiB · 0.125s",
        "11 files · 7 .nut · 5 item scripts · 3 background scripts",
        "12 / 12 BB-Edit IDs retained · 100.5 KiB",
        "8 equipment-like · 6 values · 2 unresolved · 75.5%",
        "7 exact script-hash matches · 5 with resolved Value",
        "9 / 10 scripts · 6 local · 3 inherited · 1 unresolved",
        "BB-Edit dl 0.111s · parse 0.222s · join 0.033s · write 0.044s",
        "U0, U1, U2, U3, U4, U5, U6, U7, U8, U9",
        "4 resolved / 9 scanned",
        "hire=2 · daily=3 · inferred id=1",
        "hire=5 · daily=6 · parse 0.555s",
        "13 perks · 8 core-stat modifiers · 5 exact · 3 conditional",
        "0.666s · 200.5 KiB",
    ]
    for fragment in expected_fragments:
        assert fragment in out

    assert "U10" not in out
    assert "U11" not in out


def test_print_reference_status_omits_missing_optional_sections(capsys):
    status = {
        "initial_cache": {
            "dictionary": {"exists": True},
            "backgrounds": {"exists": False},
            "perks": {"exists": True},
        }
    }

    console.print_reference_status(status)
    out = capsys.readouterr().out

    assert "dictionary=yes · backgrounds=no · perks=yes" in out
    assert "vanilla scripts download" not in out
    assert "dictionary.json" not in out
    assert "backgrounds.json" not in out
    assert "perk_effects.json" not in out


def test_print_reference_status_omits_empty_unresolved_sample(capsys):
    status = _full_status()
    status["dictionary_stats"]["unresolved_sample"] = []

    console.print_reference_status(status)
    out = capsys.readouterr().out

    assert "dictionary.json" in out
    assert "unresolved item sample" not in out


def test_print_projection_profile_full_contract(capsys):
    profile = {
        "base_matrix_s": 1.111,
        "structural_paths_s": 2.222,
        "advisor_s": 3.333,
        "summary_s": 4.444,
        "trajectory_s": 5.555,
        "trajectory_cache_hits": 6,
        "trajectory_cache_misses": 7,
        "trajectory_adaptive_refinements": 8,
        "full_projection_calls": 9,
        "fast_projection_calls": 10,
        "project_role_calls": 19,
    }

    console.print_projection_profile(profile)
    out = capsys.readouterr().out

    expected_fragments = [
        "1.111s",
        "2.222s",
        "3.333s",
        "4.444s",
        "5.555s",
        "6 hits · 7 misses · 8 refined",
        "full projections",
        "9",
        "fast projections",
        "10",
        "projection calls",
        "19",
        "* internal subcomponent; included in base/structural path wall time",
    ]
    for fragment in expected_fragments:
        assert fragment in out


def test_print_projection_profile_default_contract(capsys):
    console.print_projection_profile({"project_role_calls": 0})
    out = capsys.readouterr().out

    assert out.count("0.000s") == 5
    assert "0 hits · 0 misses · 0 refined" in out
    assert "full projections                0" in out
    assert "fast projections                0" in out
    assert "projection calls                0" in out


def test_generated_file_observability_is_sorted_and_includes_exact_sizes(tmp_path, capsys):
    (tmp_path / "z.json").write_bytes(b"z" * 1024)
    (tmp_path / "a.html").write_bytes(b"abc")

    console.print_generated_files(tmp_path)

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"File: {tmp_path / 'a.html'} — 3 B"
    assert lines[1] == f"File: {tmp_path / 'z.json'} — 1.0 KiB (1024 B)"
    assert console.sha256_file(tmp_path / "a.html") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
