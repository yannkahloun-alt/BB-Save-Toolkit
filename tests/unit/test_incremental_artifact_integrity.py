import copy

import bbtool.app.output as output
from bbtool.app.analysis import analyze_brothers
from bbtool.incremental.cache import IncrementalCache


def _cold_run(bro, roles, classification):
    cache = IncrementalCache(None)
    analysis = analyze_brothers([bro], roles, classification, cache)
    manifest = cache.manifest_payload(generated_at="cold", source_save="same.sav")
    return analysis, manifest


def _entry(manifest):
    return next(iter(manifest["brothers"].values()))


def test_impossible_role_payload_is_rejected_and_only_corrupted_role_recomputes(
    bro_factory, simple_role, cfg
):
    bro = bro_factory(Level=11)
    roles = [
        {**simple_role(("HP", "MAtk")), "id": "one", "name": "One"},
        {**simple_role(("HP", "MDef")), "id": "two", "name": "Two"},
    ]
    _cold, manifest = _cold_run(bro, roles, cfg.classification)
    corrupt = copy.deepcopy(manifest)
    artifact = _entry(corrupt)["roles"][IncrementalCache._role_storage_key(roles[0])]
    artifact["result"]["ProjectedFitPct"] = 999.0
    artifact["result"]["ProjectedFit"] = 9.99

    warm_cache = IncrementalCache(corrupt)
    warm = analyze_brothers([bro], roles, cfg.classification, warm_cache)
    full = analyze_brothers([bro], roles, cfg.classification, None)

    assert warm == full
    assert warm_cache.stats.role_computed == 1
    assert warm_cache.stats.role_reused == 1
    assert warm_cache.miss_reasons["role_artifact_invalid"] == 1
    assert all(row["ProjectedFitPct"] <= 100.0 for row in warm.fits)


def test_in_range_role_tamper_fails_integrity_and_cannot_publish_with_stale_summary(
    bro_factory, simple_role, cfg
):
    bro = bro_factory(Level=11)
    role = {**simple_role(("HP", "MAtk", "MDef")), "id": "one"}
    cold, manifest = _cold_run(bro, [role], cfg.classification)
    corrupt = copy.deepcopy(manifest)
    artifact = _entry(corrupt)["roles"][IncrementalCache._role_storage_key(role)]
    original = float(artifact["result"]["ProjectedFitPct"])
    artifact["result"]["ProjectedFitPct"] = 42.0 if original != 42.0 else 41.0

    warm_cache = IncrementalCache(corrupt)
    warm = analyze_brothers([bro], [role], cfg.classification, warm_cache)

    assert warm == cold
    assert warm_cache.stats.role_reused == 0
    assert warm_cache.stats.role_computed == 1
    assert warm_cache.miss_reasons["role_artifact_integrity_mismatch"] == 1
    assert warm.summaries[0]["ProjectedFitPct"] == warm.fits[0]["ProjectedFitPct"]


def test_summary_tamper_recomputes_summary_but_preserves_valid_role_and_advisor_reuse(
    bro_factory, simple_role, cfg
):
    bro = bro_factory(Level=11)
    role = {**simple_role(("HP", "MAtk", "MDef")), "id": "one"}
    cold, manifest = _cold_run(bro, [role], cfg.classification)
    corrupt = copy.deepcopy(manifest)
    _entry(corrupt)["summary"]["result"]["Category"] = "tampered"

    warm_cache = IncrementalCache(corrupt)
    warm = analyze_brothers([bro], [role], cfg.classification, warm_cache)

    assert warm == cold
    assert warm_cache.stats.role_reused == 1
    assert warm_cache.stats.advisor_reused == 1
    assert warm_cache.stats.summary_reused == 0
    assert warm_cache.stats.summary_computed == 1
    assert warm_cache.miss_reasons["summary_artifact_integrity_mismatch"] == 1


def test_advisor_tamper_recomputes_advisor_without_invalidating_valid_intrinsic_artifacts(
    bro_factory, simple_role, cfg
):
    bro = bro_factory(Level=11)
    role = {**simple_role(("HP", "MAtk", "MDef")), "id": "one"}
    cold, manifest = _cold_run(bro, [role], cfg.classification)
    corrupt = copy.deepcopy(manifest)
    _entry(corrupt)["advisor"]["result"]["tampered"] = True

    warm_cache = IncrementalCache(corrupt)
    warm = analyze_brothers([bro], [role], cfg.classification, warm_cache)

    assert warm == cold
    assert warm_cache.stats.role_reused == 1
    assert warm_cache.stats.summary_reused == 1
    assert warm_cache.stats.advisor_reused == 0
    assert warm_cache.stats.advisor_computed == 1
    assert warm_cache.miss_reasons["advisor_artifact_integrity_mismatch"] == 1


def test_validation_oracle_in_range_tamper_recomputes_oracle_only(
    monkeypatch, bro_factory, simple_role, cfg
):
    bro = bro_factory(Level=10, LevelPoints=0)
    role = {**simple_role(("HP", "MAtk", "MDef")), "id": "one"}
    _cold, manifest = _cold_run(bro, [role], cfg.classification)
    corrupt = copy.deepcopy(manifest)
    oracle = _entry(corrupt)["roles"][IncrementalCache._role_storage_key(role)][
        "validation_oracle"
    ]
    oracle["outcomes_pct"][0] = 42.0 if oracle["outcomes_pct"][0] != 42.0 else 41.0

    warm_cache = IncrementalCache(corrupt)
    warm = analyze_brothers([bro], [role], cfg.classification, warm_cache)
    rebuilt = {"_outcomes_pct": (42.0,)}
    monkeypatch.setattr(output, "_blind_projection_for_validation", lambda *_args: rebuilt)
    validation = output.build_projection_validation(
        [bro], warm.fits, [role], warm_cache.get_validation_oracle,
        warm_cache.store_validation_oracle,
    )

    assert warm_cache.stats.role_reused == 1
    assert warm_cache.miss_reasons["validation_oracle_integrity_mismatch"] == 1
    assert validation["summary"]["oracle_reused"] == 0
    assert validation["summary"]["oracle_recomputed"] == 1
    assert warm_cache.get_validation_oracle(bro, role) == rebuilt


def test_missing_integrity_is_artifact_scoped_and_fails_closed(
    bro_factory, simple_role, cfg
):
    bro = bro_factory(Level=11)
    roles = [
        {**simple_role(("HP", "MAtk")), "id": "one", "name": "One"},
        {**simple_role(("HP", "MDef")), "id": "two", "name": "Two"},
    ]
    cold, manifest = _cold_run(bro, roles, cfg.classification)
    legacy = copy.deepcopy(manifest)
    entry = _entry(legacy)
    entry["roles"][IncrementalCache._role_storage_key(roles[0])].pop("integrity")

    warm_cache = IncrementalCache(legacy)
    warm = analyze_brothers([bro], roles, cfg.classification, warm_cache)

    assert warm == cold
    assert warm_cache.stats.role_computed == 1
    assert warm_cache.stats.role_reused == 1
    assert warm_cache.miss_reasons["role_artifact_integrity_missing"] == 1
