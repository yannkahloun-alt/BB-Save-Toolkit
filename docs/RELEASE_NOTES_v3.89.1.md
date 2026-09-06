# Battle Brothers Save Toolkit v3.89.1

v3.89.1 is a focused hotfix for the v3.89 Windows/local application release.

## Fixes

- Disables the unvalidated Recruitment Background × Archetype prior and recruit candidate-estimate models from normal application and CLI analysis.
- Prevents large recruit pools from entering the expensive combinatorial recruitment-potential path after core Brother × Archetype analysis has already completed.
- Keeps recruit parsing, settlement/economics display, core Brother Fit, classification, Level-Up Advisor, AssignedBuild, Company planning, save watching, and identity semantics unchanged.
- Recruitment potential now reports an explicit unavailable state while the retained model awaits a separate validation/product decision.
- Relevant Roster Need remains unavailable whenever candidate-potential evidence is unavailable, avoiding false negative recruiting conclusions.

## Why this hotfix exists

The first real v3.89 installed-app analysis of a roughly day-60 campaign exposed the issue clearly: 13 brothers × 11 archetypes completed in about 5.34 seconds and projection validation in about 0.13 seconds, while the job then remained running in recruitment analysis over 86 parsed recruit records. The old path could enter 86 × 11 recruit/build potential evaluations after the core analysis was already complete.

The regression suite now includes an 86-recruit × 11-build workload that fails if normal production analysis re-enters the disabled estimator.

## Compatibility

This hotfix does not change the core natural-stat level-11 Fit model, projection semantics, identity, persistence, or save parsing contracts. The Background × Archetype and candidate-estimate model code remains in the repository for explicit future research/validation; v3.89.1 removes it from normal production execution only.

## Windows application

The recommended player download is:

```text
BB-Save-Toolkit-3.89.1-setup.exe
```

Normal repair/update preserves durable application state under `%LOCALAPPDATA%\BB-Save-Toolkit\`.
