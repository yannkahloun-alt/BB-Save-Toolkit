# Testing and Quality Gates

## Install development dependencies

    python -m pip install -r tests\requirements.txt

## Routine autonomous tickets: CI-owned quality validation

Implementation changes still require deterministic regression coverage where the
project contract calls for it. Push the coherent change to the named ticket's
single draft implementation pull request; GitHub Actions is the authoritative
executor of routine CI-equivalent automated quality validation. Do not normally
duplicate pytest, Pyflakes, Ruff, coverage, mutation testing, or other static
analysis locally during autonomous ticket work.

For every exact PR head targeting main, GitHub Actions owns these stable
merge-readiness checks:

- tests: python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -m "not coverage_slow" -q
- ruff: .\run_ruff.ps1 -Tests
- pyflakes: .\run_lint.ps1 -Tests

The stable CI identities are `tests`, `ruff`, and `pyflakes`.

These names are operationally required merge-gate identities, not currently
configured GitHub required-status-check contexts. GitHub's merge UI is therefore
not the trust boundary: the coordinator and independent reviewer must verify all
three checks against the exact current PR head before merge. The expected
GitHub-host enforcement state and its verification procedure are documented in
`docs/DEVELOPMENT_WORKFLOW.md`.

CI evidence must be green for the exact current head before independent review
and merge. A changed implementation head receives new evidence on the same PR;
it never creates another implementation PR for the named ticket.

## Explicit validation exclusions

Until an explicit later project decision changes this policy, **tests marked
`coverage_slow` and mutation testing are excluded from every required validation,
merge, pre-release, release, and publication gate**.

- Do not run `coverage_slow` as a required gate.
- Do not run mutation testing as a required gate.
- Their absence, failure, or stale historical result must not block a ticket,
  release candidate, tag, or publication.
- They may remain available only as optional diagnostic tools when explicitly
  requested for investigation; optional results do not become merge/release
  requirements unless project policy is explicitly changed again.

This exclusion does **not** remove ordinary branch-coverage validation where a
release workflow currently requires `run_coverage.ps1`; it applies specifically
to the `coverage_slow` pytest marker and mutation testing.

## Manual, reference, and local-only validation

These commands remain useful for explicit user-directed diagnosis, local
development, or validation CI cannot reasonably perform. They are not routine
autonomous-ticket gates:

    python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -m "not coverage_slow" -q
    .\run_lint.ps1 -Tests
    .\run_ruff.ps1 -Tests
    .\run_coverage.ps1

Private real-save smoke validation remains local-only when relevant save or game
data is unavailable to CI. Record its scope and result when it is used. Branch
coverage is intentionally excluded from normal PR CI; its 89.4% baseline applies
whenever explicit local or pre-release coverage validation is run.

The independent review required by the shared workflow verifies the stable
checks on the exact current PR head. It does not replace deterministic GitHub
checks. Generic review execution, exact-head invalidation, and fallback
isolation are defined only by the shared workflow. The reviewer also confirms
that normal PR CI excludes branch coverage, `coverage_slow`, mutation testing,
real-save smoke tests, and release ZIP generation.

## Pre-release / pre-production

Required pre-release validation must use the gates defined in `docs/RELEASE.md`
and must continue to exclude `coverage_slow` and mutation testing until an
explicit later project decision re-enables either one.

The tracked-file ZIP remains independently verifiable with:

    python tools\verify_release_zip.py <release.zip>

The manually dispatched Release validation workflow runs reproducible tests
excluding `coverage_slow`, branch coverage, Pyflakes, Ruff, and verified
release-ZIP packaging. Real-save smoke tests remain local because private game
data and game files are unavailable in CI.

## Incremental cache verification

When modifying cache fingerprints, dependencies, identity, engine versions,
projection semantics, classification, or advisor behavior, exercise:

    python .\bb_analyze.py <save.sav> --verify-cache --cache-debug

The invariant is incremental == independent full recomputation.

## Completion evidence for a normal ticket

A normal ticket is ready to merge when:

1. changed behavior has deterministic regression coverage where applicable;
2. the coherent implementation is on the named ticket's one implementation PR;
3. the CI-owned tests, ruff, and pyflakes checks are green on its exact current head;
4. the shared-workflow independent review approves that exact head under the project-specific review guard; and
5. docs/specs are updated if the contract changed.

`coverage_slow` and mutation testing are not completion requirements under the
current policy. Branch coverage and release ZIP validation remain governed by
the explicit release workflow when applicable.
