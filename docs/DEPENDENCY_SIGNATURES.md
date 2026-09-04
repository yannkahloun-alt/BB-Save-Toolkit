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

## Adding an input or artifact

1. Add a typed enum member; do not use a display label or storage revision.
2. Add the artifact's exact direct inputs and upstream artifacts to
   `ARTIFACT_DEPENDENCIES`.
3. Add its semantic engine version to `ENGINE_VERSIONS` when applicable.
4. Define and test the normalized evidence supplied by the owning domain.
5. Test direct invalidation, transitive consumers, and unaffected artifacts.
6. Verify incremental output against an independent full recomputation.

The existing manifest fingerprints retain their serialized payloads through
compatibility builders in this module. The current Advisor remains intrinsically
BestRole-anchored until #108; #108 should move it to the declared intent-aware
signature and supply explicit `None` assignment/build evidence when unassigned.
Summary/classification and Advisor artifacts are independently cached and
validated even though presentation composes `LevelUpAdvice` into each summary.
