# AGENTS.md — Battle Brothers Save Toolkit

This repository is the source of truth. Do not use ZIP handoffs as a development workflow. ZIPs are release artifacts only.

## Mission

Maintain a read-only Battle Brothers save-analysis toolkit whose central model is level-11 Fit to configured archetypes. Preserve correctness, explainability, deterministic outputs, and conservative incremental reuse.

## Non-negotiable rules

1. **Fix all regressions introduced or exposed by a task.** Do not knowingly leave a failing test, a valid mutation survivor found during an explicitly requested pre-release campaign, a stale contract, or a broken integration behind because it looks unrelated.
2. **Never change projection semantics merely to make a test pass.** Establish the intended contract first.
3. **Incremental reuse is an optimization only.** `incremental == full recomputation` is an invariant. When uncertain, recompute.
4. **Names are display data, not identity.** `HumanOffset` is save-local. Ambiguous cross-save identity never permits reuse.
5. **Temporary injuries do not affect long-term build projections or their cache fingerprints.** Exact permanent trait and permanent-injury effects do.
6. **Archetype `ceiling` affects Fit valuation only.** It must never cap the projected/displayed stat or alter Battle Brothers mechanics.
7. **FutureRolls are quarantined from normal projection decisions.** They may be used for validation/identity research only where explicitly specified.
8. **Do not hard-code vanilla trait/permanent-injury modifiers by display name.** Reference extraction is keyed by serialized save hashes and source scripts.
9. **Generated runtime references are caches, not source files.** Do not commit generated `dictionary.json`, `backgrounds.json`, `trait_effects.json`, `permanent_injury_effects.json`, or `perk_audit.json`.
10. **No network dependency in tests.** Tests and fixtures must be deterministic and machine-independent.

## Before editing

Read, in order:

1. `docs/INVARIANTS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DEVELOPMENT_WORKFLOW.md`
4. `docs/TESTING.md`
5. `docs/specs/REMAINING_WORK_v3.84.md` for open roadmap work

If the task changes a documented contract, update the relevant doc/spec in the same commit.

## Development workflow

- Work on one coherent task per branch/worktree.
- Inspect existing tests before changing implementation.
- Add regression tests for every bug fix.
- Run the smallest relevant tests during iteration.
- Before merging to `main`, run the pre-merge validation gate from `docs/TESTING.md`.
- Do not start mutation testing or `coverage_slow` automatically during routine
  development or normal pre-merge validation.
- Review `git diff --check` and `git diff` before committing.
- Keep commits task-focused and descriptive.

### Pull-request publishing handoff

After Agent A creates or materially updates a pull request:

1. Keep the pull request draft while implementation, self-review, fixes, and
   required CI are incomplete.
2. When the exact current head has all required checks green, Agent A marks the
   pull request **Ready for review** and verifies that it is no longer a draft.
3. Resolve the pull request's exact current 40-character head SHA.
4. Automatically create a fresh Codex task in an isolated worktree titled
   `Independent review — PR #<number>`.
5. Give that task only the repository, pull-request URL/number, and instruction
   to use `$review-bb-pr` to review the complete diff at the exact current head.
6. Wait for Agent B to return `APPROVE` or `DO NOT APPROVE`.
7. Treat a draft PR, missing, incomplete, malformed, stale-SHA, or
   `DO NOT APPROVE`
   verdict as a failed review.
8. If Agent A pushes another commit, invalidate the previous verdict, complete
   the Agent A gates again, and launch a new Agent B task for the new head SHA.
9. After Agent B returns `APPROVE`, fetch the PR again and verify that its full
   head SHA is unchanged and every required check is still green.
10. If that final verification passes, Agent A automatically squash-merges the
    PR. A separate owner confirmation is not required.

Agent B is strictly read-only. It must refuse to review a draft PR.
It must not mark a PR ready, modify the branch, submit GitHub reviews or
comments, merge, or change any GitHub or repository setting.
See `docs/AGENT_B_REVIEW.md` for the complete protocol and trust boundary.

## Validation levels

### Routine development / task iteration

- targeted tests for changed behavior and affected modules;
- lint and Ruff;
- no `coverage_slow`;
- no mutation testing.

### Pre-merge to main

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -m "not coverage_slow" -q
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
```

Branch coverage is temporarily excluded from the normal PR and pre-merge gate
until its runtime is optimized. `run_coverage.ps1` remains available for
explicit local validation and pre-release work.

### Pre-release / pre-production

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -m "not coverage_slow" -q
.\run_coverage.ps1
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
```

The default GitHub release workflow excludes `coverage_slow` and mutation
testing. Run either gate only when explicitly requested for a particular
release. Mutation campaigns must be targeted to changed or high-risk modules;
broader campaigns, including `-Target all`, require an explicit request.

## Release policy

Do not bump a version for every small commit. Git history is the development history.

A release is created only when an explicit release decision is made. Follow `docs/RELEASE.md`. Release ZIPs must pass `tools/verify_release_zip.py`.

## Specs

- Active/open spec: `docs/specs/REMAINING_WORK_v3.84.md`
- Completed incremental design: `docs/specs/INCREMENTAL_PROJECTION_REUSE_DONE.md`
- Completed stat-ceiling design: `docs/specs/ARCHETYPE_STAT_CEILING_DONE.md`

Completed specs remain in the repository as architectural history; do not reopen them silently. New behavior that changes their contract requires a new spec or explicit amendment.
