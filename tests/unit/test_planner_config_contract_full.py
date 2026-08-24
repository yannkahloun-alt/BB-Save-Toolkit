import json
from pathlib import Path
import pytest
pytestmark=pytest.mark.unit
from bbtool.projection.planner import project_role


def test_natural_projection_ignores_owned_stat_modifying_perks(
    bro_factory, simple_role, monkeypatch
):
    """Owned build perks must not rewrite natural level-11 potential."""
    from bbtool.projection import perks
    from bbtool.projection.context import reset_bro_context_cache
    from bbtool.projection.trajectory import reset_trajectory_cache

    monkeypatch.setattr(
        perks,
        "_PERK_EFFECTS_CACHE",
        {
            "Fortified Mind": {
                "Effects": [
                    {
                        "stat": "Resolve", "op": "*=", "value": 1.25,
                        "property": "BraveryMult", "exact": True,
                        "conditional": False,
                    }
                ]
            },
            "Colossus": {
                "Effects": [
                    {
                        "stat": "HP", "op": "*=", "value": 1.25,
                        "property": "HitpointsMult", "exact": True,
                        "conditional": False,
                    }
                ]
            },
        },
    )
    role = simple_role(("HP", "Resolve"), baselines={"HP": 40, "Resolve": 30})
    raw = bro_factory(Level=4, HP=70, Resolve=58)
    perked = bro_factory(
        Level=4, HP=70, Resolve=58, Perks=["Colossus", "Fortified Mind"]
    )

    reset_bro_context_cache()
    reset_trajectory_cache()
    without_perks = project_role(raw, role)
    with_perks = project_role(perked, role)

    assert with_perks["HP"] == without_perks["HP"]
    assert with_perks["Resolve"] == without_perks["Resolve"]
    assert with_perks["ProjectedFitPct"] == without_perks["ProjectedFitPct"]


def test_config_perk_model_categories_are_known():
    root=Path(__file__).resolve().parents[2]
    model=json.loads((root/'config/perk_model.json').read_text(encoding="utf-8"))
    allowed={'_meta','structural','excluded'}
    assert set(model).issubset(allowed), set(model)-allowed
