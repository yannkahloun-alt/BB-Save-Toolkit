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
file. Its `coherence_signature` hashes source-content provenance, effective
configuration fingerprints and those component hashes. The validator also
checks duplicated semantic relations (health, Mechanics, builds, Brothers and
recruits), so accidentally combining files from separate runs is rejected even
if someone refreshes only the outer manifest hashes.

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

The foundation does not include AssignedBuild (#107), evolved intent-aware
Advisor output (#108), intended Company Planning/gap semantics (remaining
#128), or Relevant Roster Need (#112). Those fields require a future additive
presentation-contract version after their domain contracts and implementations
are complete.
