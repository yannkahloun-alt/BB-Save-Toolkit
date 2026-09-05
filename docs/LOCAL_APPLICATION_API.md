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
address only when authoritative identity evidence exists. It does not expose
FutureRolls, source/configuration fingerprints, filesystem paths, or diagnostic
samples.

Analysis handlers never execute parsing or projection. The application reads
the explicitly selected save into immutable bytes and submits a
`DesiredAnalysis` to `AnalysisCoordinator`. Job and publication responses carry
the represented source fingerprint, both configuration fingerprints, artifact
signatures, generation, publication state, and structured failure. A failed
refresh leaves the service alive and preserves the last successful publication;
that older result is marked stale when it no longer represents the newest job.
Published fingerprints and timestamps are persisted through the #95
`last-success` feature without exposing its storage location.

Changing a followed save returns stale/unavailable freshness immediately.
Archetype mutation responses return the committed revision, canonical effective
catalog, definition hashes, and an explicit `request_analysis` recompute state.
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
