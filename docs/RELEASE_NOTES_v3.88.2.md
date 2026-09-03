# Battle Brothers Save Toolkit v3.88.2

## Highlights

- Makes normal cold Fit analysis substantially faster by leaving costly Python
  heap allocation tracing off unless `--measure-python-heap` is requested. On
  the validated two-brother × 11-archetype representative workload, analysis
  improved from 11.924 s to 2.399 s (4.97× faster), while the slowest projection
  improved from 1.043 s to 0.166 s (6.28× faster).
- Persists and reuses the exact deterministic projection-validation oracle with
  compatible role artifacts. Identical warm incremental runs can now validate
  without rebuilding cold-sized Fit trajectories.
- Retries transient reference downloads three times with bounded backoff and
  continues to prefer an already-valid complete local cache, without weakening
  TLS certificate verification.
- Fixes save-visible reference and parser failures caused by false circle
  candidates, roster item-state sizing, and variable-length recruit equipment.
  On the validated same-save reproduction, unresolved references fell from 12
  to 0, recoverable parsing failures from 11 to 0, and result-affecting warnings
  from 22 to 0.
- Uses the native serialized `CampaignID` as exact `CampaignIdentity` evidence
  for incremental manifest discovery and retention. Renamed or copied saves
  from the same campaign retain eligible reuse, while a reused path cannot
  select another campaign's manifest. Missing or uncertain identity disables
  campaign-dependent behavior conservatively.

## Compatibility and semantics

The release also rehydrates current-save display fields during safe analytical
reuse, adds bounded projection diagnostics, and clarifies trajectory sampling
and cache ownership. It introduces no intentional redesign of Fit, projections,
classification, or Level-Up Advisor semantics. The parser/reference correction
does not claim a projection-runtime improvement; its historical cache fallback
and recomputation counters had a separate cause.
