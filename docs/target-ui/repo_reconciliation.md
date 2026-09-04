# Battle Brothers Save Toolkit — Target UI ↔ Repository Reconciliation

**Date:** 2026-08-31
**Repository:** `yannkahloun-alt/BB-Save-Toolkit`
**Target UI status:** Company/Brother, Level Up, Recruitment validated and closed
**Purpose:** reconcile the validated target UI with the actual repository, current public contracts, and existing GitHub issues before any implementation-ticket graph is created.

This document does **not** create, close, update, or replace GitHub issues.

---

## 1. Executive conclusion

The repository is further along architecturally than the first implementation roadmap assumed.

Three major foundations already exist:

1. a transport-independent analysis service has been implemented and issue #94 is closed;
2. a strict versioned public report dataset (`bbtool.reference_analysis.v1`) already exists with render-only / serve-report validation;
3. the current Level-Up Advisor already exposes a structured machine-readable decision payload, not only presentation prose.

Therefore the target-UI implementation should **not** start by rebuilding analysis/report separation or inventing a new generic presentation pipeline.

The real work is now concentrated in:

- durable identity and user-state contracts;
- AssignedBuild persistence and invalidation;
- target-specific public dataset evolution;
- current-state mechanics;
- roster-level planning outputs;
- recruitment analytical models;
- local-first runtime/API/state dependencies;
- replacing the current presentation with the validated target information architecture.

The most important planning consequence is:

> The validated Target UI should become the visual/product source of truth for #100 and related UI work, while existing backend/public-contract foundations should be reused rather than duplicated.

No issue should be edited or closed solely from this document without an explicit project decision.

---

## 2. What already exists

### 2.1 Transport-independent analysis boundary — DONE

Issue **#94** is closed.

The repository contains:

```text
bbtool/app/analysis_service.py
```

with typed concepts including:

- `SaveSource`
- `AnalysisServiceOptions`
- `CompatibleCacheContext`
- `ProgressEvent`
- `AnalysisServiceRequest`
- `AnalysisServiceResult`
- structured `AnalysisServiceError`

The result already exposes:

- public analytical data;
- source fingerprint;
- configuration fingerprints;
- warnings;
- diagnostics;
- timings;
- progress events;
- incremental cache;
- projection validation.

#### Reconciliation result

The old roadmap phase “create an application/service analysis boundary” is obsolete.

The target UI must consume/extend this service boundary, not introduce another analytical entry point.

---

### 2.2 Public report dataset v1 — DONE as infrastructure

The public report contract is documented in:

```text
docs/REPORT_DATASET.md
```

Current schema:

```text
bbtool.reference_analysis.v1
```

Canonical logical files:

```text
roster
recruits
role_fit
classification
archetypes
classification_config
```

The loader already validates:

- exact schema;
- exact file set;
- safe relative paths;
- SHA-256;
- UTF-8 JSON;
- root types;
- BrotherID/HumanOffset consistency;
- Brother/archetype joins;
- one Fit row per Brother × archetype;
- one classification row per Brother;
- `BestRole`;
- absence of hidden `FutureRolls`;
- renderer-contract preflight.

The renderer path is explicitly presentation-only.

#### Reconciliation result

The missing artifact is **not** “a public report dataset”.

The missing artifact is:

> **a deliberate next-version / additive target-UI public presentation contract built on the existing v1 contract.**

Because v1 requires an exact file set, adding new independent artifacts such as public Run Health would require an explicit contract evolution rather than silently dropping a seventh JSON file beside the existing six.

One coordinated schema evolution is preferable to many unrelated report-contract bumps.

---

### 2.3 Brother Gear data — DONE at data level

Issue **#61** is closed.

`Brother` currently contains stable public fields:

```text
Equipment
GearFatigue
```

with public shape for:

- MainHand
- OffHand
- Body
- Head
- Accessory
- Ammo
- Bag

`GearFatigue` contains per-slot values and `Total`.

The public roster serializer uses `asdict(bro)` and removes only hidden `FutureRolls`, so Gear currently participates in public Brother data.

#### Reconciliation result

The target Brother Gear surface does **not** need a new gear parser foundation.

Remaining work is:

- presentation;
- any still-missing normalized item metadata;
- usable-FAT semantics where not directly available;
- Mechanical Facts from #91.

Issue #92 can reuse the same Gear contract even if its current-report presentation is later replaced by the target Brother UI.

---

### 2.4 Level-Up Advisor structured payload — SUBSTANTIALLY EXISTS

The current analyzer stores:

```text
classification[].LevelUpAdvice
```

The Advisor payload already contains structured fields equivalent to:

- `AnchorRole`
- `Recommended`
- `Alternative`
- `PickReasons`
- `AllRolls`
- `SkippedImportant`
- eligible/excluded stats;
- free-pick state;
- evaluated combination counts;
- `Method`;
- optional gamble comparison metrics.

`Recommended` / `Alternative` already expose:

- selected stats;
- rolls;
- roll quality;
- Fit before/after;
- likely/full ranges;
- feasibility before/after;
- Fit delta.

#### Important gap

The current Advisor chooses:

```text
anchor_role = baseline BestRole
```

It is not yet anchored to persistent `AssignedBuild`.

The payload also primarily describes consequence against the anchor role. The validated Level Up UI requires enough structured evidence to show both:

- effect on Assigned Build;
- effect on Best Fit / competing intrinsic trajectory;

when those differ.

#### Reconciliation result

Do not create a second Advisor engine for the target UI.

Evolve the existing Advisor contract once AssignedBuild semantics are available.

---

### 2.5 Run Health backend — EXISTS, public report exposure missing

`AnalysisServiceResult` already exposes structured:

- warnings;
- diagnostics;
- `run_health`;
- projection validation.

Issue **#74** remains open because this health state is intentionally outside the current six-file public report contract.

#### Reconciliation result

The target shell's Run Health requirement aligns directly with #74.

The UI need is not a new health engine; it is:

- public contract exposure;
- compact shell status;
- selective local validity where support exists.

---

## 3. Existing issues that map directly to the target UI

### #91 — Mechanical Facts

Strong alignment with the validated target.

It already requires:

- factual perk/gear states;
- no warnings;
- no alert severity;
- no archetype coupling;
- no Fit / BestRole mutation.

This matches the final target spec almost exactly.

#### Target-UI dependency

Brother → Mechanics depends on #91 for real data.

---

### #92 — Gear UI

Conceptual placement already matches the target:

```text
Brother
  → Gear
  → Mechanical Facts
```

It explicitly rejects:

- global Gear tab;
- Fit coupling;
- gear requirements inside archetypes.

#### Reconciliation caution

#92 is written as a targeted addition to the **current** report, while the final Target UI has now been validated.

If #92 executes before the broader target-UI implementation, its data/component work should remain modular enough to be reused.

Do not let #92 freeze current-report layout as the final architecture.

---

### #74 — Run Health in report

Direct target-shell dependency.

Likely candidate to participate in the coordinated public report-contract evolution rather than independently creating a one-off schema shape.

---

### #71 / #84 — Recruit freshness and identity

The validated Recruitment UI deliberately uses conservative observation semantics:

- first observed;
- previously seen;
- new since previous analysis;
- exact game refresh unknown when not evidenced.

This is compatible with #71/#84.

The target UI does **not** require #71 to falsely promise game-native refresh age.

---

### #72 / #73 — Roster Management study + UX redesign

The validated Target UI has now answered the product question that these issues were created to investigate:

- useful Roster Management capability belongs under **Company**;
- `Roster` is the default people scan;
- `Planning / Coverage` owns composition/depth/gaps;
- `Fit Matrix` remains a specialist comparison view;
- Brother detail is a drill-down rather than duplicated analytical content;
- AssignedBuild and Best Fit remain separate.

#### Reconciliation result

From a product-design perspective, #72/#73 are no longer unconstrained studies.

Their remaining relevance should be reconciled against the validated Company architecture before implementation.

Possible future project decisions include:

- treating the final Target UI spec as #72's design conclusion and adapting #73;
- superseding both into broader #100 target-UI implementation work;
- retaining only specific backend/data pieces.

This document does **not** make that issue-state decision.

---

## 4. The real persistent-state critical path

The largest unresolved dependency is not HTML.

It is durable identity + player intent.

### 4.1 Campaign Identity — #79

Open.

Required before persistent campaign-local state can be considered safe.

Map seed is explicitly insufficient.

### 4.2 Cross-save Brother Identity — #77

Open and blocked by #79.

Current public `BrotherID` remains:

```text
human:<HumanOffset>
```

and is explicitly documented in code as unique only inside one parsed save.

Therefore current `BrotherID` is **not** a valid AssignedBuild persistence key.

### 4.3 AssignedBuild study — #81

Open.

Depends on:

```text
#79 CampaignIdentity
#77 BrotherIdentity
```

Its semantic model is strongly aligned with the validated UI:

```text
BestRole       = analytical best fit
AssignedBuild  = explicit player intent
Alternatives   = other viable paths
```

The target UI should be treated as concrete UX evidence for #81.

### 4.4 BuildIdentity — #85

Open.

Needed so a persisted assignment points to a stable build identity rather than mutable display text.

The target spec already requires:

```text
BuildIdentity
DisplayName
BuildDefinition
BuildDefinitionHash / semantic version
```

### 4.5 Durable user-state lifecycle — #86

Open.

This is the conceptual prerequisite for implementation issue #95.

Its required distinctions align with the Target UI:

- generated outputs;
- cache;
- durable player state;
- historical observation state.

### 4.6 Persistent app-state implementation — #95

Open, blocked by #86 and coordinated with #85.

This is the actual local-first storage implementation.

### Critical conclusion

A real editable/persistent `AssignedBuild` cannot safely be implemented merely as a frontend control.

The dependency chain is conceptually:

```text
#79 CampaignIdentity
    ↓
#77 BrotherIdentity
    ↓
#81 AssignedBuild identity semantics

#85 BuildIdentity ───────┐
#86 durable state ──────┼→ #95 per-user state
#89 purity ─────────────┤
#88 invalidation ───────┘

then interactive write/API/UI
```

Some studies can run in parallel, but the final persistence schema must respect all of them.

---

## 5. Semantic studies partially answered by the Target UI

### #89 — analytical purity

Open.

The validated Target UI already supplies strong product-level conclusions:

```text
Intrinsic:
  raw projections
  Fit
  BestRole / Best Fit
  recruit intrinsic potential

Intent:
  AssignedBuild

Intent-aware:
  Level Advisor toward AssignedBuild
  intended roster coverage

Mixed but decomposable:
  planning / recruitment decisions
```

It also validated:

```text
change roster need
→ recruit intrinsic potential unchanged
```

and:

```text
AssignedBuild
-X-> intrinsic Fit / BestRole
```

#### What #89 still needs

Repository-level proof/classification of every artifact and regression tests.

The target spec can be used as normative product input, but it does not replace the code dependency audit.

---

### #88 — dependency / invalidation

Open.

The Target UI determines several semantic edges, but #88 still needs to turn them into an actual technical dependency graph / fingerprint contract.

Examples already implied:

```text
AssignedBuild
-X-> raw projection
-X-> intrinsic Fit
-X-> BestRole

AssignedBuild
 -> intent-aware Level Advisor
 -> intended Company coverage
 -> other explicitly intent-aware output
```

The target UI therefore reduces ambiguity for #88 but does not implement invalidation.

---

### #87 — safe browser write path

Open.

The local-first epic has since made the likely architecture clearer:

```text
Browser UI
  → bounded loopback API
  → validated durable-state layer
```

The current public report contract remains presentation-only.

The Target UI's AssignedBuild controls must have a clear read-only state until #87/#95/#98 make writes authoritative.

---

## 6. Local-first web epic alignment

### Epic #93

The open local-first web epic already supplies the runtime/delivery architecture:

```text
#94 analysis service           DONE
#95 per-user state
#96 archetype overrides
#97 background job coordinator
#98 loopback API
#99 save watcher
#100 web UI
#101 Windows delivery
#102 integrated quality gate
#103 hosted readiness (non-blocking)
```

The Target UI should be implemented **inside this local-first architecture**, not as a second unrelated application.

---

### #100 — Web UI issue needs product-scope reconciliation

#100 currently asks for:

- first-run/no-save;
- selected-save controls;
- freshness/progress;
- stale last-success behavior;
- existing report reuse;
- archetype editor;
- accessibility;
- local assets.

It has an explicit artifact checkpoint:

> Before visual implementation, request an approved low-fidelity screen flow or explicit permission to derive it from the current report.

That checkpoint is now materially satisfied by:

```text
bb_target_ui_spec_final.md
bb_target_ui_company_brother_levelup_recruitment_mockup_v16.html
```

The Target UI is substantially more specific than #100's original “reuse current report where practical” premise.

#### Important project decision before #100 implementation

Decide whether #100 becomes:

**A. the umbrella implementation issue for the validated Target UI**, plus first-run/save/archetype-management flows;

or:

**B. only the local-app shell/save/archetype flows**, with separate target-surface implementation issues underneath/alongside it.

Do not start visual implementation from #100's old wording without making that reconciliation explicit.

No issue update is performed by this document.

---

## 7. Public contract gap map by target surface

### Company / Brother

Already available or substantially available:

- current roster state;
- CurrentRolls;
- perks/traits/injuries;
- Equipment;
- GearFatigue;
- Brother × archetype Fit/projections;
- BestRole;
- LevelUpAdvice.

Missing or not yet contract-stable:

- durable CampaignIdentity;
- durable BrotherIdentity;
- BuildIdentity;
- AssignedBuild;
- Mechanical Facts (#91);
- public Run Health (#74);
- result-local validity/provenance;
- explicit Company Planning/Coverage derived contract;
- final target presentation contract.

### Level Up

Already available:

- all current rolls;
- roll ranges/quality;
- structured Primary recommendation;
- Alternative;
- skipped-important analysis;
- Fit/feasibility consequence for current anchor;
- gamble comparison metrics.

Missing/evolution required:

- persistent AssignedBuild;
- Advisor anchoring semantics using AssignedBuild;
- explicitly structured impact on both Assigned Build and intrinsic Best Fit when they differ;
- validated conditional-branch semantics matching the target Gamble contract;
- target public presentation schema.

### Recruitment

Already available:

- recruits extracted from save;
- settlement grouping/public recruit state where parser exposes it.

Missing:

- Background × Archetype prior model;
- Recruit known-evidence analytical model;
- explicit `prior_only` / `known_evidence_estimate` contract;
- deterministic Top Potential field/derivation in backend;
- Relevant Roster Need contract;
- recruit observation/freshness state;
- recruit identity if history required;
- target public presentation schema.

---

## 8. Target public dataset evolution

The current v1 contract should be preserved as an explicit compatibility baseline.

Recommended planning principle:

> Design one coordinated Target UI contract revision rather than allowing #74, #91, AssignedBuild, Company Planning and Recruitment to each independently mutate the report contract.

Potential logical additions/evolutions include:

```text
roster
  + durable identity when available
  + AssignedBuild resolved state
  + MechanicalFacts
  + local validity

classification
  + evolved intent-aware LevelUpAdvice / target presentation payload

company_analysis     (new logical artifact, if justified)
analysis_health      (new logical artifact, likely #74)
recruit_analysis     (new logical artifact, once model exists)
```

The exact file topology should be decided by the contract owner.

Because v1 validates an exact file set, any added logical file requires explicit schema/version compatibility work.

Do not make `report.js` derive these semantics from the old six files if the backend can own them explicitly.

---

## 9. Revised dependency graph

### Parallel discovery / contract lane

These can meaningfully proceed in parallel:

```text
#79 CampaignIdentity
#85 BuildIdentity
#86 durable-state lifecycle
#89 analytical-purity contract
#91 Mechanical Facts
#71 single-save recruit freshness investigation
Background-potential model work
```

### Identity / intent lane

```text
#79
 ↓
#77 BrotherIdentity
 ↓
#81 AssignedBuild
```

with:

```text
#85 BuildIdentity
#86 state lifecycle
#89 purity
```

feeding the final AssignedBuild/persistence contract.

### Durable state / invalidation lane

```text
#86 → #95
#89 → #88
#85 ─┐
#81 ─┼→ #88 final dependency rules
#83 ─┘
```

### Local web runtime lane

Current epic dependency remains broadly sound:

```text
#94 DONE

#95 + #96 + #97 + #87
            ↓
           #98
            ↓
           #99
            ↓
           #100
            ↓
           #101
            ↓
           #102
```

with the precise parallelization defined by existing issue dependencies.

### Target UI data lane

```text
#61 DONE → Gear
#91 → Mechanical Facts
#74 → public Run Health

#79 → #77 → #81 → AssignedBuild
#85 ────────────────┘

#72 conclusions now supplied by Target UI
        → Company Planning/Coverage contract

Background prior model
        → Recruit known-evidence model
        → Relevant Need + recruit presentation contract

all target contracts
        → coordinated public dataset revision
        → target UI implementation / #100 reconciliation
```

---

## 10. Existing issues that should not be duplicated

Before any new target-UI implementation issue is created, explicitly check overlap with:

- #74 Run Health UI/public contract;
- #77 BrotherIdentity;
- #79 CampaignIdentity;
- #81 AssignedBuild;
- #85 BuildIdentity;
- #86 durable state;
- #87 write path;
- #88 invalidation;
- #89 analytical purity;
- #91 Mechanical Facts;
- #92 Gear UI;
- #93 local-first epic;
- #95–#100 web application foundation/UI;
- #71/#84 recruit freshness/identity;
- #72/#73 Roster Management study/UX.

The target-UI ticket graph should reference/reuse these, not recreate them under new names.

---

## 11. Artifacts the Target UI work has now supplied

The design project itself has produced artifacts that were previously missing.

### Supplied

#### Target product / semantic contract

```text
bb_target_ui_spec_final.md
```

#### Validated interactive target

```text
bb_target_ui_company_brother_levelup_recruitment_mockup_v16.html
```

#### Implementation sequencing proposal

```text
bb_target_ui_implementation_roadmap.md
```

#### This repo reconciliation

```text
bb_target_ui_repo_reconciliation.md
```

### These artifacts materially answer parts of

- #72 product role / information architecture;
- #73 target UX direction;
- #81 AssignedBuild UX separation;
- #89 semantic-purity product rules;
- #100 visual artifact checkpoint.

They do not automatically close those issues because several require repository/code studies or implementation.

---

## 12. Artifacts still genuinely missing

### Critical contract artifacts

1. **CampaignIdentity evidence/contract** — #79
2. **BrotherIdentity contract** — #77
3. **BuildIdentity + definition migration contract** — #85
4. **durable-state lifecycle contract** — #86
5. **AssignedBuild final persistence semantics** — #81
6. **dependency/invalidation matrix** — #88
7. **safe interactive write contract** — #87

### Target-data artifacts

8. **Mechanical Facts machine contract** — #91
9. **Company Planning/Coverage backend contract**
10. **Background × Archetype probability model**
11. **Recruit known-evidence estimate model**
12. **Relevant Roster Need contract**
13. **Recruit observation/freshness contract** — #71/#84 where history is needed
14. **public Run Health contract** — #74
15. **local result validity/provenance contract**

### Presentation integration artifacts

16. **coordinated next-version Target UI report dataset**
17. **final mapping of #100 to the validated Target UI**
18. **browser-level real-data fixtures for the three validated target surfaces**

---

## 13. What should happen next

Do **not** create a fresh “implement target UI” mega-ticket yet.

Recommended next planning action:

1. treat the final target spec as approved product/UX input;
2. reconcile it formally with #72/#73/#89/#100;
3. resolve or progress the critical contract studies, especially #79/#85/#86/#89;
4. identify the exact Target UI public dataset revision after the contract owners are known;
5. then construct the ticket graph around existing issues rather than duplicating them.

The next ticket graph should distinguish:

```text
existing issue reused
existing issue needs scope update
existing issue likely superseded
genuinely new issue required
missing artifact before issue can start
```

No GitHub state change should occur without explicit owner approval.
