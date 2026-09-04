# BB Save Toolkit — Backlog Reconciliation Against the Validated Target UI

**Date:** 2026-08-31
**Repository:** `yannkahloun-alt/BB-Save-Toolkit`
**Target UI source of truth:** `bb_target_ui_spec_final.md` + validated v16 prototype
**Action taken:** analysis only — **no GitHub issue was modified, closed or created**

---

## 1. Purpose

This document classifies the existing backlog against the now-validated Target UI.

Each relevant issue receives a **primary disposition**:

```text
REUSE EXISTING ISSUE
UPDATE / EXPAND EXISTING ISSUE
SUPERSEDED BY TARGET SPEC
NEW ISSUE REQUIRED
```

and, separately where relevant:

```text
BLOCKED BY MISSING ARTIFACT / PREREQUISITE
```

The blocker flag is deliberately separate from disposition. An issue can be the correct existing owner of a problem **and** still be blocked by missing identity, persistence, data or evidence.

---

# 2. Executive result

The target implementation does **not** need a new mega-ticket replacing the current backlog.

Most foundations already have the correct issue owners.

The main reconciliation actions are:

1. **keep and reuse** the identity, persistence, runtime, health and mechanics issues;
2. **update #81, #89, #93, #92 and especially #100** so they consume the validated target design rather than rediscovering it;
3. treat **#72 and #73 as superseded at the product/UX level** by the validated `Company` architecture;
4. create new issues only for genuinely missing analytical/data contracts and independently reviewable target-UI implementation slices;
5. do not start final UI implementation while critical identity/persistence contracts remain unresolved.

The most important no-go:

> Do not execute #73 or #100 literally from their current wording without reconciling them with the validated Target UI.

---

# 3. Completed foundations — no replacement work

These are already completed and should be treated as prerequisites, not reopened.

| Issue | Status | Target-UI relevance |
|---|---|---|
| #48 Output retention | DONE | Confirms generated output retention is separate from durable user state |
| #61 Equipped Gear in roster JSON | DONE | Supplies Brother `Equipment` / `GearFatigue` |
| #94 Transport-independent analysis service | DONE | Core service boundary for local web app / UI |

No new issues should duplicate these foundations.

---

# 4. Existing backlog classification

## 4.1 Target-facing / product-facing issues

| Issue | Primary disposition | Recommendation | Blocker / missing artifact |
|---|---|---|---|
| **#69 In-Game Level Advisor** | **REUSE EXISTING ISSUE** | Keep as separate future integration study. Target UI provides a clearer Advisor data contract but does not replace the in-game integration question. | Durable Campaign/Brother identity if cross-save linking is required; #81 if in-game Advisor follows AssignedBuild |
| **#70 Runtime optimization** | **REUSE EXISTING ISSUE** | Keep independent. Faster analysis materially benefits auto-refresh/local-first but is not a UI redesign dependency. | Benchmark evidence / profiling only |
| **#71 Recruit freshness** | **REUSE EXISTING ISSUE** | Keep as the source of truth for freshness semantics. Target Recruitment must remain conservative until evidence exists. | #79/#80 only if history is required |
| **#72 Roster Management study** | **SUPERSEDED BY TARGET SPEC** | The product question has now been answered by the validated Target UI: useful Roster Management behavior becomes `Company → Planning/Coverage + Fit Matrix`. Preserve the issue as provenance, but do not run another unconstrained product study. | Data feasibility still needs implementation contracts |
| **#73 Roster Management UX redesign** | **SUPERSEDED BY TARGET SPEC** | Do not redesign a standalone `Roster Management` tab. That top-level surface no longer exists in the target architecture. Replace its implementation role with Company-target implementation work. | Replacement Company implementation/data issues must exist before closing/superseding |
| **#74 Analysis Health in report** | **REUSE EXISTING ISSUE** | Direct match for target shell `Run Health`. Keep scope focused on public health contract + global presentation. | Coordinated public report-contract evolution |
| **#78 Since previous analysis** | **REUSE EXISTING ISSUE** | Future cross-cutting/history capability. Not a blocker for the baseline Target UI. | #79 + #80 + #77 |
| **#81 AssignedBuild study** | **UPDATE / EXPAND EXISTING ISSUE** | Keep issue, but reference the validated Target UI as approved UX/semantic evidence. Remove the need to rediscover `AssignedBuild vs Best Fit` presentation. Narrow remaining study to persistence semantics, identity, lifecycle and downstream dependency contract. | #79 + #77; coordinate #85/#86/#89 |
| **#89 Analytical purity** | **UPDATE / EXPAND EXISTING ISSUE** | Target UI already establishes the normative product boundary. Update issue to treat final target spec as input and focus remaining work on repository dependency audit + purity regression tests. | #81 semantics where intent-aware outputs are concerned |
| **#90 Fatigue viability over turns** | **REUSE EXISTING ISSUE** | Keep explicitly future-only. Target architecture already reserves this as Scenario Analysis, not current Fit/Mechanics. | Explicit action-scenario model; not a baseline blocker |
| **#91 Mechanical Facts** | **REUSE EXISTING ISSUE** | Excellent match with validated Brother → Mechanics. Execute without alert semantics or Fit coupling. | Missing normalized item metadata if discovered |
| **#92 Gear UI** | **UPDATE / EXPAND EXISTING ISSUE** | Preserve its semantic/data requirements but replace “add to current report layout” with implementation against the validated Brother target architecture, or explicitly scope it as reusable interim component work. Do not freeze the legacy report layout. | #91 for Mechanics subsection; target UI implementation context |
| **#100 Web UI** | **UPDATE / EXPAND EXISTING ISSUE — CRITICAL** | This must become the umbrella/local-app UI issue that explicitly adopts the validated Target UI. Its current “reuse existing report where practical / no assumed redesign” wording is obsolete as implementation guidance. | #96/#98/#99/#87 + target public data contracts |
| **#103 Hosted readiness** | **REUSE EXISTING ISSUE** | Keep non-blocking. Target UI should remain reusable but hosting remains outside local-first milestone. | #97/#98 boundaries for final study |

---

## 4.2 Identity / persistence / coherence issues

| Issue | Primary disposition | Recommendation | Blocker / missing artifact |
|---|---|---|---|
| **#77 BrotherIdentity** | **REUSE EXISTING ISSUE** | Correct owner for stable cross-save Brother identity. Do not replace it. | **BLOCKED: #79 CampaignIdentity** |
| **#79 CampaignIdentity** | **REUSE EXISTING ISSUE** | Critical-path study. Highest-value identity work to progress now. | Real-save evidence including same-map-seed independent campaigns |
| **#80 Save lineage** | **REUSE EXISTING ISSUE** | Keep separate from CampaignIdentity and AssignedBuild. Not required if AssignedBuild is campaign-global. | **BLOCKED: #79** |
| **#82 Toolkit-managed campaign fallback** | **REUSE EXISTING ISSUE** | Keep conditional. Only execute if #79 cannot establish strong native/composite identity. | **BLOCKED: #79 conclusion** |
| **#83 Incremental cache campaign boundaries** | **REUSE EXISTING ISSUE** | Keep. Current audit can proceed; final campaign-aware behavior waits for #79. Important before AssignedBuild alters Advisor cache dependencies. | Partial: #79 for final design |
| **#84 Recruit/recruit-pool identity** | **REUSE EXISTING ISSUE** | Keep conditional on #71 proving history is needed. | #79 and potentially #80 |
| **#85 BuildIdentity** | **REUSE EXISTING ISSUE** | Critical parallel study. Correct owner for stable build IDs and definition migration semantics. | Existing config/code audit; no identity prerequisite for initial study |
| **#86 Durable user-state lifecycle** | **REUSE EXISTING ISSUE** | Critical parallel study. Correct owner for storage topology, migration, atomicity, retention boundary and backup. | None for study; implementation follows conclusions |
| **#87 Browser → durable-state write path** | **REUSE EXISTING ISSUE** | Correct architecture study. Local loopback direction is now stronger because of #93/#98, but authority/security/concurrency still need formalization. | #86 plus identity semantics for AssignedBuild use case |
| **#88 Dependency/invalidation** | **REUSE EXISTING ISSUE** | Correct owner for invalidation graph and mixed-generation safety. Target spec supplies semantic constraints but not technical graph. | #89 conclusions + #81/#85 semantics |
| **#95 Per-user application state** | **REUSE EXISTING ISSUE** | Correct implementation foundation. Must stay generic enough to host save preference, archetypes and future user state. | **BLOCKED: #86; coordinate #85** |
| **#96 Archetype overrides** | **REUSE EXISTING ISSUE** | Keep. Archetype management is application configuration, not a new top-level analytical workspace. | #85 + #95 + #88 |
| **#97 Background job coordinator** | **REUSE EXISTING ISSUE** | Keep. Essential for responsive local UI and stale-result protection. | #95 + #88; #94 is done |
| **#98 Loopback API** | **REUSE EXISTING ISSUE** | Keep. Correct transport for interactive local app. It will likely need domain-specific AssignedBuild mutation later, not a generic JSON write endpoint. | #87 + #95/#96/#97 |
| **#99 Save watcher** | **REUSE EXISTING ISSUE** | Keep. Directly supplies shell freshness/current/stale semantics. | #95 + #97 + #98 |
| **#101 Windows packaging** | **REUSE EXISTING ISSUE** | Keep unchanged conceptually. | #95 + #98 + #100; owner delivery artifacts |
| **#102 Integrated quality gate** | **REUSE EXISTING ISSUE** | Keep as final system-level gate. Expand its UI fixtures later to include validated target workflows. | #94–#101 implementation complete |

---

## 4.3 Data quality / reproducibility issues

| Issue | Primary disposition | Recommendation | Blocker / missing artifact |
|---|---|---|---|
| **#75 Save-visible unresolved references** | **REUSE EXISTING ISSUE** | Keep. Improves trustworthiness of Gear/Recruit/Brother displays and Run Health. | Representative degraded archives |
| **#76 Pin external references** | **REUSE EXISTING ISSUE** | Keep independent. Important reproducibility foundation, but not a direct UI blocker. | Pinned upstream revisions / update workflow |
| **#93 Local-first epic** | **UPDATE / EXPAND EXISTING ISSUE** | Keep as parent epic, but update tracking: #94 is complete and the validated Target UI should now be referenced as the approved analytical UI direction. | No blocker to updating epic; implementation still follows child dependencies |

---

# 5. Issues that should NOT be executed literally anymore

## 5.1 #72 — Roster Management study

Its original question was:

> What should Roster Management become?

The validated target has answered that:

```text
Company
├─ Roster
├─ Planning / Coverage
└─ Fit Matrix
```

with Brother as a dedicated context.

The remaining work is no longer a product-design study. It is:

- define the Company-level derived data contract;
- implement Company against that contract;
- validate it with real data.

### Recommended eventual GitHub disposition

After the target artifacts are attached/referenced:

```text
#72 → close as completed / design study resolved by Target UI
```

Do not do this until the project explicitly accepts the target spec as #72's study output.

---

## 5.2 #73 — standalone Roster Management UX redesign

The requested destination no longer exists as a top-level tab.

Executing it now would actively move the product away from the validated architecture.

### Recommended eventual GitHub disposition

After replacement Company implementation issues exist:

```text
#73 → close as not planned / superseded by Target UI architecture
```

Its useful acceptance ideas — roster questions, drill-down, Best Fit vs AssignedBuild separation, realistic roster sizes — should be carried into Company implementation tickets.

---

## 5.3 #100 — current wording is too narrow

#100 currently assumes:

> reuse current report and public JSON where practical

and says it does not assume a visual redesign.

That made sense before the design project.

It is now misleading.

The owner has produced and validated a comprehensive target redesign.

### #100 should become

The **local application UI umbrella**, responsible for integrating:

```text
application shell / save flow / freshness
+
validated analytical target UI
+
archetype management
```

It should reference the final Target UI artifacts rather than derive UI from the legacy report.

---

# 6. Existing issues that need explicit target-artifact references

These should likely be updated later, but no update has been made.

## #81 AssignedBuild

Attach/reference:

```text
bb_target_ui_spec_final.md
```

as approved evidence for:

- explicit AssignedBuild;
- Best Fit remains independent;
- disagreement remains visible;
- Brother and Level Up presentation;
- no recruit AssignedBuild.

The unresolved study should focus on:

- campaign-global vs historical semantics;
- identity prerequisites;
- persistence;
- migration;
- downstream recomputation.

---

## #89 Analytical purity

Use the target spec as normative product classification:

```text
Intrinsic:
  raw projections
  Fit
  Best Fit / BestRole
  recruit intrinsic potential

Intent:
  AssignedBuild

Intent-aware:
  Level Advisor toward AssignedBuild
  intended Company coverage

Mixed/decomposable:
  roster planning
  recruitment decision support
```

Then audit the actual code to prove/enforce it.

---

## #92 Gear UI

Replace legacy-layout assumptions with:

```text
Brother → Gear
Brother → Mechanics
```

and preserve the already-correct semantic constraints:

- Gear belongs to Brother;
- facts != warnings;
- Gear/Mechanics do not modify intrinsic Fit;
- no global Gear tab.

---

## #93 Local-first epic

At minimum eventually record:

```text
#94 completed
Target UI artifacts now exist
#100 visual artifact checkpoint satisfied
```

and link the target design as product direction.

---

## #100 Web UI

This is the single most important update.

It should explicitly adopt:

```text
Company | Level Up | Recruitment
```

and the final spec/prototype as implementation input.

---

# 7. Genuinely NEW issues required

The following work does not currently have a sufficiently explicit owner in the existing backlog.

These are proposed issue **concepts only**. No issues have been created.

---

## NEW-1 — Define and implement the Target UI public dataset contract

### Why new

The current `bbtool.reference_analysis.v1` has an exact six-file contract.

Target UI requires additional structured state beyond those six files.

### Scope

Coordinate the next public presentation contract for at least:

- durable identities when available;
- resolved AssignedBuild;
- Mechanical Facts;
- Company Planning/Coverage;
- evolved Level Up decision evidence;
- Run Health;
- Recruitment analysis;
- freshness/current/stale provenance as appropriate.

### Dependencies

```text
#74
#77/#79
#81/#85
#88/#89
#91
Company-analysis contract
Recruitment-analysis contracts
```

Not all upstream implementations must finish before schema exploration, but the contract should not freeze unknown semantics prematurely.

---

## NEW-2 — Implement persistent AssignedBuild domain state

### Why new

#81 is a study.

#95 supplies generic durable storage.

No current issue clearly owns implementation of:

```text
CampaignIdentity
+ BrotherIdentity
+ BuildIdentity
→ AssignedBuild
```

with domain validation, read model and clear/change operations.

### Dependencies

```text
#79
#77
#81 approved semantics
#85
#86
#95
#89
```

and coordinate post-write behavior with #88/#87/#98.

---

## NEW-3 — Make Level Advisor intent-aware without contaminating Best Fit

### Why new

The current Advisor anchors to analytical BestRole.

The Target UI requires an explicit intended-build decision tool when AssignedBuild exists.

### Scope

- anchor recommendation to AssignedBuild where semantically approved;
- preserve intrinsic Best Fit separately;
- expose structured consequence on both trajectories when different;
- preserve all rolls and Explain data;
- keep cache fingerprints complete.

### Dependencies

```text
NEW-2 AssignedBuild
#88
#89
#85
existing Advisor engine
```

---

## NEW-4 — Company Planning / Coverage analytical contract

### Why new

The Target UI has resolved the UI role, but current backend primarily exposes Brother × Archetype Fit and summaries.

The Company view needs explicit roster-level derived semantics.

### Scope candidates

- intended depth;
- intrinsic viable depth;
- gaps;
- redundancy;
- replacement risk;
- role scarcity;
- inputs suitable for Relevant Roster Need.

Avoid one opaque Company score.

### Dependencies

Intrinsic-only portions can begin now.

Intent-aware portions depend on:

```text
#81 / NEW-2
#89
#88
```

---

## NEW-5 — Background × Archetype potential model

### Why new

Recruitment target requires an intrinsic background prior.

No current issue owns the full production analytical contract.

### Required output concept

```text
Background
× Archetype
→ distribution / probability / potential
```

It must be versioned, deterministic and explainable.

This is the foundational Recruitment analytical artifact.

---

## NEW-6 — Recruit known-evidence analytical model

### Why new

Recruitment distinguishes:

```text
prior_only
known_evidence_estimate
```

The backend must determine when candidate-specific evidence exists and how it updates the background prior.

### Dependencies

```text
NEW-5 Background prior
recruit parser/data contract
#89 analytical purity
```

Roster need must not alter intrinsic candidate estimates.

---

## NEW-7 — Recruitment Relevant Roster Need model

### Why new

The validated UI explicitly rejected:

```text
Relevant Need = highest global company gap
```

Need must be related to the candidate's viable archetypes.

### Required decomposition

```text
candidate intrinsic potential
+
company need
→ relevant decision context
```

without modifying candidate intrinsic potential.

### Dependencies

```text
NEW-4 Company Planning
NEW-5/NEW-6 recruit potential
#89
```

---

## NEW-8 — Implement recruit observation/freshness history, IF supported

### Why conditional

#71/#84 are feasibility studies.

Only create this implementation issue after they establish safe semantics.

Possible outputs include:

- first observed;
- last observed;
- unchanged observed state;
- pool generation/freshness if provable.

Never create an implementation issue that promises game refresh age before evidence exists.

---

## NEW-9 — Shared Target UI shell implementation

### Why new

#100 is too broad to be a single reviewable implementation diff.

A child issue should own:

- `Company | Level Up | Recruitment` navigation;
- sticky shell;
- freshness/current/stale status;
- Run Health placement;
- responsive shell behavior;
- shared context/state routing.

### Dependencies

```text
#74
#99
NEW-1 target dataset
#100 umbrella
```

---

## NEW-10 — Company + Brother Target UI implementation

### Why new

Company/Brother target has been fully validated and should be an independently testable implementation slice.

### Dependencies

Baseline can consume existing data.

Full target depends on:

```text
NEW-1
NEW-2 AssignedBuild
NEW-4 Company Planning
#91/#92 for mechanics/gear
```

---

## NEW-11 — Level Up Target UI implementation

### Why new

The surface has a validated workstation design and should not be hidden inside a generic #100 implementation.

### Dependencies

```text
NEW-1
NEW-2
NEW-3
#100
```

---

## NEW-12 — Recruitment Target UI implementation

### Why new

The surface has a validated settlement-first UI but needs real analytical contracts.

### Dependencies

```text
NEW-1
NEW-5
NEW-6
NEW-7
#71/#84 only for optional history/freshness enrichment
#100
```

---

# 8. Optional new issue, not baseline blocker

## Local result validity / provenance

The Target UI architecture supports selective local degraded-state indicators.

Do not create this blindly.

First determine under #74 whether `run_health` can reliably identify the affected analytical records.

If yes, a small additive contract can expose:

```text
result validity / degraded basis
```

at the appropriate object level.

If not, keep only global Run Health rather than inventing fake local precision.

---

# 9. Work that is BLOCKED by missing artifacts

This is the blocker view independent of issue disposition.

| Work | Missing prerequisite artifact / evidence |
|---|---|
| Durable BrotherIdentity | #79 CampaignIdentity conclusion |
| Persistent AssignedBuild | CampaignIdentity + BrotherIdentity + BuildIdentity + durable-state contract |
| Intent-aware Advisor | AssignedBuild implementation + purity/invalidation rules |
| Intended Company coverage | AssignedBuild implementation |
| Historical recruit freshness | CampaignIdentity + lineage + recruit/pool identity if single-save evidence is insufficient |
| Final target report schema | Stable enough upstream domain contracts |
| Recruitment candidate-specific estimates | Background prior model + known-evidence model |
| Relevant Roster Need | Company need contract + recruit viable-potential model |
| Local validity markers | Proven mapping from degraded input to affected result |
| Windows installed-app validation | Windows/distribution/signing/update artifacts from owner |
| Real save watcher validation | Evidence of actual Battle Brothers Windows save-write behavior if synthetic evidence is insufficient |

---

# 10. Critical path after reconciliation

The target UI itself is no longer the uncertainty.

The primary uncertainty is domain persistence + data contracts.

```text
                 ┌──────────── #85 BuildIdentity ────────────┐
                 │                                            │
#79 CampaignID ──┴→ #77 BrotherID ─→ #81 study ─→ NEW-2 AssignedBuild
                                      │              │
#86 state contract ─→ #95 state ──────┘              │
#89 purity ───────────────→ #88 invalidation ─────────┤
                                                     ↓
                                         NEW-3 intent-aware Advisor
                                                     │
                                                     ↓
                                             Level Up target UI
```

Parallel:

```text
#91 Mechanics ──────────────→ Brother target UI

#74 Run Health ─────────────→ Shared shell

NEW-5 Background prior
        ↓
NEW-6 known-evidence recruit model
        ↓
NEW-7 Relevant Need ← NEW-4 Company Planning
        ↓
Recruitment target UI
```

Local application:

```text
#94 DONE
  ↓
#95 / #96 / #97
  ↓
#98
  ↓
#99
  ↓
#100 reconciled umbrella
  ↓
NEW-9 / NEW-10 / NEW-11 / NEW-12
  ↓
#101
  ↓
#102
```

Exact parallel execution should still respect the dependencies written in the existing issues.

---

# 11. Recommended GitHub changes — NOT YET APPLIED

If the owner approves a later mutation pass, the safest sequence would be:

1. **Update #93**
   - mark/reference #94 as completed;
   - reference final Target UI artifacts;
   - state that #100 will consume the approved target architecture.

2. **Update #100**
   - adopt `Company | Level Up | Recruitment`;
   - reference final spec + v16 prototype;
   - retain first-run/save/freshness/archetype-management responsibilities;
   - become umbrella for target UI child implementation issues.

3. **Update #81**
   - treat target AssignedBuild UX as resolved input;
   - narrow unresolved work to persistence semantics/identity/lifecycle.

4. **Update #89**
   - treat target purity rules as normative input;
   - narrow study toward code dependency audit and regression enforcement.

5. **Update #92**
   - point Gear/Mechanics presentation at validated Brother architecture instead of legacy report layout.

6. **Resolve #72 as completed**
   - only after attaching/referencing the target design as its study outcome.

7. **Supersede #73**
   - only after replacement Company implementation/data issues are available.

8. Create only the genuinely new issues listed in section 7, with explicit dependencies.

No such change was made during this review.

---

# 12. Recommended implementation grouping

Do not create one giant `Implement target UI` ticket.

Recommended hierarchy:

```text
#93 Local-first epic
└─ #100 Web UI umbrella, updated
   ├─ Target public dataset / presentation contract
   ├─ Shared target shell
   ├─ Company analytical contract
   ├─ Company + Brother UI
   ├─ Intent-aware Level Advisor contract
   ├─ Level Up UI
   ├─ Recruitment background prior
   ├─ Recruit known-evidence analysis
   ├─ Recruitment Relevant Need
   └─ Recruitment UI
```

Existing issues remain dependencies rather than being duplicated inside this tree.

---

# 13. Immediate priority order

If implementation resources are available now, the best work to start first is not CSS.

### Priority 1 — parallel contract work

```text
#79 CampaignIdentity
#85 BuildIdentity
#86 durable-state lifecycle
#89 analytical-purity code audit
#91 Mechanical Facts
NEW-5 Background × Archetype prior
NEW-4 Company Planning analytical design
```

### Priority 2 — after the corresponding studies

```text
#77 BrotherIdentity
#95 persistent app state
#88 invalidation
NEW-2 AssignedBuild
```

### Priority 3 — local runtime + analytical expansion

```text
#96
#97
#87
#98
NEW-3 intent-aware Advisor
NEW-6 recruit known-evidence
NEW-7 Relevant Need
#74 public health
```

### Priority 4 — freeze coordinated target public contract

```text
NEW-1
```

### Priority 5 — actual target UI

```text
#99
#100 updated
NEW-9 shell
NEW-10 Company/Brother
NEW-11 Level Up
NEW-12 Recruitment
```

### Priority 6 — delivery

```text
#101
#102
```

Some work can overlap; this is dependency priority, not a demand for strict serial execution.

---

# 14. Final disposition summary

## REUSE EXISTING ISSUE

```text
#69 #70 #71 #74 #75 #76 #77 #78 #79 #80
#82 #83 #84 #85 #86 #87 #88 #90 #91
#95 #96 #97 #98 #99 #101 #102 #103
```

## UPDATE / EXPAND EXISTING ISSUE

```text
#81  AssignedBuild — target UX now approved
#89  Analytical purity — target semantics now approved
#92  Gear UI — point presentation at Target Brother
#93  Local-first epic — reflect #94 completion + target UI
#100 Web UI — adopt validated target architecture
```

## SUPERSEDED BY TARGET SPEC

```text
#72  Roster Management product study
#73  standalone Roster Management UX redesign
```

## DONE FOUNDATION

```text
#48
#61
#94
```

## NEW ISSUE REQUIRED

```text
1. Target UI public dataset / presentation contract
2. Persistent AssignedBuild domain implementation
3. Intent-aware Level Advisor + dual trajectory evidence
4. Company Planning / Coverage analytical contract
5. Background × Archetype potential model
6. Recruit known-evidence analytical model
7. Recruitment Relevant Roster Need model
8. Recruit observation/freshness implementation — conditional
9. Shared Target UI shell
10. Company + Brother Target UI
11. Level Up Target UI
12. Recruitment Target UI
```

Potential local-result-validity issue remains conditional on evidence.

---

# 15. Decision

The backlog is coherent enough to proceed.

There is no need for another broad architecture or UX design phase.

The project should now move into:

```text
contract resolution
→ data implementation
→ coordinated public contract
→ validated target UI implementation
```

while reusing the existing local-first epic and its foundation.

**No repository or GitHub issue was changed by this classification pass.**
