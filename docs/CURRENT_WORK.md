# Current Work

> **Session-continuity snapshot only. GitHub issues, pull requests, and Git are authoritative. Verify live state before acting on anything below.**

Last updated: 2026-09-04

## Workflow state

BB-Save-Toolkit currently pins the shared `codex-agent-workflow` release:

- tag: `v1.1.3`
- commit: `ff0647d3dc205a47734d569ae5247ee4ba9109e9`

For orientation only, the current shared lifecycle means routine CI-equivalent automated validation is CI-owned, one named ticket owns one implementation PR, fixes and review generations reuse that PR, fresh read-only subagent review is required when available, and a changed implementation head requires fresh exact-head CI and review evidence.

The pinned `.agent-workflow` plus repository policy remain authoritative for the full workflow contract.

## Recently completed critical-path work

The Target presentation-data foundation is complete:

- #174 completed through PR #177, squash-merged as `4942715c3d9601af283d6d95701be3224b5431ff`;
- umbrella #106 is closed;
- the backend Target presentation contract now carries resolved AssignedBuild state, intrinsic and intent-aware Company planning, the evolved Level-Up Advisor payload, Relevant Roster Need, and result-local validity/provenance needed by the Target UI.

Workflow adoption #178 is also complete through PR #179, squash-merged as `f9bb99df33a1dae2e4810595e08bca9577f10567`. `main` now pins shared workflow v1.1.3.

## Current product critical path

The active product phase is Target UI implementation under umbrella #100.

Current expected implementation order:

1. #114 — shared application shell;
2. #115 — Company + Brother;
3. #116 — Level Up;
4. #117 — Recruitment.

Verify the live issue/PR state before starting any item in this sequence. This file does not claim or reserve work.

## Release direction

The next meaningful release direction is v3.89 with the actual local Target UI, not an infrastructure-only release.

The validated analytical navigation is:

```text
Company | Level Up | Recruitment
```

Brother remains a drill-down context rather than a fourth top-level workspace.

#113 recruit observation/freshness history and #80 save lineage are not currently treated as v3.89 blockers unless live issue state or an explicit product decision changes that.

## Starting a new session

1. Read this file for orientation only.
2. Verify every active issue/PR referenced here against live GitHub state before acting.
3. Apply the currently pinned `.agent-workflow` and BB-Save repository policy.
4. Preserve one named ticket / one implementation PR.
5. Never infer completion or current ownership from this snapshot.
6. When preparing an autonomous-agent prompt, recommend an appropriate model for the task.

## Maintenance

Keep this file compact. It is a living handoff, not a changelog or duplicate backlog.

When a major critical-path transition naturally touches this context, update the snapshot in that ticket/PR. Otherwise use a small dedicated documentation ticket. A slightly stale snapshot must never block product work; live GitHub and Git state remain authoritative.
