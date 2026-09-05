# Hosted readiness and threat-model delta

## Status and decision boundary

This document records the design boundary for a possible future hosted edition.
It does **not** authorize or implement hosting, and it does not change the
local-first application. A hosted implementation starts only after an explicit
product go decision and the owner artifacts in this document are supplied.

The local product remains a single-user application that reads an explicitly
selected local save, stores bounded per-user state on the same machine, runs one
analysis worker process, and serves a loopback-only API and frontend. The
security assumptions of that design must not be stretched to cover an
Internet-reachable service.

## Existing boundaries that are reusable

The following repository contracts are useful hosted foundations because they
are already independent of the local HTTP transport or of a filesystem path as
analytical identity:

- `bbtool.app.analysis_service.AnalysisServiceRequest` accepts immutable save
  bytes, normalized effective archetypes, classification configuration,
  execution options, and optional compatible cache state. `SaveSource.name` is
  display/provenance only.
- `bbtool.app.analysis_service.AnalysisServiceResult` returns structured data,
  errors, warnings, timings, progress, content/configuration fingerprints,
  `CampaignIdentity`, `BrotherIdentity`, and result-local analytical state.
- `bbtool.app.analysis_coordinator` already separates CPU-heavy analysis from a
  request handler and publishes only a result whose source, configuration, and
  artifact-validity evidence still match the desired generation.
- Versioned public/report, Target-presentation, BuildIdentity,
  CampaignIdentity, BrotherIdentity, and dependency-signature contracts can be
  reused at a transport boundary without changing their analytical meaning.
- The presentation builders in `bbtool.app.target_presentation`,
  `bbtool.app.company_brother_view`, `bbtool.app.level_up_view`, and
  `bbtool.app.recruitment_view` are reusable read-model boundaries where their
  existing exposure rules remain appropriate.
- The static frontend assets under `bbtool/app/static/` provide reusable screen
  structure, styles, and interaction patterns. Their local API URLs,
  same-origin session bootstrap, and local capability handling are adapters to
  replace rather than hosted authentication mechanisms.
- `tests/fixtures/reference_analysis/` provides deterministic analysis,
  configuration, health, roster/recruit, role-fit, and Target-presentation
  reference artifacts. `tests/fixtures/full_preview/` and the browser/UI tests
  provide additional end-to-end presentation evidence. These are reusable
  equivalence fixtures for future worker, API, and frontend adapters.

The local HTTP adapter itself is **not** a hosted security boundary. Its
loopback Host/Origin checks and per-process session capability assume a trusted
local user and no remote account model.

## Local-to-hosted mapping

| Local-first responsibility | Hosted replacement | Contract to preserve |
| --- | --- | --- |
| Explicit local `.sav` selection and immutable read | Authenticated upload with bounded size/type validation, producing immutable bytes/object version before analysis | The analysis service receives bytes. Filename/path remains provenance only. |
| `UserStateRoot` feature files | Tenant/user-scoped durable state in an authenticated transactional store | Feature schemas, explicit migrations, optimistic revisions, BuildIdentity/CampaignIdentity/BrotherIdentity semantics, and conservative conflict handling |
| One in-process application coordinator plus spawned worker | Durable job queue plus isolated remote workers | Desired-generation identity, exact source/config fingerprints, stale-result rejection, structured progress/failure, no partial publication |
| Local generated/latest publication | Tenant-scoped result/object storage with explicit retention | Versioned result schemas, exact publication fingerprints/signatures, last-success semantics where still desired |
| Local generated reference cache | Immutable prebuilt reference bundle or controlled shared cache pinned to the repository-declared upstream commit SHAs | Reference provenance and schema validation; no branch-head fallback |
| Loopback browser session | Authenticated HTTPS application session | Least privilege, CSRF/session protection appropriate to the chosen auth model, exact tenant authorization on every state/result/job operation |
| Local filesystem backups/uninstall choice | Export, deletion, retention and account-lifecycle workflows | User-owned state remains distinguishable from reproducible analytical/cache data |

A hosted adapter should call the existing typed analysis service rather than
recreate parser/projection orchestration. A remote worker may add transport
metadata around a request, but must not make tenant IDs, upload paths, object
keys, or HTTP request properties analytical inputs unless a future contract
explicitly requires them.

## Identity and path audit

The current analytical service is suitable for a hosted source boundary:

- `SaveSource` contains `content: bytes` plus a `name` documented as
  display/provenance, never identity.
- source snapshot identity is `sha256(save bytes)`;
- campaign identity is parsed from the native serialized `CampaignID`;
- brother identity is campaign-local native identity, not a path or display
  name;
- configuration identity is derived from normalized effective configuration;
- compatible incremental history is selected under CampaignIdentity and exact
  artifact dependencies, with path retained only as provenance where present.

`tests/unit/test_analysis_service.py` explicitly analyzes identical bytes under
renamed source labels and requires the same source fingerprint. The CLI path
entrypoints are tested as byte adapters. This is the required evidence that a
Windows path is not part of the analysis-service identity contract.

Local-only preferences may still contain a selected filesystem path. Those
preferences must not be copied into hosted domain identity. A hosted source
record instead needs a tenant-scoped upload/object identifier for storage and
a separate immutable content fingerprint for snapshot equality.

## Hosted threat-model delta

Hosting changes the trust model from one local user talking to loopback code to
mutually untrusted remote users sending untrusted save bytes to shared
infrastructure. At minimum the hosted design must address the following before
production implementation.

### Authentication and authorization

- Define account, tenant, administrator, support, and service identities.
- Authorize every upload, job, result, durable-state mutation, export, and
  deletion by tenant ownership; never trust a client-supplied tenant key alone.
- Prevent object identifiers, job IDs, campaign IDs, brother IDs, or predictable
  URLs from becoming cross-tenant capabilities.
- Replace the local loopback session capability with an authenticated HTTPS
  session/API model, including CSRF protection where cookies are used and
  secure credential/session rotation and revocation.

### Worker and parser isolation

- Treat every uploaded save as hostile binary input even when it has a `.sav`
  name. Enforce upload and decompression/resource limits before expensive work.
- Run analysis in a constrained worker identity with no tenant-to-tenant shared
  writable directory and no access to unrelated durable state or results.
- Give workers the minimum network access required. Prefer prebuilt validated
  reference data so arbitrary outbound fetches are unnecessary during a job.
- Apply CPU, memory, wall-time, concurrency, queue-depth, and result-size limits.
  A failed or killed worker must retain the existing structured-failure and
  no-partial-publication semantics.

### Tenant and storage isolation

- Namespace every durable record and object by authoritative server-side tenant
  identity and enforce that namespace below the HTTP routing layer.
- Encrypt data in transit and define encryption-at-rest requirements for save
  uploads, durable user state, results, backups, and logs.
- Separate reproducible cache/reference data from user-owned state and save
  content. Shared content-addressed caches are allowed only when their keys
  cover all result-affecting inputs and the cached value cannot expose another
  tenant's private metadata.
- Define backup isolation, restore authorization, key management, and disaster
  recovery. Restores must not resurrect data past an acknowledged deletion
  boundary without a documented policy.

### Retention, deletion, and privacy

- Define retention independently for raw save uploads, derived analysis
  results, user-authored state, security/audit events, operational logs, and
  backups.
- Provide tenant-scoped export and deletion workflows with a documented maximum
  deletion window, including backup expiry/tombstone behavior.
- Continue the local rule that save contents, hidden rolls, filesystem/storage
  paths, and complete durable state are absent from ordinary diagnostics.
- Establish data classification for save contents and derived data before
  deciding telemetry fields or support access.

### Abuse, quotas, rate limiting, and cost

- Apply per-account/tenant request rates, upload bytes, stored bytes, concurrent
  jobs, queued jobs, analysis CPU time, and result retention quotas.
- Bound retries and reject duplicate work using exact request/content identity
  where safe; do not allow retry storms to multiply compute cost.
- Define abuse handling for automated uploads, resource exhaustion, credential
  stuffing, and attempts to exploit the save parser or worker runtime.
- Add cost budgets/alerts and a deliberate degraded-service policy for queue or
  dependency pressure rather than silently weakening isolation or validation.

### Observability and operations

- Use structured operational events with tenant-safe correlation IDs; redact
  save bytes, secrets, state payloads, hidden rolls, and private storage
  locations.
- Separate product analytics from security/audit logging and obtain the policy
  basis for each before collection.
- Record worker/job state transitions and administrative access needed for
  incident investigation without turning logs into a shadow copy of user data.
- Define alerting, incident response, vulnerability handling, dependency
  patching, backup/restore testing, and capacity escalation before public use.

## What can be reused, adapted, or replaced

### Reuse with the same semantics

- parser/projection/classification/advisor engines;
- `analysis_service` request/result and structured error boundary;
- normalized archetype and classification inputs;
- CampaignIdentity, BrotherIdentity, BuildIdentity and dependency signatures;
- public/Target presentation schemas where their exposure remains appropriate;
- presentation read-model builders listed above, subject to the same data
  exposure contracts;
- deterministic `reference_analysis` and `full_preview` fixtures for analytical
  and presentation equivalence;
- stale-result publication rule from the coordinator.

### Adapt behind a new hosted boundary

- coordinator scheduling becomes a durable queue/worker protocol while
  preserving generation/fingerprint checks;
- durable feature schemas move from local atomic files to tenant-scoped
  transactional persistence with equivalent revision/conflict semantics;
- `bbtool/app/static/index.html`, `app.css`, `app.js`, `catalog_recovery.js`,
  `level-up.js`/`level-up.css`, and `recruitment.js`/`recruitment.css` may reuse
  their current screen composition and interaction behavior, but their local
  endpoint wiring, same-origin session bootstrap, and capability handling must
  be replaced by the selected authenticated hosted API/session model;
- last-success/result retention becomes an explicit product retention policy
  rather than an implicit local-machine lifecycle.

### Do not reuse as hosted security mechanisms

- `127.0.0.1` reachability as an access-control assumption;
- exact loopback `Host`/`Origin` validation as authentication;
- the local `X-BBST-Session` capability as an account/tenant credential;
- local filesystem permissions as tenant isolation;
- a selected local Windows path as source identity or hosted storage key.

## Owner decisions and artifacts required before implementation

An explicit hosted go decision must be accompanied by, or explicitly delegate
creation of, at least these product/legal/operational inputs:

1. supported audience and tenant/account model, including administrator/support
   access rules;
2. authentication provider/session strategy and account-recovery policy;
3. hosting regions and any data-residency requirements;
4. data-classification and retention/deletion matrix for uploads, results,
   durable state, logs, and backups;
5. privacy policy and terms of service appropriate to uploaded game-save data
   and derived analyses;
6. subprocessor/cloud-provider inventory and any required data-processing terms;
7. security contact, incident-response and vulnerability-disclosure procedures;
8. abuse policy, rate/usage quotas, billing or cost-allocation policy, and
   behavior when limits are reached;
9. encryption/key-management, backup/restore and disaster-recovery policy;
10. observability/support-access policy specifying what may be logged or viewed,
    by whom, and for how long;
11. availability/support expectations and an operational ownership/escalation
    model.

Until those decisions exist, hosted implementation would guess at product and
legal requirements that are intentionally outside the local-first architecture.

## Follow-up backlog gate

Do not create implementation tickets merely from this document. After an
explicit hosted go decision, create a sequenced backlog that covers, at
minimum: authenticated tenant persistence; upload/object lifecycle; durable job
queue and worker isolation; hosted API authorization; quotas/rate/cost controls;
retention/export/deletion; security/observability operations; and deployment,
backup, recovery, and production validation.

Each hosted ticket must preserve the existing analytical invariants unless a
separate approved contract change says otherwise. In particular, changing
transport or storage must not change Fit, BestRole, identity, deterministic
analysis, or `incremental == independent full recomputation` semantics.
