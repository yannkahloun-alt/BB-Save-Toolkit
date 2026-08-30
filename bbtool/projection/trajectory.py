"""Deterministic real-level-up trajectory projection for Fit (v3.18).

One simulation path serves blind probabilistic projection, the current-level Advisor,
and serialized-save ground truth. Callers differ only in the per-round roll ranges
they provide; exact known rolls are represented as degenerate ranges (X, X).
"""
from __future__ import annotations

from functools import cache, lru_cache
import time
from ..models import STATS, Brother
from .perks import effective_stat_value
from .progression import development_rounds_to_11
from .scoring import curve_value
from .runtime import PROFILE
from .context import bro_fingerprint, bro_projection_context

_PRIMES = (2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,
           73,79,83,89,97,101,103,107,109,113,127,131,137,139,149,151,
           157,163,167,173,179,181,191,193,197,199,211,223,227,229)
_STAT_INDEX = {stat: i for i, stat in enumerate(STATS)}
_TRAJECTORY_CACHE: dict[tuple, dict] = {}
_TRAJECTORY_CACHE_MAX = 4096
_CONTEXT_CACHE: dict[tuple, tuple] = {}
_CONTEXT_CACHE_MAX = 1024


def reset_trajectory_cache() -> None:
    _TRAJECTORY_CACHE.clear()
    _CONTEXT_CACHE.clear()


def _fit_stats(role: dict) -> tuple[str, ...]:
    return tuple(s for s in STATS if role.get("stats", {}).get(s, {}).get("fit"))


def _radical_inverse(n: int, base: int) -> float:
    inv = 1.0 / base
    factor = inv
    out = 0.0
    while n:
        n, digit = divmod(n, base)
        out += digit * factor
        factor *= inv
    return out


@lru_cache(maxsize=128)
def _sample_dimension(samples: int, dim: int) -> tuple[float, ...]:
    """One deterministic low-discrepancy dimension, reusable across shapes.

    Different archetypes/levels request many overlapping dimensionalities. v3.6
    rebuilt dimensions 0..N for every distinct N. Caching columns means a later
    36-D request can reuse the first 32 dimensions already built by a 32-D one.
    """
    samples = max(1, int(samples))
    base = _PRIMES[dim % len(_PRIMES)]
    return tuple(_radical_inverse(i + 1, base) for i in range(samples))


@lru_cache(maxsize=32)
def _sample_coordinates(samples: int, dimensions: int) -> tuple[tuple[float, ...], ...]:
    """Cache deterministic low-discrepancy rows shared by all roles."""
    samples = max(1, int(samples))
    dimensions = max(1, int(dimensions))
    columns = tuple(_sample_dimension(samples, dim) for dim in range(dimensions))
    return tuple(
        tuple(columns[dim][scenario] for dim in range(dimensions))
        for scenario in range(samples)
    )


def _normalize_round_ranges(
    rounds: int,
    first_round_ranges: dict[str, tuple[int, int]] | None = None,
    round_ranges: list[dict[str, tuple[int, int]]] | tuple[dict[str, tuple[int, int]], ...] | None = None,
) -> tuple[dict[str, tuple[int, int]], ...]:
    """Normalize all caller-supplied roll knowledge into per-round range overrides.

    Blind projection supplies no overrides. The Advisor may fix the current round.
    Ground truth fixes every serialized future roll as ``(X, X)``.
    """
    rounds = max(0, int(rounds))
    out: list[dict[str, tuple[int, int]]] = [dict() for _ in range(rounds)]
    if round_ranges is not None:
        for rd, mapping in enumerate(round_ranges[:rounds]):
            if not mapping:
                continue
            for stat, bounds in mapping.items():
                if stat not in _STAT_INDEX:
                    continue
                lo, hi = bounds
                out[rd][stat] = (int(lo), int(hi))
    if first_round_ranges and rounds:
        for stat, bounds in first_round_ranges.items():
            if stat not in _STAT_INDEX:
                continue
            lo, hi = bounds
            out[0][stat] = (int(lo), int(hi))
    return tuple(out)


def _round_ranges_key(round_ranges) -> tuple:
    return tuple(
        tuple(sorted((stat, tuple(bounds)) for stat, bounds in mapping.items()))
        for mapping in (round_ranges or ())
    )


def _projection_context(bro: Brother, role: dict, rounds: int, round_ranges=()):
    fit_stats = _fit_stats(role)
    round_key = _round_ranges_key(round_ranges)
    context_key = (bro_fingerprint(bro), _role_fingerprint(role, fit_stats), int(rounds), round_key)
    cached = _CONTEXT_CACHE.get(context_key)
    if cached is not None:
        return cached

    raw_start, effects, _current, _levels, _gains, all_normal_ranges = bro_projection_context(bro)
    normal_ranges = {stat: all_normal_ranges[stat] for stat in fit_stats}
    selection_cfg = {
        stat: (
            float(role["stats"][stat].get("weight", 1.0)),
            -_STAT_INDEX[stat],
        )
        for stat in fit_stats
    }

    # Compile the actual ranges used at every round, aligned to fit_stats.
    # This is the single input seam used by blind, Advisor, and ground-truth runs.
    range_plan = tuple(
        tuple(
            round_ranges[rd].get(stat, normal_ranges[stat]) if rd < len(round_ranges)
            else normal_ranges[stat]
            for stat in fit_stats
        )
        for rd in range(rounds)
    )

    effective_lookup = {}
    utility_lookup = {}
    for j, stat in enumerate(fit_stats):
        # Validation may deliberately replay an out-of-normal-range serialized
        # roll so it can be reported as a violation. Size the lookup for the
        # actual supplied range plan instead of crashing before validation can
        # report it. Normal blind projection is unchanged.
        max_gain = sum(max(int(range_plan[rd][j][1]), int(normal_ranges[stat][1])) for rd in range(rounds))
        start = int(raw_start[stat])
        stop = start + max_gain
        eff_map = {}
        util_map = {}
        stat_cfg = role["stats"][stat]
        curve = stat_cfg["projected_curve"]
        ceiling = stat_cfg.get("ceiling")
        for raw_value in range(start, stop + 1):
            eff = effective_stat_value(bro, stat, float(raw_value), effects)
            eff_map[raw_value] = eff
            fit_value = min(eff, float(ceiling)) if ceiling is not None else eff
            util_map[raw_value] = curve_value(fit_value, curve)
        effective_lookup[stat] = eff_map
        utility_lookup[stat] = util_map

    static_effective = _current
    total_weight = sum(float(role["stats"][s].get("weight", 1.0)) for s in fit_stats)
    result = (fit_stats, effects, raw_start, normal_ranges, range_plan, selection_cfg,
              effective_lookup, utility_lookup, static_effective, total_weight)
    if len(_CONTEXT_CACHE) >= _CONTEXT_CACHE_MAX:
        _CONTEXT_CACHE.clear()
    _CONTEXT_CACHE[context_key] = result
    return result


def _make_final_fit_policy(fit_stats, normal_ranges, selection_cfg, utility_lookup, total_weight):
    """Value a known current roll by projected final Fit at level 11.

    Future hidden rolls are never inspected. For lookahead, every still-unknown
    future roll is represented by the midpoint of its normal roll range. The
    policy then finds the best 3-of-N allocation over those remaining average
    rounds. This keeps validation blind while valuing investments that only pay
    off after crossing a baseline.
    """
    import itertools
    n = len(fit_stats)
    if n <= 3:
        return lambda rd, raw_tuple, rolls_tuple, total_rounds: tuple(range(n))

    weights = tuple(float(selection_cfg[s][0]) for s in fit_stats)
    ties = tuple(selection_cfg[s][1] for s in fit_stats)
    avg_rolls = tuple((float(normal_ranges[s][0]) + float(normal_ranges[s][1])) / 2.0 for s in fit_stats)
    utilities = tuple(utility_lookup[s] for s in fit_stats)
    combos = tuple(itertools.combinations(range(n), 3))

    def util(i, raw_value):
        # Utility curves are piecewise linear in raw space between integer
        # lookup points, so midpoint future rolls can be evaluated exactly by
        # interpolation without exposing any hidden future roll.
        lo = int(raw_value // 1)
        hi = lo if raw_value == lo else lo + 1
        if hi == lo:
            return utilities[i][lo]
        t = raw_value - lo
        return utilities[i][lo] + t * (utilities[i][hi] - utilities[i][lo])

    @cache
    def terminal(raw_tuple):
        return sum(weights[i] * util(i, raw_tuple[i]) for i in range(n)) / total_weight

    if n >= 4:
        # Future lookahead uses fixed average rolls and only terminal Fit.
        # Therefore the order of future pick-combos is irrelevant: a terminal
        # state is fully described by how many of the r future rounds each stat
        # is *not* picked. For n stats with three picks/round there are
        # (n-3)*r total drops. Cache the bounded drop-count compositions by
        # horizon: every sampled state shares exactly the same combinatorics.
        @cache
        def drop_compositions(r):
            total_drops = (n - 3) * r
            out = []

            def visit(i, drops_left, prefix):
                if i == n - 1:
                    if 0 <= drops_left <= r:
                        out.append(prefix + (drops_left,))
                    return
                remaining_stats = n - i - 1
                lo = max(0, drops_left - remaining_stats * r)
                hi = min(r, drops_left)
                for drops in range(lo, hi + 1):
                    visit(i + 1, drops_left - drops, prefix + (drops,))

            visit(0, total_drops, ())
            return tuple(out)

        @cache
        def best_average_future(rounds_left, raw_tuple):
            if rounds_left <= 0:
                return terminal(raw_tuple)
            r = int(rounds_left)
            contributions = tuple(
                tuple(
                    weights[i] * util(
                        i, raw_tuple[i] + avg_rolls[i] * (r - drops)
                    )
                    for drops in range(r + 1)
                )
                for i in range(n)
            )
            best = float("-inf")
            for drops in drop_compositions(r):
                value = sum(contributions[i][drops[i]] for i in range(n)) / total_weight
                if value > best:
                    best = value
            return best
    else:
        @cache
        def best_average_future(rounds_left, raw_tuple):
            return terminal(raw_tuple)

    def choose(round_index, raw_tuple, rolls_tuple, total_rounds):
        future_rounds = total_rounds - round_index - 1
        best_key = None; best = None
        for picks in combos:
            nxt = list(raw_tuple)
            for i in picks:
                nxt[i] += rolls_tuple[i]
            value = best_average_future(future_rounds, tuple(nxt))
            key = (value, tuple(ties[i] for i in picks))
            if best_key is None or key > best_key:
                best_key = key; best = picks
        return best

    return choose

def _simulate_one_four(
    rounds, fit_stats, raw_start, normal_ranges,
    range_plan, selection_cfg, effective_lookup, utility_lookup,
    static_effective, total_weight, coordinates=None,
    forced_first_combo=None, extreme: str | None = None, trace=None, policy=None,
):
    """Specialized allocation-free hot path for exactly four Fit stats."""
    s0, s1, s2, s3 = fit_stats
    r0 = int(raw_start[s0]); r1 = int(raw_start[s1])
    r2 = int(raw_start[s2]); r3 = int(raw_start[s3])
    c0 = selection_cfg[s0]; c1 = selection_cfg[s1]
    c2 = selection_cfg[s2]; c3 = selection_cfg[s3]
    e0 = effective_lookup[s0]; e1 = effective_lookup[s1]
    e2 = effective_lookup[s2]; e3 = effective_lookup[s3]
    u0 = utility_lookup[s0]; u1 = utility_lookup[s1]
    u2 = utility_lookup[s2]; u3 = utility_lookup[s3]
    w0, tie0 = c0; w1, tie1 = c1
    w2, tie2 = c2; w3, tie3 = c3

    forced = set(forced_first_combo) if forced_first_combo is not None else None
    use_min = extreme == "min"
    use_max = extreme == "max"
    if policy is None:
        policy = _make_final_fit_policy(
            fit_stats, normal_ranges, selection_cfg, utility_lookup, total_weight
        )

    for rd in range(rounds):
        a0, a1, a2, a3 = range_plan[rd]
        lo0, hi0 = a0; lo1, hi1 = a1; lo2, hi2 = a2; lo3, hi3 = a3
        if use_min:
            q0, q1, q2, q3 = lo0, lo1, lo2, lo3
        elif use_max:
            q0, q1, q2, q3 = hi0, hi1, hi2, hi3
        else:
            base = rd * 4
            cnt = hi0 - lo0 + 1; q0 = lo0 + min(cnt - 1, int(coordinates[base] * cnt))
            cnt = hi1 - lo1 + 1; q1 = lo1 + min(cnt - 1, int(coordinates[base + 1] * cnt))
            cnt = hi2 - lo2 + 1; q2 = lo2 + min(cnt - 1, int(coordinates[base + 2] * cnt))
            cnt = hi3 - lo3 + 1; q3 = lo3 + min(cnt - 1, int(coordinates[base + 3] * cnt))

        if forced is not None and rd == 0:
            picks = tuple(s for s in fit_stats if s in forced)
            if s0 in forced: r0 += q0
            if s1 in forced: r1 += q1
            if s2 in forced: r2 += q2
            if s3 in forced: r3 += q3
            if trace is not None:
                trace.append({"round": rd + 1, "rolls": {s0:q0,s1:q1,s2:q2,s3:q3}, "picks": list(picks)})
            continue

        raw_tuple = (r0, r1, r2, r3)
        roll_tuple = (q0, q1, q2, q3)
        picked_idx = policy(rd, raw_tuple, roll_tuple, rounds)
        drop = next(i for i in range(4) if i not in picked_idx)

        if drop != 0: r0 += q0
        if drop != 1: r1 += q1
        if drop != 2: r2 += q2
        if drop != 3: r3 += q3
        if trace is not None:
            picks = [fit_stats[i] for i in range(4) if i != drop]
            trace.append({"round": rd + 1, "rolls": {s0:q0,s1:q1,s2:q2,s3:q3}, "picks": picks})

    v0 = e0[r0]; v1 = e1[r1]; v2 = e2[r2]; v3 = e3[r3]
    effective = dict(static_effective)
    effective[s0] = v0; effective[s1] = v1
    effective[s2] = v2; effective[s3] = v3
    weighted_sum = w0 * u0[r0] + w1 * u1[r1] + w2 * u2[r2] + w3 * u3[r3]
    score = max(0.0, weighted_sum / total_weight) if total_weight else 0.0
    return score * 100.0, effective

def _simulate_one(
    role, rounds, fit_stats, raw_start, normal_ranges,
    range_plan, selection_cfg, effective_lookup, utility_lookup,
    static_effective, total_weight, coordinates=None,
    forced_first_combo=None, extreme: str | None = None, trace=None, policy=None,
):
    if len(fit_stats) == 4:
        return _simulate_one_four(
            rounds, fit_stats, raw_start, normal_ranges,
            range_plan, selection_cfg, effective_lookup, utility_lookup,
            static_effective, total_weight, coordinates,
            forced_first_combo, extreme, trace, policy,
        )

    raw = dict(raw_start)
    fit_count = len(fit_stats)
    no_choice = fit_count <= 3 and forced_first_combo is None
    if fit_count > 3 and policy is None:
        policy = _make_final_fit_policy(
            fit_stats, normal_ranges, selection_cfg, utility_lookup, total_weight
        )

    for rd in range(rounds):
        rolls = {}
        base_dim = rd * max(1, fit_count)
        for j, stat in enumerate(fit_stats):
            lo, hi = range_plan[rd][j]
            if extreme == "min":
                roll = lo
            elif extreme == "max":
                roll = hi
            else:
                count = hi - lo + 1
                u = coordinates[base_dim + j]
                roll = lo + min(count - 1, int(u * count))
            rolls[stat] = int(roll)

        if no_choice:
            combo = fit_stats
        else:
            if forced_first_combo is not None and rd == 0:
                combo = tuple(s for s in forced_first_combo if s in fit_stats)
            else:
                raw_tuple = tuple(int(raw[s]) for s in fit_stats)
                rolls_tuple = tuple(int(rolls[s]) for s in fit_stats)
                picked_idx = policy(rd, raw_tuple, rolls_tuple, rounds)
                combo = tuple(fit_stats[i] for i in picked_idx)
        if trace is not None:
            trace.append({"round": rd + 1, "rolls": dict(rolls), "picks": list(combo)})
        for stat in combo:
            raw[stat] += rolls[stat]

    effective = dict(static_effective)
    weighted_sum = 0.0
    for stat in fit_stats:
        raw_i = int(raw[stat])
        eff = effective_lookup[stat][raw_i]
        effective[stat] = eff
        weighted_sum += float(role["stats"][stat].get("weight", 1.0)) * utility_lookup[stat][raw_i]

    score = max(0.0, weighted_sum / total_weight) if total_weight else 0.0
    return score * 100.0, effective

def _role_fingerprint(role: dict, fit_stats: tuple[str, ...]) -> tuple:
    return (
        role.get("name"),
        tuple((stat, repr(role.get("stats", {}).get(stat, {}))) for stat in fit_stats),
    )


def _cache_key(bro, role, rounds, round_ranges, forced_first_combo, samples, include_trace):
    fit_stats = _fit_stats(role)
    forced = tuple(forced_first_combo or ())
    return (
        bro_fingerprint(bro), _role_fingerprint(role, fit_stats), int(rounds),
        _round_ranges_key(round_ranges), forced, int(samples), bool(include_trace),
    )

def _project_fit_trajectory_fixed(
    bro: Brother,
    role: dict,
    *,
    rounds: int | None = None,
    first_round_ranges: dict[str, tuple[int, int]] | None = None,
    round_ranges: list[dict[str, tuple[int, int]]] | tuple[dict[str, tuple[int, int]], ...] | None = None,
    forced_first_combo: tuple[str, ...] | None = None,
    samples: int = 512,
    include_trace: bool = False,
    _miss_reason_hint: str | None = None,
) -> dict:
    if rounds is None:
        rounds = development_rounds_to_11(bro)
    rounds = max(0, int(rounds))
    samples = max(1, int(samples))
    normalized_ranges = _normalize_round_ranges(rounds, first_round_ranges, round_ranges)
    key = _cache_key(bro, role, rounds, normalized_ranges, forced_first_combo, samples, include_trace)
    cached = _TRAJECTORY_CACHE.get(key)
    if cached is not None:
        PROFILE["trajectory_cache_hits"] += 1
        return cached

    PROFILE["trajectory_cache_misses"] += 1
    miss_reason = _miss_reason_hint
    if miss_reason is None:
        same_brother_or_role = any(
            cached_key[0] == key[0] or cached_key[1] == key[1]
            for cached_key in _TRAJECTORY_CACHE
        )
        miss_reason = "fingerprint_change" if same_brother_or_role else "missing_entry"
    reasons = PROFILE["trajectory_cache_miss_reasons"]
    reasons[miss_reason if miss_reason in reasons else "other_fallback"] += 1
    _trajectory_started = time.perf_counter()
    ctx = _projection_context(bro, role, rounds, normalized_ranges)
    (fit_stats, effects, raw_start, normal_ranges, range_plan, selection_cfg,
     effective_lookup, utility_lookup, static_effective, total_weight) = ctx
    dimensions = max(1, rounds * max(1, len(fit_stats)))
    coordinate_rows = _sample_coordinates(samples, dimensions)
    # The final-Fit policy contains memoized lookahead states. It depends only
    # on this projection context, not on the sampled scenario, so build it once
    # and share it across every deterministic sampled path. Rebuilding it per path was
    # functionally identical but discarded the cache hundreds of times.
    policy = _make_final_fit_policy(
        fit_stats, normal_ranges, selection_cfg, utility_lookup, total_weight
    ) if len(fit_stats) > 3 else None

    outcomes = []
    sums = {s: 0.0 for s in STATS}
    mins = {s: float("inf") for s in STATS}
    maxs = {s: float("-inf") for s in STATS}
    selected_trace = [] if include_trace else None

    for scenario, coordinates in enumerate(coordinate_rows):
        scenario_trace = selected_trace if include_trace and scenario == 0 else None
        fit, values = _simulate_one(
            role, rounds, fit_stats, raw_start, normal_ranges,
            range_plan, selection_cfg, effective_lookup, utility_lookup,
            static_effective, total_weight, coordinates,
            forced_first_combo, trace=scenario_trace, policy=policy,
        )
        outcomes.append(fit)
        for s in STATS:
            v = float(values[s])
            sums[s] += v
            if v < mins[s]: mins[s] = v
            if v > maxs[s]: maxs[s] = v

    dummy = (0.0,) * dimensions
    min_fit, min_values = _simulate_one(
        role, rounds, fit_stats, raw_start, normal_ranges,
        range_plan, selection_cfg, effective_lookup, utility_lookup,
        static_effective, total_weight, dummy, forced_first_combo, "min", policy=policy
    )
    max_fit, max_values = _simulate_one(
        role, rounds, fit_stats, raw_start, normal_ranges,
        range_plan, selection_cfg, effective_lookup, utility_lookup,
        static_effective, total_weight, dummy, forced_first_combo, "max", policy=policy
    )
    outcomes.sort()
    n = len(outcomes)
    expected = sum(outcomes) / n
    feasible = 100.0 * sum(v >= 100.0 - 1e-12 for v in outcomes) / n
    q05 = outcomes[min(n-1, int(0.05 * (n-1)))]
    q95 = outcomes[min(n-1, int(0.95 * (n-1)))]

    for s in STATS:
        mins[s] = min(mins[s], float(min_values[s]), float(max_values[s]))
        maxs[s] = max(maxs[s], float(min_values[s]), float(max_values[s]))

    result = {
        "expected_pct": round(expected, 1),
        "full_min_pct": round(min(min(outcomes), min_fit, max_fit), 1),
        "full_max_pct": round(max(max(outcomes), min_fit, max_fit), 1),
        "likely_min_pct": round(q05, 1),
        "likely_max_pct": round(q95, 1),
        "feasibility_pct": round(feasible, 1),
        "state_count": n,
        "sample_count": n,
        "pruned": False,
        "method": "deterministic_low_discrepancy",
        # Internal calibration data. Kept on the cached trajectory so validation
        # can rank the serialized real future against the *same* blind sample
        # distribution without running or reimplementing the simulator again.
        # Callers do not serialize this field into normal analysis/debug output.
        "_outcomes_pct": tuple(outcomes),
        "fit_stats": list(fit_stats),
        "stat_ranges": {
            s: {"min": round(mins[s], 1), "ev": round(sums[s] / n, 1), "max": round(maxs[s], 1)}
            for s in STATS
        },
    }
    if include_trace:
        result["trace"] = selected_trace or []
    if len(_TRAJECTORY_CACHE) >= _TRAJECTORY_CACHE_MAX:
        _TRAJECTORY_CACHE.clear()
    _TRAJECTORY_CACHE[key] = result
    PROFILE["trajectory_s"] += time.perf_counter() - _trajectory_started
    return result

def _needs_refinement(result: dict) -> bool:
    expected = float(result.get("expected_pct", 0.0))
    likely_min = float(result.get("likely_min_pct", expected))
    likely_max = float(result.get("likely_max_pct", expected))
    full_max = float(result.get("full_max_pct", expected))
    feasible = float(result.get("feasibility_pct", 0.0))
    return (
        95.0 <= expected <= 105.0
        or likely_min <= 100.0 <= likely_max
        or 0.0 < feasible < 100.0
        or (expected >= 85.0 and full_max >= 100.0)
    )


def project_fit_trajectory(
    bro: Brother,
    role: dict,
    *,
    rounds: int | None = None,
    first_round_ranges: dict[str, tuple[int, int]] | None = None,
    round_ranges: list[dict[str, tuple[int, int]]] | tuple[dict[str, tuple[int, int]], ...] | None = None,
    forced_first_combo: tuple[str, ...] | None = None,
    samples: int | None = None,
    include_trace: bool = False,
) -> dict:
    if rounds is None:
        rounds = development_rounds_to_11(bro)
    if samples is not None:
        result = _project_fit_trajectory_fixed(
            bro, role, rounds=rounds, first_round_ranges=first_round_ranges,
            round_ranges=round_ranges, forced_first_combo=forced_first_combo,
            samples=max(1, int(samples)), include_trace=include_trace,
        )
        result["adaptive_refined"] = False
        result["initial_sample_count"] = int(samples)
        return result

    initial = 512
    result = _project_fit_trajectory_fixed(
        bro, role, rounds=rounds, first_round_ranges=first_round_ranges,
        round_ranges=round_ranges, forced_first_combo=forced_first_combo,
        samples=initial, include_trace=include_trace,
    )
    if _needs_refinement(result):
        PROFILE["trajectory_adaptive_refinements"] += 1
        refined = _project_fit_trajectory_fixed(
            bro, role, rounds=rounds, first_round_ranges=first_round_ranges,
            round_ranges=round_ranges, forced_first_combo=forced_first_combo,
            samples=2048, include_trace=include_trace, _miss_reason_hint="refinement",
        )
        refined["adaptive_refined"] = True
        refined["initial_sample_count"] = initial
        return refined
    result["adaptive_refined"] = False
    result["initial_sample_count"] = initial
    return result

def compare_fit_trajectories(
    bro_primary: Brother,
    bro_alternative: Brother,
    role: dict,
    *,
    rounds: int | None = None,
    samples: int = 2048,
) -> dict:
    if rounds is None:
        rounds = development_rounds_to_11(bro_primary)
    rounds = max(0, int(rounds))
    fit_stats = _fit_stats(role)
    dimensions = max(1, rounds * max(1, len(fit_stats)))
    coordinate_rows = _sample_coordinates(max(1, int(samples)), dimensions)

    pctx = _projection_context(bro_primary, role, rounds, ())
    actx = _projection_context(bro_alternative, role, rounds, ())
    ppolicy = _make_final_fit_policy(
        pctx[0], pctx[3], pctx[5], pctx[7], pctx[9]
    ) if len(pctx[0]) > 3 else None
    apolicy = _make_final_fit_policy(
        actx[0], actx[3], actx[5], actx[7], actx[9]
    ) if len(actx[0]) > 3 else None

    wins = ties = losses = 0
    deltas = []
    n = len(coordinate_rows)
    for coordinates in coordinate_rows:
        primary_fit, _ = _simulate_one(
            role, rounds, pctx[0], pctx[2], pctx[3], pctx[4], pctx[5], pctx[6], pctx[7], pctx[8], pctx[9], coordinates, policy=ppolicy
        )
        alternative_fit, _ = _simulate_one(
            role, rounds, actx[0], actx[2], actx[3], actx[4], actx[5], actx[6], actx[7], actx[8], actx[9], coordinates, policy=apolicy
        )
        delta = alternative_fit - primary_fit
        deltas.append(delta)
        if delta > 1e-12: wins += 1
        elif delta < -1e-12: losses += 1
        else: ties += 1

    winning_deltas = [d for d in deltas if d > 1e-12]
    losing_deltas = [-d for d in deltas if d < -1e-12]
    return {
        "alternative_beats_primary_pct": round(100.0 * wins / n, 1),
        "tie_pct": round(100.0 * ties / n, 1),
        "primary_beats_alternative_pct": round(100.0 * losses / n, 1),
        "mean_delta_pct": round(sum(deltas) / n, 2),
        "avg_upside_when_wins_pct": round(sum(winning_deltas) / len(winning_deltas), 2) if winning_deltas else 0.0,
        "max_upside_pct": round(max(winning_deltas), 2) if winning_deltas else 0.0,
        "avg_downside_when_loses_pct": round(sum(losing_deltas) / len(losing_deltas), 2) if losing_deltas else 0.0,
        "max_downside_pct": round(max(losing_deltas), 2) if losing_deltas else 0.0,
        "sample_count": n,
        "method": "paired_deterministic_low_discrepancy",
    }


def project_seeded_fit_trajectory(bro: Brother, role: dict) -> dict | None:
    """Replay serialized future rolls through the *same* public Fit engine.

    Ground truth has no parallel planner. Each known future roll is encoded as a
    degenerate per-round range ``(X, X)`` and sent through
    :func:`project_fit_trajectory`, including the same specialized hot paths and
    pick-selection code used by blind projection.
    """
    rounds = max(0, development_rounds_to_11(bro))
    sequences = getattr(bro, "FutureRolls", {}) or {}
    if any(len(sequences.get(stat, ())) < rounds for stat in STATS):
        return None

    fit_stats = _fit_stats(role)
    exact_round_ranges = [
        {stat: (int(sequences[stat][rd]), int(sequences[stat][rd])) for stat in fit_stats}
        for rd in range(rounds)
    ]
    trajectory = project_fit_trajectory(
        bro, role, rounds=rounds, round_ranges=exact_round_ranges,
        samples=1, include_trace=True,
    )
    return {
        "fit_pct": trajectory["expected_pct"],
        "rounds": rounds,
        "fit_stats": list(fit_stats),
        "final_stats": {
            s: round(float(trajectory["stat_ranges"][s]["ev"]), 1) for s in STATS
        },
        "choices": trajectory.get("trace", []),
        "method": "serialized_future_rolls_via_shared_fit_engine",
    }

