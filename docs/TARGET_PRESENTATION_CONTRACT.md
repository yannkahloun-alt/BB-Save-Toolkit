# Target UI presentation contract

`bbtool.reference_analysis.v3` is the first production-facing foundation for
the validated Target UI. It adds one `bbtool.target_presentation.v1` logical
artifact while retaining the existing report payloads and renderer.

## Ownership

The backend owns every value in the presentation artifact. JavaScript must not
derive durable identity, BuildIdentity, Mechanical Facts, Run Health,
Recruitment potential, or validity from names or display strings.

Campaign and Brother identities preserve their typed confidence and failure
reason. Exact identity values are present only for exact native evidence.
Build display names remain labels; BuildIdentity is the durable join and
BuildDefinitionHash records the observed semantic definition.

Recruit rows use their array index only as a join to the same dataset snapshot;
this is not a durable RecruitIdentity. Each recruit/build relationship is one
of `prior_only`, `known_evidence_estimate`, or `unavailable`, and successful
results embed the already-versioned #110/#111 analytical payload unchanged.
The completed intrinsic slice of #128 is exposed under
`company.intrinsic_coverage` unchanged, including each build-local
`ArtifactSignature`. It does not imply assignment-aware depth or Company need.

## Coherence and validity

The presentation artifact binds the exact SHA-256 of every legacy component
file and a canonical hash of every presentation section. Its
`coherence_signature` hashes source-content provenance, effective configuration
fingerprints, component hashes, and presentation-content hashes. The validator also
checks duplicated semantic relations (health, Mechanics, builds, Brothers and
recruits), so accidentally combining files from separate runs is rejected even
if someone refreshes only the outer manifest hashes.

Exact Campaign and Brother identities are validated against their native
integer ranges and canonical namespace form. Recruitment wrappers and embedded
#110/#111 payloads are validated through every versioned field, including
state/result coherence, build and background joins, engine versions, evidence,
and distribution invariants. Intrinsic Company coverage is recomputed from the
bound roster, archetypes, Fit rows, classification configuration, and exact
Brother identities; the published rows and artifact signatures must match that
authoritative result exactly.

Artifact currency is separate from publication coherence. Role projection,
strategic classification and Level Advisor carry their own input signatures
from the #122 dependency domains. Reuse from an older computation generation
is valid when its result-local signature is still current; an unrelated state
revision does not stale it. Missing or malformed signature evidence rejects the
v3 dataset rather than manufacturing validity.

## Compatibility and pending semantics

The v2 report contract remains readable with its exact seven files. Historical
v1 remains deliberately unsupported and frozen at six files. Neither version's
name-based joins are redefined as durable IDs.

## Final integration

The same v1 presentation artifact now includes the completed additive domains.
Every Brother row has a resolved `assigned_build` payload with the #107
statuses (`current`, `definition_changed`, `deprecated`, `missing`,
`unassigned`, or explicitly `unavailable` when exact durable resolution was
not available). Build IDs and definition hashes are verified exactly; a display
name is never used as a remap key.

`advisors` publishes the complete existing backend-owned Advisor payload for
each Brother, including the AssignedBuild anchor/fallback, intrinsic Best Fit,
Primary/RunnerUp/ConditionalBranch, and both consequence sides. Its
result-local signature includes the resolved assignment, so a stale Advisor is
rejected without staling Fit or BestRole.

`company.intrinsic_coverage` and `company.intended_coverage` remain distinct
artifacts. The latter is validated by recomputation from resolved current
assignments and carries #166 holder, availability, fragility, and need-base
facts. `relevant_roster_need` is one separate mixed artifact per recruit; its
candidate evidence and authoritative intended-coverage/intrinsic-coverage
upstreams are recomputed and its signature must match. Unavailable intent is
explicit rather than interpreted as Company need.

These additions remain presentation data only: AssignedBuild changes can affect
Advisor, intended coverage, and Relevant Need, but never intrinsic Fit,
BestRole, intrinsic coverage, or recruitment-potential evidence.
