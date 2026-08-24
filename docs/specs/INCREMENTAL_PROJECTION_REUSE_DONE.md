# Incremental Projection Reuse Specification

## Status

**Completed specification, amended 2026-08-24**

The 2026-08-24 amendment retires the former hypothetical structural/perk-path
artifact. Role Fit, classification, and the Level-Up Advisor now follow one
natural-stat trajectory. Owned perks may still affect displayed current combat
stats, but they do not create an alternate projection path or reusable artifact.

This document defines an incremental computation and projection-reuse
mechanism for the Battle Brothers Save Toolkit.

The objective is to avoid systematically recomputing every projection,
trajectory, classification, and level-up recommendation
when a newly analyzed save is sufficiently similar to a previously
analyzed save.

The mechanism MUST behave as a dependency-aware incremental build
system: a previous result may be reused only when every input relevant
to that result is proven unchanged.

Correctness takes priority over cache hit rate.

------------------------------------------------------------------------

## 1. Goals

The implementation MUST:

1.  Detect whether compatible outputs from a previous save analysis are
    available.
2.  identify brothers consistently across successive saves without
    relying on their display name;
3.  determine which analysis inputs changed between the previous and
    current save;
4.  reuse previous outputs whose complete dependency set is unchanged;
5.  recompute only outputs affected by changed inputs;
6.  invalidate results selectively when configuration or projection
    logic changes;
7.  preserve exactly the same functional result as a clean full
    recomputation;
8.  expose reuse/recalculation decisions in console diagnostics;
9.  remain backward compatible when no previous compatible output
    exists;
10. allow the cache/reuse mechanism to be disabled for validation and
    debugging.

This feature is an optimization only. It MUST NOT alter projection
semantics.

------------------------------------------------------------------------

## 2. Non-goals

The first implementation does NOT need to:

-   maintain an unbounded historical database of every save;
-   reuse arbitrary intermediate Python objects;
-   infer compatibility from filenames alone;
-   rely on timestamps as proof that inputs are unchanged;
-   reuse a result when its dependency set cannot be established;
-   optimize parsing of the save itself unless separately specified;
-   guarantee reuse across toolkit versions unless the relevant
    computation stages explicitly declare compatibility.

When uncertain, the implementation MUST recompute.

------------------------------------------------------------------------

## 3. Core principle

Every reusable output is treated as a derived artifact.

A derived artifact is valid if and only if all inputs that influence it
are unchanged.

Conceptually:

``` text
artifact_key =
    hash(
        artifact_type
        + artifact_schema_version
        + relevant_brother_state
        + relevant_archetype/config
        + relevant_engine_versions
        + relevant_runtime_parameters
    )
```

If the newly calculated key matches the key stored with a previous
artifact, the artifact MAY be reused.

If it differs, the artifact MUST be recomputed.

The implementation MUST NOT use a single global save hash as the only
invalidation mechanism, because that would invalidate all brothers when
only one brother changed.

------------------------------------------------------------------------

## 4. Terminology

### 4.1 Current save

The save file being analyzed by the current toolkit invocation.

### 4.2 Previous analysis

A completed analysis of an earlier save from the same campaign whose
incremental manifest and reusable outputs are available.

### 4.3 Brother identity

A stable identifier used to correlate the same Battle Brother across
different save files.

This is distinct from a save-local parser identifier such as a byte
offset.

### 4.4 Fingerprint

A deterministic hash of a normalized set of inputs.

Fingerprints MUST be independent of dictionary ordering and other
irrelevant serialization differences.

### 4.5 Artifact

A reusable derived result such as:

-   a role projection;
-   a trajectory result;
-   a classification result;
-   a level-up advisor result.

### 4.6 Invalidation

The decision that a previous artifact cannot safely be reused and
therefore must be recomputed.

------------------------------------------------------------------------

## 5. Cross-save brother identity

### 5.1 Requirement

Incremental reuse requires the toolkit to correlate a brother in the
current save with the same brother in the previous save.

The display name MUST NOT be the primary identity mechanism.

A save-local offset MUST NOT be assumed stable across saves unless
stability has been demonstrated and explicitly documented.

### 5.2 Preferred identity

The parser SHOULD identify an immutable identifier serialized by Battle
Brothers for the entity if such a field exists.

The implementation SHOULD investigate the serialized brother/entity
structure before introducing a synthetic identity.

If a native stable identifier is available, it MUST be preferred.

### 5.3 Synthetic fingerprint fallback

If no native cross-save identifier is available, the toolkit MAY derive
a `BrotherFingerprint` from fields believed to be immutable for the
lifetime of a brother.

Mutable fields MUST NOT be used as identity components when avoidable.

In particular, the following are unsuitable as sole identity fields:

-   name;
-   title;
-   level;
-   XP;
-   stats;
-   stars if the save format can mutate them;
-   perks;
-   equipment;
-   injuries;
-   current rolls.

### 5.4 Ambiguity

Identity resolution MUST be conservative.

If:

-   no previous brother matches;
-   more than one previous brother matches;
-   the identifier is malformed;
-   identity confidence is insufficient;

the brother MUST be treated as new and all of its artifacts recomputed.

The toolkit MUST NOT guess between ambiguous matches.

### 5.5 Lifecycle

The comparison layer SHOULD classify brothers as:

``` text
unchanged identity
new
removed
ambiguous
```

Removed brothers require no new projection but SHOULD be visible in
diagnostics when useful.

------------------------------------------------------------------------

## 6. Previous-analysis discovery

### 6.1 Discovery

At startup, the toolkit SHOULD search its existing output location for
previous incremental manifests.

The selected previous analysis MUST:

-   belong to the same campaign;
-   use a supported manifest schema;
-   contain reusable artifacts;
-   pass compatibility checks.

The most recent compatible analysis SHOULD normally be selected.

### 6.2 Campaign identity

A campaign fingerprint SHOULD be derived from stable campaign-level data
available in the save.

It MUST NOT depend solely on the save filename.

If reliable campaign identity cannot be established, reuse MUST be
disabled rather than risk cross-campaign contamination.

### 6.3 No previous analysis

If no compatible previous analysis exists, behavior MUST be equivalent
to the current full-analysis path.

Example:

``` text
incremental cache          no compatible previous analysis
projection mode            full
```

------------------------------------------------------------------------

## 7. Incremental manifest

Each successful analysis SHOULD write a manifest alongside the normal
outputs.

Suggested filename:

``` text
<save-output-prefix>-incremental-manifest.json
```

Suggested top-level schema:

``` json
{
  "schema": "bb-incremental-v1",
  "campaign": {
    "fingerprint": "..."
  },
  "save": {
    "source": "...",
    "fingerprint": "...",
    "analyzed_at": "..."
  },
  "engine": {
    "projection": "...",
    "trajectory": "...",
    "scoring": "...",
    "classification": "...",
    "advisor": "..."
  },
  "config": {
    "archetypes": {
      "global_hash": "...",
      "roles": {
        "Thrower Hybrid": "..."
      }
    },
    "classification_hash": "..."
  },
  "brothers": {
    "<stable-brother-id>": {
      "fingerprints": {},
      "artifacts": {}
    }
  }
}
```

Exact field names MAY differ, but the information represented by the
schema is required.

------------------------------------------------------------------------

## 8. Brother-state fingerprints

A single opaque `brother_state_hash` is insufficient for fine-grained
invalidation.

The manifest SHOULD store specialized fingerprints.

Suggested fingerprints include:

``` text
identity
natural_stats
stars
level_xp
perks
traits
injuries
current_rolls
equipment
background
```

Additional fingerprints MAY be introduced when required.

Each fingerprint MUST contain only normalized data relevant to that
category.

Example:

``` json
"fingerprints": {
  "natural_stats": "sha256:...",
  "stars": "sha256:...",
  "level_xp": "sha256:...",
  "perks": "sha256:...",
  "traits": "sha256:...",
  "injuries": "sha256:...",
  "current_rolls": "sha256:..."
}
```

This enables artifact-specific dependency checks.

------------------------------------------------------------------------

## 9. Configuration fingerprints

### 9.1 Archetypes

Each archetype MUST have its own deterministic fingerprint.

Changing `Thrower Hybrid` MUST NOT automatically invalidate projections
for `Banner`, `Tank`, `Archer`, etc.

The fingerprint MUST include every archetype field that can influence
its results, including when applicable:

-   Fit stats;
-   targets;
-   baselines;
-   weights;
-   ceilings;
-   perk requirements;
-   selection/tie-breaking configuration;
-   any future archetype-specific projection option.

### 9.2 Global configuration

Configuration that affects every role MAY have a global fingerprint.

A global change MUST invalidate only artifacts that depend on it.

### 9.3 Formatting-only changes

Formatting, report presentation, CSS, or other display-only
configuration MUST NOT invalidate numerical projections unless it
actually participates in their computation.

------------------------------------------------------------------------

## 10. Engine compatibility

Toolkit package version alone SHOULD NOT be the sole engine invalidation
key.

Each reusable computation stage SHOULD declare an explicit
algorithm/schema version.

For example:

``` text
projection_engine_version = 3
trajectory_engine_version = 5
scoring_engine_version = 2
classification_engine_version = 2
advisor_engine_version = 4
```

A change to HTML rendering SHOULD therefore not invalidate trajectories.

A change to trajectory semantics MUST invalidate trajectory-dependent
artifacts.

If compatibility cannot be determined after an engine change, affected
artifacts MUST be invalidated.

------------------------------------------------------------------------

## 11. Artifact dependency model

The implementation SHOULD define artifact dependencies centrally rather
than scattering cache decisions throughout application code.

Conceptual examples follow.

### 11.1 Role projection

A role projection may depend on:

``` text
brother natural stats
stars
level / remaining development rounds
relevant traits
relevant injuries/effects
archetype fingerprint
projection engine version
trajectory engine version
scoring engine version
projection runtime parameters
```

It MUST NOT depend on fields that have no influence on the calculation.

### 11.2 Classification

Classification may depend on:

``` text
all role projection results used by classification
classification configuration
classification engine version
```

If one role projection changes, classification MUST be recomputed if
that role participates in classification.

### 11.3 Level-up advisor

The advisor may depend on:

``` text
current level-up rolls
current brother state
anchor role/archetype
relevant role projections
advisor engine version
trajectory engine version
```

A change in current rolls MUST invalidate the advisor without
necessarily invalidating unrelated base role projections.

### 11.4 Report rendering

Report rendering SHOULD normally consume current and reused numerical
artifacts identically.

The HTML report itself does not need to be reused. It MAY be regenerated
cheaply from a mixture of cached and newly computed analysis data.

------------------------------------------------------------------------

## 12. Dependency graph

The implementation SHOULD model invalidation conceptually as:

``` text
Save
 ├─ Campaign state
 └─ Brother
     ├─ Identity
     ├─ Natural stats
     ├─ Stars
     ├─ Level / XP
     ├─ Perks
     ├─ Traits / injuries
     └─ Current rolls
          │
          │
          ▼
    Role projection
          │
          ▼
    Classification
          │
          └─────────────┐
                        ▼
                 Level-up advisor

Archetype definition ─────► affected role projection

Engine versions ──────────► dependent artifact stages
```

This graph is illustrative. The implementation MUST use the actual
dependencies of the code.

------------------------------------------------------------------------

## 13. Reuse decision

For every artifact requested by the current analysis:

1.  resolve the current brother identity;
2.  locate the corresponding previous brother;
3.  calculate the artifact's current input fingerprint;
4.  locate the previous artifact;
5.  verify artifact schema/engine compatibility;
6.  compare the current input fingerprint with the previous input
    fingerprint;
7.  reuse only on exact compatibility;
8.  otherwise recompute;
9.  store the newly produced/reused artifact in the new manifest.

Pseudo-code:

``` python
previous = previous_manifest.artifact(brother_id, artifact_id)

current_key = build_artifact_key(
    brother=current_brother,
    config=current_config,
    engines=current_engines,
    parameters=current_parameters,
)

if previous is not None and previous.input_hash == current_key:
    result = previous.result
    source = "reused"
else:
    result = compute()
    source = "computed"
```

------------------------------------------------------------------------

## 14. Reused result semantics

A reused result MUST be indistinguishable from a newly computed result
to downstream code.

Downstream classification/reporting logic MUST NOT need separate
implementations for cached and computed artifacts.

The cache layer SHOULD therefore return the same model/dictionary shape
as the normal computation path.

Cache metadata SHOULD be carried separately where possible.

------------------------------------------------------------------------

## 15. Required invalidation scenarios

The implementation MUST correctly handle at least the following.

### 15.1 No brother change

If a brother and all relevant configuration/engine inputs are unchanged:

``` text
all compatible artifacts -> reuse
```

### 15.2 One brother levels up

If only one brother changes level/stats:

``` text
unchanged brothers -> reuse
changed brother -> recompute affected artifacts
```

No other brother SHOULD be invalidated.

### 15.3 Current level-up rolls change

Only artifacts dependent on current rolls SHOULD be invalidated.

### 15.4 One archetype changes

If only `Thrower Hybrid` changes:

``` text
Thrower Hybrid projections -> recompute for applicable brothers
other role projections      -> reuse
classification              -> recompute where dependent
advisor                      -> recompute where dependent
```

### 15.5 Ceiling changes

Changing a stat `ceiling` in one archetype MUST invalidate that
archetype's Fit-dependent projection/scoring artifacts.

It MUST NOT invalidate unrelated archetypes.

### 15.6 Projection engine changes

All artifacts depending on that projection engine version MUST be
recomputed.

Unrelated artifacts MAY remain reusable.

### 15.7 HTML/report code changes

Numerical projections SHOULD remain reusable.

The report MAY simply be regenerated from cached numerical results.

### 15.8 New brother

All required artifacts for the new brother MUST be computed.

Existing brothers remain eligible for reuse.

### 15.9 Removed/dead brother

No current artifact needs to be computed.

Previous artifacts MUST NOT be assigned to another brother.

### 15.10 Ambiguous identity

All artifacts for that current brother MUST be recomputed.

------------------------------------------------------------------------

## 16. Cache storage strategy

The initial implementation SHOULD favor simplicity and inspectability
over maximum compression.

Storing reusable results directly in the incremental JSON manifest is
acceptable if file size remains reasonable.

If artifacts become too large, the design MAY evolve toward:

``` text
manifest.json
cache/
  <artifact-hash>.json
```

The manifest would then reference content-addressed artifacts.

The first implementation does not require this split.

------------------------------------------------------------------------

## 17. Atomicity and corruption handling

The incremental manifest MUST be written atomically.

Recommended process:

``` text
write temporary manifest
validate serialization
rename/replace final manifest
```

A failed or interrupted analysis MUST NOT overwrite the last known-good
manifest with a partial manifest.

If a manifest is unreadable or malformed:

-   emit a warning;
-   ignore it;
-   perform a normal full recomputation.

Cache corruption MUST NOT prevent save analysis.

------------------------------------------------------------------------

## 18. Console diagnostics

Incremental behavior MUST be visible.

Suggested normal output:

``` text
[START] Incremental analysis
        previous analysis          found · compatible
        campaign                   matched
        brothers                   7
        matched                    7
        new                        0
        removed                    0
        ambiguous                  0
        role projections reused    60 / 70
        role projections computed  10 / 70
        advisors reused            6 / 7
        advisors computed          1 / 7
[DONE ] Incremental analysis        1.82s
```

When configuration caused invalidation:

``` text
        config changes             1 archetype
        changed archetypes         Thrower Hybrid
        affected role projections  7
```

Diagnostics SHOULD distinguish at least:

``` text
reused
computed because brother changed
computed because config changed
computed because engine changed
computed because no previous artifact
computed because identity ambiguous
```

A verbose/debug mode MAY expose exact fingerprint/dependency
differences.

------------------------------------------------------------------------

## 19. CLI behavior

Incremental reuse SHOULD become the default once considered stable.

The toolkit MUST provide a way to force a clean computation.

Suggested option:

``` text
--no-cache
```

or:

``` text
--full-recompute
```

One canonical option SHOULD be selected; duplicate synonyms are
unnecessary.

A debug option MAY be added:

``` text
--cache-debug
```

to print detailed invalidation reasons.

The existing user-facing outputs MUST remain unchanged except for
additional diagnostics.

------------------------------------------------------------------------

## 20. Validation mode

For development, a cache verification mode is strongly recommended.

Suggested option:

``` text
--verify-cache
```

In this mode the toolkit:

1.  performs the incremental analysis;
2.  independently performs a clean recomputation;
3.  compares all reusable numerical artifacts;
4.  fails loudly on any difference.

This mode may be expensive and does not need to be enabled by default.

It is intended to prove that the dependency model is complete.

------------------------------------------------------------------------

## 21. Determinism requirements

Fingerprint generation MUST be deterministic.

Normalization MUST define:

-   stable dictionary key ordering;
-   numeric representation;
-   handling of missing vs null fields;
-   list ordering where order is semantically irrelevant;
-   schema version.

Recommended hash algorithm:

``` text
SHA-256
```

Cryptographic security is not required, but collision resistance and
easy debugging are useful.

Python's built-in `hash()` MUST NOT be used because it is not stable
across processes.

------------------------------------------------------------------------

## 22. Cache-key explainability

The implementation SHOULD make artifact-key construction testable and
inspectable.

For example:

``` python
ArtifactInputs(
    brother={
        "natural_stats": "...",
        "stars": "...",
        "level_xp": "...",
    },
    archetype="sha256:...",
    engines={
        "projection": 3,
        "trajectory": 5,
    },
)
```

This structure is then normalized and hashed.

This is preferred to manually concatenating arbitrary strings.

------------------------------------------------------------------------

## 23. Performance expectations

The optimization is primarily intended for repeated quicksave analysis
during gameplay.

A representative case:

``` text
7 brothers
10 archetypes
only 1 brother changed since previous save
configuration unchanged
```

Expected behavior:

``` text
~60/70 role projections reusable
only changed-brother role projections recomputed
unaffected advisors reused when their dependencies are unchanged
report regenerated from mixed reused/computed data
```

No fixed speedup is mandated because projection complexity may evolve.

However, the incremental layer itself SHOULD add negligible cost
relative to the projections it avoids.

Fingerprinting and manifest loading SHOULD remain in the
millisecond-to-low-tens-of-milliseconds range for normal rosters.

------------------------------------------------------------------------

## 24. Cache pruning

The first implementation MAY retain only a limited number of previous
manifests.

Suggested policy:

``` text
keep the latest N compatible analyses per campaign
```

with a conservative default such as 5 or 10.

Alternatively, if outputs are already organized per save, manifests MAY
follow the same lifecycle as their parent outputs.

Pruning MUST NOT delete normal user outputs unless explicitly part of
the existing output retention policy.

------------------------------------------------------------------------

## 25. Security and trust boundary

Previous manifests are local optimization data, not authoritative save
data.

The current save remains the source of truth.

The toolkit MUST NOT restore brother state from the cache.

Only derived analysis artifacts may be reused.

Any value that represents current game state MUST come from the current
save parser.

------------------------------------------------------------------------

## 26. Testing requirements

### 26.1 Fingerprint unit tests

Tests MUST cover:

-   deterministic serialization;
-   dictionary ordering;
-   missing values;
-   numeric values;
-   changed relevant input changes hash;
-   changed irrelevant input does not change an artifact-specific hash.

### 26.2 Brother identity tests

Tests MUST cover:

-   same brother across successive saves;
-   renamed brother if names are mutable;
-   level-up;
-   stat increase;
-   perk acquisition;
-   new brother;
-   removed brother;
-   ambiguous identity.

### 26.3 Artifact invalidation tests

Tests MUST verify that:

-   unchanged brother + unchanged config reuses;
-   changed brother invalidates only that brother;
-   changed archetype invalidates only that role;
-   changed ceiling invalidates only dependent Fit artifacts;
-   changed trajectory engine invalidates trajectory-dependent
    artifacts;
-   changed report code does not invalidate numerical projections;
-   changed current rolls invalidate advisor-dependent artifacts;
-   new brothers are computed;
-   ambiguous brothers are computed.

### 26.4 Equivalence tests

For representative saves:

``` text
incremental output == clean full recomputation output
```

Comparison MUST include all numerical analysis fields, not merely final
classification.

### 26.5 Corruption tests

Tests MUST cover:

-   missing manifest;
-   malformed JSON;
-   unsupported schema;
-   incomplete artifact;
-   interrupted temporary manifest;
-   mismatched campaign.

All cases MUST safely fall back to recomputation.

------------------------------------------------------------------------

## 27. Mutation-testing expectations

The incremental subsystem SHOULD receive dedicated mutation coverage.

Particularly important mutation targets include:

-   relevant fingerprint field removed;
-   equality changed to inequality;
-   archetype hash omitted;
-   engine version omitted;
-   brother identity match relaxed;
-   ambiguous match incorrectly accepted;
-   cache hit incorrectly returned after dependency mismatch;
-   current rolls omitted from advisor dependency;
-   ceiling omitted from archetype fingerprint.

Surviving mutants in invalidation logic SHOULD be treated as high
priority because incorrect reuse can silently produce stale
recommendations.

------------------------------------------------------------------------

## 28. Implementation architecture

A dedicated module/package is recommended rather than embedding cache
logic directly in projection algorithms.

Possible structure:

``` text
bbtool/
  incremental/
    __init__.py
    identity.py
    fingerprint.py
    manifest.py
    dependencies.py
    cache.py
```

Responsibilities:

``` text
identity.py
    cross-save brother correlation

fingerprint.py
    deterministic normalization + hashing

manifest.py
    schema, load, validation, atomic write

dependencies.py
    artifact dependency declarations / input builders

cache.py
    reuse-or-compute orchestration
```

Projection/scoring/advisor modules SHOULD remain primarily responsible
for computation, not cache persistence.

------------------------------------------------------------------------

## 29. Suggested implementation phases

### Phase 1 - identity and manifest infrastructure

Implement:

-   campaign identity;
-   cross-save brother identity;
-   deterministic fingerprint helper;
-   manifest schema/load/write;
-   diagnostics.

No artifact reuse yet.

### Phase 2 - role projection reuse

Implement incremental reuse for the most expensive and best-defined
unit:

``` text
brother × archetype role projection
```

Add full-vs-incremental equivalence tests.

### Phase 3 - downstream artifacts

Extend reuse/invalidation to:

-   classification;
-   level-up advisor.

### Phase 4 - validation and tuning

Add:

-   `--full-recompute`;
-   cache-debug diagnostics;
-   optional `--verify-cache`;
-   profiling;
-   retention/pruning.

This phased approach is preferred because it allows correctness of the
dependency model to be proven before broadening cache reuse.

------------------------------------------------------------------------

## 30. Acceptance criteria

The feature is accepted when all of the following are true:

1.  A save analyzed without previous outputs produces the same results
    as today.
2.  An unchanged subsequent save reuses compatible projections.
3.  A change to one brother does not force unrelated brothers to be
    reprojected.
4.  A change to one archetype does not force unrelated archetypes to be
    reprojected.
5.  A change to a `ceiling` invalidates the affected archetype/stat Fit
    projections.
6.  A computation-engine change invalidates every artifact that depends
    on that engine.
7.  A report-only change does not invalidate numerical analysis.
8.  Ambiguous cross-save identity never causes reuse.
9.  Cache corruption falls back safely to full computation.
10. Incremental and forced-full outputs are numerically equivalent.
11. Console output clearly reports reuse and invalidation.
12. The user can force a clean recomputation.
13. Tests exercise dependency/invalidation behavior and mutation testing
    targets the subsystem.

------------------------------------------------------------------------

## 31. Design rule

The governing rule for the implementation is:

> **Reuse is permitted only when unchanged inputs are proven;
> recomputation is the safe default.**

The desired result is not merely a cache. It is a small dependency-aware
incremental analysis engine in which each projection artifact explicitly
knows what makes it valid.
