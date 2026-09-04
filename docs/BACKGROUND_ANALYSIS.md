# Background analysis coordination

`bbtool.app.analysis_coordinator` is the scheduling boundary for the local web
runtime. It does not expose HTTP routes, watch files, write reports, or define
analytical dependencies.

## Job model

Each desired analysis contains immutable save bytes, the normalized effective
archetypes and classification configuration accepted by the analysis service,
and artifact dependency signatures supplied by the dependency owner. Source
SHA-256 and normalized configuration fingerprints are calculated before work is
scheduled. Behavior-affecting execution options participate in desired-job
identity. Compatible incremental cache context does not: it is a disposable
optimization and cannot change authoritative output, though its mutable
manifest is still snapshotted for a scheduled worker. The controller runs at
most one worker process and retains at most
one pending request; a newer request deterministically supersedes the pending
request it replaces. Duplicate notifications for identical inputs coalesce.

`stabilizing` is an explicit pre-queue state for a future filesystem adapter.
Only that adapter may decide when bytes are stable and call `mark_stable`;
stabilization policy is not implemented here.

Analysis runs through `analysis_service.analyze_save` in a spawned process.
Progress crosses the process queue and is retained on the job independently of
any HTTP request. Worker startup errors, structured analysis errors, and process
crashes become job failures rather than exceptions in the controlling
application. A crashed newest job receives one bounded restart by default.

## Publication and failure

A completed result is publishable only when all of these remain true:

1. its job is still the newest desired generation;
2. its returned source and effective-configuration fingerprints exactly match
   the scheduled inputs; and
3. the injected artifact-validity callback proves its dependency signatures
   still current.

Failure of any check marks the result superseded. Partial messages never form a
successful publication. The last successful publication is replaced atomically
only after all checks pass.

The coordinator deliberately does not use a durable user-state revision as a
global invalidation key. Until #122 supplies the central registry, callers
inject two narrow operations: proof that scheduled artifact signatures are
current, and selection of independently still-valid artifacts after a failed
refresh. If either operation fails, validity fails closed. A refresh failure
does not roll back durable state or erase the last successful result; only
artifacts explicitly revalidated by the injected dependency boundary may be
offered as retained current artifacts.

Shutdown cancels queued/stabilizing work, terminates the active child, and never
publishes its partial result. #98 should expose this state machine without
running analysis in request handlers. #99 should submit immutable bytes and own
source stabilization/coalescing notifications.
