# AssignedBuild persistence and semantics contract

## Meaning and lifetime

`AssignedBuild` is the player's current intended build for one hired brother in
one campaign. It is campaign-global durable intent, not save-snapshot history:

```text
CampaignIdentity + BrotherIdentity -> BuildIdentity
```

Loading an older save does not restore an older assignment. When the same exact
`BrotherIdentity` appears in any compatible snapshot of the campaign, the
current durable assignment applies. Save ordering, ancestry, and rollback
reconstruction from #80 are therefore not required. A future historical-intent
feature may record events separately, but such events are not authority for the
current assignment.

Recruit candidates have no `AssignedBuild`. Intent can be created only after a
candidate becomes a roster brother with exact identity.

## Authoritative identity and value

The campaign namespace is the exact non-negative signed 32-bit native
`CampaignIdentity` from [`CAMPAIGN_IDENTITY.md`](CAMPAIGN_IDENTITY.md). Within
that namespace, the record key is the exact `BrotherIdentity` from
[`BROTHER_IDENTITY.md`](BROTHER_IDENTITY.md), whose canonical form already
contains the same campaign value:

```text
campaign:<CampaignID>/entity:<native token>
```

An implementation must validate that the embedded campaign value matches the
containing campaign namespace. The apparent repetition is an integrity check,
not a second identity mechanism. Only `confidence=exact` campaign and brother
evidence may read, create, change, clear, or consume an assignment.

The authoritative assignment value contains:

- `build_identity`: an explicit `BuildIdentity` valid under
  [`BUILD_IDENTITY.md`](BUILD_IDENTITY.md);
- `assigned_definition_hash`: the `BuildDefinitionHash` observed and accepted
  when the assignment was last assigned, reassigned, or explicitly
  acknowledged.

The acknowledged hash is retained unchanged until such an explicit operation.
It must not be silently refreshed while reading the current catalog. A display
name may be returned as derived presentation data, but it is never persisted as
authority.

Names, titles, build display names, save paths/names, map seed, `HumanOffset`,
save-local `BrotherID`, `BestRole`, observable state, and hidden `FutureRolls`
must never create, recover, or migrate an assignment.

## Durable representation

Issue #107 must add one bounded feature-local AssignedBuild state document
under `UserStateRoot`, using the existing `bbtool.app.user_state` substrate.
Its first supported domain schema is `bbtool.assigned-builds.v1`, with:

- the schema name and integer schema version;
- one optimistic, monotonic feature revision;
- campaign records keyed by exact `CampaignIdentity`;
- brother records keyed by canonical exact `BrotherIdentity`;
- the authoritative value fields `build_identity` and
  `assigned_definition_hash`.

The normalized representation must reject duplicate campaign or brother keys,
cross-namespace BrotherIdentity values, non-exact/malformed identities, invalid
BuildIdentity syntax, invalid definition hashes, unknown fields, and unbounded
payload growth according to the shared user-state limits. Catalog availability
is resolved at read/mutation time; it is not a reason to reject an otherwise
well-formed stored tombstone during migration or restore.

Feature migrations must be explicit one-version transformations. A migration
may preserve an ID, apply an explicit version-controlled successor mapping, or
leave the old ID unresolved. It must never infer a brother or build from a
display name or similar definition. Missing/failing migrations and unsupported
future schemas leave the original bytes untouched and fail visibly.

Generated report JSON, browser storage, incremental manifests, caches, and run
archives are derived or disposable data and are never assignment authority.
Normal output retention, cache clearing, rendering, updates, and uninstall do
not remove assignments. Backup and restore operate through the complete
`UserStateRoot` contract, including validation, feature-local migrations,
recovery backups, and fresh local revisions after restore.

## Build evolution and resolved read state

A read resolves the stored value against the current effective catalog without
mutating it:

| Stored/current state | Resolution |
| --- | --- |
| Same ID and same hash | `current` |
| Same ID and different hash | `definition_changed`; intent remains attached |
| ID explicitly deprecated but still known | `deprecated`; intent is preserved |
| ID absent from the effective catalog | `missing`; intent is preserved as a tombstone |
| Explicit successor mapping | Apply only through an explicit migration or user mutation |

A cosmetic rename retains the same ID and hash, so it remains `current`.
Splits, merges, replacements, and similar definitions never trigger fuzzy
remapping. Reassigning the same BuildIdentity against its current hash is an
explicit acknowledgement of a semantic redefinition; changing to another ID
is a new intent decision.

An unresolved/deprecated assignment remains readable and clearable but is not
a valid input to an intent-aware computation that requires a current build
definition. That computation must report unavailable/stale intent evidence or
use only a fallback explicitly owned by its domain contract; it must not
silently substitute `BestRole` while presenting the result as assigned-build
advice.

## Brother and campaign lifecycle

- Present exact brother: resolve and apply the campaign-global assignment.
- Dismissed, dead, or absent brother: retain the record dormant. Presentation
  may call it inactive/orphaned, but absence never deletes or remaps it.
- Older save where the same exact identity reappears: apply the current
  assignment, regardless of when the save was written.
- New/unmatched brother token: no assignment.
- Missing, invalid, or duplicate identity evidence: assignment behavior is
  unavailable for that parsed record; do not guess. Existing durable records
  remain untouched.
- New campaign, including one with the same map seed: a different exact
  `CampaignIdentity` has an independent namespace and receives no carry-over.
- The residual finite native-ID collision caveat is inherited from the identity
  contracts; no heuristic may be added locally to conceal contradictory
  evidence.

Explicit deletion scopes are distinct:

- clear one brother's assignment;
- clear all assignments in one exact campaign;
- reset the complete AssignedBuild feature;
- reset other user state;
- clear cache or generated output.

Only the first three affect assignments. Each uses the shared revision,
locking, backup, atomic-write, and stale-writer protections.

## Mutation contract

The browser is a requester and the local application service is the authority.
Assign, change/reassign, acknowledge, clear-one, and clear-campaign operations
are typed domain mutations, not generic JSON or filesystem writes. Each request
must:

1. provide an expected AssignedBuild feature revision;
2. validate exact CampaignIdentity and BrotherIdentity and their namespace
   agreement;
3. validate the requested BuildIdentity and current BuildDefinitionHash when
   assigning or acknowledging;
4. commit the complete canonical state through the shared feature lock and
   atomic-write path; and
5. return the new authoritative revision and canonical resolved assignment
   state.

A revision mismatch or lock failure is an explicit conflict/failure. There is
no last-writer-wins behavior. Clearing a nonexistent assignment is an
idempotent no-content success: return the unchanged authoritative revision and
resolved unassigned state, write no tombstone, and invalidate no artifact.

Every committed mutation emits normalized change evidence sufficient for the
central dependency layer: exact campaign and brother identity, old and new
assignment values, old acknowledged and current definition identity/hash state
as applicable, and the committed feature revision. The revision coordinates
writes but is not a global analysis validity key.

## Invalidation, recomputation, and publication

After a commit, invalidate only artifacts whose declared semantic dependencies
consume the changed intent, following
[`DEPENDENCY_SIGNATURES.md`](DEPENDENCY_SIGNATURES.md):

- the affected brother's intent-aware Level Advisor (#108);
- the affected brother's intended-build progress/checks;
- campaign intended-coverage aggregates and their declared downstream Company
  or Relevant Roster Need consumers;
- an in-game Advisor export only when configured to follow AssignedBuild.

The mutation does not invalidate or change raw projections, Brother x
Archetype Fit, `BestRole`/Best Fit, intrinsic Alternatives, intrinsic Company
coverage, recruit intrinsic potential, or Mechanical Facts. A campaign-level
clear invalidates the union of intent-aware consumers for assignments actually
removed, without staling intrinsic artifacts.

When the local application supports refresh, a successful write immediately
invalidates the prior desired generation, prevents queued/running pre-mutation
work from publishing, and requests recomputation for the newest durable state.
Otherwise it marks the affected intent-aware artifacts explicitly stale or
unavailable. Still-valid intrinsic artifacts may remain current.

Persistence success is never rolled back because recomputation fails. On a
refresh failure, the new assignment remains authoritative, valid unaffected
artifacts remain publishable, and any old affected Advisor/planning/export
artifact remains explicitly stale or unavailable. It must never be labeled as
reflecting the new assignment.

## Implementation ownership

#107 is the bounded implementation owner for this state, its typed read/write
operations, validation, resolved states, and normalized mutation evidence.
#108 owns intent-aware Advisor behavior and its exact fallback semantics. The
existing user-state, local-application mutation, dependency-signature, and
background-publication infrastructure supplies persistence, conflicts,
invalidation closure, and stale-result protection. No additional feature-local
persistence or invalidation mechanism is required.
