# Artifact dependency signatures

`bbtool/incremental/dependencies.py` is the registry for result-affecting input
categories and reusable artifact dependencies. It is intentionally a small
validity substrate, not a scheduler or a reactive framework.

## Contract

Each `ArtifactKind` declares direct normalized `InputKind` evidence and any
upstream artifacts whose results it consumes. `artifact_signature()` hashes
only that declared evidence using canonical UTF-8 JSON. Mapping order, machine,
filesystem path, display name, and an unrelated durable-state revision do not
affect the result. Stable object IDs are references, not proof that semantics
are unchanged; build-definition evidence remains required.

Missing declared evidence raises `MissingDependencyEvidence`. Callers must
therefore recompute or mark the artifact unavailable rather than guessing.
`changed_inputs()` identifies changed or missing categories, and
`recomputation_closure()` follows the complete registered graph before
optionally filtering requested outputs. This keeps the closure minimal while
preventing a caller from hiding an invalid upstream dependency.

An AssignedBuild-only change invalidates intent-aware Advisor and intended
Company consumers, but not role projections, intrinsic Fit, BestRole,
intrinsic Alternatives, or recruit intrinsic potential. A classification-only
change invalidates strategic classification while preserving role projections.
Each intended Company build signs resolved availability-relevant intent, its
effective build hash, roster membership, Fit-label thresholds, its roster Fit
inputs, and the other role inputs required to establish BestRole for assigned
holders. Unrelated assignment targets and role projections remain reusable.
Stored definition-changed, deprecated, or missing assignments are not accepted
as current intent evidence.

## Local publication boundary

Local-app scheduling separates two kinds of signature evidence.
`DesiredAnalysis.dependency_signatures` is a pre-analysis, campaign-scoped
snapshot of mutable #122 input categories. It hashes semantic build definitions
(without BuildIdentity/display names), classification configuration, and resolved
AssignedBuild intent for the represented campaign; storage revisions and other
campaigns are excluded. The controlling process recomputes that snapshot at
worker completion, and missing or changed evidence rejects stale publication.

`PublishedAnalysis.artifact_signatures` is different evidence: it is copied only
after success from the represented analysis result's authoritative
`IncrementalCache.publication_signatures()`. API freshness and debug-export
provenance expose both fields without overloading one map. This preserves the
#122 rule that an AssignedBuild-only change does not alter intrinsic role
projection signatures, while still preventing stale intent-aware publication.

## Adding an input or artifact

1. Add a typed enum member; do not use a display label or storage revision.
2. Add the artifact's exact direct inputs and upstream artifacts to
   `ARTIFACT_DEPENDENCIES`.
3. Add its semantic engine version to `ENGINE_VERSIONS` when applicable.
4. Define and test the normalized evidence supplied by the owning domain.
5. Test direct invalidation, transitive consumers, and unaffected artifacts.
6. Verify incremental output against an independent full recomputation.

The manifest fingerprint payloads use compatibility builders in this module.
Issue #122 deliberately bumped affected engines when semantic validity stopped
including build identity/display labels, so older manifests cannot be mistaken
for the new contract. The current Advisor remains intrinsically BestRole-anchored
until #108; #108 should move it to the declared intent-aware signature and
supply explicit `None` assignment/build evidence when unassigned.
Summary/classification and Advisor artifacts are independently cached and
validated even though presentation composes `LevelUpAdvice` into each summary.
