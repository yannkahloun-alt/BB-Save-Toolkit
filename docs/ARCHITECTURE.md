# Architecture — v3.46 Fit-only model

## Design rule

There is one central concept: **level-11 Fit to a configured archetype**. Secondary systems must consume that model rather than recreate their own scoring formula.

## Archetype schema

Each evaluated stat contains:

- `target`: the level-11 reference corresponding to utility 1.0;
- `weight`: relative contribution to archetype Fit;
- `baseline`: optional lower reference used to shape the continuous utility curve.

The loader derives `projected_curve` from `baseline -> 0.55`, `target -> 1.0`, with a small capped upside above target. Stats absent from the JSON do not contribute to Fit.

Perk metadata is data-only for now. Structural projection perks such as Colossus may create alternate paths because they change effective stats.

## Stars

Stars have no direct Fit value. They only alter future vanilla roll ranges:

`stars -> roll ranges -> simulated level-ups -> final stats -> Fit`.

Therefore two brothers with identical final projected stats receive identical Fit regardless of how many stars produced those stats.

## Trajectory engine

`projection/trajectory.py` is the source of truth for future development.

For each simulated development round:

1. produce legal rolls from star-adjusted ranges;
2. evaluate each legal pick combination by the expected final Fit it enables at level 11;
3. choose at most three attributes using that final-Fit lookahead policy;
4. apply permanent perk transforms correctly on aggregated raw stats;
5. continue to level 11;
6. score the resulting profile against the archetype Fit curves.

The lookahead uses only the configured roll ranges for unknown future levels. Hidden serialized future rolls are validation-only and never influence normal pick decisions.

The standard distribution uses 512 deterministic low-discrepancy trajectories. Ambiguous cases are refined to 2048. Explicit all-MIN/all-MAX paths anchor the full range.

Outputs:

- Expected Fit;
- P5/P95 Likely Fit range;
- Full Fit min/max;
- `P(Fit >= 100%)` Fit Feasibility;
- projected stat ranges for Fit stats.

## Level-Up Advisor

The Advisor has no separate weighted scoring formula.

It evaluates all legal 3-stat combinations from the current observed level-up. For a known `+4` roll, the current round is passed to the trajectory engine as `4-4`; later rounds use normal ranges. Primary and Runner-up are then projected through the same Fit engine.

A Runner-up is labelled `GAMBLE` when its Expected Fit is lower than Primary but, under paired identical future-roll scenarios, it sometimes finishes with higher Fit. The report exposes that probability rather than inventing a gamble score.

## Strategic Classification

Classification is Fit-only:

- **Invest**: Expected Fit >= configured Invest threshold.
- **Use**: Expected Fit >= configured Use threshold.
- **Fodder**: Expected Fit is below Use, but the Full Fit ceiling still reaches the Use threshold.
- **Trash**: even the Full Fit ceiling remains below the Use threshold.

Best-role ordering uses Expected Fit first, then Fit Feasibility, then the Likely Fit floor. Structural path selection first maximizes strategic category, prefers fewer hypothetical structural perks, then uses the same Fit dimensions.

## Removed legacy concepts

v3.9 deliberately deletes the v2-era analytical branches that no longer feed the v3 model:

- Development Burden;
- Patch / Support / Core pick accounting;
- Current Readiness;
- projected/current gates;
- viability `min` and `ready` archetype fields;
- fixed deterministic `_role_alloc` development plans;
- exact Burden uncertainty / feasibility;
- legacy `bbtool.engine` compatibility facade;
- Gifted-specific projection analysis (removed earlier in v3.4).

Historical rationale remains in `CHANGELOG.md`; these concepts are not active runtime inputs or outputs.

## Performance invariants

Optimizations must not alter Fit semantics. The current engine caches brother-level projection context and role-level trajectory context, shares low-discrepancy dimensions, specializes the common 4-Fit-stat / 3-pick loop, and uses adaptive 512 -> 2048 sampling only where needed.

If future archetypes introduce 5+ active Fit stats, profile the generic top-3 selection path and consider a mathematically equivalent specialization rather than constraining archetype design for performance.


## Projection ground truth

The save serializes the remaining level-up rolls for every attribute through level 11. The parser exposes them as `FutureRolls`. They are deliberately quarantined from normal analysis: probabilistic Fit, classification, and Level-Up Advisor never read them.

There is **no separate ground-truth planner**. `project_seeded_fit_trajectory()` converts each serialized roll into a per-round degenerate range (`4 -> 4-4`) and calls the public `project_fit_trajectory()` engine with `samples=1`. The blind projection, Advisor-compatible exact-round overrides, and ground truth therefore share the same round-range compilation, pick selection, perk transforms, specialized 4-stat hot path, and final Fit scoring. Only the range inputs differ.

This is an architectural proof invariant: any future change to the trajectory algorithm automatically applies to ground-truth validation because there is only one simulation implementation.
