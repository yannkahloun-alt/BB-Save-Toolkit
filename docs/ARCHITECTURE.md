# Architecture — current repository baseline

## Central analytical model

The toolkit has one primary gameplay concept: **level-11 Fit to a configured archetype**. Secondary systems consume that model instead of inventing parallel scoring systems.

Core flow:

```text
save bytes
  -> parser / current brother facts
  -> source-derived references
  -> effective stats / permanent transforms
  -> trajectory projection per archetype
  -> Fit / ranges / feasibility
  -> classification + Level-Up Advisor
  -> JSON / HTML outputs
```

## Module boundaries

### `bbtool/save_parser.py`

Read-only binary save parser. It extracts roster/recruit facts, serialized IDs, traits, injuries, perks, stars, current rolls, and quarantined future-roll validation data.

`BrotherID = human:<HumanOffset>` is save-local. Names are display-only.

### `references/`

Contains tracked seed/catalog data plus generators for runtime vanilla references. Generated references are derived from source scripts/save-hash semantics and are disposable caches.

Important generated caches include enriched dictionaries, backgrounds, trait effects, permanent-injury effects, and perk audit data.

### `bbtool/projection/`

Pure computation layer where practical.

- `context.py` compiles reusable brother projection context.
- `perks.py` keeps natural projection effects (traits and permanent injuries)
  separate from perk-modified effective combat stats.
- `trajectory.py` simulates legal future 3-stat level-up decisions and is the source of truth for development trajectories.
- `scoring.py` evaluates continuous archetype Fit, including optional Fit-only ceilings.
- `planner.py` assembles role projection outputs.

The normal projection never uses hidden serialized FutureRolls to make decisions.

### `bbtool/levelup_advisor.py`

Evaluates legal current 3-stat choices using the same trajectory/Fit model. Known current rolls are injected as exact ranges; later levels remain probabilistic.

### `bbtool/classification.py` and `bbtool/app/analysis.py`

Classification derives Invest / Use / Fodder / Trash from Fit outputs and configured thresholds. Analysis orchestrates brother × archetype rows, advisor output, and summaries.

### `bbtool/incremental/`

Dependency-aware reuse layer. It must remain above the computation engines rather than embedding persistence in trajectory/scoring code.

Current artifacts can be cached independently where dependencies permit:

```text
role projection
advisor
summary
```

Conservative exact-state reuse is production-safe. Cross-save progression identity remains an open roadmap item; experimental FutureRoll continuity helpers are diagnostic only until validated on real before/after progression saves.

### `bbtool/app/`

CLI, orchestration, console diagnostics, output writing, and runtime workspace management.

### `bbtool/html_report.py`, `report.js`, `report.css`

Presentation layer. Report/UI-only changes should not invalidate numerical caches.
The archetype-details renderer consumes the projection payload's per-stat
minimum, maximum, expected, baseline, target, and weight values; it does not
recompute trajectory or Fit semantics in the presentation layer.

## Fit semantics

A configured Fit stat may contain:

```text
target
baseline
weight
ceiling (optional)
```

Stars influence roll ranges only. They do not add Fit directly.

`ceiling` is valuation-only:

```text
fit_value = min(effective_value, ceiling)
```

The uncapped projected stat remains the actual displayed projection.

Each Fit stat uses a continuous bounded signed utility curve:

```text
baseline - (target - baseline) -> -1
baseline                       ->  0
target and above               -> +1
```

After weighting, each stat therefore contributes within
`[-weight, +weight]`. The weighted mean keeps baseline at 0% and all targets
at 100%; negative aggregate Fit is clamped to the public minimum of 0%.

## Permanent effects

Natural projected stats may include exact unconditional permanent transforms from:

```text
traits
permanent injuries
```

Owned or hypothetical perk stat transforms are excluded from archetype Fit and
the displayed level-11 natural projection. They may still appear in separately
labelled effective-combat-stat contexts.

Temporary injuries are intentionally excluded from long-term build evaluation.

## Trajectory engine

For each future development round:

1. derive legal star-adjusted roll ranges;
2. evaluate legal 3-stat picks using expected terminal Fit;
3. choose the Fit-optimal legal pick with deterministic tie behavior;
4. apply future gains to raw stats;
5. evaluate permanent transforms on aggregated values;
6. continue through level 11;
7. score the final effective profile.

The engine uses deterministic low-discrepancy sampling and exact/min/max anchors. Five-stat archetypes use a mathematically equivalent drop-composition optimization instead of exponential recursive future ordering.

## Ground-truth validation

Serialized `FutureRolls` are validation-only. Ground-truth validation feeds exact serialized rolls into the public trajectory engine as degenerate ranges. There is no separate ground-truth planner.

This preserves the invariant that algorithm changes affect blind projection and validation through one implementation.

## Incremental invariant

```text
incremental result == full recomputation result
```

If artifact compatibility cannot be proven, recompute. Cache contents are derived analysis only; current save facts always come from the current parser run.

## Open architecture work

The active roadmap is `docs/specs/REMAINING_WORK_v3.84.md`. Its main unresolved architectural blocker is proven stable cross-save brother identity after normal progression.
