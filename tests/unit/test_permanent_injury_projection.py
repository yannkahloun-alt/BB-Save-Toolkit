import io
import json
import zipfile

import pytest

from bbtool.incremental.fingerprint import brother_projection_fingerprint
from bbtool.projection import perks
from bbtool.projection.context import bro_fingerprint, reset_bro_context_cache
from references.update_references import (
    battle_brothers_save_hash,
    build_permanent_injury_effect_dictionary,
)


@pytest.fixture(autouse=True)
def refs(monkeypatch):
    monkeypatch.setattr(perks, "_PERK_EFFECTS_CACHE", {})
    monkeypatch.setattr(perks, "_TRAIT_EFFECTS_CACHE", {})
    monkeypatch.setattr(
        perks,
        "_PERMANENT_INJURY_EFFECTS_CACHE",
        {
            "11223344": {
                "Effects": [{
                    "stat": "MDef", "property": "MeleeDefenseMult",
                    "op": "*=", "value": 0.6,
                    "conditional": False, "exact": True,
                }]
            },
            "55667788": {
                "Effects": [{
                    "stat": "Fatigue", "property": "StaminaMult",
                    "op": "*=", "value": 0.6,
                    "conditional": False, "exact": True,
                }]
            },
        },
    )
    reset_bro_context_cache()
    yield
    reset_bro_context_cache()


def test_permanent_injury_modifies_projection_stats(bro_factory):
    bro = bro_factory(
        MDef=20, Fatigue=100,
        PermanentInjuryIDs=["11223344", "55667788"],
        PermanentInjuries=["Broken Knee", "Partly Collapsed Lung"],
    )
    effective, _ = perks.effective_stat_profile(bro)
    assert effective["MDef"] == pytest.approx(12.0)
    assert effective["Fatigue"] == pytest.approx(60.0)


def test_temporary_injury_does_not_change_projection_or_incremental_fingerprint(bro_factory):
    clean = bro_factory(Injuries=[], InjuryIDs=[], TemporaryInjuryIDs=[])
    injured = bro_factory(
        Injuries=["Cut Artery"],
        InjuryIDs=["AABBCCDD"],
        TemporaryInjuryIDs=["AABBCCDD"],
    )
    assert perks.effective_stat_profile(clean)[0] == perks.effective_stat_profile(injured)[0]
    assert bro_fingerprint(clean) == bro_fingerprint(injured)
    assert brother_projection_fingerprint(clean) == brother_projection_fingerprint(injured)


def test_permanent_injury_invalidates_context_and_incremental_fingerprint(bro_factory):
    clean = bro_factory()
    injured = bro_factory(
        Injuries=["Broken Knee"],
        InjuryIDs=["11223344"],
        PermanentInjuryIDs=["11223344"],
        PermanentInjuries=["Broken Knee"],
    )
    assert bro_fingerprint(clean) != bro_fingerprint(injured)
    assert brother_projection_fingerprint(clean) != brother_projection_fingerprint(injured)


def test_permanent_injury_reference_builder_uses_save_hash_not_display_name(tmp_path):
    script_path = "scripts/skills/injury/permanent/broken_knee_injury"
    save_hash = battle_brothers_save_hash(script_path)
    source = '''
        function onUpdate( _properties ) {
            _properties.MeleeDefenseMult *= 0.6;
            _properties.RangedDefenseMult *= 0.6;
            _properties.InitiativeMult *= 0.6;
        }
    '''
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("repo/" + script_path + ".nut", source)

    out = tmp_path / "permanent_injury_effects.json"
    stats = build_permanent_injury_effect_dictionary(
        out,
        scripts_archive=buf.getvalue(),
        reference_entries={
            save_hash: {"name": "Broken Knee", "type": "permanentInjury"}
        },
    )
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert stats["injuries"] == 1
    assert save_hash in raw["injuries"]
    assert {e["stat"] for e in raw["injuries"][save_hash]["Effects"]} == {
        "MDef", "RDef", "Initiative"
    }
