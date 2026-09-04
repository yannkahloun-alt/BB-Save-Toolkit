
from __future__ import annotations

import itertools
from dataclasses import replace

from .build_identity import build_definition_hash, build_identity
from .models import STATS
from .projection import gain_range, development_rounds_to_11
from .projection.trajectory import project_fit_trajectory, compare_fit_trajectories
from .classification import role_sort_key


def _roll_quality(bro, stat: str, roll: int) -> float:
    lo, hi = gain_range(stat, getattr(bro, stat + "Stars"))
    if hi <= lo:
        return 1.0
    return max(0.0, min(1.0, (float(roll) - lo) / (hi - lo)))



def _roll_band(bro, stat: str, roll: int) -> dict:
    lo, hi = gain_range(stat, getattr(bro, stat + "Stars"))
    avg = (lo + hi) / 2.0
    if roll <= lo:
        label = "MIN"
    elif roll >= hi:
        label = "MAX"
    elif roll < avg:
        label = "LOW"
    elif roll > avg:
        label = "HIGH"
    else:
        label = "AVG"
    return {
        "Roll": int(roll),
        "Min": int(lo),
        "Max": int(hi),
        "Average": round(avg, 1),
        "Label": label,
        "Quality": round(_roll_quality(bro, stat, roll), 3),
    }


def _skipped_important_notes(
    anchor_role: dict,
    best: dict,
    all_rolls: dict[str, dict],
) -> list[dict]:
    """
    Explain surprising omissions: role-relevant/Fit stats that were available
    but not selected. Keep this deterministic and descriptive, not prescriptive.
    """
    selected = set(best["Stats"])
    role_stats = anchor_role.get("stats", {})
    notes = []

    for stat, cfg in role_stats.items():
        if stat in selected or stat not in all_rolls:
            continue

        # Only surface stats the archetype explicitly treats as meaningful.
        weight = float(cfg.get("weight", 0.0) or 0.0)
        is_core = bool(cfg.get("fit"))
        if not is_core and weight <= 0:
            continue

        meta = all_rolls[stat]
        reason_bits = []
        if is_core:
            reason_bits.append("Fit stat")
        elif weight > 0:
            reason_bits.append(f"role weight {weight:g}")

        reason_bits.append(
            f"current +{meta['Roll']} is {meta['Label']} "
            f"for its +{meta['Min']}–+{meta['Max']} range"
        )

        notes.append({
            "Stat": stat,
            "Weight": weight,
            "Core": is_core,
            "Roll": meta,
            "Reason": " · ".join(reason_bits),
        })

    notes.sort(key=lambda row: (not row["Core"], -row["Weight"], row["Stat"]))
    return notes


def _valid_assigned_role(roles: list[dict], assigned_build: dict | None):
    resolved = (assigned_build or {}).get("assignment", assigned_build or {})
    identity = resolved.get("build_identity")
    role = next((item for item in roles if build_identity(item) == identity), None)
    if (
        resolved.get("status") != "current" or role is None
        or resolved.get("assigned_definition_hash") != build_definition_hash(role)
        or resolved.get("current_definition_hash") != build_definition_hash(role)
    ):
        return None, resolved
    return role, resolved


def advise_levelup(
    bro, roles: list[dict], baseline_rows: list[dict], assigned_build: dict | None = None,
):
    """Recommend the current 3-pick line by expected final level-11 Fit.

    Current picks are restricted to positively weighted Fit stats for the
    anchor role. If fewer than three such stats are available, the remaining
    slots are explicitly treated as Fit-neutral free picks. Each resulting
    state is projected to level 11 by the same blind trajectory engine used
    everywhere else. Hidden serialized future rolls are never consulted.
    """
    rolls = getattr(bro, "CurrentRolls", {}) or {}
    if int(getattr(bro, "LevelPoints", 0)) <= 0 or len(rolls) < 3:
        return None

    baseline_best = sorted(baseline_rows, key=role_sort_key, reverse=True)[0]
    role_by_name = {r["name"]: r for r in roles}
    best_fit_role = role_by_name[baseline_best["Role"]]
    assigned_role, assignment = _valid_assigned_role(roles, assigned_build)
    anchor_role = assigned_role or best_fit_role
    row_by_name = {row["Role"]: row for row in baseline_rows}
    anchor_before = row_by_name[anchor_role["name"]]
    ranked = []
    role_stats = anchor_role.get("stats", {})
    eligible_stats = tuple(
        stat for stat in STATS
        if stat in rolls
        and bool(role_stats.get(stat, {}).get("fit"))
        and float(role_stats.get(stat, {}).get("weight", 0.0) or 0.0) > 0.0
    )
    excluded_stats = {}
    for stat in STATS:
        if stat not in rolls or stat in eligible_stats:
            continue
        cfg = role_stats.get(stat, {})
        weight = float(cfg.get("weight", 0.0) or 0.0)
        if weight <= 0.0:
            excluded_stats[stat] = f"role weight {weight:g}"
        else:
            excluded_stats[stat] = "not a Fit stat"

    free_pick_mode = len(eligible_stats) < 3
    free_pick_candidates = tuple(
        stat for stat in STATS if stat in rolls and stat not in eligible_stats
    ) if free_pick_mode else ()
    free_slots = max(0, 3 - len(eligible_stats))
    if free_pick_mode:
        candidate_combos = (
            tuple(eligible_stats) + tuple(free_stats)
            for free_stats in itertools.combinations(free_pick_candidates, free_slots)
        )
    else:
        candidate_combos = itertools.combinations(eligible_stats, 3)

    # Fit-neutral free picks are equivalent. Project one canonical
    # representative per Fit decision rather than allowing roll quality in a
    # neutral stat to influence the role recommendation.
    groups = {}
    legal_combo_count = 0
    for combo in candidate_combos:
        legal_combo_count += 1
        fit_key = tuple(stat for stat in eligible_stats if stat in combo)
        groups.setdefault(fit_key, []).append(combo)

    for fit_key, equivalent_combos in groups.items():
        combo = equivalent_combos[0]
        changes = {stat: int(rolls[stat]) for stat in combo}
        sim_kwargs = {
            stat: getattr(bro, stat) + changes.get(stat, 0)
            for stat in STATS
        }
        sim = replace(
            bro,
            **sim_kwargs,
            LevelPoints=max(0, int(bro.LevelPoints) - 1),
            CurrentRolls={},
        )
        trajectory = project_fit_trajectory(
            sim, anchor_role, rounds=development_rounds_to_11(sim),
        )
        ranked.append((
            float(trajectory["expected_pct"]), combo, changes, sim, trajectory,
            fit_key, equivalent_combos,
        ))

    ranked.sort(
        key=lambda item: (
            item[0],
            tuple(-i for i, s in enumerate(STATS) if s in item[1]),
        ),
        reverse=True,
    )
    if not ranked:
        return None

    # Prefer a runner-up with a genuinely different Fit-relevant decision.
    primary_entry = ranked[0]
    primary_key = primary_entry[5]
    runner_entry = next(
        (entry for entry in ranked[1:] if entry[5] != primary_key),
        ranked[1] if len(ranked) > 1 else None,
    )

    def consequence(sim, role, before):
        trajectory = project_fit_trajectory(
            sim, role, rounds=development_rounds_to_11(sim),
        )
        return {
            "BuildIdentity": build_identity(role),
            "Role": role["name"],
            "FitBeforePct": before["ProjectedFitPct"],
            "FitAfterPct": trajectory["expected_pct"],
            "FitDeltaPct": round(
                trajectory["expected_pct"] - before["ProjectedFitPct"], 1
            ),
            "FitMinAfterPct": trajectory["full_min_pct"],
            "FitMaxAfterPct": trajectory["full_max_pct"],
            "FitLikelyMinAfterPct": trajectory["likely_min_pct"],
            "FitLikelyMaxAfterPct": trajectory["likely_max_pct"],
            "FitFeasibilityBeforePct": before.get("FitFeasibilityPct", 0.0),
            "FitFeasibilityAfterPct": trajectory["feasibility_pct"],
        }

    def build_candidate(entry):
        if entry is None:
            return None
        _, combo, changes, sim, trajectory, _fit_key, _equivalent = entry
        qualities = {
            stat: round(_roll_quality(bro, stat, changes[stat]), 3)
            for stat in combo
        }
        consequences = {
            "BestFit": consequence(sim, best_fit_role, baseline_best),
            "AssignedBuild": (
                consequence(sim, assigned_role, row_by_name[assigned_role["name"]])
                if assigned_role is not None else None
            ),
        }
        return {
            "_SimBro": sim,
            "Stats": list(combo),
            "Rolls": changes,
            "RollQuality": qualities,
            "RoleBefore": anchor_role["name"],
            "RoleAfter": anchor_role["name"],
            "AnchorFitBeforePct": anchor_before["ProjectedFitPct"],
            "AnchorFitAfterPct": trajectory["expected_pct"],
            "FitMinAfterPct": trajectory["full_min_pct"],
            "FitMaxAfterPct": trajectory["full_max_pct"],
            "FitLikelyMinAfterPct": trajectory["likely_min_pct"],
            "FitLikelyMaxAfterPct": trajectory["likely_max_pct"],
            "FitFeasibilityBeforePct": anchor_before.get("FitFeasibilityPct", 0.0),
            "FitFeasibilityAfterPct": trajectory["feasibility_pct"],
            "FitDeltaPct": round(trajectory["expected_pct"] - anchor_before["ProjectedFitPct"], 1),
            "Consequences": consequences,
        }

    best = build_candidate(primary_entry)
    alternative = build_candidate(runner_entry)

    gamble = None
    if alternative is not None:
        alt_expected = float(alternative["AnchorFitAfterPct"])
        best_expected = float(best["AnchorFitAfterPct"])
        potential_gamble = alt_expected < best_expected - 1e-9
        if potential_gamble:
            comparison = compare_fit_trajectories(
                best["_SimBro"], alternative["_SimBro"], anchor_role,
                rounds=development_rounds_to_11(best["_SimBro"]), samples=512,
            )
            # Small win probabilities are exactly where sample resolution matters.
            # Refine any detected gamble (or very close expected-value contest)
            # before exposing a percentage to the user.
            if comparison["alternative_beats_primary_pct"] > 0.0 or abs(best_expected - alt_expected) <= 1.0:
                comparison = compare_fit_trajectories(
                    best["_SimBro"], alternative["_SimBro"], anchor_role,
                    rounds=development_rounds_to_11(best["_SimBro"]), samples=2048,
                )
        else:
            comparison = {
                "alternative_beats_primary_pct": 0.0, "tie_pct": 0.0,
                "primary_beats_alternative_pct": 0.0, "mean_delta_pct": round(alt_expected-best_expected, 2),
                "avg_upside_when_wins_pct": 0.0, "max_upside_pct": 0.0,
                "avg_downside_when_loses_pct": 0.0, "max_downside_pct": 0.0,
                "sample_count": 0,
            }
        is_gamble = (
            potential_gamble and comparison["alternative_beats_primary_pct"] > 0.0
        )
        gamble = {
            "IsGamble": is_gamble,
            "ChanceToBeatPrimaryPct": comparison["alternative_beats_primary_pct"],
            "TiePct": comparison["tie_pct"],
            "PrimaryWinsPct": comparison["primary_beats_alternative_pct"],
            "MeanDeltaPct": comparison["mean_delta_pct"],
            "AvgUpsideWhenWinsPct": comparison["avg_upside_when_wins_pct"],
            "MaxUpsidePct": comparison["max_upside_pct"],
            "AvgDownsideWhenLosesPct": comparison["avg_downside_when_loses_pct"],
            "MaxDownsidePct": comparison["max_downside_pct"],
            "Samples": comparison["sample_count"],
        }
        alternative["Gamble"] = gamble

    best.pop("_SimBro", None)
    if alternative is not None:
        alternative.pop("_SimBro", None)

    reasons = {}
    for stat in best["Stats"]:
        cfg = role_stats.get(stat, {})
        if cfg.get("fit"):
            head = f'Fit stat · weight {float(cfg.get("weight", 1.0)):g}'
        elif stat in role_stats:
            head = "Fit-neutral role stat"
        else:
            head = "Fit-neutral"
        band = _roll_band(bro, stat, best["Rolls"][stat])["Label"]
        reasons[stat] = f'{head} · current +{best["Rolls"][stat]} is {band}'

    all_rolls = {
        stat: _roll_band(bro, stat, int(roll))
        for stat, roll in rolls.items()
    }
    skipped_important = _skipped_important_notes(
        anchor_role, best, all_rolls
    )

    return {
        "AnchorRole": anchor_role["name"],
        "Anchor": {
            "Source": "AssignedBuild" if assigned_role is not None else "BestFitFallback",
            "BuildIdentity": build_identity(anchor_role),
            "Role": anchor_role["name"],
            "AssignmentStatus": assignment.get("status", "unassigned"),
        },
        "AssignedBuild": {
            "Status": assignment.get("status", "unassigned"),
            "BuildIdentity": assignment.get("build_identity"),
            "AssignedDefinitionHash": assignment.get("assigned_definition_hash"),
            "CurrentDefinitionHash": assignment.get("current_definition_hash"),
            "ValidAdvisorAnchor": assigned_role is not None,
        },
        "BestFit": {
            "BuildIdentity": build_identity(best_fit_role),
            "Role": best_fit_role["name"],
            "ProjectedFitPct": baseline_best["ProjectedFitPct"],
        },
        "Primary": best,
        "RunnerUp": alternative,
        "ConditionalBranch": None,
        "Recommended": best,
        "Alternative": alternative,
        "PickReasons": reasons,
        "AllRolls": all_rolls,
        "SkippedImportant": skipped_important,
        "AdvisorEligibleStats": list(eligible_stats),
        "AdvisorExcludedStats": excluded_stats,
        "FreePickMode": free_pick_mode,
        "FreePickCandidates": list(free_pick_candidates),
        "FreePickStats": [stat for stat in best["Stats"] if stat not in eligible_stats],
        "CombinationsEvaluated": legal_combo_count,
        "DistinctFitDecisionsEvaluated": 2 if alternative else 1,
        "Method": "Fit-only advisor: score current 3-pick combinations drawn from positively weighted Fit stats using the shared blind trajectory engine; when fewer than three are available, remaining slots are explicit Fit-neutral free picks; paired deterministic scenarios are used only for runner-up gamble diagnostics",
    }

