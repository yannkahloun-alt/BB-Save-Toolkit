# Mutation testing

`run_mutation.ps1` is the supported entry point for Cosmic Ray campaigns.

## Target naming

Any module or package below `bbtool` can be selected with `-Target`. Use
`.\run_mutation.ps1 -ListTargets` to list canonical targets.

Examples:

```powershell
.\run_mutation.ps1 -Target classification
.\run_mutation.ps1 -Target projection/scoring
.\run_mutation.ps1 -Target projection
```

## Automatic test discovery convention

Unless `-Tests` is supplied, the launcher maps production modules to pytest files
by basename.

For a production module named `foo.py`, the launcher searches:

```text
tests/unit/test_foo.py
tests/unit/test_foo_*.py
tests/unit/test_*foo*.py
tests/integration/test_foo.py
tests/integration/test_foo_*.py
tests/integration/test_*foo*.py
```

For package targets, the launcher performs that lookup for every contained
Python module and unions the matches. Tests named after the package itself are
also considered.

This naming convention is the preferred way to associate tests with mutation
targets. The module basename may appear anywhere after the `test_` prefix, so
`classification.py` automatically discovers both
`test_classification_contract_full.py` and `test_planner_classification.py`. This
avoids a manually maintained target-to-test map.

If no tests match, the launcher warns and falls back to the full pytest suite.
For exceptional cases, use the explicit override:

```powershell
.\run_mutation.ps1 -Target foo -Tests tests/unit/test_bar.py,tests/integration/test_baz.py
```

Generated Cosmic Ray TOML uses forward-slash paths even on Windows to avoid
backslash escape parsing issues.

## Safety

The launcher snapshots the selected source target before mutation, restores it
after completion or recoverable interruption, verifies restored file hashes,
and can recover an abandoned snapshot with:

```powershell
.\run_mutation.ps1 -Restore
```


## Equivalent mutants

A mutant is equivalent when no reachable input can distinguish it from the
original program. Record reviewed cases in `equivalent_mutants.json` with the
module, operator, occurrence, definition name, and reasoning.

The launcher reports both Cosmic Ray's raw survivors and an effective score
that excludes only these documented equivalents.


## Console outcome summary and encoding

After report generation, the launcher prints KILLED / SURVIVED / INCOMPETENT /
TOTAL counts and lists every INCOMPETENT mutant in the console.

The launcher forces UTF-8 Python/pytest output for Cosmic Ray campaigns.
Cosmic Ray 8.7 decodes captured pytest output as UTF-8; without this, Windows
legacy code pages can turn an otherwise killed mutant into a false INCOMPETENT.


## Hardening rule

Treat every survivor as a potential regression gap first. Strengthen observable
contracts or simplify ambiguous production logic when that improves future
change safety. Do not restructure stable code solely to eliminate a mutant that
has been proven behaviorally equivalent on all valid inputs.


## Automatic test selection

Mutation test selection uses **direct Python imports as the primary dependency
signal**. For a target such as `bbtool/levelup_advisor.py`, the launcher scans
`tests/unit` and `tests/integration` with the Python AST and selects tests that
import `bbtool.levelup_advisor` directly, including `from bbtool import
levelup_advisor` and `from bbtool.levelup_advisor import ...`.

The existing `test_<module>*.py` naming convention remains mandatory project
hygiene and is used as a complementary signal. The launcher unions import
matches and name matches. It does **not** depend on naming alone.

Selection order is therefore:

1. explicit `-Tests`, when supplied;
2. automatic import dependency plus naming matches;
3. full pytest suite only when neither mechanism finds a test.

This avoids accidental full-suite mutation campaigns when a valid test file has
a broader behavioral name such as `test_advisor_contract_full.py`.
