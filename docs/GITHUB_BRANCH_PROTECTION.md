# GitHub merge-safety enforcement

GitHub Actions provides deterministic validation for pull requests into `main`,
and the pinned shared workflow provides an independent read-only review gate.
Under the current repository policy, those merge guards are operationally
mandatory but are **not** configured as GitHub-hosted branch-protection or
ruleset requirements.

## Operational merge guards

Before the coordinator may merge a normal ticket pull request, all of the
following must hold for the exact current 40-character head SHA:

- the stable GitHub Actions checks `tests`, `ruff`, and `pyflakes` are green;
- a fresh independent read-only reviewer has returned an explicit exact-head
  `APPROVE` verdict;
- the pull request is re-fetched after approval and the head SHA plus all three
  checks are confirmed unchanged and green; and
- the coordinator follows the repository's normal squash-merge procedure.

Any new implementation commit invalidates the prior CI/review generation and
requires fresh exact-head evidence on the same implementation pull request.
These requirements are enforced by the coordinator/reviewer procedure described
in `docs/DEVELOPMENT_WORKFLOW.md` and `docs/TESTING.md`; GitHub's merge UI is not
the trust boundary for this repository.

## Expected GitHub-hosted enforcement baseline

The intentional current baseline is no GitHub-hosted required-check enforcement
for `main` and no repository rulesets. Verify that boundary with the supported
GitHub reads before relying on it:

- `GET /repos/yannkahloun-alt/BB-Save-Toolkit/branches/main` is expected to
  report `protected: false`, `protection.enabled: false`, and
  `required_status_checks.enforcement_level: off`, with no required
  contexts/checks.
- `GET /repos/yannkahloun-alt/BB-Save-Toolkit/rulesets` is expected to return an
  empty list.

The detailed classic branch-protection endpoint
`GET /repos/yannkahloun-alt/BB-Save-Toolkit/branches/main/protection` may return
`403 Resource not accessible by integration` for the managed GitHub connection.
That response is inconclusive and must not be treated as evidence that branch
protection is either enabled or disabled. The supported branch summary and
ruleset reads above define the observable policy/configuration baseline.

If either supported read stops matching this baseline, treat the difference as
policy/configuration drift. Reconcile the documentation and GitHub settings
explicitly before claiming that the merge-safety boundary is unchanged.

Normal ticket work must not create, remove, weaken, bypass, or otherwise change
branch protection or repository rulesets. That prohibition is a safety rule; it
does not imply that protection is currently enabled.

## Release-only checks

The manually dispatched release workflow's stable `release-tests`,
`release-quality`, `release-package`, and `release-summary` jobs are deliberately
not routine PR merge guards. They contain release-only work and remain governed
by `docs/TESTING.md` and `docs/RELEASE.md`.
