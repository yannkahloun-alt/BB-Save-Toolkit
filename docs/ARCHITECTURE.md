# Architecture — current repository baseline

The code-level architecture review and incremental cleanup plan for the v3.86
development baseline is documented in
[`ARCHITECTURE_REVIEW_v3.86.md`](ARCHITECTURE_REVIEW_v3.86.md). This file remains
the concise statement of the current supported architecture; the review records
observed debt, target boundaries, open decisions, and sequenced migrations.

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

Roster brothers also expose their current six equipped slots and ordered bag
items. Item records are decoded conservatively from the source-derived
reference dictionary; an unknown item is reported as partial data and never
prevents the rest of the roster from being exported.

The public roster additionally exposes `PerkGearFacts`, a derived current-state
mechanics list. It is computed only while serializing public data and is never
an input to projection, Fit, BestRole, classification, or incremental reuse.
Its supported formulas and conservative unknown states are specified in
[`PERK_GEAR_FACTS.md`](PERK_GEAR_FACTS.md).

`BrotherID = human:<HumanOffset>` is save-local. Names are display-only.

The parser also exposes the native asset-manager `CampaignID` through a typed
`CampaignIdentity`. It validates the source-defined post-stash serialization
sequence and requires a unique, non-negative signed 32-bit value. The map seed,
save path, filename, and timestamps do not participate. This identity means
"same campaign" only; the SHA-256 source fingerprint means exact snapshot
equality, while lineage remains a separate contract.

### `references/`

Contains tracked seed/catalog data plus generators for runtime vanilla references. Generated references are derived from source scripts/save-hash semantics and are disposable caches.

Important generated caches include enriched dictionaries, backgrounds, trait effects, permanent-injury effects, and perk audit data.

Each run reports reference provenance through the
`bbtool.reference_status.v1` runtime payload. It records the cache directory,
the expected schema of every generated reference, cache-versus-network source,
requested upstream revision, downloaded size and SHA-256, and the validated
final state and absolute path of every persisted cache file. The run-health
summary separately identifies unresolved references that occur in the current
save; unresolved upstream entries that are not used by that save remain
informational and do not produce a result-affecting warning.
Reference downloads retry transient transport, TLS-handshake, throttling, and
server failures three times with bounded increasing backoff while preserving
normal certificate verification. A valid complete local cache remains the
preferred fallback: it is validated before any download and is used without a
network refresh, while a missing or invalid required cache still fails cleanly
if the bounded download attempts cannot rebuild it.
Every external input is requested by a version-controlled full commit SHA; the
source inventory, provenance contract, and intentional upgrade procedure are in
[`REFERENCE_SOURCES.md`](REFERENCE_SOURCES.md). There is no branch-head fallback.

### `bbtool/projection/`

Pure computation layer where practical.

- `context.py` compiles reusable brother projection context.
- `sampling.py` owns deterministic low-discrepancy coordinate generation and
  its bounded process-local memoization.
- `perks.py` keeps natural projection effects (traits and permanent injuries)
  separate from perk-modified effective combat stats.
- `trajectory.py` simulates legal future 3-stat level-up decisions and is the source of truth for development trajectories.
- `scoring.py` evaluates continuous archetype Fit, including optional Fit-only ceilings.
- `planner.py` assembles role projection outputs.

The normal projection never uses hidden serialized FutureRolls to make decisions.
The trajectory hot path consumes a named, recursively read-only
`TrajectoryContext` rather
than an anonymous positional tuple. Trajectory, compiled-context, lookahead-policy,
diagnostic, and sampling caches have one explicit reset lifecycle through
`reset_trajectory_cache()`; callers must not rely on state surviving that reset
or being shared across worker processes.

### `bbtool/levelup_advisor.py`

Evaluates legal current 3-stat choices using the same trajectory/Fit model. Known current rolls are injected as exact ranges; later levels remain probabilistic.
The current candidate pool contains only anchor-role stats with `fit: true` and
`weight > 0`. Roles with fewer than three eligible stats expose the remaining
slots as Fit-neutral free picks.

### `bbtool/classification.py` and `bbtool/app/analysis.py`

Classification derives Invest / Use / Fodder / Trash from Fit outputs and configured thresholds. Analysis orchestrates brother × archetype rows, advisor output, and summaries.

### `bbtool/app/analysis_service.py`

This is the transport-independent application boundary around parsing and
analysis. A caller supplies immutable save bytes, already-normalized effective
archetypes, classification configuration, bounded execution options, and an
optional compatible incremental-cache context. The typed result contains the
parsed public data, Fit/summary outputs, content and configuration fingerprints,
structured warnings/diagnostics, timings, and progress events.

The typed result includes `campaign_identity` for downstream durable-state
consumers, but `public_data` intentionally omits it while the public report v1
schema remains unchanged.

The service does not invoke argument parsing, choose output paths, write reports,
or use a filesystem path as save identity. CLI and future HTTP/worker entry
points are adapters around this boundary. Generated reports consume the returned
analysis directly; they do not recompute projections.

Service failures carry stable `code`, `stage`, and `message` fields. Cache
context remains disposable optimization state. This boundary intentionally does
not define durable user-state storage or new invalidation semantics while the
corresponding architecture studies remain open.

Runtime profiling reports bounded slowest-projection samples plus aggregate time
by brother and archetype. Trajectory-cache misses are categorized and their
total reconciles with the miss counter. The former hypothetical structural-perk
alternatives are retired: profiling therefore reports zero structural
alternatives rather than implying a second projection model.
Slowest-projection entries also carry bounded policy-complexity counters and
phase timings. Python heap allocation tracing is disabled during normal runs
because it materially perturbs the allocation-heavy trajectory engine; it is
available explicitly through `--measure-python-heap` for diagnostic runs.
The debug bundle also owns a versioned `bbtool.performance_diagnostics.v1`
runtime section. It persists CLI stage timings, workload and incremental reuse
counts, service-stage timings, cache miss reasons, and projection-validation
cache/oracle diagnostics used by the console. The debug file is excluded from
the main archive pass and appended before the archive timer stops, so its
compression is part of both archive and total time. The loose debug file is
then finalized with those timings; the ZIP receives the same final data in a
small `*-performance.json` member. Only persistence of that necessarily
self-referential stopwatch record remains outside the reported total. Internal
performance evidence stays out of the public report contract.

### `bbtool/incremental/`

Dependency-aware reuse layer. It must remain above the computation engines rather than embedding persistence in trajectory/scoring code.

Current artifacts can be cached independently where dependencies permit:

```text
role projection
advisor
summary
```

Each role-projection artifact also carries a private validation oracle: the
exact deterministic blind Fit outcome distribution used to calibrate serialized
future rolls. The oracle has its own engine version and an input fingerprint
covering brother projection state, archetype semantics, and role-projection
semantics. Missing, incompatible, or malformed oracle data is recomputed through
the shared trajectory engine and repaired in the next manifest; it is never
included in public analysis/report data.

Conservative exact-state reuse is production-safe. Cross-save progression identity remains an open roadmap item; experimental FutureRoll continuity helpers are diagnostic only until validated on real before/after progression saves.

Incremental manifests use `bb-incremental-v2` and carry a versioned native
`CampaignIdentity` namespace. Discovery selects the newest compatible manifest
with the same exact serialized `CampaignID`, independent of save filename or
path, and retention is scoped by that identity. The path remains provenance
only. Missing, invalid, contradictory, or legacy-v1 identity evidence disables
history discovery and pruning; exact artifact fingerprints remain authoritative
for numerical reuse within a selected campaign manifest.

### `bbtool/app/`

CLI, orchestration, console diagnostics, output writing, and runtime workspace management.
Normal and render-only outputs share the versioned public report dataset
contract. The generated HTML is a data-free launcher; a loopback-only local
server validates the adjacent manifest/JSON and invokes the shared Python
renderer at view time. This avoids unreliable `file://` JSON access without
duplicating analysis data or introducing a network dependency.
`app/render_only.py` is a presentation-only entry point. It validates the
versioned public report dataset, reconstructs display models, and calls the
same HTML/output functions as a normal analysis run. It does not parse a save,
prepare runtime references, or invoke projection, classification, Advisor, or
incremental-cache logic.
After a run archive is written successfully, output retention keeps the 10
newest timestamped ZIP archives for that source-save filename. Retention does
not rename outputs, remove run directories, or act on unrelated files.

`bbtool/app/user_state.py` owns the versioned durable per-user state substrate.
Its OS-appropriate `UserStateRoot` is outside repository, installation, output,
manifest, and reference-cache trees. Bounded feature files use typed validation,
atomic replacement, feature locks, optimistic revisions, explicit migrations,
and feature-scoped recovery. See [`USER_STATE.md`](USER_STATE.md). Domain
semantics for user archetypes and assigned builds remain downstream concerns.

### `bbtool/html_report.py`, `report.js`, `report.css`

Presentation layer. Report/UI-only changes should not invalidate numerical caches.
The archetype-details renderer consumes the projection payload's per-stat
minimum, maximum, expected, baseline, target, and weight values; it does not
recompute trajectory or Fit semantics in the presentation layer.

## Fit semantics

Stable archetype identity and semantic definition versioning are specified in
[`BUILD_IDENTITY.md`](BUILD_IDENTITY.md). They remain separate from current
name-keyed v1 report joins and artifact-specific cache fingerprints.

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
