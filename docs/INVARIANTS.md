# Core Invariants

These are architectural contracts, not implementation suggestions.

## Projection model

- Level-11 **Fit** is the primary analytical model.
- Stars have no direct Fit value; they affect future roll ranges only.
- Normal blind projection does not consume serialized hidden `FutureRolls`.
- Level-Up Advisor uses the same trajectory/Fit engine as normal projection.
- Level-Up Advisor recommendations use only positively weighted Fit stats for
  the anchor role. If fewer than three are available, neutral slots are
  explicitly reported as free picks rather than role recommendations.
- Ground-truth validation may inject serialized rolls as degenerate ranges, but must not fork the simulation algorithm.
- Optimizations must be mathematically/behaviorally equivalent to the reference semantics.

## Archetypes and scoring

- Only stats marked as Fit stats contribute to role Fit.
- `target`, `baseline`, `weight`, and optional `ceiling` are archetype-local inputs.
- `baseline` is the neutral point of a bounded signed contribution; one
  baseline-to-target interval below it reaches `-weight`.
- `target` is the positive Fit saturation point at `+weight`.
- `ceiling` remains a Fit-valuation-only cap: `fit_value = min(effective_value, ceiling)`.
- The uncapped projected/effective stat remains the displayed/statistical value.
- Changing one archetype must not invalidate unrelated archetypes in incremental reuse.

## Brother identity

- `Name` is display-only.
- `BrotherID = human:<HumanOffset>` is unique only inside one parsed save.
- `HumanOffset` is not a proven cross-save identity.
- Cross-save identity must be native/proven or conservatively synthetic.
- Ambiguity always disables reuse.
- Experimental `FutureRolls` continuity helpers are not production identity until real progression saves validate them.

## Campaign identity

- `CampaignIdentity` is the exact non-negative signed 32-bit `CampaignID`
  serialized by vanilla `asset_manager`; map seed and filesystem provenance
  are never substitutes.
- Campaign identity proves membership in one Battle Brothers run. It proves
  neither exact snapshot equality nor save ancestry.
- Missing, malformed, negative, or ambiguous native evidence is explicit and
  disables campaign-dependent behavior rather than triggering a heuristic.

## Traits and injuries

- Serialized trait IDs are Battle Brothers 4-byte save hashes.
- Exact unconditional permanent trait effects participate in effective projection stats.
- Temporary injuries are excluded from long-term projections and long-term projection fingerprints.
- Exact permanent-injury effects participate in effective projection stats and relevant fingerprints.
- Conditional/complex effects must not be silently treated as unconditional permanent stat changes.

## Perks and natural potential

- Archetype Fit and displayed level-11 projections measure natural brother
  potential and must not consume owned or hypothetical perk stat modifiers.
- Owned-perk effective combat stats may be exposed separately, but hypothetical
  perk paths are not classification alternatives and must not rewrite the
  natural stat input used to discover or compare archetypes.

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
- Routine and pre-merge validation exclude `coverage_slow`; those tests are a
  pre-release/pre-production gate.
- Coverage instrumentation excludes `coverage_slow` because tracing makes
  combinatorial projection tests pathologically slow.
- Mutation testing is pre-release/pre-production only and is never started
  automatically for routine tasks or normal pre-merge validation.
- Valid mutation survivors found during an explicitly requested campaign are
  defects to investigate, not numbers to ignore.
