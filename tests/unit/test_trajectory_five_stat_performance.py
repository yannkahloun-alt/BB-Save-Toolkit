from functools import cache
import itertools

from bbtool.projection.trajectory import _make_final_fit_policy


def _brute_choice(fit_stats, normal_ranges, selection_cfg, utility_lookup, total_weight,
                  round_index, raw_tuple, rolls_tuple, total_rounds):
    n = len(fit_stats)
    combos = tuple(itertools.combinations(range(n), 3))
    weights = tuple(float(selection_cfg[s][0]) for s in fit_stats)
    ties = tuple(selection_cfg[s][1] for s in fit_stats)
    avg = tuple((normal_ranges[s][0] + normal_ranges[s][1]) / 2 for s in fit_stats)

    def util(i, x):
        lo = int(x // 1)
        hi = lo if x == lo else lo + 1
        if hi == lo:
            return utility_lookup[fit_stats[i]][lo]
        t = x - lo
        a = utility_lookup[fit_stats[i]]
        return a[lo] + t * (a[hi] - a[lo])

    def terminal(raw):
        return sum(weights[i] * util(i, raw[i]) for i in range(n)) / total_weight

    @cache
    def future(r, raw):
        if not r:
            return terminal(raw)
        best = float("-inf")
        for picks in combos:
            nxt = list(raw)
            for i in picks:
                nxt[i] += avg[i]
            best = max(best, future(r - 1, tuple(nxt)))
        return best

    remaining = total_rounds - round_index - 1
    best_key = None
    best = None
    for picks in combos:
        nxt = list(raw_tuple)
        for i in picks:
            nxt[i] += rolls_tuple[i]
        key = (future(remaining, tuple(nxt)), tuple(ties[i] for i in picks))
        if best_key is None or key > best_key:
            best_key, best = key, picks
    return best


def test_five_stat_drop_composition_policy_matches_recursive_reference():
    stats = ("HP", "Fatigue", "Resolve", "MAtk", "MDef")
    normal = {s: (2, 4) for s in stats}
    selection = {s: (i + 1.0, i) for i, s in enumerate(stats)}
    # Linear utility tables make the reference compact while still exercising
    # five-stat 3-of-5 allocation and deterministic tie breaking.
    utility = {s: {x: x / 100.0 for x in range(0, 201)} for s in stats}
    total_weight = sum(v[0] for v in selection.values())
    policy = _make_final_fit_policy(stats, normal, selection, utility, total_weight)
    raw = (60, 70, 40, 55, 5)
    rolls = (4, 2, 3, 3, 2)

    for total_rounds in (2, 3, 4):
        assert policy(0, raw, rolls, total_rounds) == _brute_choice(
            stats, normal, selection, utility, total_weight,
            0, raw, rolls, total_rounds,
        )
