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
that normal PR CI excludes branch coverage, coverage_slow, mutation testing,
real-save smoke tests, and release ZIP generation.

## Pre-release / pre-production

Before a release or production handoff, additionally run:

    .\run_tests.ps1
    .\run_mutation.ps1 -Target <changed-or-high-risk-module>
    python tools\verify_release_zip.py <release.zip>

run_tests.ps1 includes coverage_slow. The manually dispatched Release validation
workflow runs reproducible tests excluding that marker, coverage, lint, Ruff,
and verified release-ZIP packaging. Neither coverage_slow nor mutation testing
is invoked automatically by that workflow; both remain separate, explicitly
requested pre-release work. Real-save smoke tests remain local because private
game data and game files are unavailable in CI.

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

coverage_slow, branch coverage, targeted mutation testing, and release ZIP
validation are explicit local or pre-release/pre-production work, not routine
ticket CI or local completion requirements.
