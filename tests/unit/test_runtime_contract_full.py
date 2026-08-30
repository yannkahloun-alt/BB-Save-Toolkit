import json
import subprocess
import sys

import bbtool.projection.runtime as runtime

EXPECTED_PROFILE = {
    "project_role_calls": 0,
    "full_projection_calls": 0,
    "fast_projection_calls": 0,
    "trajectory_s": 0.0,
    "trajectory_cache_hits": 0,
    "trajectory_cache_misses": 0,
    "trajectory_adaptive_refinements": 0,
    "trajectory_cache_miss_reasons": {
        "missing_entry": 0,
        "fingerprint_change": 0,
        "schema_version_mismatch": 0,
        "refinement": 0,
        "other_fallback": 0,
    },
    "base_matrix_s": 0.0,
    "advisor_s": 0.0,
    "summary_s": 0.0,
    "brother_projection_s": {},
    "archetype_projection_s": {},
    "slowest_projections": [],
}

def _counter_key(key):
    return key.endswith(("_calls", "_hits", "_misses", "_refinements"))

def _assert_profile_types(profile):
    for key in EXPECTED_PROFILE:
        if isinstance(EXPECTED_PROFILE[key], (dict, list)):
            assert type(profile[key]) is type(EXPECTED_PROFILE[key])
            continue
        expected_type = int if _counter_key(key) else float
        assert type(profile[key]) is expected_type

def test_profile_initialization_contract_is_exact_in_fresh_process():
    code = (
        "import json\n"
        "import bbtool.projection.runtime as runtime\n"
        "print(json.dumps({'values': runtime.PROFILE, "
        "'types': {k: type(v).__name__ for k, v in runtime.PROFILE.items()}}, sort_keys=True))\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], check=True, text=True, capture_output=True)
    payload = json.loads(proc.stdout.strip())
    assert payload["values"] == EXPECTED_PROFILE
    expected_types = {key: type(value).__name__ for key, value in EXPECTED_PROFILE.items()}
    assert payload["types"] == expected_types

def test_reset_profile_values_resets_every_entry_and_preserves_types():
    original = runtime.get_profile_values()
    try:
        runtime.PROFILE["project_role_calls"] = 17
        runtime.PROFILE["trajectory_s"] = 17.5
        runtime.PROFILE["trajectory_cache_miss_reasons"]["missing_entry"] = 17
        runtime.PROFILE["brother_projection_s"]["Bodo [human:1]"] = 17.5
        runtime.PROFILE["slowest_projections"].append({"seconds": 17.5})
        runtime.reset_profile_values()
        assert runtime.PROFILE == EXPECTED_PROFILE
        _assert_profile_types(runtime.PROFILE)
    finally:
        runtime.PROFILE.clear()
        runtime.PROFILE.update(original)

def test_get_profile_values_returns_detached_snapshot():
    original = runtime.get_profile_values()
    try:
        runtime.PROFILE["project_role_calls"] = 3
        runtime.PROFILE["trajectory_s"] = 1.25
        original_missing_entries = runtime.PROFILE["trajectory_cache_miss_reasons"]["missing_entry"]
        snapshot = runtime.get_profile_values()
        assert snapshot == runtime.PROFILE
        assert snapshot is not runtime.PROFILE
        snapshot["project_role_calls"] = 999
        snapshot["trajectory_s"] = 999.0
        snapshot["trajectory_cache_miss_reasons"]["missing_entry"] = 999
        assert runtime.PROFILE["project_role_calls"] == 3
        assert runtime.PROFILE["trajectory_s"] == 1.25
        assert runtime.PROFILE["trajectory_cache_miss_reasons"]["missing_entry"] == original_missing_entries
    finally:
        runtime.PROFILE.clear()
        runtime.PROFILE.update(original)


def test_record_projection_aggregates_and_bounds_slowest_entries():
    original = runtime.get_profile_values()
    try:
        runtime.reset_profile_values()
        for index in range(12):
            runtime.record_projection("human:1", "Bodo", f"Role {index}", "full", index / 10)
        profile = runtime.get_profile_values()
        assert profile["brother_projection_s"]["Bodo [human:1]"] == 6.6
        assert profile["archetype_projection_s"]["Role 11"] == 1.1
        assert len(profile["slowest_projections"]) == 10
        assert profile["slowest_projections"][0] == {
            "brother_id": "human:1", "brother": "Bodo", "archetype": "Role 11",
            "kind": "full", "seconds": 1.1, "structural_alternatives": 0,
        }
    finally:
        runtime.PROFILE.clear()
        runtime.PROFILE.update(original)
