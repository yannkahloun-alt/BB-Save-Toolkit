import json
from pathlib import Path

import pytest

from bbtool.app.config import _normalize_role
from bbtool.app.config import load_config
from bbtool.recruitment_prior import (
    background_archetype_prior,
    load_background_potential_reference,
    supported_backgrounds,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "background_prior_reference.json"
VANILLA_FIXTURE = Path(__file__).parents[1] / "fixtures" / "background_prior_vanilla_excerpt.json"
ROOT = Path(__file__).parents[2]


def _role():
    return _normalize_role({
        "id": "melee_test", "name": "Melee test",
        "stats": {"MAtk": {"baseline": 70, "target": 90, "weight": 1}},
    })


def test_fixture_backed_prior_is_deterministic_and_machine_readable():
    reference = load_background_potential_reference(FIXTURE)
    first = background_archetype_prior("aaaabbbb", _role(), reference)
    second = background_archetype_prior("AAAABBBB", _role(), reference)

    assert first == second
    assert first["schema"] == "bbtool.background_archetype_prior.v1"
    assert first["background"] == {
        "save_hash": "AAAABBBB",
        "background_id": "background.farmhand",
        "source_revision": "fixture-pinned-revision",
    }
    assert first["build"]["id"] == "melee_test"
    assert first["build"]["definition_hash"].startswith("sha256:")
    distribution = first["distribution"]
    assert sum(distribution["fit_histogram_weight"].values()) == distribution["weight_denominator"]
    assert distribution["talent_weight_denominator"] == 56_000
    assert distribution["unique_talent_profiles"] == 4
    assert distribution["weight_denominator"] > distribution["talent_weight_denominator"]
    assert distribution["mean_fit_pct"] == 24.7


def test_background_talent_rules_change_only_intrinsic_prior_inputs():
    reference = load_background_potential_reference(FIXTURE)
    normal = background_archetype_prior("AAAABBBB", _role(), reference)
    excluded = background_archetype_prior("CCCCDDDD", _role(), reference)
    untalented = background_archetype_prior("EEEEFFFF", _role(), reference)

    assert excluded["distribution"]["talent_weight_denominator"] == 20_000
    assert excluded["distribution"]["unique_talent_profiles"] == 4
    assert untalented["distribution"]["talent_weight_denominator"] == 1
    assert untalented["distribution"]["unique_talent_profiles"] == 1
    assert normal["distribution"]["mean_fit_pct"] > excluded["distribution"]["mean_fit_pct"]


def test_supported_backgrounds_and_explicit_unsupported_cases():
    reference = load_background_potential_reference(FIXTURE)
    assert [row["save_hash"] for row in supported_backgrounds(reference)] == [
        "AAAABBBB", "CCCCDDDD", "EEEEFFFF",
    ]
    with pytest.raises(KeyError, match="unsupported background"):
        background_archetype_prior("00000000", _role(), reference)
    legacy_role = dict(_role())
    legacy_role.pop("id")
    with pytest.raises(ValueError, match="BuildIdentity"):
        background_archetype_prior("AAAABBBB", legacy_role, reference)


def test_reference_loader_rejects_unversioned_input(tmp_path):
    path = tmp_path / "backgrounds.json"
    path.write_text(json.dumps({"AAAABBBB": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="bbtool.backgrounds.v2"):
        load_background_potential_reference(path)


def test_reference_profile_uses_integer_lower_midpoints(monkeypatch):
    reference = load_background_potential_reference(FIXTURE)
    observed = []

    def oracle(brother, _role):
        observed.append((brother.Resolve, brother.MDef))
        return {"outcomes_pct": [0.0], "sample_count": 1}

    monkeypatch.setattr("bbtool.recruitment_prior.project_validation_oracle", oracle)
    result = background_archetype_prior("AAAABBBB", _role(), reference)

    assert observed and set(observed) == {(32, 2)}
    assert result["assumptions"]["starting_stats"].startswith("lower integer midpoint")


def test_pinned_vanilla_excerpt_distinguishes_shipped_melee_ranged_and_banner_roles():
    reference = load_background_potential_reference(VANILLA_FIXTURE)
    roles = {
        role["id"]: role for role in load_config(
            ROOT / "config" / "archetypes.json", ROOT / "config" / "classification.json"
        ).roles
    }
    results = {
        (background, build): background_archetype_prior(background, roles[build], reference)
        for background, build in (
            ("C6DD9695", "reach_dps"),
            ("3B7D9408", "archer"),
            ("71648BCF", "banner"),
        )
    }
    means = {key: value["distribution"]["mean_fit_pct"] for key, value in results.items()}
    assert means == {
        ("C6DD9695", "reach_dps"): 9.3,
        ("3B7D9408", "archer"): 42.4,
        ("71648BCF", "banner"): 25.6,
    }
    assert all(
        sum(row["distribution"]["fit_histogram_weight"].values())
        == row["distribution"]["weight_denominator"]
        for row in results.values()
    )
