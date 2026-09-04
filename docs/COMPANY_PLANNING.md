# Company planning contract

Company planning exposes two structurally separate artifacts: intrinsic coverage
and intent-aware coverage. Intrinsic coverage remains unchanged.
For every effective authoritative `BuildIdentity`, it exposes deterministic:

```text
BuildIdentity
BuildDefinitionHash
ArtifactSignature
ViableCount / GoodCount / PremiumCount
ViableBrothers[]
TopFitPct / SecondFitPct
```

Depth uses the existing `classification.display.viable_fit`, `good_fit`, and
`premium_fit` thresholds. `TopFitPct` and nullable `SecondFitPct` describe the
best two intrinsic fits even when they are below viable. Viable evidence carries
`BrotherIdentity` when production has one, the current-save `BrotherID`, Fit
percentage, and Fit label. Names are excluded from identity and deterministic
tie-breaking.

The artifact depends only on current roster membership, the corresponding
Brother × Build intrinsic projection signatures, and the intrinsic Company
coverage engine version. Its signature ignores display labels, mutable player
state, and unrelated builds. The signature includes the three configured depth
thresholds, so a threshold change invalidates
coverage without invalidating the reusable intrinsic Fit rows that feed it.

Id-less legacy archetypes remain supported by ordinary analysis, but are omitted
from durable Company coverage because no authoritative identity may be derived
from a display name.

Intent-aware coverage consumes only resolved `current` AssignedBuild records
whose acknowledged definition hash still matches the effective build. Per
BuildIdentity it exposes assigned holder counts/evidence, viable holder depth,
free (`unassigned`) and contested (`assigned_elsewhere`) viable backups, and
keeps the assigned Fit beside independently computed Best Fit. A mismatch is
inspectable evidence and never rewrites either value.

`FragilityFacts` contains orthogonal booleans for `NoIntent`,
`AssignedButNoViableHolder`, `SinglePointOfFailure`, `ContestedBackupOnly`,
`FreeBackupAvailable`, and `MultiHolderDepth`. `NeedBases` is the deterministic
machine-readable subset approved for recruitment's future #112 layer:
`assigned_but_no_viable_holder`, `single_point_of_failure`, and
`contested_backup_only`. No intent produces no need merely because intrinsic
depth is scarce. No desired slots, target composition, redundancy count, or
generic Company score is inferred.

Its per-build signature includes normalized availability-relevant intent, exact
roster membership, that build's definition hash, the three Fit-label thresholds,
that build's roster projections, all projections needed to establish BestRole
for its assigned holders, and the intent-aware Company engine version. Thus an
elsewhere-to-elsewhere reassignment for a non-viable brother or an unrelated
role change when there is no assigned holder leaves the target build valid,
while availability, holder, and mismatch dependencies invalidate it. An
assignment-only mutation therefore
changes intended coverage (and downstream Relevant Roster Need) while leaving
Fit, BestRole, and intrinsic Company coverage byte-for-byte unchanged.
