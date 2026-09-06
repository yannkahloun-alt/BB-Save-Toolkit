# Mutation Testing

The mutation framework uses Cosmic Ray through `run_mutation.ps1`.

## Current policy

Until an explicit later project decision changes this policy, **mutation testing is excluded from every required validation, merge, pre-release, release, and publication gate**.

The tooling remains available as an optional diagnostic aid when explicitly requested, but a mutation run is not required for ticket completion or release publication, and its absence, failure, or stale historical result must not block work.

## Philosophy

Mutation testing is a correctness tool, not a vanity score. In this project, survivors can identify missing behavioral contracts that ordinary coverage may not reveal.

When mutation testing is explicitly requested as an investigation and a touched target has survivors, the diagnostic default is:

> inspect and kill all valid survivors.

Do not select only convenient survivors to fix. This diagnostic guidance does not make mutation testing a validation gate under the current exclusion policy.

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

Broad `all` runs are expensive and should only be run when explicitly requested for investigation. They are not a release requirement under the current policy.

## Survivors

For an explicitly requested mutation investigation, handle each survivor by:

1. understanding the semantic mutation;
2. determining the intended behavior;
3. adding/strengthening a test that distinguishes the mutant from correct behavior;
4. rerunning the target when useful to the investigation;
5. not altering production semantics solely to manipulate the mutation score.

## High-priority diagnostic areas

- parser record selection and identity;
- trajectory/fit allocation;
- ceiling/scoring behavior;
- trait/permanent-injury transforms;
- incremental fingerprints and invalidation;
- ambiguous identity rejection;
- classification thresholds;
- Level-Up Advisor path comparison.
