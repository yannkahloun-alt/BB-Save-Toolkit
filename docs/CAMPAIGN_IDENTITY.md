# Campaign identity contract

## Guarantee

`CampaignIdentity` is the non-negative signed 32-bit `CampaignID` serialized by
vanilla `scripts/states/world/asset_manager.nut`. Battle Brothers creates this
native run token independently from `SeedString`, writes it with `writeI32`,
and restores it with `readI32`.

An exact `CampaignIdentity` establishes the game's native campaign-membership
namespace. It does not establish that two save byte streams are equal, that one
save descends from another, or that one snapshot is newer. Exact snapshot
equality uses the save-content SHA-256. Ordering, rollback, and branch ancestry
belong to the separate save-lineage contract in #80.

`exact` describes the provenance and parsing of the native token, not a claim
that a finite randomly generated integer is mathematically collision-free. A
collision between two independently created campaigns is possible in
principle and cannot be detected from the two `CampaignID` values alone.

## Representation and availability

The typed value is `CampaignIdentity(value, basis, confidence, reason)`:

- `value` is an integer in `0..2_147_483_647` only when confidence is `exact`;
- `basis` is `native_campaign_id`;
- `confidence` is `exact`, `unavailable`, or `invalid`;
- `reason` records the conservative failure classification.

The parser accepts one uniquely validated asset-manager serialization tail.
No structurally valid candidate produces `unavailable/not_found`; multiple
candidates produce `invalid/ambiguous`; and a negative signed value produces
`invalid/negative_value`. Corrupt or unsupported layouts are unavailable.
Zero is valid under the vanilla non-negative contract.

There is no fallback to map seed, company name, roster contents, save filename,
path, timestamps, or newest output. Consumers must disable identity-dependent
behavior when confidence is not `exact`.

## Stability and boundaries

Because the value is serialized game state:

| Case | CampaignIdentity result | What it proves |
| --- | --- | --- |
| Rename or byte-for-byte copy | unchanged | same native campaign namespace and same snapshot |
| Manual, quick, or autosave from one run | expected unchanged | same native campaign namespace only |
| Older save or rollback in one run | expected unchanged | same campaign; no ordering or ancestry |
| Copy to another machine | unchanged | identity travels with save content |
| New run with the same map seed | independently generated | map seed cannot join campaign state |
| Missing, malformed, negative, or ambiguous token | not exact | campaign-dependent behavior unavailable |

The expected same-run and same-seed behavior follows directly from vanilla's
assignment and serialization contract. It is also covered by deterministic
source-layout tests. It must not be reinterpreted as proof from a broad sample
of real campaigns.

## Persistence namespace

Incremental manifests serialize `bbtool.campaign_identity.v1` and are eligible
for automatic discovery and pruning only when their exact native value matches
the current exact value. Save path and filename are provenance only. Legacy-v1
manifests and malformed or non-exact evidence are not automatically discovered
or pruned. Artifact-specific dependency signatures remain the authority for
whether analytical values may be reused after a manifest is selected.

This namespace is suitable for campaign-local durable state under the game's
native identity semantics. Consumers that cannot tolerate the residual finite
ID collision risk need additional independently proven evidence; they must not
silently substitute heuristics. The value is currently kept out of the public
report-v1 dataset and exposed through the typed application-service result, so
normal reports disclose no new campaign token. It is an opaque game-run token,
not user-authored personal data, but durable consumers should still treat it as
linkable local state and avoid unnecessary public disclosure.

## Evidence completed for #79

- Vanilla source semantics: `CampaignID` and `SeedString` are separate fields;
  campaign creation assigns `CampaignID` independently; serialization writes
  and restores the signed 32-bit value.
- The checked-in approved real fixture
  `tests/fixtures/full_preview/reference-save.sav` parses deterministically as
  exact CampaignID `25809`; a renamed byte-for-byte copy yields the same value.
- Synthetic source-layout tests hold CampaignID constant while unrelated
  serialized bytes change, and hold map seed constant while independent
  CampaignIDs differ.
- Manifest tests prove same-identity discovery across path/name variants,
  different-identity separation even when a map-seed field is equal, and safe
  refusal for legacy, unavailable, invalid, or malformed evidence.
- Incremental boundary tests prove a same-path new campaign is not selected and
  that a renamed save remains discoverable within the same namespace.

Repository assets do **not** contain a real successive-save set from one
campaign, real manual/quicksave/autosave/rollback variants, two independently
created campaigns sharing one map seed, or a broad independent-campaign sample.
Accordingly, the repository cannot empirically measure real-save stability,
zero frequency, or collision frequency for those cases. Acquiring such saves
would strengthen empirical confidence but does not justify different machinery
from the native token. If future evidence shows duplicate native IDs for
distinct campaigns, affected identity-dependent state must remain separated or
become unavailable under a separately specified contract; it must not be
joined heuristically.

## Downstream status

#79's campaign-namespace prerequisite for #77 is satisfied. #77 remains a
separate investigation of a campaign-local stable brother token and must not
use `HumanOffset`, name, or save-state similarity as exact identity. #80 remains
responsible for lineage. The toolkit-managed fallback proposed in #82 is not
needed for normal supported saves.
