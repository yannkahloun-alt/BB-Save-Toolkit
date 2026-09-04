# Battle Brothers Save Toolkit — Target UI Implementation Roadmap v2

**Status:** reconciled with repository state on 2026-08-31
**Target UI:** validated Company/Brother, Level Up, Recruitment
**Rule:** reuse existing issues/contracts; do not duplicate work
**Ticket creation:** not performed here

---

## 1. Key corrections from roadmap v1

The first roadmap was intentionally target-oriented and overestimated several missing foundations.

Repository reconciliation changes the plan:

### Already done

- transport-independent analysis service (#94);
- strict JSON-driven public report contract (`bbtool.reference_analysis.v1`);
- render-only / serve-report presentation separation;
- Brother Gear extraction (#61);
- structured Level-Up Advisor payload.

### Still missing

- durable identities;
- user-state lifecycle/persistence;
- AssignedBuild;
- invalidation/write path;
- Mechanical Facts;
- public Run Health;
- Company Planning contract;
- Recruitment analytical models;
- coordinated target presentation contract;
- local web runtime/API/watcher;
- actual target UI implementation.

The roadmap should therefore start from **contracts + existing local-web epic**, not from analysis/report decoupling.

---

## 2. Lane A — identity and durable intent

### A1. Campaign identity

Owner issue:

```text
#79
```

Required for safe campaign-local persistence.

### A2. Brother identity

Owner issue:

```text
#77
```

Blocked by #79.

Current `BrotherID = human:<HumanOffset>` remains save-local and must not be promoted to durable identity.

### A3. Build identity

Owner issue:

```text
#85
```

Can progress in parallel with #79.

Must establish:

- stable BuildIdentity;
- mutable DisplayName;
- BuildDefinition semantics/hash;
- rename/redefinition/removal migration.

### A4. AssignedBuild

Owner issue:

```text
#81
```

Requires #79 + #77, and must align with #85/#86/#89.

Target contract:

```text
AssignedBuild = explicit player intent
BestRole      = intrinsic analysis
```

### Gate A

No persistent AssignedBuild mutation ships until campaign, brother and build references are safe enough to avoid attaching player intent to the wrong object.

---

## 3. Lane B — durable state and mutation coherence

### B1. Durable-state lifecycle

Owner issue:

```text
#86
```

Defines the lifecycle contract.

### B2. Persistent state implementation

Owner issue:

```text
#95
```

Blocked by #86; coordinates #85.

### B3. Analytical purity

Owner issue:

```text
#89
```

The final Target UI supplies product-level classifications.

Repository audit/tests still required.

### B4. Dependency/invalidation

Owner issue:

```text
#88
```

Turns semantic classification into:

- dependency graph;
- cache/fingerprint rules;
- targeted invalidation;
- stale/mixed-generation semantics.

### B5. Browser write path

Owner issue:

```text
#87
```

Interactive Target UI mutation must use the authoritative local state layer.

Static/report-only contexts must never pretend a browser-only change is persisted.

### Gate B

Before interactive intent controls:

```text
durable state
+ safe IDs
+ bounded mutation API contract
+ post-write invalidation semantics
```

must all be defined.

---

## 4. Lane C — local-first application foundation

This lane is already tracked by epic #93.

### C0. Analysis service

```text
#94 DONE
```

### C1. User state

```text
#95
```

### C2. Archetype override model

```text
#96
```

Depends on #85/#88/#94/#95.

### C3. Background jobs / stale protection

```text
#97
```

Depends on #94/#95/#88.

### C4. Loopback API

```text
#98
```

Depends on #94/#95/#96/#97 and safe write architecture #87.

### C5. Save watcher / freshness state

```text
#99
```

Depends on #95/#97/#98.

### C6. Web UI

```text
#100
```

Depends on #96/#98/#99 and #87.

**Before execution, #100 must be reconciled with the validated Target UI.**

### C7. Windows delivery

```text
#101
```

### C8. Integrated quality

```text
#102
```

---

## 5. Lane D — target Brother current-state data

### D1. Gear

```text
#61 DONE
```

Use existing `Equipment` / `GearFatigue`.

### D2. Mechanical Facts

```text
#91
```

Required for target Brother → Mechanics.

Preserve:

```text
Fact != Alert
Gear/Mechanics -X-> intrinsic Fit
```

### D3. Gear presentation

Existing issue:

```text
#92
```

Its data/component work may be useful before the full redesign, but its current-report layout must not override the validated Brother target architecture.

### D4. Run Health public exposure

```text
#74
```

Backend health exists.

Need public target contract + shell presentation.

---

## 6. Lane E — Company target analysis

### Product role — resolved by validated Target UI

The old standalone Roster Management concept becomes:

```text
Company
  ├─ Roster
  ├─ Planning / Coverage
  └─ Fit Matrix
```

Relevant existing issues:

```text
#72
#73
```

They should be reconciled against the validated Company architecture before any new Company implementation issue is created.

### Backend/data gap

Need an explicit Company-level contract for:

- assigned depth;
- intrinsic viable depth;
- coverage;
- gaps;
- replacement risk;
- planning/recruitment-relevant need.

Do not infer these in report.js from arbitrary UI state if they are analytical outputs.

### Gate E

Company implementation can use current roster/Fit data for early rendering, but full Planning should not freeze until AssignedBuild semantics and the Company-analysis contract are clear.

---

## 7. Lane F — Level Up target implementation

### Existing foundation

The current Advisor already provides:

```text
AllRolls
Recommended
Alternative
PickReasons
SkippedImportant
Fit consequence
Feasibility consequence
Gamble diagnostics
```

### Required evolution

After AssignedBuild:

1. determine intent-aware anchor semantics;
2. preserve independent Best Fit;
3. expose impact on Assigned Build and Best Fit when different;
4. normalize Primary / Runner-up / ConditionalBranch for presentation;
5. keep all rolls public;
6. preserve Explain inputs structurally.

### Important constraint

Do not duplicate current Advisor logic in JavaScript.

### Gate F

Target Level Up implementation is complete only when its displayed consequence evidence comes from structured backend payload rather than frontend reconstruction.

---

## 8. Lane G — Recruitment analytical foundation

### G1. Background prior model

Need a versioned artifact:

```text
Background × Archetype probability distribution
```

This is the prerequisite for the validated Recruitment potential model.

### G2. Recruit known-evidence model

Must support:

```text
prior_only
known_evidence_estimate
```

No candidate-specific estimate without legitimate candidate evidence.

### G3. Top Potential

Backend must own or deterministically expose the intrinsic rule:

```text
if known-evidence estimates exist:
    max(candidate estimate)
else:
    max(background prior)
```

### G4. Relevant Roster Need

Need explicit contract independent from intrinsic candidate quality.

It must not simply select the highest company gap.

### G5. Recruit observation/freshness

Relevant issues:

```text
#71
#84
```

Use only proven semantics.

Game-native refresh age remains unknown unless evidence establishes it.

### Gate G

Recruitment can be implemented with partial states before every future model exists, but it must never fabricate a stronger analytical state than the backend supports.

---

## 9. Lane H — coordinated target report contract

### Current baseline

```text
bbtool.reference_analysis.v1
```

is production infrastructure and must remain an explicit compatibility point.

### Target need

Design the next coordinated public presentation contract after enough upstream contracts are stable.

Likely concerns:

- durable IDs where safe;
- AssignedBuild resolved state;
- Mechanical Facts;
- Company analysis;
- evolved Level Up payload;
- public Run Health;
- Recruitment analysis;
- local result validity/provenance.

### Rule

Avoid sequential schema churn such as:

```text
v2 = health only
v3 = mechanics
v4 = assignment
v5 = recruitment
```

when the target implementation can coordinate these changes safely.

This does not mean blocking independent backend work.

Backend contracts may land first; public report packaging can be coordinated later.

---

## 10. Lane I — target UI presentation

Once the necessary contracts exist, implement against the validated target:

```text
Company | Level Up | Recruitment
```

### I1. Shared shell

- top-level navigation;
- run/freshness status;
- Run Health;
- stale/current state;
- responsive structure.

### I2. Company + Brother

Use validated Company/Brother interactions.

### I3. Level Up

Use validated decision workstation.

### I4. Recruitment

Use validated settlement-first browser and Current settlement band.

### I5. Archetype management / first-run

These remain #100 local-application flows and must be integrated coherently with, not substituted for, the three validated primary analytical workspaces.

---

## 11. What can proceed now in parallel

Without waiting for the entire critical path, useful work can proceed on:

```text
#79 CampaignIdentity study
#85 BuildIdentity study
#86 durable-state study
#89 analytical-purity audit
#91 Mechanical Facts
#71 single-save recruit freshness evidence
Background-potential computation/model work
Company Planning analytical contract design
public Target UI schema design exploration (not frozen)
```

Static fixture/component work can also progress if it does not pretend missing state is authoritative.

---

## 12. What should wait

### Persistent AssignedBuild UI writeback

Wait for identity/state/write/invalidation contracts.

### Intent-aware final Level Up

Wait for AssignedBuild semantics.

### Full Company intended coverage

Wait for AssignedBuild if it relies on player intent.

### Historical recruit freshness

Wait for identity/lineage evidence if single-save evidence is insufficient.

### Public target schema freeze

Wait until enough upstream data contracts are known to avoid unnecessary schema churn.

### #100 visual implementation

Do not execute against the old “current report reuse” assumption without formally adopting the validated Target UI as visual/product input.

---

## 13. Proposed implementation gates

### Gate 0 — existing foundation acknowledged

- #94 done;
- public dataset v1 reused;
- #61 Gear reused;
- Advisor payload reused.

### Gate 1 — identity/state contracts

- #79;
- #77;
- #85;
- #86;
- #81 semantics;
- #89 purity.

### Gate 2 — mutation/runtime contracts

- #88;
- #95;
- #87;
- #96/#97/#98.

### Gate 3 — target data contracts

- #91;
- #74;
- Company Planning;
- evolved Level Up;
- Recruitment models.

### Gate 4 — public target dataset

Versioned, validated, fixture-backed.

### Gate 5 — target UI real-data implementation

Validated Company/Brother, Level Up, Recruitment against real payloads.

### Gate 6 — local app integration

- #99 freshness/watcher;
- #100 flows;
- state restoration;
- stale/current semantics.

### Gate 7 — delivery / E2E

- #101;
- #102.

---

## 14. Testing requirements carried forward from prototype reviews

The prototype review cycle exposed failures that should become explicit tests.

### Company / Brother

- filter/search opens correct Brother;
- return restores Company subview/filter/scroll;
- Brother switch preserves active section;
- no stale Brother DOM;
- no shell/dock overlap.

### Level Up

- all current rolls rendered;
- switch clears all old decision data;
- Primary/Runner-up evidence internally coherent;
- AssignedBuild vs Best Fit remains separate;
- conditional branch omitted when not genuinely distinct;
- mobile time-to-answer.

### Recruitment

- multiple candidates at desktop/980;
- candidate switch preserves browser scroll;
- prior-only emits no candidate estimate;
- Top Potential obeys intrinsic max rule;
- Relevant Need cannot select unrelated company gap;
- settlement observation summary coherent;
- Current settlement sequence stable in both directions;
- shortlist mutation does not reset browser state.

### Cross-cutting

- no horizontal overflow at representative widths;
- no JS errors;
- stale/current report state cannot be confused;
- public dataset validation rejects incompatible/mixed-generation payloads.

---

## 15. Next planning action

The project is now ready for a **ticket-graph reconciliation pass**, not yet blind ticket creation.

That pass should classify each piece of target work as:

```text
REUSE EXISTING ISSUE
UPDATE/EXPAND EXISTING ISSUE
SUPERSEDED BY TARGET SPEC
NEW ISSUE REQUIRED
BLOCKED BY MISSING ARTIFACT
```

Particular attention should go to:

```text
#72
#73
#74
#81
#85–#89
#91
#92
#95–#100
```

Only after that classification should issue bodies/dependencies be edited or new implementation issues created.

No issue state or repository content has been modified by this roadmap.
