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

## Validation levels

### Routine development / task iteration

- targeted tests for changed behavior and affected modules;
- lint and Ruff;
- no `coverage_slow`;
- no mutation testing.

### Pre-merge to main

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -m "not coverage_slow" -q
.\run_coverage.ps1
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
```

### Pre-release / pre-production

```powershell
.\run_tests.ps1
.\run_mutation.ps1 -Target <changed-or-high-risk-module>
```

`run_tests.ps1` includes `coverage_slow`. Targeted mutation testing is a
pre-release/pre-production gate only. Broader mutation campaigns, including
`-Target all`, run only when explicitly requested.

## Release policy

Do not bump a version for every small commit. Git history is the development history.

A release is created only when an explicit release decision is made. Follow `docs/RELEASE.md`. Release ZIPs must pass `tools/verify_release_zip.py`.

## Specs

- Active/open spec: `docs/specs/REMAINING_WORK_v3.84.md`
- Completed incremental design: `docs/specs/INCREMENTAL_PROJECTION_REUSE_DONE.md`
- Completed stat-ceiling design: `docs/specs/ARCHETYPE_STAT_CEILING_DONE.md`

Completed specs remain in the repository as architectural history; do not reopen them silently. New behavior that changes their contract requires a new spec or explicit amendment.
