# Development Workflow

## Source of truth

Git is the only development source of truth. Do not exchange modified source trees as numbered ZIPs during development.

Recommended local layout:

```text
BattleBrothers/
  BB_Save_Toolkit/          # main checkout
  worktrees/
    task-identity/
    task-parser-fix/
```

Codex may work in a task branch/worktree while the main checkout remains stable.

## Task lifecycle

### 1. Start from a clean main branch

```powershell
git status
git switch main
git pull --ff-only
```

For a new task:

```powershell
git switch -c task/<short-name>
```

or create a worktree if parallel work is useful.

### 2. Read the contract

Before code changes, inspect:

```text
AGENTS.md
docs/INVARIANTS.md
docs/ARCHITECTURE.md
relevant spec in docs/specs/
existing tests around the target module
```

### 3. Reproduce first

For bugs, create or identify a failing test/fixture before changing implementation whenever possible.

### 4. Implement minimally

Prefer changes that preserve module boundaries:

```text
parser                 -> current save facts
references             -> source-derived metadata/effects
projection/*            -> calculation
incremental/*           -> reuse/invalidation/persistence
app/*                   -> orchestration / I/O
html_report             -> presentation
```

Do not put cache persistence into projection algorithms.

### 5. Validate incrementally

Run focused tests during iteration, then the applicable pre-merge gate in
`docs/TESTING.md`. Do not start `coverage_slow` or mutation testing during
routine development or normal pre-merge validation.

### 6. Review the diff

```powershell
git diff --check
git diff --stat
git diff
```

Look specifically for:

- accidental generated reference/cache files;
- version bumps that are not releases;
- stale docs/contracts;
- missing cache engine-version bump after semantic changes;
- broad invalidation where a narrower dependency is possible;
- display names used as technical identity.

### 7. Commit

Use task-oriented messages, for example:

```text
Fix trait save-hash effect lookup
Add campaign-safe manifest identity
Harden advisor cache invalidation
```

Avoid meaningless release-style commit names such as `v3.85` during normal development.

### 8. Independent pull-request review

After Agent A's adversarial self-review, fixes, and required green CI, Agent A
marks the PR **Ready for review**. Only then does Agent A automatically create a
fresh Codex task in an isolated worktree and wait for Agent B to review the
complete GitHub PR diff at the exact current head SHA. Agent B is strictly
read-only and returns `DO NOT APPROVE` without a full review if the PR is still
draft. Every new commit invalidates the old verdict and requires Agent A to
complete its gates before launching a new Agent B task. The verdict is an
operational Codex gate rather than a GitHub status check because both agents use
one human GitHub account and no paid external integration is configured. See
`docs/AGENT_B_REVIEW.md`. Passing review never authorizes a merge without
explicit owner confirmation.

## Branch discipline

- `main` should remain releasable or close to releasable.
- One coherent feature/fix per branch.
- Avoid mixing formatting churn with logic changes.
- Rebase/merge only after tests pass.

## Real save fixtures

Real `.sav` files may contain useful validation data but should not be committed casually.

For durable parser/identity tests, prefer:

1. minimal synthetic byte fixtures;
2. sanitized extracted structures;
3. explicitly approved real-save fixtures if required.

Document provenance and purpose for any committed binary fixture.
