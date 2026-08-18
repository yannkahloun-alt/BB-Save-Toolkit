import pytest
pytestmark=pytest.mark.unit
from bbtool.app.output import build_projection_validation
from bbtool.projection.planner import project_role
from bbtool.models import STATS

def future_for(b,rounds):
    from bbtool.projection.progression import gain_range
    return {s:[gain_range(s,getattr(b,s+'Stars'))[0] for _ in range(rounds)] for s in STATS}
def test_validation_n_by_roles_and_fields(cfg,bro_factory):
    bros=[]; fits=[]
    for i in range(2):
        b=bro_factory(Name=f'B{i}',HumanOffset=i+1,Level=10); b.FutureRolls=future_for(b,1); bros.append(b); fits += [dict(project_role(b,r),BrotherID=b.BrotherID,Name=b.Name) for r in cfg.roles]
    v=build_projection_validation(bros,fits,cfg.roles); assert len(v['rows'])==2*len(cfg.roles); assert len({(r['BrotherID'],r['Role']) for r in v['rows']})==2*len(cfg.roles)
    for r in v['rows']:
        assert r['DeltaVsExpectedPct']==pytest.approx(round(r['SeededFitPct']-r['ExpectedFitPct'],1)); assert r['LikelyRangePct'][0]<=r['LikelyRangePct'][1]; assert r['FullRangePct'][0]<=r['FullRangePct'][1]
def test_validation_nine_bros_by_roles(cfg,bro_factory):
    bros=[]; fits=[]
    for i in range(9):
        b=bro_factory(Name=f'B{i}',HumanOffset=i+1,Level=11); b.FutureRolls={s:[] for s in STATS}; bros.append(b); fits += [dict(project_role(b,r),BrotherID=b.BrotherID,Name=b.Name) for r in cfg.roles]
    assert build_projection_validation(bros,fits,cfg.roles)['summary']['comparisons']==9*len(cfg.roles)
def test_roll_range_violation_detected(cfg,bro_factory):
    b=bro_factory(Level=10); b.FutureRolls=future_for(b,1); b.FutureRolls['MAtk']=[99]; fits=[dict(project_role(b,r),Name=b.Name) for r in cfg.roles]; assert build_projection_validation([b],fits,cfg.roles)['summary']['roll_range_violations']==1
