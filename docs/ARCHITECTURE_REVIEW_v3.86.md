# Architecture review and incremental cleanup plan

**Reviewed baseline:** `338d3b5` (v3.86 development line)

**Scope:** issue #16

**Decision status:** findings and sequencing are actionable; open decisions are
listed explicitly rather than hidden in implementation tasks.

This review describes the code that is executed today, the contracts that must
remain stable, and a sequence of independently deliverable refactorings. It does
not authorize changes to projection, Fit, classification, Advisor, or cache
semantics.

## 1. Executive assessment

The computational core has a sound dependency direction: parser facts feed the
projection engine, classification and Advisor consume projection results, and
incremental reuse sits above those engines. The principal architectural debt is
at the application boundary:

1. `bbtool/app/runner.py` owns the complete lifecycle and knows every concrete
   output, cache, diagnostic, monitoring, archive, and browser detail.
2. `bbtool/app/output.py` combines four different responsibilities: public
   serialization, hidden-roll validation, HTML delivery, and filesystem/archive
   lifecycle.
3. `bbtool/html_report.py` accepts live domain objects and imports analytical
   helpers. A future render-only path therefore cannot prove that it is merely a
   consumer of versioned public data.
4. JSON artifacts have file-local formats but no single public run contract or
   relation manifest. The incremental and debug formats are versioned; normal
   roster, recruits, role-fit, and classification outputs are not.
5. Mutable process-wide caches and profiling state are deliberately reset by
   orchestration, but this lifecycle is implicit and tests commonly replace
   broad runner collaborators to isolate it.

The recommended direction is not a rewrite. First characterize and declare the
existing public run dataset. Then extract pure payload builders, split delivery
services, introduce an explicit application pipeline result, and only afterward
add render-only consumers. The projection package remains untouched except for
adapters at its public boundary.

## 2. Executed architecture

### 2.1 Module ownership and observed contracts

| Area | Current responsibility and inputs | Outputs / side effects | Contract owner today | Main issue |
|---|---|---|---|---|
| `bb_analyze.py`, `app/main.py`, `app/cli.py` | Parse one `.sav` path and run options | `CliOptions`, process exit via argparse errors | `app/cli.py` | CLI models a full analysis only; future modes would add branching to one flat option set. |
| `save_parser.py` | Binary save bytes plus generated reference dictionaries | `Brother` records and recruit dictionaries; recoverable diagnostics | parser tests and `models.py` | Large module, but its boundary is clear. Split only after byte-level characterization. |
| `references/update_references.py` | Tracked seeds, local caches, optionally downloaded source archives | Disposable generated dictionaries and provenance status | reference generator | Generation, download, extraction, audit, and cache validation share one large module. Normal runs may perform network-capable preparation before parsing. |
| `app/config.py` | Editable archetype and classification JSON | Normalized roles with derived Fit curves; classification dict | configuration loader | Normalized dictionaries are an implicit internal schema shared by projection, cache hashing, analysis, and rendering. |
| `projection/*` | `Brother`, normalized role, visible current rolls | trajectory distributions and role projection rows | projection public API | Good core boundary. Internal global memoization/profile lifecycle is controlled indirectly by `configure_engine()` and `reset_profile()`. |
| `classification.py` | Best projection row and classification config | category, label and perk compatibility | classification module | Pure and small; preserve as an analytical service. |
| `levelup_advisor.py` | Brother, roles and baseline rows | current level-up recommendations | Advisor module | Correctly reuses trajectory semantics; keep `FutureRolls` quarantined. |
| `app/analysis.py` | Brothers, roles, classification config, optional cache | `AnalysisResult(fits, summaries)` plus profile/cache mutations | analysis orchestrator | Row/summary dictionaries are not typed or versioned; summary assembly mixes analytical results with display strings. |
| `incremental/*` | Current facts, normalized roles/config, previous manifest | reusable role/advisor/summary artifacts and diagnostics | incremental package | Safe conservative behavior, but dependency/version declarations are split across fingerprint and cache code; path is campaign authority. |
| `app/output.py` | Live brothers, analysis rows, roles/config, workspace | public JSON, private validation JSON, debug JSON, HTML/assets, ZIP and pruning | output module | Multiple trust boundaries and lifecycle phases in one module; `_decorate_fit_rows` mutates analysis rows during serialization. |
| `html_report.py`, `report.js`, `report.css` | Live brothers plus analytical dictionaries and configs | standalone HTML with static assets | renderer | Presentation imports `classify_bro` and `effective_stat_profile`; it is not yet a pure consumer of a public report model. |
| `app/health.py`, `console.py`, `telemetry.py` | Run objects, reference/cache/profile state | console diagnostics and debug metadata; tracemalloc lifecycle | application diagnostics | Useful observability, but data collection, formatting and process state are coupled to runner sequencing. |
| release/test scripts | Repository and test configuration | CI gates, release archive verification | scripts plus workflow tests | Strong policy coverage; no end-to-end public dataset contract yet. |

### 2.2 Allowed dependency direction

The current healthy core direction is:

```text
models/config/reference facts
          |
          v
       parser ---------> Brother + recruits
          |
          v
projection/trajectory -> classification -> Advisor
          |                    |              |
          +--------------------+--------------+
                               v
                         analysis result
                               |
                    +----------+----------+
                    v                     v
             incremental cache       output/report
```

The notable reverse edges are confined to presentation/output:

- `html_report.py -> classification.classify_bro`;
- `html_report.py -> projection.perks.effective_stat_profile`;
- `app/output.py -> projection` for validation-oracle calculations;
- `app/telemetry.py -> incremental` for version metadata.

The first two make the report a partial analytical consumer rather than a pure
view. The third is legitimate only for a separately labelled validation
service. The fourth should eventually consume a public version registry rather
than implementation modules.

### 2.3 End-to-end flows and artifact classes

| Flow | Validation owner | Derived data / transformations | Failure propagation |
|---|---|---|---|
| Save -> roster/recruits | `save_parser.py` | Binary discovery, reference-name decoration, public/current and hidden roll extraction | Hard failures propagate; selected tail failures are recorded in parser diagnostics. |
| Config/references -> analytical context | `ensure_references`, `load_config` | Generated reference caches; normalized roles and Fit curves | Exceptions abort before analysis; generated reference caches are not source artifacts. |
| Facts -> projections -> summaries | projection modules, then `app/analysis.py` | role rows, best role, classification and Advisor summary | Exceptions abort the run; incremental misses recompute. |
| Previous manifest -> reuse | incremental package | Exact-state and artifact hashes | Missing/corrupt/incompatible/ambiguous state falls back safely. `--verify-cache` compares to full recomputation. |
| Analysis -> normal JSON | `app/output.py` | Adds display summaries in place, then serializes role-fit/classification | Write errors abort; no top-level schema validation/version marker. |
| Facts/results -> validation JSON | validation functions inside `app/output.py` | Hidden `FutureRolls`, seeded trajectories and percentile diagnostics | Roll violations are reported but do not fail the process; file-build errors abort. |
| Facts/results -> debug JSON | `app/output.py` | Public facts plus config, health, reference and profile diagnostics | Write errors abort; final metadata is rewritten after archiving. |
| Live objects -> HTML/assets | `app/output.py` and `html_report.py` | Recomputes effective display stats and some classification presentation | Render/copy errors abort. Browser-open errors are non-fatal and reported. |
| Workspace -> archive/retention | `app/output.py` | ZIP, checksum, a second ZIP after final metadata, per-save retention | Archive errors abort; obsolete-output deletion failures warn. |

Artifact classification must remain explicit:

- **source:** `.sav`, editable configuration, tracked reference seeds;
- **derived public user artifacts:** roster, recruits, role-fit,
  classification, report and assets;
- **derived private/diagnostic artifacts:** projection validation and debug bundle;
- **cache:** generated runtime references and incremental manifest;
- **delivery:** run directory and ZIP archive.

`FutureRolls` may appear only in the private validation artifact. They must not
enter the public run dataset, report model, cache decisions, classification, or
Advisor.

## 3. Interfaces, versions, and effects

### 3.1 Entry points

- `python bb_analyze.py <save>` is the only production entry point.
- `CliOptions` combines source, config, destination, projection/cache controls,
  and report opening.
- `runner.run()` returns `(workspace, archive_path)`; callers cannot directly
  inspect analytical or delivery results without filesystem reads.
- Tests directly call lower-level builders and broadly monkeypatch runner
  functions. These functions are therefore semi-public even when prefixed.

Before #12-#15, stabilize three separate application operations:

```text
analyze(inputs) -> PublicAnalysisDataset + DiagnosticDataset
render(PublicAnalysisDataset, destination) -> ReportArtifact
package(RunArtifacts, retention policy) -> ArchiveArtifact
```

The existing CLI may continue to compose all three. A future render-only command
must call only the second and third operations.

### 3.2 Existing format/version boundaries

| Data | Version signal | Compatibility behavior |
|---|---|---|
| Editable archetypes/classification | none | Structural checks in `load_config`; missing/invalid values fail locally. |
| Normal roster/recruits/role-fit/classification | none | Consumers infer fields; there is no dataset-level compatibility check. |
| Incremental manifest | `bb-incremental-v1` plus per-artifact engine integers | Unsupported/corrupt manifests are ignored and recomputed. |
| Projection validation | `bbtool.projection_validation.v3` | Diagnostic writer owns the format; no general reader exists. |
| Debug bundle | `bbtool.debug_bundle.v1` | Support artifact only; no general reader exists. |
| HTML | no machine-readable report contract | Generated from live objects and same-run config. |

The first target contract should be a small run manifest that names each public
file, declares one dataset schema version, and records stable source identity
without local absolute paths. It must not absorb the incremental manifest or
private validation data.

### 3.3 Side-effect lifecycle

`runner._run()` currently relies on this order:

1. start process monitoring;
2. ensure reference caches;
3. parse twice from the save (roster, then recruits);
4. create a timestamped workspace and copy the source save;
5. configure/reset engines and optionally discover a manifest;
6. analyze, optionally verify, write/prune manifests;
7. write normal, report, validation and debug artifacts;
8. archive, stop monitoring, rewrite debug metadata, archive again;
9. prune ZIPs, print, optionally open the browser.

The double parse and double archive are observable costs. They should be
measured before optimization. The source-save copy is a deliberate user
artifact today and cannot be removed without a compatibility decision.

## 4. Duplication, debt, and test coverage

### 4.1 Prioritized findings

| ID | Priority | Finding and evidence | Risk / target direction | Verification |
|---|---|---|---|---|
| A1 | P0 | Public report input has no versioned dataset contract; normal JSON writers emit bare lists. | #12-#15 could create silent incompatibility. Add a manifest and strict reader before render-only work. | Contract tests for missing files, versions, IDs and forbidden fields. |
| A2 | P0 | Renderer consumes live `Brother` objects and calls analytical helpers. | Render-only cannot prove absence of analysis and may diverge. Build a complete public report model during analysis; renderer consumes only that model. | Monkeypatch analytical/parser entry points to fail in render-only tests; semantic equivalence test. |
| A3 | P1 | `app/output.py` owns public output, oracle validation, debug, HTML, ZIP and pruning. | Trust boundaries and failures are difficult to isolate. Extract `public_dataset`, `validation`, `report_delivery`, and `archive` modules incrementally. | Move-only characterization tests plus focused failure tests. |
| A4 | P1 | `_decorate_fit_rows` mutates the `fits` result during writing. | Output order can alter later cache/debug/report payloads and makes purity unclear. Return decorated copies from a payload builder. | Assert input rows are unchanged and emitted payload is equivalent. |
| A5 | P1 | Engine versions and dependency declarations live in `incremental/fingerprint.py`, while cache validation/reasons live in `cache.py`. | A semantic input can be omitted or version bumps can drift. Implement roadmap workstream D with typed/normalized dependency builders and registry. | Existing invalidation suite plus field-by-field mutation tests. |
| A6 | P1 | `runner._run()` is a long transaction with concrete imports and tuple return. | New modes add branch complexity; broad mocks hide integration gaps. Introduce typed stage results and injected narrow services. | Runner contract tests for stage order, cleanup, and errors. |
| A7 | P2 | Parser and reference generator are the two largest Python modules. | Maintenance cost, but premature splitting risks binary/reference regressions. First add maps and byte/extraction characterization, then extract cohesive helpers. | Parser/reference focused suites and deterministic fixtures. |
| A8 | P2 | Process-wide projection caches/profile require manual reset sequencing. | Multiple analyses in one process may leak state if a caller bypasses runner. Encapsulate a run-scoped engine session or make lifecycle explicit in API. | Two-run tests with different configs/brothers and deterministic profiles. |
| A9 | P2 | Summary dictionaries include analytical values and presentation strings such as joined perks/traits. | Schema ownership is unclear and presentation changes may affect cache artifacts. Separate analytical summary from report-view decoration. | Cache reuse tests showing report-only changes do not invalidate numerical artifacts. |
| A10 | P2 | HTML is generated by a large string-building module and JS/CSS contracts are checked mostly statically. | UI changes are hard to isolate; avoid framework rewrite. Split view sections only after a report model exists. | Existing UI/static tests plus fixture-based DOM/interaction tests. |
| A11 | P3 | Roster and recruits each read the same save through separate public parser calls. | Possible avoidable I/O; not a correctness defect. Consider `parse_save()` only after profiling and shared diagnostic semantics are defined. | Equivalence and malformed-tail tests. |
| A12 | P3 | Debug metadata causes the archive to be built twice. | Extra I/O and lifecycle complexity. Finalize metadata before a single package step, or explicitly exclude post-package metrics. | Archive contents/checksum and telemetry lifecycle tests. |

No current evidence justifies deleting compatibility branches such as the
validation fallback from missing `BrotherID` to one unambiguous name. Inventory
real artifact consumers first; if retained, label it with an expiry condition.

### 4.2 Test boundary map

| Boundary | Existing protection | Important gap before refactoring |
|---|---|---|
| Binary parser -> `Brother`/recruits | parser primitive, full-brother, roster, recruits and reference tests | One documented `parse_save` aggregate contract if parsing is unified. |
| Config -> normalized roles | config/planner/scoring/ceiling tests | Explicit schema/error-path tests for the future public dataset, not just config. |
| Trajectory/scoring/projection | trajectory, shared trajectory, sampling, scoring, planner, perk/trait/injury tests | Preserve unchanged; no refactor prerequisite identified. |
| Analysis -> rows/summaries | analysis, classification, Advisor and integration output tests | Purity test: serialization/reporting must not mutate analytical results. |
| Incremental -> full equivalence | core, artifact reuse, identity, verify/prune tests | Central-dependency declaration tests and batch dataset scenarios remain roadmap work. |
| Output -> files | config/output, validation, debug, retention and release tests | Dataset manifest, cross-file IDs, version rejection, forbidden-field scanner. |
| Report -> UI | HTML, UI architecture, JS/CSS and output UI tests | One fixture-driven semantic equivalence contract and render-only no-analysis proof. |
| Runner lifecycle | runner, browser-open, health and telemetry tests | Typed stage/result contract; cleanup behavior after exceptions at each stage. |
| Release/CI | policy, archive and static contract tests | Full reference-save E2E is intentionally deferred to #15 and requires approved data. |

Some `coverage_*` tests aggregate unrelated branches and some runner tests mock
nearly every collaborator. Do not delete them during extraction. Add focused
contract tests first, migrate assertions to their owning boundary, and remove an
aggregate assertion only after equivalent focused coverage is proven.

## 5. Target architecture

### 5.1 Layer rules

```text
CLI / application composition
          |
          +--> reference preparation
          +--> parser ----------> source facts
          +--> analysis --------> analytical dataset
          |       |                    |
          |       +--> projection      +--> incremental adapter
          |       +--> classification
          |       +--> Advisor
          |
          +--> public dataset builder -> schema validator/reader
                                            |
                                            v
                                      report renderer
                                            |
                                  delivery / archive / open

diagnostic validation <--- source facts + analytical dataset
         (separate, never a report input)
```

Rules:

- Parser and reference layers do not import application, output, or report code.
- Projection, classification, and Advisor remain free of persistence and UI.
- Incremental code wraps analytical calls and consumes centralized dependency
  declarations; cached data is never authoritative current state.
- The public dataset builder is the only owner of analysis-to-public-JSON
  conversion. It returns new values and never mutates analysis results.
- The report renderer imports only public report-model/schema utilities and
  presentation helpers. It never imports parser, projection, classification,
  Advisor, references, or incremental modules.
- Diagnostic validation is explicitly allowed to consume `FutureRolls`; its
  artifacts can never satisfy a public dataset dependency.
- Filesystem delivery, archiving, retention, console formatting, monitoring,
  and browser opening remain application-side effects outside pure builders.

### 5.2 Data contracts and ownership

Introduce narrow immutable result types (dataclasses are sufficient; no new
framework is required):

- `ParsedSave`: roster, recruits, parse diagnostics;
- `AnalysisResult`: analytical role rows and summaries (existing type, tightened
  without changing payload semantics);
- `PublicRunDataset`: version, source metadata, roster, recruits, role fits,
  classifications, roles, public presentation data;
- `RunArtifacts`: paths for dataset files, report, validation, debug, manifest;
- `RunResult`: analysis/health summary plus delivery artifacts.

The public schema reader owns syntax, version, required fields, cross-file
`BrotherID`/role relationships, and the `FutureRolls` prohibition. The renderer
may reject unsupported datasets but may not repair or recalculate them.

Compatibility policy:

- add the first version alongside current filenames;
- keep the full-run CLI output stable during migration;
- accept only explicitly supported public dataset versions;
- retain adapters for legacy same-run calls until all internal consumers move;
- remove adapters only after repository and release-archive searches prove no
  consumer, and document the removal in changelog/release notes.

### 5.3 Error and observability ownership

- Each pure builder raises a contextual typed/value error naming the artifact,
  file, field, brother, or role where possible.
- Application composition assigns stage names and exit status; it does not
  reinterpret analytical errors.
- Health and telemetry consume stage results and counters. They do not alter
  business payloads.
- A failed dataset validation produces no report advertised as valid.
- Browser opening remains a post-success, non-fatal delivery action.
- Cache miss reasons remain machine-readable and are surfaced by the runner.

## 6. Sequenced refactoring plan

Each phase is one or more coherent PRs. A new issue should be created for every
row before implementation; #12-#15 should depend on the relevant rows rather
than absorb them.

| Phase | Deliverable and unchanged behavior | Prerequisites / files | Tests and rollback |
|---|---|---|---|
| 0 | Merge this review; no runtime change. | `docs/ARCHITECTURE.md`, this document | Markdown links and normal static gates. Revert documentation if findings are disproved. |
| 1 | Characterize current public outputs and report semantics. Add assertions for filenames, fields, relationships, forbidden hidden data, input immutability, and same-run rendering. | Existing output/UI tests; `app/output.py`, `html_report.py` unchanged | Focused contract tests plus normal suite. Test-only rollback. |
| 2 | Add a versioned public run manifest and strict reader while preserving all existing files and HTML. | Decision: single manifest referencing current files; #13 may provide maintained fixtures later. | Missing/corrupt/version/cross-ID/Unicode tests. Disable reader path without changing the writer if rollback is needed. |
| 3 | Extract pure public payload builders; replace `_decorate_fit_rows` mutation with copies. Keep byte-equivalent meaningful JSON fields. | `app/output.py`, new `app/public_dataset.py` | Golden structural comparison, immutability test, full output integration. Revert call-site switch independently. |
| 4 | Complete the public report model so all values currently computed by `html_report.py` are produced upstream. Change renderer to consume only the model; keep one adapter for the full-run call. | Phases 1-3; `html_report.py`, analysis/view-model builder | Import-boundary test, semantic DOM comparison, no numerical/cache diff. Adapter permits rollback. |
| 5 | Split output side effects into validation, report delivery, archive/retention, and debug modules. No format or lifecycle change. | Phases 1-4; `app/output.py`, runner tests | Move-only tests, archive/debug equivalence, failure injection. Keep compatibility re-exports temporarily. |
| 6 | Introduce typed `RunResult` and stage functions; reduce `_run` to composition. Preserve CLI/options/messages except intentionally documented improvements. | Phase 5; `app/runner.py`, health/telemetry/console | Stage-order and exception cleanup tests, existing runner contracts, full suite. Old facade remains rollback boundary. |
| 7 | Centralize incremental dependencies and engine versions as specified by roadmap workstream D. No new identity or progression reuse. | Stable analysis types from phase 6; incremental modules | Existing cache suite, field dependency matrix, `incremental == full`. Bump only versions whose semantics actually change. |
| 8 | Add the render-only application/CLI path from a validated public dataset (#14), then adjacent-JSON report loading (#12). | Phases 2-6 and maintained fixture work #13 | Parser/projection/classification/Advisor fail-fast spies; functional report equivalence; malformed dataset failures. |
| 9 | Split parser/reference modules only along proven cohesive seams and only if size/coupling still impedes work. | Characterization fixtures and profiling | Parser/reference suites, offline determinism. Mechanical moves separated from behavior changes. |
| 10 | Add approved-save PR E2E and preview delivery (#15/#9/#10) after data authorization and security design. | #13, #12, #14 plus approved save | Full chain, exact-SHA binding, artifact security/retention. Workflow can be removed without altering local application behavior. |

Suggested follow-up issues from phases 1-7:

1. **Characterize and version the public run dataset** (phases 1-2).
2. **Make public output serialization pure** (phase 3).
3. **Make the HTML renderer consume a public report model** (phase 4).
4. **Split output validation and delivery services** (phase 5).
5. **Introduce explicit application stage results** (phase 6).
6. **Centralize incremental dependency declarations** (phase 7, already
   aligned with roadmap workstream D).

Do not combine issues 2-5 in one PR. Each has a compatibility seam and an
independent rollback point.

## 7. Open decisions and required evidence

| Decision | Options | Evidence needed / recommendation |
|---|---|---|
| Public dataset layout | One combined JSON; current files plus manifest | Prefer current files plus a small manifest to keep diffs readable and avoid a duplicate format. Validate with #13 fixture size and consumer ergonomics. |
| Schema machinery | Hand-written validator; JSON Schema; third-party model library | Start with dependency-free explicit validation matching current project style. Adopt a schema library only if multiple external consumers justify it. |
| CLI shape | New option; subcommands; separate script | Choose after phase 6. Prefer subcommands if both full analysis and render-only are first-class; preserve the current invocation as a compatibility route. |
| Source save in normal run directory | Retain; opt-in; remove | Inventory user/release consumers and privacy expectations. Do not silently remove or expose it through previews. |
| One-pass save parsing | Aggregate parser versus current two calls | Measure actual I/O and define combined error/diagnostic semantics first. This is not required for render-only architecture. |
| Run-scoped projection state | Explicit engine session; retain reset API | Add multi-run process tests and profile leakage measurements. Prefer a small session/context owner if a real caller needs repeated in-process analyses. |
| Legacy name fallback in validation | Retain indefinitely; deprecate | Search archived artifacts and release compatibility requirements. Never extend name matching to production identity or cache reuse. |
| Reference network preparation | Automatic fallback; explicit bootstrap | Measure fresh-install usability and define offline failure diagnostics. Tests remain entirely offline in either design. |

## 8. Acceptance mapping for issue #16

- Major modules, flows, side effects, data classes, and version boundaries are
  mapped in sections 2 and 3.
- Concrete duplication and debt have locations, risks, priorities, targets, and
  verification strategies in section 4.
- Existing test ownership and prerequisite gaps are mapped in section 4.2.
- The target layer direction, data owners, compatibility, errors, and
  observability are defined in section 5.
- Section 6 provides independently deliverable migrations, tests, rollback
  seams, prerequisites, and completion order.
- Sections 6 and 7 make interactions with #12-#15 explicit without selecting an
  implementation prematurely.
- No runtime behavior or analytical contract is changed by this review.
