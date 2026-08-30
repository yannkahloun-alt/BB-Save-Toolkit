from functools import lru_cache
import itertools
import pytest
pytestmark=pytest.mark.unit
import bbtool.projection.trajectory as tr


def generic_policy_factory(fit_stats, normal_ranges, selection_cfg, utility_lookup, total_weight):
    n=len(fit_stats); weights=tuple(float(selection_cfg[s][0]) for s in fit_stats); ties=tuple(selection_cfg[s][1] for s in fit_stats)
    avg=tuple((normal_ranges[s][0]+normal_ranges[s][1])/2 for s in fit_stats); utils=tuple(utility_lookup[s] for s in fit_stats); combos=tuple(itertools.combinations(range(n),3))
    def util(i,x):
        lo=int(x//1); hi=lo if x==lo else lo+1
        if hi==lo:return utils[i][lo]
        t=x-lo; return utils[i][lo]+t*(utils[i][hi]-utils[i][lo])
    @lru_cache(None)
    def terminal(raw): return sum(weights[i]*util(i,raw[i]) for i in range(n))/total_weight
    @lru_cache(None)
    def future(r,raw):
        if r<=0:return terminal(raw)
        best=None
        for picks in combos:
            nxt=list(raw)
            for i in picks:nxt[i]+=avg[i]
            key=(future(r-1,tuple(nxt)),tuple(ties[i] for i in picks))
            if best is None or key>best:best=key
        return best[0]
    def choose(rd,raw,rolls,total):
        left=total-rd-1; best=None; out=None
        for picks in combos:
            nxt=list(raw)
            for i in picks:nxt[i]+=rolls[i]
            key=(future(left,tuple(nxt)),tuple(ties[i] for i in picks))
            if best is None or key>best:best=key;out=picks
        return out
    return choose


@pytest.mark.parametrize('rounds',[1,2,3,10])
def test_four_stat_specialization_exactly_matches_generic_reference(monkeypatch,bro_factory,simple_role,rounds):
    role=simple_role(('HP','Fatigue','MAtk','MDef'),weights={'HP':1.5,'Fatigue':2.5,'MAtk':4,'MDef':4},baselines={'HP':60,'Fatigue':90,'MAtk':70,'MDef':15},targets={'HP':90,'Fatigue':130,'MAtk':90,'MDef':35})
    b=bro_factory(Level=8)
    tr.reset_trajectory_cache(); optimized=tr.project_fit_trajectory(b,role,rounds=rounds,samples=32,include_trace=True)
    original=tr._make_final_fit_policy
    monkeypatch.setattr(tr,'_make_final_fit_policy',generic_policy_factory)
    tr.reset_trajectory_cache(); generic=tr.project_fit_trajectory(b,role,rounds=rounds,samples=32,include_trace=True)
    assert optimized==generic
    monkeypatch.setattr(tr,'_make_final_fit_policy',original)


def test_three_stat_role_does_not_use_four_stat_simulator(monkeypatch,bro_factory,simple_role):
    monkeypatch.setattr(tr,'_simulate_one_four',lambda *a,**k:(_ for _ in ()).throw(AssertionError('4-stat path used')))
    tr.reset_trajectory_cache(); tr.project_fit_trajectory(bro_factory(),simple_role(('HP','MAtk','MDef')),rounds=1,samples=1)


def test_five_stat_role_falls_back_without_four_stat_simulator(monkeypatch,bro_factory,simple_role):
    monkeypatch.setattr(tr,'_simulate_one_four',lambda *a,**k:(_ for _ in ()).throw(AssertionError('4-stat path used')))
    tr.reset_trajectory_cache(); r=tr.project_fit_trajectory(bro_factory(),simple_role(('HP','Fatigue','Resolve','MAtk','MDef')),rounds=1,samples=1)
    assert len(r['fit_stats'])==5
