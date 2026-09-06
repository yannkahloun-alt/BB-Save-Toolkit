# Local application API

The interactive application runs with:

```powershell
python .\bb_analyze.py --serve-app --open-report
```

It binds an ephemeral port on `127.0.0.1` by default. `--app-port` may select a
specific local port, but the bind address is intentionally not configurable.
The legacy generated report, `--render-only`, `--serve-report`, and
`--open-report` after analysis remain derived, read-only surfaces.

## Authority and security

`bbtool.app.local_application.LocalApplication` exposes typed application
operations backed by the durable state, effective archetype catalog, and
background analysis coordinator. The HTTP adapter never reads or writes the
durable-state root directly and has no generic JSON, path-write, or filesystem
endpoint.

Every request must use the exact loopback `Host`. Every mutation additionally
requires all of:

- the exact application `Origin`;
- the unpredictable capability returned by same-origin `GET /api/v1/session`
  in `X-BBST-Session`;
- `POST` with `application/json`;
- a body no larger than 256 KiB;
- an operation-specific exact field set; and
- the expected durable feature revision.

No CORS permission is emitted. Responses disable caching, MIME sniffing,
referrers, framing, external scripts, and external objects. Request bodies,
save contents, and durable state are not logged.

The application shell is served only from the fixed repository-owned assets
`index.html`, `app.css`, and `app.js`. Request paths are never translated into
arbitrary filesystem paths.

## Versioned endpoints

All JSON responses use `bbtool.local-api.v1` and the envelope
`{schema, data, error}`. Errors contain a stable code and message, with bounded
field-level details where applicable.

| Method | Endpoint | Operation |
| --- | --- | --- |
| GET | `/api/v1/health` | Service health, toolkit/API version, bind policy |
| GET | `/api/v1/session` | Same-origin mutation capability |
| GET | `/api/v1/shell` | Least-privilege shell read model: save display context, freshness, public Run Health, and summarized current progress |
| GET | `/api/v1/company-brother` | Company + Brother read model from the latest publication plus current AssignedBuild intent |
| GET | `/api/v1/recruitment` | Recruitment read model with factual candidate/economics data plus bounded analytical availability/reasons |
| GET | `/api/v1/followed-save` | Inspect selected-save preference and availability |
| POST | `/api/v1/followed-save/select` | Select/change an existing `.sav` with expected revision |
| POST | `/api/v1/followed-save/forget` | Forget the selected save with expected revision |
| GET | `/api/v1/archetypes` | Effective roles, definition hashes, and base/user provenance |
| GET | `/api/v1/archetypes/export` | Export bounded user-owned archetype intent |
| POST | `/api/v1/archetypes/set-override` | Set a sparse shipped-role override |
| POST | `/api/v1/archetypes/set-disabled` | Enable/disable a shipped role |
| POST | `/api/v1/archetypes/reset-base` | Remove override and disabled intent |
| POST | `/api/v1/archetypes/reset-override` | Remove only the sparse override |
| POST | `/api/v1/archetypes/create-custom` | Create a validated custom role |
| POST | `/api/v1/archetypes/edit-custom` | Edit a custom role by BuildIdentity |
| POST | `/api/v1/archetypes/duplicate` | Duplicate an effective role into a new identity |
| POST | `/api/v1/archetypes/delete-custom` | Delete and retire a custom identity |
| POST | `/api/v1/archetypes/import` | Merge/replace a validated bounded export document |
| GET | `/api/v1/assigned-builds/{campaign}/{entity}` | Resolve authoritative assignment intent against the current catalog |
| POST | `/api/v1/assigned-builds/assign` | Assign a current BuildIdentity with expected AssignedBuild revision |
| POST | `/api/v1/assigned-builds/change` | Change assignment with expected AssignedBuild revision |
| POST | `/api/v1/assigned-builds/acknowledge` | Re-acknowledge the current definition hash with expected revision |
| POST | `/api/v1/assigned-builds/clear` | Clear one exact brother assignment with expected revision |
| POST | `/api/v1/assigned-builds/clear-campaign` | Clear one exact campaign namespace with expected revision |
| POST | `/api/v1/analysis/jobs` | Snapshot selected bytes/config and enqueue through #97 |
| GET | `/api/v1/analysis/jobs/{id}` | Status, progress, errors, and scheduled fingerprints |
| GET | `/api/v1/analysis/result` | Last publication, warnings, data, and freshness identity |

`GET /api/v1/shell` is a read-only composition endpoint for the global Target UI
shell. It does not create a second analytical source of truth. It projects only
the fields required by the shell from authoritative application/coordinator
state: the followed save's display name/availability/freshness, publication
availability/freshness, the public `bbtool.analysis_health.v1` contract, and a
current-job summary containing only job id, status, completed progress-event
count, and latest stage/status. It deliberately omits selected filesystem paths,
source/configuration/artifact fingerprints, job errors, progress `details`,
debug/reference provenance, hidden rolls, save bytes, and generic durable state.
The full job/result endpoints remain available to explicit consumers that need
their documented data.

`GET /api/v1/company-brother` is a read-only UI composition endpoint. Intrinsic
Fit, Best Fit, Company coverage, durable identity, and Mechanical Facts are
projected from the latest successful backend publication rather than inferred in
JavaScript. Current AssignedBuild is re-read from durable state so a successful
intent mutation becomes visible immediately; if that intent differs from the
publication used for Company intended coverage, the response marks
`company.intent_fresh=false` until refreshed analysis publishes. The endpoint
also exposes the AssignedBuild revision and exact campaign/entity mutation
address only when authoritative identity evidence exists. The UI read model
keeps BuildIdentity and display/status semantics but deliberately strips
BuildDefinitionHash / ArtifactSignature metadata and AssignedBuild definition
hashes, because those validity fingerprints are internal analytical provenance
and are not required by the Company/Brother frontend. It also does not expose
FutureRolls, source/configuration/artifact fingerprints, filesystem paths,
diagnostic samples, save bytes, or generic durable state.

`GET /api/v1/recruitment` keeps factual recruit identity/economics separate from
analytical availability. Each candidate retains raw build-indexed `potential` rows
for partial/future evidence and also publishes `potential_availability` as
`available`, `partial`, or `unavailable` with a bounded backend reason. Uniform
unavailability may therefore be rendered once at candidate level without the
frontend inferring semantics from repeated display rows. `relevant_need` publishes
its own bounded reason (`candidate_potential_unavailable`,
`candidate_potential_incomplete`, `company_intent_coverage_unavailable`, or the
combined/fallback states) and may preserve the upstream candidate-potential reason.
Nullable analytical percentages remain unavailable values rather than numeric zero.

Analysis handlers never execute parsing or projection. The application reads
the explicitly selected save into immutable bytes and submits a
`DesiredAnalysis` to `AnalysisCoordinator`. Job responses carry a scoped
`dependency_signatures` snapshot of #122 input evidence used to reject a worker
whose mutable semantic inputs changed while it ran. Before success,
`artifact_signatures` is `null` because no produced result has been published.
A successful publication then carries both that represented dependency snapshot
and the distinct analysis-owned `artifact_signatures` returned by
`IncrementalCache.publication_signatures()`. Result freshness and debug-export
provenance copy those same publication fields; they do not reconstruct them in
the HTTP/UI layer. Source and configuration fingerprints, generation,
publication state, and structured failure remain separate metadata. A failed
refresh leaves the service alive and preserves the last successful publication;
that older result is marked stale when it no longer represents the newest job.
Published fingerprints and timestamps are persisted through the #95
`last-success` feature without exposing its storage location.

Changing a followed save returns stale/unavailable freshness immediately.
Archetype mutation responses return the committed revision, canonical effective
catalog, definition hashes, and an explicit `request_analysis` recompute state.
The recovery-only exception is `reset-base` while `GET /api/v1/archetypes`
reports shipped override/disabled conflicts: one explicitly selected conflicting
identity may be removed under the expected revision even when other shipped
conflicts remain. That successful response continues to expose the remaining
`catalog_conflict` and no effective roles until recovery is complete. Unrelated
catalog validation failures still block the write. `GET /api/v1/archetypes/export`
reads bounded user-owned durable records directly and remains available during
this recovery state so the player can preserve intent before reset/recreation.
After any committed source/configuration mutation, the application invalidates
the #97 desired generation and cancels queued/running pre-mutation work so it
cannot publish. The previous successful publication remains available as
explicitly stale until a new requested generation succeeds.
The application command boundary serializes the short save/config snapshot and
job submission step against durable mutation commit plus invalidation. Analysis
result/status reads use the same boundary, so they cannot observe a committed
mutation before its publication invalidation. Analysis itself remains
asynchronous in the worker process and never holds this lock.
The persisted selection is watched and stabilized as documented in
[`SAVE_WATCHING.md`](SAVE_WATCHING.md). Followed-save and result reads expose
the detected/stabilizing/queued/analyzing/current/unavailable/failed freshness
states through the existing responses. No generic filesystem endpoint is
introduced. Level Up and Recruitment workspace bodies remain owned by #116 and
#117.
