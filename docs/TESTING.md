# Testing and Quality Gates

## Install development dependencies

```powershell
python -m pip install -r tests\requirements.txt
```

## Fast focused iteration

Examples:

```powershell
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest tests/unit/test_incremental_core.py -q
python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest -k advisor -q
.\run_tests.ps1 parser
```

## Mandatory correctness gate

Before finishing a normal code task:

```powershell
.\run_tests.ps1
```

This runs the complete correctness suite, including `coverage_slow` tests.

## Static analysis

```powershell
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
```

Both must pass for changed Python code unless a documented repository-wide pre-existing failure exists. Do not introduce new warnings.

## Branch coverage

For parser, projection, scoring, classification, advisor, incremental, trait/permanent-injury, and other correctness-critical changes:

```powershell
.\run_coverage.ps1
```

Coverage excludes `coverage_slow` under instrumentation only because tracing makes those combinatorial tests too expensive. They remain part of the non-instrumented correctness suite.

Coverage percentage alone is not the goal. New branches affecting correctness need explicit assertions.

## Incremental cache verification

When modifying cache fingerprints, dependencies, identity, engine versions, projection semantics, classification, or advisor behavior, exercise:

```powershell
python .\bb_analyze.py <save.sav> --verify-cache --cache-debug
```

The invariant is:

```text
incremental == independent full recomputation
```

## Mutation testing

List available targets, dependency counts, mutant counts, and qualitative cost:

```powershell
.\run_mutation.ps1 -ListTargets
```

Run the touched module:

```powershell
.\run_mutation.ps1 -Target projection/scoring
.\run_mutation.ps1 -Target incremental/cache
```

Mutation policy:

- fix every survivor in touched correctness logic or add the missing test that kills it;
- do not cherry-pick only "interesting" survivors;
- module/file-oriented campaigns are preferred for development;
- `-Target all` is an orchestrator for intentionally broad campaigns, not a routine per-task command.

## Release archive test

A release ZIP must pass:

```powershell
python tools\verify_release_zip.py <release.zip>
```

## Definition of done for a bug fix

A bug fix is done when:

1. the bug is reproduced by a test/fixture;
2. the implementation is corrected;
3. focused tests pass;
4. full correctness tests pass;
5. static analysis passes;
6. relevant coverage is exercised;
7. relevant mutation survivors are addressed where practical;
8. docs/specs are updated if the contract changed.
