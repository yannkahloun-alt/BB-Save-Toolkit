# Core Invariants

These are architectural contracts, not implementation suggestions.

## Projection model

- Level-11 **Fit** is the primary analytical model.
- Stars have no direct Fit value; they affect future roll ranges only.
- Normal blind projection does not consume serialized hidden `FutureRolls`.
- Level-Up Advisor uses the same trajectory/Fit engine as normal projection.
- Ground-truth validation may inject serialized rolls as degenerate ranges, but must not fork the simulation algorithm.
- Optimizations must be mathematically/behaviorally equivalent to the reference semantics.

## Archetypes and scoring

- Only stats marked as Fit stats contribute to role Fit.
- `target`, `baseline`, `weight`, and optional `ceiling` are archetype-local inputs.
- `ceiling` is a Fit-valuation saturation point only: `fit_value = min(effective_value, ceiling)`.
- The uncapped projected/effective stat remains the displayed/statistical value.
- Changing one archetype must not invalidate unrelated archetypes in incremental reuse.

## Brother identity

- `Name` is display-only.
- `BrotherID = human:<HumanOffset>` is unique only inside one parsed save.
- `HumanOffset` is not a proven cross-save identity.
- Cross-save identity must be native/proven or conservatively synthetic.
- Ambiguity always disables reuse.
- Experimental `FutureRolls` continuity helpers are not production identity until real progression saves validate them.

## Traits and injuries

- Serialized trait IDs are Battle Brothers 4-byte save hashes.
- Exact unconditional permanent trait effects participate in effective projection stats.
- Temporary injuries are excluded from long-term projections and long-term projection fingerprints.
- Exact permanent-injury effects participate in effective projection stats and relevant fingerprints.
- Conditional/complex effects must not be silently treated as unconditional permanent stat changes.

## Incremental analysis

- Cache reuse is never a source of truth for current game state.
- The current save parser is authoritative for current brother state.
- Incremental results must equal independent full recomputation.
- Missing, corrupt, incompatible, ambiguous, or uncertain cache state falls back to computation.
- Artifact invalidation should be as fine-grained as proven dependencies permit.
- Computation-engine semantic changes require relevant cache-engine version bumps.
- UI/report-only changes should not invalidate numerical artifacts.

## Parser and references

- Parser changes require regression tests based on deterministic fixtures/byte structures.
- Vanilla reference generation should derive from source scripts/save-hash semantics rather than hand-maintained display-name tables where practical.
- Generated reference caches are disposable and reproducible.

## Testing

- A bug fix is incomplete without a regression test unless a test is technically impossible; document exceptions.
- Full correctness tests include `coverage_slow` tests.
- Coverage instrumentation may exclude `coverage_slow` because tracing makes combinatorial projection tests pathologically slow.
- Mutation survivors in touched correctness-critical logic are defects to investigate, not numbers to ignore.
