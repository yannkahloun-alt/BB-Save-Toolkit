# AGENTS.md — Battle Brothers Save Toolkit

First apply the shared workflow pinned at `.agent-workflow/AGENTS.md`. If the
directory is absent in a fresh clone or worktree, initialize it with:

```powershell
git submodule update --init --recursive
```

This file specializes that workflow for Battle Brothers Save Toolkit. Explicit
user instructions still take precedence. The repository is the development
source of truth; ZIP files are release artifacts only.

## Shared workflow dependency

- Workflow submodule path: `.agent-workflow`
- Workflow upstream: `yannkahloun-alt/codex-agent-workflow`
- Approved stable selector: greatest non-prerelease SemVer tag in the `v1.x`
  series

The selector permits dedicated workflow-bump lifecycle updates within `v1.x`.
A new major series requires an explicit project-policy change and review.

## Mission and non-negotiable rules

Maintain a read-only save-analysis toolkit centered on level-11 Fit to configured
archetypes. Preserve correctness, explainability, deterministic output, and
conservative incremental reuse.

1. Fix regressions introduced or exposed by the task.
2. Establish projection semantics before changing them; never change them only
   to satisfy a test.
3. Preserve `incremental == full recomputation`; recompute when uncertain.
4. Names are display data. `HumanOffset` is save-local, and ambiguity forbids
   cross-save reuse.
5. Temporary injuries affect neither long-term projections nor their cache
   fingerprints. Exact permanent trait and injury effects do.
6. Archetype `ceiling` affects Fit valuation only, never projected stats.
7. Keep `FutureRolls` out of normal projections; use them only for explicitly
   scoped validation or identity research.
8. Resolve vanilla effects from serialized save hashes and source scripts, not
   display-name tables.
9. Do not commit generated runtime reference caches.
10. Tests must be deterministic, machine-independent, and network-free.

## Required project context

Before editing, read in order:

1. `docs/INVARIANTS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DEVELOPMENT_WORKFLOW.md`
4. `docs/TESTING.md`
5. `docs/specs/REMAINING_WORK_v3.84.md` for roadmap work

Update relevant documentation when a contract changes. Keep one coherent task
per branch/worktree, inspect existing tests first, add regression tests for bug
fixes, run the documented gates, review the complete diff, and keep commits
task-focused.

The exact project-specific pull-request and independent-review protocol is in
`docs/AGENT_B_REVIEW.md`; release policy is in `docs/RELEASE.md`.
