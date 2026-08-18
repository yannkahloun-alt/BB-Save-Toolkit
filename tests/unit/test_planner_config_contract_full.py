import json
from pathlib import Path
import pytest
pytestmark=pytest.mark.unit
from bbtool.projection.planner import project_role


def test_project_role_with_effective_perk_and_without(cfg,bro_factory):
    role=next(r for r in cfg.roles if r['name']=='Nimble Tank')
    raw=bro_factory(Level=11,HP=80,Perks=[])
    col=bro_factory(Level=11,HP=80,Perks=['Colossus'])
    a=project_role(raw,role); b=project_role(col,role)
    assert b['HP']>=a['HP'] and b['ProjectedFitPct']>=a['ProjectedFitPct']


def test_config_perk_model_categories_are_known():
    root=Path(__file__).resolve().parents[2]
    model=json.loads((root/'config/perk_model.json').read_text(encoding="utf-8"))
    allowed={'_meta','structural','excluded'}
    assert set(model).issubset(allowed), set(model)-allowed
