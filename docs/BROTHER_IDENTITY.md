# Brother identity contract

## Guarantee

`BrotherIdentity` is the exact pair of the native `CampaignIdentity` and the
non-zero unsigned 32-bit entity token stored by the save container immediately
before a structural `battleBrother` record. Its canonical text representation
is:

```text
campaign:<CampaignID>/entity:<native token>
```

The entity token alone is only campaign-local. The pair identifies the same
serialized player brother across compatible snapshots in that native campaign.
It is independent of name, title, `HumanOffset`, roster position, level, XP,
stats, perks, traits, injuries, and equipment.

`exact` means both native values were parsed from their validated structural
locations. As with `CampaignIdentity`, it does not turn finite game-generated
integers into a mathematical no-collision guarantee. Consumers needing a
stronger adversarial or globally unique identity require separately proven
evidence.

## Binary source and representation

The player roster is a count-prefixed sequence of structural `battleBrother`
records. The container writes a little-endian `uint32` entity token 17 bytes
before each record's 29-byte class signature. This field is outside the
Squirrel `actor`/`player` `onSerialize()` payload parsed by BB-Edit, which is why
the script-level audit did not reveal it.

The parser stores that raw value privately as `Brother.NativeEntityToken`.
`resolve_brother_identities()` combines it with the separately parsed exact
`CampaignIdentity` and returns one typed `BrotherIdentity` per save-local
`BrotherID`. `BrotherID = human:<HumanOffset>` remains the join key inside one
parsed dataset and has not changed meaning.

The typed value contains `campaign_value`, `native_token`, `basis`,
`confidence`, and `reason`; `value` is populated only for exact evidence. The
basis is `native_campaign_entity_token`.

## Conservative failure behavior

- A missing token is unavailable. A zero/malformed token is invalid. A
  truncated or structurally misplaced container header yields no token and is
  unavailable.
- A token duplicated in one parsed company roster is invalid for every brother
  carrying that token. No duplicate is selected by name or state.
- A missing or non-exact `CampaignIdentity` makes every brother identity
  unavailable, even when an entity token was parsed.
- Equal entity tokens in different exact campaign namespaces are different
  identities.
- Names, titles, `HumanOffset`, hidden `FutureRolls`, hire time, and observable
  state fingerprints are never substitutes.
- A newly appearing token is a new/unmatched brother. A disappearing token is
  simply absent; it is not reassigned to a similar recruit.

Identity-dependent reuse or durable state must be disabled for unavailable or
invalid records. There is no nearest-neighbor or probabilistic fallback.

## Progression, rollback, and lineage

The identity is expected to survive normal same-campaign save/load,
progression, renaming, equipment changes, injuries, roster movement, and copy or
rename of a save file. Loading an older save restores the brother identities
present in that snapshot. The pair establishes membership, not ordering or
ancestry: it cannot decide whether one save descends from another, and #80
remains responsible for lineage and rollback policy.

Dismissed or dead brothers disappear from later rosters. If an older save is
loaded, their historical token may reappear because the older snapshot contains
that brother; this does not prove that a later save descends from it.

## Evidence

The strongest available local evidence was an 18-save real sequence covering
two native campaigns (`CampaignID` 17110 and 7496). It contained 22 distinct
player-brother tokens and 150 total brother observations. Every surviving
brother retained the same token while `HumanOffset` changed repeatedly. The
sequence included XP/stat progression, level-ups, perk, trait, permanent-injury,
and equipment changes, new hires, and removals. New brothers received
previously unseen roster tokens; removed brothers were not reassigned. No
roster contained a duplicate token.

The checked-in `reference-save.sav` independently provides 12 more unique,
non-zero real roster tokens and locks the byte location in a deterministic
parser regression. Synthetic tests cover campaign namespacing, coincident
cross-campaign entity tokens, name/offset/progression independence, and every
failure class above.

Repository fixtures do not contain the 18-save sequence because the historical
run artifacts are not suitable source fixtures. They also do not prove a real
rename, an explicit manual rollback, or two independent campaigns with a
coincident entity token. Those limitations prevent
stronger empirical claims, but none require a heuristic fallback. Future
contradictory evidence must make the affected identity unavailable rather than
silently widening this contract.

## Public and incremental contracts

`AnalysisServiceResult.brother_identities` exposes the typed mapping to local
durable-state consumers. The public report-v1 JSON deliberately excludes both
`NativeEntityToken` and `BrotherIdentity`; therefore its schema and existing
within-dataset joins remain unchanged. A future public exposure requires a
versioned additive schema decision.

Current incremental artifacts continue to use conservative projection-state
fingerprints and do not use `BrotherIdentity`. This ticket therefore changes no
reuse or invalidation semantics, and `incremental == full recomputation`
remains unchanged. #81 may now use exact `BrotherIdentity` for campaign-local
persistent assignments without requiring #80 lineage semantics.
