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

## Versioned endpoints

All JSON responses use `bbtool.local-api.v1` and the envelope
`{schema, data, error}`. Errors contain a stable code and message, with bounded
field-level details where applicable.

| Method | Endpoint | Operation |
| --- | --- | --- |
| GET | `/api/v1/health` | Service health, toolkit/API version, bind policy |
| GET | `/api/v1/session` | Same-origin mutation capability |
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
| POST | `/api/v1/analysis/jobs` | Snapshot selected bytes/config and enqueue through #97 |
| GET | `/api/v1/analysis/jobs/{id}` | Status, progress, errors, and scheduled fingerprints |
| GET | `/api/v1/analysis/result` | Last publication, warnings, data, and freshness identity |

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
itself remains asynchronous in the worker process and never holds this lock.
No watcher or automatic source stabilization is implemented here; those belong
to #99. The complete Target UI belongs to #100.
