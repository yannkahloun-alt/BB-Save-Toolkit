# Mutation Testing

The mutation framework uses Cosmic Ray through `run_mutation.ps1`.

## Philosophy

Mutation testing is a correctness tool, not a vanity score. In this project, survivors often identify missing behavioral contracts that ordinary coverage cannot reveal.

Mutation testing belongs to pre-release/pre-production validation. It is not
started automatically for routine tasks or pull requests into `main`.

When a touched target has survivors, the default policy is:

> inspect and kill all valid survivors.

Do not select only convenient survivors to fix.

## Commands

```powershell
.\run_mutation.ps1 -ListTargets
.\run_mutation.ps1 -Target models
.\run_mutation.ps1 -Target projection/trajectory
.\run_mutation.ps1 -Target incremental/cache
```

`-ListTargets` reports test dependency count, potential mutant count, and a qualitative runtime scale. Historical run times improve those estimates.

## `all`

The old monolithic whole-package strategy was too expensive and produced poor test economics. `-Target all` now orchestrates module-by-module campaigns so each target resolves its own dependencies and produces separate results.

Even so, broad `all` runs are expensive. Use touched/high-risk module campaigns
for pre-release validation and run `all` only when explicitly requested.

## Survivors

For each survivor:

1. understand the semantic mutation;
2. determine the intended behavior;
3. add/strengthen a test that distinguishes the mutant from correct behavior;
4. rerun the target;
5. do not alter production semantics solely to manipulate the mutation score.

## High-priority mutation areas

- parser record selection and identity;
- trajectory/fit allocation;
- ceiling/scoring behavior;
- trait/permanent-injury transforms;
- incremental fingerprints and invalidation;
- ambiguous identity rejection;
- classification thresholds;
- Level-Up Advisor path comparison.
