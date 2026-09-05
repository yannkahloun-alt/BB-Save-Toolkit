# Development Workflow

Generic coordinator, implementation, review, worktree, handoff, freshness, and
cleanup mechanics come from the pinned shared workflow described in
`docs/AGENT_WORKFLOW_DEPENDENCY.md`. This document contains only Battle Brothers
Save Toolkit-specific development policy.

## Source of truth

Git is the only development source of truth. Do not exchange modified source trees as numbered ZIPs during development.

The shared-workflow coordinator owns Git and workspace boundaries. Delegated
implementation and review agents must use the checkout they are assigned and
must not choose, create, move, or clean up branches or worktrees themselves.

## Ticket selection and deferral

Briefly considering a ticket does not claim it. Once an agent selects, claims,
or meaningfully investigates a GitHub ticket with the intent to implement it,
the ticket becomes part of that agent's visible work history.

If the agent later decides not to proceed, it must leave a concise GitHub
comment before switching to another ticket or ending the task. The comment
must record:

- why work is being deferred or forgone;
- the concrete blocker, uncertainty, or missing evidence;
- any useful investigation result that avoids duplicated work; and
- the evidence, decision, or action needed to resume safely.

Deferral does not mean the request is complete, so the ticket remains open
unless it independently meets the repository's closure rules. Do not post a
duplicate deferral comment when equivalent current context is already present.
Do not imply that implementation or validation was completed when it was not.

## Project implementation rules

### Read the contract

Before code changes, inspect:

```text
AGENTS.md
docs/INVARIANTS.md
docs/ARCHITECTURE.md
relevant spec in docs/specs/
existing tests around the target module
```

### Reproduce first

For bugs, create or identify a failing test/fixture before changing implementation whenever possible.

### Implement minimally

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

New transports (for example a local HTTP API or hosted worker) must call the
typed application service in `bbtool/app/analysis_service.py`. They must not
recreate parser/projection orchestration or infer failures from CLI output.

### Validate incrementally

Add or update deterministic regression coverage when the change requires it,
then push the coherent implementation to the ticket's one draft implementation
pull request. GitHub PR CI owns routine execution of the normal suite, Ruff,
and Pyflakes on that exact head; do not require equivalent local gates during a
normal autonomous ticket. The project-specific CI contract and genuine
local-only exceptions are in `docs/TESTING.md`. Do not start `coverage_slow`
or mutation testing during routine development or normal pre-merge validation.

### Review the diff

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

### Commit

Use task-oriented messages, for example:

```text
Fix trait save-hash effect lookup
Add campaign-safe manifest identity
Harden advisor cache invalidation
```

Avoid meaningless release-style commit names such as `v3.85` during normal development.

### Project-specific review and merge guards

The shared workflow owns independent-review dispatch, freshness, exact-head
invalidation, follow-up review, and fallback isolation. BB-Save requires the
reviewer to remain read-only and inspect the complete GitHub pull-request diff,
all commits, and the stable `tests`, `ruff`, and `pyflakes` checks. A draft pull
request, incomplete evidence, or any verdict other than explicit `APPROVE` for
the exact current 40-character head SHA fails the operational review gate.

This gate is operational rather than a GitHub status check because the agents
use one human GitHub account and no paid external review integration is
configured. After approval, the coordinator must re-fetch the pull request and
require the head SHA and all required checks to remain unchanged and green,
then automatically squash-merge. Branch protection must never be changed or
bypassed as part of this flow. An ordinary issue handoff does not authorize a
release, deployment, tag, or publication; those remain governed by
`docs/RELEASE.md`.

### GitHub-host enforcement boundary

The stable `tests`, `ruff`, and `pyflakes` checks and the independent exact-head
approval are mandatory merge guards, but they are enforced by the
coordinator/reviewer procedure rather than by GitHub branch protection or a
repository ruleset. Under the current policy baseline, `main` is intentionally
expected to report no GitHub-hosted required-check enforcement.

Verify that boundary directly from GitHub before relying on it:

- `GET /repos/yannkahloun-alt/BB-Save-Toolkit/branches/main` is expected to
  report `protected: false`, `protection.enabled: false`, and
  `required_status_checks.enforcement_level: off` with no contexts/checks.
- `GET /repos/yannkahloun-alt/BB-Save-Toolkit/rulesets` is expected to return an
  empty list.

The detailed classic branch-protection endpoint may return `403 Resource not
accessible by integration` for the managed GitHub connection. That response is
inconclusive and must not be represented as evidence that protection is either
enabled or disabled. If either supported read above stops matching this
baseline, treat it as policy/configuration drift and reconcile the documentation
and GitHub settings explicitly before claiming the merge-safety boundary is
unchanged.

Normal ticket work must not create, remove, weaken, bypass, or otherwise change
branch protection or rulesets. The prohibition on changing or bypassing branch
protection does not imply that protection is currently enabled.

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
