# Build identity contract

Archetypes have two separate identifiers for downstream durable state:

- `BuildIdentity` is the explicit `id` stored in an archetype catalog. It is a
  lowercase ASCII snake_case identifier matching
  `^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$`, unique within the
  effective catalog, stable across cosmetic renames, and never reused for a
  different logical build after retirement.
- `BuildDefinitionHash` is `sha256:` plus the SHA-256 of canonical JSON for the
  semantic build definition. It detects definition evolution without changing
  the logical identity.

`name` is display-only. The definition hash excludes `id`, `name`, and the
engine-derived `fit` and `projected_curve` fields specifically inside stat
definitions. It includes all other current definition fields, including stat
target/baseline/weight/ceiling, perk requirements and recommendations,
affinities, conflicts, and unknown/future explicit semantic fields by default.
Object keys are canonicalized; only the known top-level set-like collections
`perks.required`, `perks.recommended`, and `perk_conflicts` are sorted.

The reusable API is `bbtool.build_identity.build_identity()` and
`build_definition_hash()`. `build_identity()` returns `None` for an id-less
legacy role. Existing external `--targets` files therefore remain valid for
ordinary analysis, but they have no authoritative durable identity until the
owner explicitly adds a valid, unique ID. Consumers must not derive or
fuzzy-match an ID from `name` or from similar definitions.

Downstream persistence should store both the BuildIdentity and the observed
BuildDefinitionHash. The expected states are:

- same ID and hash: unchanged definition, including cosmetic rename;
- same ID and changed hash: same logical build with changed semantics;
- missing ID from the current catalog: preserve an unresolved/tombstoned
  assignment rather than remapping it;
- split, merge, or replacement: require explicit migration metadata or user
  action.

BuildDefinitionHash is metadata for semantic comparison. It does not replace
the existing artifact-specific incremental fingerprints, whose complete inputs
and engine versions remain authoritative for cache validity. The v1 report
continues to use display-name joins; migration of public joins belongs to a
future report contract.
