# Battle Brothers Save Toolkit

Read-only Battle Brothers save analyzer focused on level-11 archetype Fit, probabilistic development trajectories, strategic classification, Level-Up Advisor recommendations, and incremental reuse of unchanged analysis artifacts.

## Development model

**Git is the source of truth.** Numbered ZIP handoffs are no longer the development workflow; ZIPs are produced only for explicit releases.

Start with:

- `AGENTS.md` — instructions for Codex/other coding agents;
- `docs/INVARIANTS.md` — contracts that must not regress;
- `docs/ARCHITECTURE.md` — current architecture;
- `docs/DEVELOPMENT_WORKFLOW.md` — branch/worktree workflow;
- `docs/TESTING.md` — required quality gates;
- `docs/specs/REMAINING_WORK_v3.84.md` — current open roadmap.

## Run the analyzer

```powershell
python .\bb_analyze.py "C:\path\to\quicksave.sav"
```

Open the generated report automatically:

```powershell
python .\bb_analyze.py "C:\path\to\quicksave.sav" --open-report
```

Incremental diagnostics / safety controls:

```powershell
python .\bb_analyze.py <save.sav> --cache-debug
python .\bb_analyze.py <save.sav> --verify-cache --cache-debug
python .\bb_analyze.py <save.sav> --full-recompute
```

## Development setup

```powershell
python -m pip install -r tests\requirements.txt
```

Mandatory correctness run:

```powershell
.\run_tests.ps1
```

Static analysis:

```powershell
.\run_lint.ps1 -Tests
.\run_ruff.ps1 -Tests
```

Coverage:

```powershell
.\run_coverage.ps1
```

Mutation targets:

```powershell
.\run_mutation.ps1 -ListTargets
.\run_mutation.ps1 -Target projection/scoring
```

See `docs/TESTING.md` and `docs/MUTATION_TESTING.md` for policy.

## Repository layout

```text
bbtool/          parser, analysis, projection, incremental cache, report code
config/          human-editable archetypes/classification/perk model
references/      tracked reference seeds + vanilla reference generators
tests/           unit/integration tests and mutation helpers
docs/            architecture, invariants, workflow, specs, changelog
tools/           release/static tooling
```

## Releases

Version numbers are release markers, not commit counters. Follow `docs/RELEASE.md` when producing a gameplay ZIP.
