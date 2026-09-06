# Current Work

> **Session-continuity snapshot only. GitHub issues, pull requests, and Git are authoritative. Verify live state before acting on anything below.**

Last updated: 2026-09-05

## Workflow state

BB-Save-Toolkit currently pins the shared `codex-agent-workflow` release:

- tag: `v1.1.3`
- commit: `ff0647d3dc205a47734d569ae5247ee4ba9109e9`

For orientation only, the pinned shared lifecycle means routine CI-equivalent automated validation is CI-owned, one named ticket owns one implementation PR, fixes and review generations reuse that PR, and a changed implementation head requires fresh exact-head CI and review evidence.

The pinned `.agent-workflow` plus repository policy remain authoritative for the full workflow contract.

## Completed product milestone

The local-first Target UI and delivery critical path is complete:

- #114, #115, #116, and #117 completed the shared shell plus Company/Brother, Level Up, and Recruitment workspaces;
- UI umbrella #100 is closed;
- Windows delivery #101 is closed;
- integrated correctness, freshness, recovery, and privacy gates #102 are closed through PR #191, squash-merged as `06d21641335af4bd8639581c215db34d982bf2b6`;
- umbrella #93 is closed through PR #193, squash-merged as `cb94fdaafded4f743f9aa6856d9bc8dd54077473`.

There is no remaining implementation sequence under #93 and this file does not claim or reserve a next implementation ticket.

## Intentionally remaining backlog

The open backlog after the milestone is intentionally not empty. These items are studies, conditional work, or future capability tracks and must be selected only after live prerequisite/evidence reconciliation:

- #69 — future in-game Level Advisor feasibility/integration track. Source/UI hook feasibility is established, while the production transport choice still depends on the actual in-game loopback evidence in #124.
- #124 — technical spike requiring the real Battle Brothers embedded browser plus Modern Hooks; repository-only work cannot substitute for the required runtime/CORS evidence.
- #71 — recruit freshness feasibility study. Source evidence identifies exact settlement-pool `LastRosterUpdate` semantics, but parser/offset and controlled real-save validation remain study evidence before shipping behavior.
- #84 — conditional recruit/recruit-pool cross-save identity study; needed only if #71 ultimately requires historical identity stronger than the exact single-save pool freshness signal.
- #80 — save lineage study. Campaign identity (#79) is resolved, but controlled linear and rollback/fork real-save evidence is still required; ancestry must remain unknown when not proven.
- #78 — historical change-summary study. Campaign/brother identity prerequisites are resolved, but safe `previous` semantics still depend on #80 lineage evidence.
- #113 — conditional recruitment observation/freshness implementation; do not start until #71/#84 establish the supported semantics and prerequisites.
- #90 — intentionally future, non-blocking fatigue-viability investigation only.

These open issues are not unfinished work in the completed #93 Target UI milestone merely because they remain open.

## Release direction

The next meaningful release direction remains v3.89 with the actual local Target UI rather than an infrastructure-only release. The implementation baseline for that direction exists, but release preparation, validation, tagging, and publication remain a separately authorized release lifecycle.

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
