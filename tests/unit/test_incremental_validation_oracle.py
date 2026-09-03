import copy

import pytest

import bbtool.app.output as output
from bbtool.app.analysis import analyze_brothers
from bbtool.incremental.cache import IncrementalCache
from bbtool.projection.trajectory import reset_trajectory_cache


def _future_rolls(bro, rounds):
    from bbtool.models import STATS
    from bbtool.projection import gain_range

    return {
        stat: [gain_range(stat, int(getattr(bro, stat + "Stars")))[0]] * rounds
        for stat in STATS
    }


def test_fresh_process_warm_role_and_validation_reuse(
    monkeypatch, bro_factory, simple_role, cfg
):
    bro = bro_factory(Level=10, LevelPoints=0)
    bro.FutureRolls = _future_rolls(bro, 1)
    role = simple_role(("HP", "MAtk", "MDef"))
    classification = cfg.classification

    first = IncrementalCache(None)
    first_analysis = analyze_brothers([bro], [role], classification, first)
    manifest = first.manifest_payload(generated_at="run-a", source_save="same.sav")

    reset_trajectory_cache()
    second = IncrementalCache(manifest)
    second_analysis = analyze_brothers([bro], [role], classification, second)
    monkeypatch.setattr(
        output,
        "_blind_projection_for_validation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("blind oracle rebuilt")),
    )
    validation = output.build_projection_validation(
        [bro], second_analysis.fits, [role], second.get_validation_oracle
    )

    assert first_analysis.fits == second_analysis.fits
    assert "_ValidationOracle" not in second_analysis.fits[0]
    assert second.stats.role_reused == 1
    assert second.stats.role_computed == 0
    assert validation["summary"]["comparisons"] == 1
    assert validation["summary"]["oracle_reused"] == 1
    assert validation["summary"]["oracle_recomputed"] == 0


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda artifact: artifact.pop("validation_oracle"), "validation_oracle_missing"),
        (
            lambda artifact: artifact["validation_oracle"].update(engine_version=-1),
            "validation_oracle_engine_changed",
        ),
        (
            lambda artifact: artifact["validation_oracle"].update(input_hash="stale"),
            "validation_oracle_inputs_changed",
        ),
        (
            lambda artifact: artifact["validation_oracle"].update(sample_count=-1),
            "validation_oracle_corrupt",
        ),
        (
            lambda artifact: artifact["validation_oracle"].update(
                sample_count=True, outcomes_pct=[True]
            ),
            "validation_oracle_corrupt",
        ),
        (
            lambda artifact: artifact["validation_oracle"].update(
                sample_count=1, outcomes_pct=[False]
            ),
            "validation_oracle_corrupt",
        ),
    ],
)
def test_missing_stale_incompatible_or_corrupt_oracle_conservatively_recomputes(
    monkeypatch, bro_factory, simple_role, cfg, mutate, reason
):
    bro = bro_factory(Level=10, LevelPoints=0)
    bro.FutureRolls = _future_rolls(bro, 1)
    role = simple_role(("HP", "MAtk", "MDef"))
    cache = IncrementalCache(None)
    analysis = analyze_brothers([bro], [role], cfg.classification, cache)
    manifest = cache.manifest_payload(generated_at="run-a", source_save="same.sav")
    corrupt = copy.deepcopy(manifest)
    role_artifact = next(iter(corrupt["brothers"].values()))["roles"][role["name"]]
    mutate(role_artifact)

    warm = IncrementalCache(corrupt)
    warm_analysis = analyze_brothers([bro], [role], cfg.classification, warm)
    rebuilt = {"_outcomes_pct": (42.0,)}
    monkeypatch.setattr(output, "_blind_projection_for_validation", lambda *_args: rebuilt)
    validation = output.build_projection_validation(
        [bro], warm_analysis.fits, [role], warm.get_validation_oracle,
        warm.store_validation_oracle,
    )

    assert analysis.fits == warm_analysis.fits
    assert warm.stats.role_reused == 1
    assert warm.miss_reasons[reason] == 1
    assert validation["summary"]["oracle_reused"] == 0
    assert validation["summary"]["oracle_recomputed"] == 1
    assert warm.get_validation_oracle(bro, role) == rebuilt
