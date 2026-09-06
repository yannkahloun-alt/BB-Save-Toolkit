# Current Work

> **Session-continuity snapshot only. GitHub issues, pull requests, and Git are authoritative. Verify live state before acting on anything below.**

Last updated: 2026-09-05

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
- the backend Target presentation contract carries resolved AssignedBuild state, intrinsic and intent-aware Company planning, the evolved Level-Up Advisor payload, Relevant Roster Need, and result-local validity/provenance needed by the Target UI.

Workflow adoption #178 is also complete through PR #179, squash-merged as `f9bb99df33a1dae2e4810595e08bca9577f10567`. `main` pins shared workflow v1.1.3.

The local-first Target UI and delivery critical path is now complete:

- #114, #115, #116, and #117 completed the shared shell plus Company/Brother, Level Up, and Recruitment workspaces;
- UI umbrella #100 is closed;
- Windows delivery #101 is closed;
- integrated correctness, freshness, recovery, and privacy gates #102 are closed through PR #191, whose squash merge is `06d21641335af4bd8639581c215db34d982bf2b6`;
- umbrella #93 is the completed local-first web-application milestone and closes with this transition.

## Current product critical path

There is no remaining implementation sequence under #93. The local-first web application, validated Target UI, Windows delivery, and integrated quality gate have reached their planned milestone boundary.

Open research or future-capability issues must be selected from live GitHub state only after checking their prerequisites and required evidence. In particular, recruit/history work (#71, #80, #84, #78, #113), the in-game Advisor track (#69, #124), and usable-fatigue follow-up #90 are not a continuation of the completed Target UI critical path merely because they remain open.

This file does not claim or reserve the next ticket.

## Release direction

The next meaningful release direction remains v3.89 with the actual local Target UI rather than an infrastructure-only release. The implementation baseline for that direction now exists, but release preparation, validation, tagging, and publication remain a separately authorized release lifecycle.

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
6. Select new work from the live backlog rather than assuming the completed #93 sequence still defines the next ticket.
7. When preparing an autonomous-agent prompt, recommend an appropriate model for the task.

## Maintenance

Keep this file compact. It is a living handoff, not a changelog or duplicate backlog.

When a major critical-path transition naturally touches this context, update the snapshot in that ticket/PR. Otherwise use a small dedicated documentation ticket. A slightly stale snapshot must never block product work; live GitHub and Git state remain authoritative.
