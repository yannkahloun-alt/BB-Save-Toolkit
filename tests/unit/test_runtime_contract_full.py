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
    "base_matrix_s": 0.0,
    "advisor_s": 0.0,
    "summary_s": 0.0,
}

def _counter_key(key):
    return key.endswith(("_calls", "_hits", "_misses", "_refinements"))

def _assert_profile_types(profile):
    for key in EXPECTED_PROFILE:
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
    expected_types = {key: ("int" if _counter_key(key) else "float") for key in EXPECTED_PROFILE}
    assert payload["types"] == expected_types

def test_reset_profile_values_resets_every_entry_and_preserves_types():
    original = dict(runtime.PROFILE)
    try:
        for key in runtime.PROFILE:
            runtime.PROFILE[key] = 17 if _counter_key(key) else 17.5
        runtime.reset_profile_values()
        assert runtime.PROFILE == EXPECTED_PROFILE
        _assert_profile_types(runtime.PROFILE)
    finally:
        runtime.PROFILE.clear()
        runtime.PROFILE.update(original)

def test_get_profile_values_returns_detached_snapshot():
    original = dict(runtime.PROFILE)
    try:
        runtime.PROFILE["project_role_calls"] = 3
        runtime.PROFILE["trajectory_s"] = 1.25
        snapshot = runtime.get_profile_values()
        assert snapshot == runtime.PROFILE
        assert snapshot is not runtime.PROFILE
        snapshot["project_role_calls"] = 999
        snapshot["trajectory_s"] = 999.0
        assert runtime.PROFILE["project_role_calls"] == 3
        assert runtime.PROFILE["trajectory_s"] == 1.25
    finally:
        runtime.PROFILE.clear()
        runtime.PROFILE.update(original)
