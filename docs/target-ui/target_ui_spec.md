# Battle Brothers Save Toolkit — Target UI Specification

**Status:** Final validated target specification
**Validated surfaces:** Company / Brother, Level Up, Recruitment
**Implementation status:** Not implemented by this document
**Repository changes:** None
**Ticket creation:** Out of scope for this document

---

## 1. Purpose

The Battle Brothers Save Toolkit UI has evolved beyond a static HTML report.

The target product is a decision-support application that must preserve analytical transparency while supporting current game state, intrinsic projections, player intent, immediate recommendations, roster planning, recruitment analysis, data trust, and future scenario analysis.

The target architecture is:

- **object-centric**, not feature-tab-centric;
- **decision-centric**, not dashboard-centric;
- explicit about the difference between facts, analysis, intent, and recommendations;
- designed around **Scan → Decision → Explain**;
- responsive without removing decision-critical semantics;
- capable of supporting future history, alerts, scenarios, and richer recruitment models without adding one top-level tab per capability.

The validated top-level workspaces are:

```text
Company | Level Up | Recruitment
```

---

## 2. Semantic model

The UI must preserve four semantic categories.

### 2.1 Fact

Observed or deterministically derived current-state information.

Examples:

- MAtk = 84
- Main Hand = Greatsword
- Gear FAT = -31
- Duelist active/inactive
- observed recruit background
- current level-up rolls

Facts do not express player preference or analytical judgment.

### 2.2 Analysis

Independent analytical evaluation.

Examples:

- Reach DPS Fit = 86
- P(Fit ≥ threshold)
- projected level-11 stats
- background prior for an archetype
- recruit known-evidence estimate
- backend `BestRole`

In player-facing UI, `BestRole` should normally be expressed as:

- **Best Fit**
- **Highest intrinsic Fit**

rather than wording that sounds prescriptive.

### 2.3 Intent

Explicit player choice.

Primary example:

```text
AssignedBuild = BF Tank
```

Intent is persistent player state.

Intent must not rewrite intrinsic analysis.

### 2.4 Recommendation / interpretation

Advice derived from facts, analysis, and optionally intent.

Examples:

- Level Advisor recommends MDef + FAT + HP
- a future alert says a loadout deserves attention
- recruitment priority interpretation
- scenario-dependent advice

Recommendations must remain identifiable as recommendations rather than being presented as facts.

---

## 3. Hard analytical invariants

These rules are part of the product contract.

1. Backend `BestRole` remains the intrinsic analytical result.
2. `AssignedBuild` remains explicit player intent.
3. `Alternatives` remain other viable analytical trajectories.
4. Durable Brother identity is distinct from one save-analysis observation.
5. Gear and perks do not modify intrinsic archetype Fit unless a separately approved analytical model changes that contract.
6. Gear belongs to the Brother's current snapshot, not to an Archetype.
7. Mechanical facts belong to current Brother state, not intrinsic Fit.
8. Scenario results require explicit assumptions and are not current-state facts.
9. Recruit quality remains separate from roster need.
10. Roster need remains separate from recruit quality.
11. `Background × Archetype`, `Recruit Snapshot × Archetype`, and `Brother Snapshot × Archetype` are different analytical relationships.
12. A combined score, if ever introduced, must leave its underlying factors inspectable.
13. Run Health is global, but result-specific degraded validity must be representable locally.
14. Historical/time-based values must expose provenance and confidence.
15. Fatigue-at-turn-X and similar projections belong to Scenario Analysis, not current mechanics or intrinsic Fit.
16. A prior-only recruit must not receive a fabricated candidate-specific probability.
17. Recruit `Top Potential` must be derived only from the strongest available intrinsic analytical layer:
    - prior-only recruit → highest Background Prior;
    - known-evidence recruit → highest Known-evidence Estimate.
18. Roster Need must never alter recruit Top Potential.

---

## 4. Core information objects

### 4.1 Analysis Run / Campaign Context

Represents one generated analysis.

Owns:

- source save / campaign context;
- toolkit version;
- generation metadata;
- global analysis-health summary;
- degraded-data summary;
- result-affecting warnings;
- projection validation status;
- stale/mixed-generation state where applicable;
- historical comparison context where available.

Run Health is global context, not the only owner of result validity.

### 4.2 Brother Identity

Durable person across saves/analyses.

Owns:

- stable Brother identity where available;
- campaign association;
- persistent player-state relationships such as AssignedBuild.

Observed name/title are display labels, not the durable identity key.

### 4.3 Brother Snapshot / Observation

Observed Brother state from one save/analysis.

Owns:

- level / XP;
- stats;
- stars;
- perks;
- traits;
- injuries;
- current rolls;
- gear;
- Gear FAT;
- usable FAT where reliable;
- source analysis/run;
- observation lineage/provenance.

### 4.4 Archetype / Build Definition

Durable analytical definition.

Owns:

- BuildIdentity;
- display name;
- weights;
- baseline / target / required values;
- projection semantics;
- Fit rules;
- leveling-plan association;
- version metadata where required.

### 4.5 Brother Snapshot × Archetype Analysis

Intrinsic relationship between one Brother snapshot and one Build Definition.

Owns:

- Fit;
- likely/full Fit ranges;
- P(Fit ≥ threshold);
- projected level-11 stats;
- expected values;
- Fit components;
- burden / feasibility where applicable;
- development trajectory;
- local validity/provenance where needed.

This relationship is independent of AssignedBuild.

Near-ties must remain representable without fake winner/loser precision.

### 4.6 AssignedBuild

Persistent player intent.

Conceptually:

```text
BrotherIdentity
  └── AssignedBuild → BuildDefinition
```

Owns:

- selected BuildIdentity;
- clear/unassigned state;
- invalid/deprecated target state;
- revision/staleness metadata where required.

AssignedBuild must never modify intrinsic Fit.

### 4.7 Mechanical Facts — Current State

Deterministic interpretations of the current Brother snapshot.

Examples:

- mastery applies or not;
- Duelist active/inactive;
- Shield Expert active/inactive;
- Nimble efficiency;
- Battle Forged reduction;
- Brawny benefit;
- Dodge contribution.

Mechanical Facts are not:

- alerts;
- archetype Fit;
- scenario projections.

### 4.8 Scenario Analysis

Derived result under explicit assumptions.

Owns:

- source Brother snapshot;
- current-state inputs;
- named scenario;
- action pattern;
- assumptions;
- model/version;
- result;
- validity/provenance.

Future fatigue viability at combat turn X belongs here.

### 4.9 Analysis Result Validity / Provenance

Result-local trust metadata.

May represent:

- valid;
- degraded;
- fallback-derived;
- unresolved reference;
- partially stale;
- projection validation concern;
- evidence source.

Healthy local validity should normally remain visually quiet.

### 4.10 Alert

Cross-domain interpretation that something deserves attention.

Alerts are distinct from facts and analysis.

Potential future sources include:

- gear;
- mechanics;
- data quality;
- roster planning;
- recruitment;
- scenario analysis.

Severity/color semantics are not frozen by this spec.

### 4.11 Recruit Identity / Recruit Snapshot

Recruitment must preserve the distinction between durable identity, when reliable, and one observed recruit state.

Recruit Snapshot may own:

- settlement;
- observed name/title;
- background;
- level;
- hire cost;
- wage;
- revealed traits;
- tryout state;
- observation history/provenance.

Recruit identity must not be assumed durable until supported by evidence.

### 4.12 Background × Archetype Analysis

Population-level prior.

Answers:

> How often can this background plausibly develop into this archetype?

It is not a probability about one exact recruit.

### 4.13 Recruit Snapshot × Archetype Analysis

Candidate-specific analysis using only legitimately known recruit evidence.

Possible evidence:

- background;
- public level;
- revealed traits;
- other known recruit information.

If no recruit-specific evidence justifies a different estimate, the UI must show **Background prior only**.

### 4.14 Roster-level Analysis

Company-level analytical context.

Owns concepts such as:

- assigned depth;
- intrinsic alternative depth;
- role coverage;
- replacement risk;
- planning gaps;
- Fit Matrix relationships;
- recruitment-relevant roster need.

Roster-level analysis must not rewrite individual intrinsic quality.

---

## 5. Primary user journeys

### 5.1 Open the analysis

The user should quickly understand:

- whether the run is trustworthy;
- whether anything requires action;
- which Brothers/recruits deserve attention.

### 5.2 Understand one Brother

The user moves from Company into a stable Brother context and can inspect:

- identity/current state;
- Assigned Build;
- Best Fit;
- Gear;
- mechanics;
- Potential;
- Development.

### 5.3 Take a level-up decision

The user opens Level Up and can understand within seconds:

- who is leveling;
- Assigned Build;
- Best Fit;
- all current rolls;
- Primary recommendation;
- Runner-up;
- consequences/trade-off;
- deeper reasoning if desired.

### 5.4 Understand the company

Company supports:

- roster scanning;
- planning/coverage;
- specialist Fit comparison.

It should not become a generic KPI dashboard.

### 5.5 Recruit

Recruitment supports:

- settlement-first browsing;
- multiple candidates visible simultaneously where width permits;
- intrinsic candidate quality;
- roster relevance;
- economics;
- shortlist/package comparison;
- observation/freshness context.

### 5.6 Trust the analysis

Global Run Health plus local degraded-result metadata must make uncertainty visible without overwhelming healthy results.

---

## 6. Primary navigation

Validated top-level navigation:

```text
Company | Level Up | Recruitment
```

### Company

Owns:

- roster operational overview;
- Company planning/coverage;
- Fit Matrix;
- drill-in to Brother.

### Level Up

First-class decision workflow.

It remains top-level because it is frequent, substantial, and time-sensitive.

### Recruitment

Owns current recruit-pool browsing, candidate decision support, and shortlist comparison.

### Not top-level

The following must not become independent top-level tabs merely because they exist:

- Gear
- Mechanics
- Archetypes
- History
- Diagnostics
- Run Health
- Alerts
- Scenario Analysis

They belong contextually within the relevant object/workflow.

---

## 7. Global shell

The shell must provide:

- primary workspace navigation;
- current analysis/run context;
- compact Run Health state;
- stable sticky behavior;
- no floating overlay that allows unrelated content to visibly scroll behind controls.

Docked/sticky controls must be structurally anchored.

The shell must remain coherent at desktop, medium, and mobile widths.

---

## 8. Company

Company is the operational company workspace, not a dashboard.

### 8.1 Roster

Default people-oriented scan.

A roster row should preserve at minimum:

- Brother identity;
- Assigned Build;
- Best Fit;
- core operational context;
- relevant classification/state.

Assigned Build and Best Fit must remain visually distinct at all widths.

Opening a Brother after filtering/search must open the correct durable Brother.

Returning from Brother must preserve:

- Company subview;
- filter/search context;
- scroll position.

### 8.2 Planning / Coverage

Company-level planning view.

Supports:

- role coverage;
- assigned depth;
- alternative/intrinsic depth;
- gaps;
- replacement risk;
- planning questions.

Avoid recreating a generic dashboard.

### 8.3 Fit Matrix

Specialist comparison capability.

It remains useful for Brother × Archetype comparison but is not the default Company experience.

Responsive treatment may change format rather than forcing a desktop matrix into narrow widths.

---

## 9. Brother

Brother is a stable user-facing context.

Snapshot/observation is a data-layer concept, not a UI destination.

### 9.1 Header

Show:

- identity;
- background/level context;
- Assigned Build;
- Best Fit.

Assigned Build = intent.
Best Fit = intrinsic analysis.

### 9.2 Current State

Owns current Brother facts.

Includes:

- current stats;
- perks;
- traits/injuries;
- current Gear;
- current mechanical facts.

### 9.3 Gear

Gear belongs to Brother.

Target information includes:

- Head;
- Body;
- Main Hand;
- Off Hand;
- optional accessory/ammo/bag where reliably available;
- Gear FAT;
- usable FAT where reliable.

Gear does not modify intrinsic Fit.

### 9.4 Mechanics

Compact current-state mechanical facts.

Facts should be objective and deterministic where possible.

They must not be phrased as warnings by default.

### 9.5 Potential

Intrinsic archetype analysis.

Scan state must expose:

- archetype;
- Fit;
- meaningful likely range;
- probability/feasibility context where applicable.

Potential defaults collapsed rather than auto-opening Best Fit.

Deep analytical detail is Explain-level.

Do not duplicate a separate Alternatives card when ranked Potential already communicates alternatives.

### 9.6 Development

Historical/development context belongs here when reliable.

It must not turn the Brother surface into an endless report.

### 9.7 Navigation context

Brother switching must preserve the active Brother section.

Validated behavior includes preserving sections such as Potential even when switching among Brothers near the bottom of the document.

---

## 10. Level Up

Level Up is a compact decision workstation.

### 10.1 Decision queue

Desktop:

- pending Brothers remain visible in a compact queue.

Narrow widths:

- compact selector may replace the queue.

Switching must update all Brother-specific decision state without stale content.

### 10.2 Decision context

Always distinguish:

#### Player Intent
Assigned Build.

#### Intrinsic Analysis
Best Fit.

#### Immediate Recommendation
Primary / Runner-up / optional conditional branch.

Recommendation must not masquerade as either intent or intrinsic analysis.

### 10.3 Current rolls

All available current rolls remain visible.

Each roll may show:

- current value;
- offered roll;
- stars;
- roll quality;
- whether Primary uses it;
- whether Runner-up uses it.

A strong unselected roll may receive subtle explanatory treatment but must not dominate the decision.

### 10.4 Primary and Runner-up

Primary and Runner-up are visible side-by-side where width allows.

Each must expose compact consequences.

Consequences may include:

- Assigned Build Fit change;
- Best Fit trajectory change;
- P100/probability change;
- burden/feasibility change;
- explicit trade-off.

Evidence must be two-sided.

If Runner-up improves a different trajectory, that upside must be quantified rather than left qualitative.

### 10.5 Conditional branch / Gamble

A Gamble is only shown when it is genuinely distinct from Runner-up.

It requires:

- explicit alternative picks;
- explicit trigger/assumption;
- explicit scenario interpretation.

If no distinct conditional branch exists, no Gamble card is rendered.

### 10.6 Explain

Detailed reasoning is opt-in.

It may include:

- projection comparison;
- marginal pick value;
- skipped attractive rolls;
- model assumptions;
- recommendation basis.

Explain should deepen the decision rather than repeat visible cards.

### 10.7 Mobile

Mobile must preserve time-to-answer.

Priority:

1. Brother identity;
2. Assigned Build;
3. Best Fit;
4. compact Primary answer;
5. all current rolls;
6. detailed Primary/Runner-up consequences;
7. Explain.

All core rolls remain visible even on mobile.

---

## 11. Recruitment

Recruitment is a multi-candidate hiring decision surface.

### 11.1 Governing dimensions

Three dimensions remain independently inspectable:

1. **Candidate potential / quality**
2. **Relevant roster need**
3. **Hiring economics**

No opaque Recruit Score.

Composite prose judgments that silently combine these dimensions are also out of contract.

### 11.2 Settlement-first browsing

Default organization:

```text
Settlement
  └── Recruit candidates
```

Settlement context is meaningful game-world context and remains the strongest browser grouping.

### 11.3 Desktop / medium browser

At desktop and approximately 980 px:

- multiple candidates remain visible simultaneously;
- settlement grouping remains visible;
- candidate rows remain compact;
- active candidate is obvious.

Candidate scan row includes:

- identity/background;
- level;
- hire cost;
- wage;
- Top Potential;
- Relevant Need;
- known evidence / tryout state;
- shortlist affordance.

### 11.4 Current settlement context

The validated browser uses:

- one sticky `Settlements & candidates` browser header;
- one compact **Current settlement** band inside that header;
- normal in-flow settlement group headers.

The current settlement is the settlement whose recruit rows occupy the greatest visible area in the browser viewport.

This avoids independent sticky-group headers and artificial scroll-runway requirements.

The current-settlement band also carries the corresponding settlement observation summary.

### 11.5 Candidate detail

The selected candidate detail enriches the browser; it does not conceptually replace all other candidates.

Priority:

- identity/background;
- economics;
- Top Potential;
- Relevant Need;
- evidence/tryout;
- Potential detail;
- Roster Need detail;
- observation context;
- shortlist;
- model Explain.

### 11.6 Background prior vs candidate estimate

Two analytical states must be supported.

#### Prior only

Example:

```text
Candidate estimate: Not available
Background prior: 52%
Prior only
```

Use when no recruit-specific evidence justifies a separate estimate.

#### Known-evidence estimate

Example:

```text
Known-evidence estimate: 75%
Background prior: 65%
Basis: Fearless revealed
```

A known-evidence estimate must expose its basis.

### 11.7 Top Potential invariant

For each candidate:

```text
if candidate-specific estimates exist:
    Top Potential = highest candidate estimate
else:
    Top Potential = highest Background Prior
```

Roster Need and price must not alter this ordering.

### 11.8 Relevant roster need

Recruitment distinguishes:

- **Relevant Need** — company need for a trajectory the candidate can plausibly serve;
- **Other company gaps** — important needs this candidate does not meaningfully address.

An unrelated High company need must never be labeled as the candidate's best roster match.

### 11.9 Economics

Show factual economics:

- hire cost;
- daily wage;
- optional equipment value if reliably available;
- current company funds if product requirements later justify it.

Do not introduce opaque value labels such as:

- High-need bargain
- Premium but aligned
- Strong upside, moderate need

unless a future explicit interpretation model is separately approved.

### 11.10 Shortlist

Shortlist supports cross-settlement comparison.

Comparison preserves:

- cost;
- Top Potential;
- Relevant Need;
- evidence;
- tryout state.

No automatic winner.

The design is optimized for 2–3 candidates but remains usable with larger shortlists.

Persistence remains an implementation/product-state decision, not required by the validated interaction pattern.

### 11.11 Freshness / observation

Do not claim game-native recruit refresh age unless evidenced.

Possible player-facing states include:

- first observed;
- previously seen and unchanged;
- new since previous analysis;
- settlement summary such as `2 previously seen · 1 new`;
- game refresh age unknown.

Observation summary and candidate history must be mutually coherent.

### 11.12 Mobile

At narrow/mobile width:

- desktop candidate browser is replaced by a selector;
- identity/background and economics come first;
- Top Potential / Relevant Need / evidence follow;
- Potential remains readable;
- shortlist comparison stacks;
- no horizontal overflow.

---

## 12. Scan → Decision → Explain

This is the governing information-depth model.

### Scan

Answers:

> What deserves attention?

Expose enough information to decide what to inspect.

Do not hide decision-critical facts merely to reduce visual density.

### Decision

Answers:

> What should I choose or compare?

Expose the consequences and trade-offs required for an actual decision.

### Explain

Answers:

> Why does the toolkit believe this?

Expose:

- detailed math;
- projection components;
- assumptions;
- provenance;
- model basis;
- unknowns.

Explain is opt-in when the detail would otherwise overwhelm the task.

---

## 13. Responsive principles

Responsive design must preserve semantic minimums.

Do not solve narrow widths by deleting the distinction between:

- Assigned Build and Best Fit;
- candidate quality and roster need;
- Primary recommendation and current rolls;
- prior-only and candidate estimate.

Allowed adaptations include:

- queue → selector;
- matrix → stacked comparison;
- side-by-side cards → vertical stack;
- browser → selector on true mobile widths;
- compact labels / wrapping.

Avoid horizontal overflow as the default escape hatch.

---

## 14. Trust / Run Health

Run Health is global.

The shell may show compact status.

Detailed health may include:

- parsing fallback;
- unresolved references;
- cache fallback;
- projection validation;
- degraded inputs;
- stale/mixed-generation concerns.

Affected results may expose local validity/provenance.

Healthy local validity should remain quiet.

Do not create a Diagnostics top-level workspace unless a future product requirement genuinely warrants one.

---

## 15. Future-compatible capabilities

The validated architecture must accommodate these without changing the top-level navigation.

### 15.1 Alerts

Cross-domain attention layer.

Facts remain facts; alerts are interpretations.

### 15.2 History

Historical context may extend:

- Brother Development;
- recruit observation;
- analysis/run comparison.

Durable identity/provenance is prerequisite.

### 15.3 Scenario Analysis

Supports explicit assumption-bound models such as fatigue viability at turn X.

Scenario results must not contaminate current-state facts or intrinsic Fit.

### 15.4 In-game Level Advisor

Potential future integration is outside this target HTML/UI implementation contract.

---

## 16. Explicit non-goals

The target UI does not require:

- a new top-level tab for every capability;
- Gear-to-Fit coupling;
- alerts disguised as facts;
- a Recruit Score;
- current gear repeated inside every archetype card;
- a generic Company KPI dashboard;
- a giant always-expanded analytical report;
- implementation tickets inside this specification;
- repository modification.

---

## 17. Validated interaction contracts

The following are considered closed target-UI behaviors.

### Company / Brother

- Company/Brother navigation context is preserved.
- Search/filter drill-in opens the correct Brother.
- Returning preserves Company subview and scroll position.
- Brother switching preserves active section.
- Assigned Build and Best Fit remain distinct.
- Potential defaults collapsed.
- likely range is visible at Scan depth.
- Alternatives are represented by ranked Potential rather than duplicated.
- sticky shell/dock does not overlap content.
- mobile preserves semantic minimums.

### Level Up

- all current rolls visible;
- Primary and Runner-up comparable;
- two-sided consequence evidence;
- conditional Gamble only when genuinely distinct;
- deeper Explain opt-in;
- compact mobile Primary preview;
- queue/selector switching without stale data.

### Recruitment

- settlement-first browser;
- multiple candidates visible through medium width;
- clear settlement/recruit hierarchy;
- Current settlement context band;
- Potential / Relevant Need / Cost separate;
- prior-only and known-evidence analytical states;
- deterministic Top Potential rule;
- coherent freshness/observation scope;
- shortlist cross-settlement;
- no composite Value posture;
- mobile candidate-first selector;
- stable browser scroll through candidate switching/shortlist mutation.

---

## 18. Deliberately unresolved product decisions

These remain intentionally open until supporting backend/product evidence exists.

- exact significance rule for analytical near-ties;
- final alert severity/color model;
- exact recruit durable identity semantics;
- exact game-native recruit refresh semantics;
- final persistence semantics for shortlist;
- whether current company funds belong directly in Recruitment;
- exact probability labels/calibration from the future background/recruit model;
- full historical comparison UX;
- scenario-specific fatigue model and action assumptions;
- whether a second major decision workflow eventually warrants generalizing `Level Up` into a broader decisions workspace.

These unresolved points must not block implementation of the validated target surfaces where they are not required.
