# Company planning contract

The currently implemented Company planning artifact is intrinsic coverage only.
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

AssignedBuild is not yet available. Consequently the intrinsic artifact does
not emit assignment availability, intended coverage, mismatch, fragility,
Company need, gap, redundancy, desired slots, or a Company score. Those outputs
remain blocked on #107 and must be separate validity domains when implemented.
