# Battle Brothers Save Toolkit --- Remaining Work Specification

## Status

**Baseline:** v3.84\
**Purpose:** implementation handoff / remaining-work specification

This document supersedes the previous v3.83 remaining-work
specification.

It lists only the work that remains after v3.84.

------------------------------------------------------------------------

# 1. Completed by v3.84

The following items are considered DONE and MUST be preserved.

## 1.1 Incremental role-projection reuse

Implemented:

``` text
brother × archetype role projection reuse
```

with conservative exact dependency matching.

## 1.2 Downstream incremental reuse

Implemented independent reuse for:

``` text
role projections
structural paths
level-up advisor
final summary
```

This allows, for example, a classification-only change to reuse
structural paths and advisor results.

## 1.3 Cache safety controls

Implemented:

``` text
--full-recompute
--verify-cache
--cache-debug
```

`--verify-cache` now reports the first exact differing path/value.

## 1.4 Cache diagnostics

Implemented reuse/computation counts and cache-miss reasons.

## 1.5 Manifest lifecycle

Implemented:

-   atomic writes;
-   compatible-manifest discovery;
-   pruning of old incremental manifests;
-   retention of the latest 10 manifests for a given save path;
-   no deletion of normal user reports/outputs.

## 1.6 Trait effects

Implemented generated trait-effect references from vanilla scripts.

v3.84 fixes the important v3.83 lookup bug:

``` text
serialized TraitID = 4-byte Battle Brothers save hash
```

Trait effects are therefore keyed by the exact ID found in real saves.

Exact unconditional permanent core-stat effects are applied to
projection stats.

## 1.7 Temporary vs permanent injuries

Implemented parser distinction between:

``` text
temporary injury
permanent injury
trait
```

Temporary injuries:

``` text
do not affect long-term projection
do not invalidate projection cache
```

Permanent injuries:

``` text
have their own IDs
have generated effect references
affect effective projection stats when exact/unconditional
invalidate affected cached projections
```

## 1.8 Cache-version hardening

Projection and summary cache engine versions were bumped where semantics
changed.

Old incompatible cached rows are not silently reused.

## 1.9 Future-roll continuity infrastructure

Diagnostic helpers exist for testing whether:

``` text
old FutureRolls -> new FutureRolls
```

follow a consumed-prefix / suffix-continuity relationship after
level-up.

This is deliberately NOT yet used as a production identity rule.

------------------------------------------------------------------------

# 2. Governing rule

The remaining incremental work follows:

> **Reuse is allowed only when continuity and unchanged dependencies are
> proven. Recompute otherwise.**

No heuristic cross-save brother match may be promoted to production
merely because it appears plausible.

------------------------------------------------------------------------

# 3. Remaining work overview

The main remaining workstreams are now:

1.  **Prove and implement true cross-save brother identity**
2.  **Enable reuse across legitimate brother progression**
3.  **Campaign-level cache isolation**
4.  **Centralize dependency declarations**
5.  **Trait/permanent-injury completeness audit**
6.  **Cache verification and mutation hardening**
7.  **Real-save performance validation**
8.  **Optional cache storage improvements**

The highest-priority blocker is workstream 1.

------------------------------------------------------------------------

# 4. Workstream A --- True cross-save brother identity

## 4.1 Current limitation

The production cache still identifies reusable brothers from an exact
projection-state fingerprint.

That safely handles:

``` text
same bro
same relevant state
```

but not:

``` text
same bro after level-up
same bro after perk acquisition
same bro after stat change
same bro after current-roll change
```

The projection-state fingerprint is therefore still a cache-state key,
not a persistent brother identity.

## 4.2 Required result

Introduce a distinct concept:

``` text
BrotherIdentity
```

that can correlate the same brother across successive save files.

It MUST remain separate from:

``` text
BrotherID = human:<offset>
display name
projection-state hash
```

## 4.3 Native identity investigation

Before introducing any synthetic matcher, inspect the serialized Battle
Brothers brother/entity block for a native immutable ID.

The investigation SHOULD look for:

``` text
entity UUID
persistent integer ID
serialized actor ID
other immutable per-character token
```

If a reliable native identifier exists, it MUST be preferred.

## 4.4 Real FutureRolls validation

The diagnostic future-roll suffix matcher is implemented but unproven on
real progression.

We now need real before/after saves.

Required fixtures:

``` text
Save A: bro before level-up
Save B: same bro after one level-up
```

Preferably repeat this for several brothers.

For every stat:

``` text
HP
Fatigue
Resolve
Initiative
MAtk
RAtk
MDef
RDef
```

test whether the new sequence equals the previous sequence after
removing a common consumed prefix.

Expected hypothesis:

``` text
previous = [r1, r2, r3, r4, ...]
current  = [r2, r3, r4, ...]
```

after one consumed level-up roll.

The exact relationship MUST be derived from real data.

## 4.5 Identity evidence

If no native stable ID exists, a synthetic identity MAY combine:

``` text
FutureRolls continuity
background ID
stars
stable trait IDs
stable permanent injury IDs
other immutable serialized metadata
```

Mutable stats MUST NOT be required to stay equal.

Name MUST NOT be required to stay equal.

## 4.6 Ambiguity policy

If:

``` text
0 candidates -> new/unmatched
1 proven candidate -> matched
>1 candidates -> ambiguous
```

then ambiguous identity MUST always fall back to recomputation.

No nearest-neighbor / score-based guessing is allowed in production
unless an explicit future specification defines and proves it.

## 4.7 Acceptance criteria

This workstream is done when tests prove all of the following:

-   unchanged brother matches;
-   brother after one level-up matches;
-   brother after perk acquisition matches;
-   changed name does not break identity;
-   new recruit is not matched to an old bro;
-   removed/dead bro is not reassigned;
-   two similar bros cannot be silently confused;
-   ambiguity disables reuse.

------------------------------------------------------------------------

# 5. Workstream B --- Reuse across brother progression

## 5.1 Dependency categories

Once true identity exists, stop treating the entire brother projection
state as one indivisible cache identity.

Introduce specialized state fingerprints such as:

``` text
natural_stats
stars
level_xp
perks
traits
permanent_injuries
current_rolls
background
```

## 5.2 Artifact-specific dependencies

Each artifact should depend only on the inputs it actually uses.

### Role projection

Likely dependencies:

``` text
natural stats
stars
level / remaining rounds
traits
permanent injuries
structural perks
archetype
projection engine
trajectory engine
scoring engine
```

### Structural paths

Likely dependencies:

``` text
perks
perk points / level
archetype structural requirements
structural-path engine
```

### Level-up advisor

Likely dependencies:

``` text
current rolls
current brother state
anchor role
role/archetype definitions
advisor engine
trajectory engine
```

### Classification

Likely dependencies:

``` text
role projection outputs
classification configuration
classification engine
```

## 5.3 Desired behavior

Example:

``` text
Bro A levels up
Bros B-G unchanged
```

Expected mature behavior:

``` text
B-G artifacts -> reused where dependencies are unchanged
A artifacts -> selectively recomputed
```

A current-roll-only change SHOULD invalidate advisor logic without
automatically invalidating unrelated role projections.

## 5.4 Acceptance

For every supported progression case:

``` text
incremental output == full recomputation
```

------------------------------------------------------------------------

# 6. Workstream C --- Campaign-safe cache isolation

## 6.1 Current limitation

Manifest discovery is currently constrained by the resolved save-file
path.

This is safer than global reuse, but it is not yet a true campaign
identity.

Examples that can break path-based identity:

``` text
save renamed
save copied
different campaign using same filename/path later
```

## 6.2 Requirement

Introduce:

``` text
CampaignFingerprint
```

derived from stable campaign-level save data.

The save filename/path MUST NOT be the final source of truth.

## 6.3 Required investigation

Inspect the save for stable campaign identifiers such as:

``` text
campaign seed
world seed
company ID
campaign creation ID
scenario/origin state
other stable campaign metadata
```

## 6.4 Discovery behavior

Eventually:

``` text
find previous manifest
WHERE manifest schema supported
AND campaign fingerprint matches
```

The save path may remain a useful hint/filter but should not be
authoritative.

## 6.5 Acceptance

No artifact from a different campaign may ever be reused.

If campaign identity is uncertain:

``` text
reuse disabled
full recompute
```

------------------------------------------------------------------------

# 7. Workstream D --- Central dependency declarations

## 7.1 Motivation

Incremental dependency logic is now important enough that missing one
field can silently produce stale output.

The dependency rules should therefore be centralized.

## 7.2 Recommended module

Create:

``` text
bbtool/incremental/dependencies.py
```

with explicit builders such as:

``` python
RoleProjectionInputs
StructuralPathInputs
AdvisorInputs
ClassificationInputs
SummaryInputs
```

Each input object is normalized and hashed.

## 7.3 Engine-version registry

Centralize semantic engine versions for:

``` text
projection
trajectory
scoring
structural paths
advisor
classification
summary
```

Formatting/report-only changes must not invalidate numerical artifacts.

Semantic computation changes must bump the relevant engine version.

## 7.4 Acceptance

It should be possible to answer:

``` text
Why was this artifact invalidated?
```

from one dependency declaration rather than tracing scattered code.

------------------------------------------------------------------------

# 8. Workstream E --- Trait and permanent-injury completeness audit

## 8.1 Current support

The tool currently applies:

``` text
exact
unconditional
core-stat
```

effects extracted from vanilla scripts.

This is intentionally conservative.

## 8.2 Remaining audit

Enumerate generated references into:

``` text
exact unconditional
conditional
complex/multiplicative
non-core-stat
unsupported
```

Multiplicative exact effects are supported where the current generic
property parser correctly extracts them.

Conditional effects must remain explicit.

## 8.3 Required output diagnostics

Reference generation should report at least:

``` text
traits scanned
traits with exact core-stat effects
traits with conditional effects
permanent injuries scanned
permanent injuries with exact effects
permanent injuries with conditional effects
unsupported/unresolved sample
```

## 8.4 Conditional effects

Do NOT automatically treat conditional effects as permanent base-stat
effects.

Any future conditional behavior needs explicit semantics such as:

``` text
base-fit ignored
combat scenario bonus
role signal only
always-on under proven condition
```

## 8.5 Acceptance

No conditional/unsupported effect should silently masquerade as a
guaranteed permanent stat modifier.

------------------------------------------------------------------------

# 9. Workstream F --- Cache verification hardening

## 9.1 Existing behavior

`--verify-cache` now reports the first exact differing path.

## 9.2 Remaining improvements

Include artifact context where possible:

``` text
brother
role
artifact type
field
incremental value
full value
```

Example:

``` text
Brother: Bodo
Artifact: role projection
Role: Thrower Hybrid
Field: ProjectedFitPct
Incremental: 81.4
Full: 80.9
```

## 9.3 Batch verification fixtures

Add explicit real/synthetic fixtures for:

``` text
unchanged save
temporary injury only
permanent injury gained
trait change
one archetype change
ceiling change
classification threshold change
current rolls change
perk acquisition
level-up
new recruit
dead brother
```

Level-up verification depends on completion of cross-save identity.

------------------------------------------------------------------------

# 10. Workstream G --- Mutation hardening

Incremental invalidation is high-risk code because stale data can remain
plausible.

Mutation testing MUST specifically kill mutants such as:

``` text
remove TraitIDs from dependency
remove PermanentInjuryIDs
add temporary injuries back to projection hash
omit current rolls from advisor
omit ceiling from archetype hash
omit engine version
accept ambiguous identity
ignore role hash mismatch
accept wrong campaign
reuse summary after classification config change
```

Mutation campaigns should remain file/module-oriented.

------------------------------------------------------------------------

# 11. Workstream H --- Real gameplay performance validation

## 11.1 Required measurements

Collect timings for:

``` text
first run / cold cache
unchanged quicksave
one-bro change
one archetype change
classification-only change
level-up after identity support
```

## 11.2 Diagnostics

Track:

``` text
role reused/computed
structural reused/computed
advisor reused/computed
summary reused/computed
fingerprint/manifest overhead
total runtime
```

## 11.3 Acceptance

The incremental layer must produce a material real-world speedup without
changing recommendations.

Manifest/fingerprint overhead should remain negligible compared with
trajectory computation.

------------------------------------------------------------------------

# 12. Optional future storage optimization

The current JSON manifest remains acceptable while size and latency are
modest.

Only if measurement proves it necessary, introduce content-addressed
artifacts:

``` text
cache/
  <artifact-hash>.json
```

with manifests referencing those objects.

This is NOT currently a priority.

------------------------------------------------------------------------

# 13. Recommended implementation order

## Phase 1 --- Real cross-save identity evidence

1.  Obtain real before/after-level-up saves.
2.  Search for native stable entity ID.
3.  Compare FutureRolls continuity.
4.  Implement conservative BrotherIdentity.
5.  Add ambiguity and progression tests.

## Phase 2 --- Specialized dependency fingerprints

1.  Create `dependencies.py`.
2.  Split brother state into categories.
3.  Move existing artifact keys onto those declarations.
4.  Keep full-recompute verification active.

## Phase 3 --- Progression-aware reuse

1.  Reuse unaffected artifacts after level-up/perk changes.
2.  Make current-roll-only invalidation advisor-specific.
3.  Verify every case against full recomputation.

## Phase 4 --- Campaign identity

1.  Identify stable campaign metadata.
2.  Add CampaignFingerprint.
3.  Replace save-path authority with campaign-safe discovery.

## Phase 5 --- Reference completeness audit

1.  Audit trait effects.
2.  Audit permanent injury effects.
3.  Surface conditional/unsupported cases.

## Phase 6 --- Hardening

1.  Improve verify-cache diagnostics.
2.  Add real-save fixtures.
3.  Run targeted mutation campaigns.
4.  Measure actual gameplay performance.

------------------------------------------------------------------------

# 14. Explicit invariants

Future work MUST preserve:

1.  Name is not authoritative brother identity.
2.  HumanOffset is save-local only.
3.  Ambiguous identity never permits reuse.
4.  Temporary injuries do not affect long-term projections.
5.  Temporary injuries do not invalidate long-term projection cache.
6.  Permanent injuries do affect projections when they have exact
    permanent effects.
7.  Trait effects use the serialized Battle Brothers save-hash ID.
8.  Archetype ceiling remains Fit-only.
9.  One archetype change does not invalidate unrelated archetypes.
10. Cache corruption falls back safely to computation.
11. Full recomputation remains available.
12. Incremental output equals full recomputation.
13. Report-only changes do not invalidate numerical artifacts
    unnecessarily.
14. Experimental FutureRolls continuity is not production identity until
    proven on real progression saves.

------------------------------------------------------------------------

# 15. Immediate next task

The next task is now very specific:

> **Provide and analyze a real pair of saves around a brother
> level-up.**

Ideal sequence:

``` text
Save A — immediately before level-up
Save B — immediately after applying the level-up
```

Preferably without unrelated roster changes between A and B.

From those saves we should extract, for every brother:

``` text
name for human inspection only
HumanOffset
level
stats
stars
traits
permanent injuries
CurrentRolls
FutureRolls
background
perks
```

Then determine whether:

``` text
native stable identity exists
or
FutureRolls suffix continuity is sufficient
or
a stronger composite identity is required
```

Until that evidence exists, v3.84 should retain its current conservative
exact-state reuse behavior.
