# Incremental cache campaign-boundary study (#83)

## Conclusion

The current manifest lookup uses an absolute save path as a discovery scope,
not as an analytical cache key. A manifest from an unrelated campaign can be
selected when a slot such as `quicksave.sav` is reused. Its artifacts are
accepted only when normalized brother state, role/configuration inputs, and
semantic engine versions match.

That makes present cross-campaign artifact reuse content-addressed
memoization, not brother-identity reuse. The study found no numerical
counterexample: equal cache inputs imply equal current role, Advisor, and
summary calculations. It did find one current-output defect. Temporary injury
display text was stored in a summary even though temporary injuries correctly
do not enter the long-term projection fingerprint. An otherwise reusable
summary could therefore show an old injury. The fix rehydrates current-save
display fields while retaining the analytical artifact.

The current risk classification is:

- numerical correctness: protected by the audited fingerprints and ambiguity
  fallback;
- current display correctness: the stale injury defect was fixed in #83;
- observability: a selected manifest can be described as "previous" despite
  belonging to another campaign;
- performance: path scoping can miss reusable content after a rename/copy and
  can examine an unrelated manifest before rejecting its entries;
- history semantics: unsupported by this cache and must not be inferred from
  selection order.

The invariant remains `incremental == independent full recomputation`.

## Current selection and reuse flow

1. `find_previous_manifest()` recursively lists schema-v1 manifests outside
   the new run directory, orders them by filesystem mtime, and returns the
   newest manifest whose `source_save_path` equals the resolved current path.
2. `IncrementalCache` indexes that one manifest by
   `brother_projection_fingerprint()`. Exactly one state match is required;
   zero recomputes and more than one is ambiguous and recomputes.
3. A role artifact additionally requires the complete normalized role hash and
   `ROLE_PROJECTION_ENGINE_VERSION`.
4. Advisor and summary artifacts require their own full input hashes and
   engine versions. A reused summary carries its Advisor artifact into the new
   manifest so an immediate successor remains complete.
5. The newest run writes a fresh manifest. Pruning removes only manifests for
   the same source path beyond the newest ten; output/archive retention is a
   separate operation and does not remove those retained manifest sources.

The trajectory cache is different: `_TRAJECTORY_CACHE` is bounded,
process-local memoization and is not serialized in the incremental manifest.
Its `missing_entry` counter means a trajectory key was absent from that
in-process dictionary. It does not mean that a persisted manifest entry was
lost. A healthy identical warm run should reuse persisted role/summary
artifacts and consequently perform no trajectory lookup at all: zero hits and
zero misses is expected, rather than a trajectory hit.

## Deterministic reproductions

`tests/unit/test_incremental_campaign_boundaries.py` constructs all inputs and
manifests locally; it is network-free and independent of clock resolution.

### Same input, same configuration, same path

Run A computes one role and one summary and writes a complete manifest. Run B
discovers that exact manifest, produces output equal to Run A, reuses one role
and one summary, computes neither, and makes no repeated role-projection call.

The focused real-engine micro-run (one level-1 brother, one three-stat role) on
2026-09-03 measured 0.0146 s cold and 0.000134 s warm (about 109x for this
small controlled case). These timings are illustrative, not a performance
baseline. The deterministic evidence is the call count and artifact counters:

```text
Run A: role 0 reused / 1 computed; summary 0 / 1; Advisor 0 / 1
Run B: role 1 reused / 0 computed; summary 1 / 0; Advisor 0 / 0
Run A incremental fallbacks: no_previous_manifest=3
Run B incremental fallbacks/conservative recomputations: 0
output equality: true
```

The isolated real-engine measurement made one cold trajectory lookup and no
warm trajectory lookup: Run A had zero hits, one `missing_entry` miss; Run B
had zero hits and zero misses. Run B does not call the trajectory engine, so
widespread `missing_entry`
results on a truly identical immediate rerun would indicate failure before or
at persisted role-artifact reuse. The 2026-09-02 evidence in the ticket is
consistent with expected cold behavior (`missing_entry` is the in-process
trajectory cache) unless its run can also demonstrate a compatible selected
manifest and identical artifact inputs.

### Same path, different campaign

The reproduction replaces the bytes at `quicksave.sav`. The Campaign A
manifest is selected solely because the resolved path matches. A changed
brother state has no state-hash match, so the Campaign B role and summary are
computed. No stale numerical artifact is returned.

### Identical state in unrelated campaigns

Two synthetic brothers use different display names and save-local offsets but
identical result-affecting state. The second campaign reuses the first role and
summary. Current display identity is rehydrated and the analytical values equal
independent computation. This is safe content-addressed reuse: neither the name
nor `HumanOffset` is asserted to identify the brother across saves.

If a single prior manifest contains two brothers with the same state hash,
existing ambiguity handling refuses both rather than guessing. That is more
conservative than pure memoization requires, but preserves the current brother
identity boundary.

## Fingerprint-completeness audit

| Artifact | Result-affecting inputs | Current coverage | Finding |
| --- | --- | --- | --- |
| Role projection row | raw eight stats; stars; level and pending level point; exact trait and permanent-injury IDs/effects; role Fit configuration including curves, ceiling and weights; owned perks used only by compatibility; projection semantics | brother state hash; complete normalized role hash; role engine version | Complete for current implementation. `CurrentRolls`, background ID, trait labels and perk list are conservative extra invalidators. Temporary injuries and hidden `FutureRolls` are correctly absent. Current identity/background labels are rehydrated. |
| Advisor | current rolls and pending level point; same natural state and intrinsic effects; baseline role ordering; all role definitions; Advisor/trajectory semantics | full brother state; all role hashes; Advisor engine version; role artifacts separately versioned | Complete for current implementation. A future player `AssignedBuild` becomes an Advisor dependency if it can select/change the anchor role or recommendation. It does not belong in intrinsic Fit or `BestRole`. |
| Summary/classification | selected role rows and ordering; classification thresholds/display bands; current effective stats; Advisor result; current roster display fields; summary/classification semantics | full brother state; all role hashes; full classification configuration; summary engine version | Numerical dependencies are complete. Current temporary-injury text was not a hash input and was not rehydrated; fixed by rehydrating `Perks`, `Traits`, and `Injuries` from the current parsed brother. |

`brother_projection_state()` currently includes owned perks even though natural
Fit excludes perk stat modifiers. That is required today because role rows
contain perk-compatibility output and summaries contain current effective
combat stats. Splitting those dependencies is a future optimization, not a
correctness fix.

Reference dictionaries are an implicit semantic input. Changes to their effect
interpretation or source-derived values must continue to bump the affected
semantic engine version; generated cache file identity itself should not become
a per-run result key.

## Post-#79 campaign-aware behavior

#79 established the game's serialized signed 32-bit `CampaignID` as the exact
native campaign/run token in the product contract. It is assigned independently
of `SeedString`, serialized and restored, and remains stable across renamed,
copied, autosave, quicksave, manual-save, rollback, and cross-machine copies.
Campaign membership still proves neither snapshot equality nor lineage.

#123 owns parsing and exposing that value. After it lands, a new manifest
schema should record an explicit versioned `CampaignIdentity` based on the
native `CampaignID`:

- discover the newest compatible manifest within the same CampaignIdentity;
- treat path only as provenance and an optional lookup optimization;
- retain exact artifact fingerprints as the authority for computation reuse;
- prune by CampaignIdentity, not `source_save_path`;
- keep rollback/branch reuse allowed for pure deterministic artifacts when
  their complete input hashes match;
- add lineage constraints only to future history-sensitive state defined by
  #80;
- if CampaignID is unavailable, malformed, or contradictory, disable
  campaign/history-dependent behavior without substituting map seed, path,
  timestamp, company name, or roster similarity.

Cross-campaign content-addressed memoization could remain safe in a future
global artifact store, but it should be named and implemented explicitly. A
campaign-scoped "previous manifest" should not silently perform that role.

## Follow-up ownership

- #123: parse and expose native CampaignID; prerequisite for changing manifest
  discovery.
- #125: migrate manifest discovery and pruning to CampaignIdentity after #123,
  including schema compatibility and missing-identity fallback. This is
  intentionally separate from the parser.
- #80: define ancestry/rollback semantics only for history-sensitive state.
- #81: include `AssignedBuild` in the Advisor cache contract if it affects the
  anchor/recommendation; leave intrinsic Fit and `BestRole` independent.

No trajectory-cache persistence ticket is justified by this study. Persisted
role artifacts already avoid the expensive calls on a compatible warm run, and
`missing_entry` currently describes expected process-local cold behavior.
