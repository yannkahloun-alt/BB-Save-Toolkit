## Unreleased

- Add least-privilege render-only web previews for approved public JSON
  scenarios, with exact-revision metadata, stable PR/main URLs, and automatic
  closed-PR cleanup on the persistent GitHub Pages branch.
- Add `--render-only DATASET` to validate a versioned public JSON dataset and
  generate the normal portable HTML report and archive without parsing a save
  or running analysis.
- Retain the 10 newest generated run archives per source-save filename after a
  successful archive write, without renaming outputs or deleting run folders,
  unrelated files, or archives from another save family.
- Add a compact run header and structured debug-bundle metadata covering the
  toolkit, schemas and engines, Python/OS environment, privacy-safe input and
  configuration fingerprints, execution mode, cache locations, and peak
  Python memory usage.

## v3.87 — Natural-stat-only classification cleanup

- Removes the obsolete hypothetical Base/Colossus classification branches now
  that archetype Fit, BestRole, and Level-Up Advisor are natural-stat-only.
- Keeps owned Colossus effective HP in current combat-stat displays without
  emitting duplicate classification rows, archetype cards, advisor trajectories,
  JSON fields, incremental artifacts, or profiling counters.

## v3.86 — Signed archetype Fit contributions and clearer projections

- Identifies collapsed level-11 stat ranges as deterministic under the displayed
  assumptions and keeps their zero-width range visible on the numeric axis.
- Explains the level-11 optimized stat-allocation policy in Archetype Details,
  including archetype Fit-stat eligibility, three-stat choices, Fit objectives,
  roll/effect inputs, and the exclusion of temporary injuries and hidden FutureRolls.
- Adds an accessible Archetype Details explanation distinguishing expected Fit
  from `P(Fit≥100)`, including why displayed Fit may exceed 100% without being
  capped.
- Keeps archetype Fit and displayed level-11 projections based on natural stats,
  excluding owned or hypothetical perk modifiers such as Fortified Mind and
  Colossus while retaining separately reported effective combat stats.
- Preserves exact permanent trait and permanent-injury transforms in natural
  projections and invalidates all dependent incremental artifacts.

## v3.85 — Archetype projection details and verified PR workflow

- Redesigns Archetype Details with a compact Target Profile, expandable five-part explanation strip, emphasized effective-current stats, and responsive level-11 development cards.
- Places projected minimum/maximum, Baseline, Target, and Expected on one live numeric axis, with fixed semantic colors and collision-safe numeric labels.
- Extends projection-range output with archetype baseline, target, and weight while preserving projection and Fit semantics.
- Invalidates stale role, structural-path, and summary cache artifacts that predate the expanded projection-detail payload.
- Adds GitHub Actions validation for tests, Ruff, and Pyflakes plus an independent exact-head Agent B review and automatic verified squash-merge workflow.

## v3.84 — Incremental hardening and permanent injuries
- Splits serialized traits from temporary/permanent injuries; `TraitIDs` now represent actual traits only.
- Fixes the v3.83 trait-effect lookup to key generated effects by the exact serialized 4-byte save hash rather than script `m.ID`, so real-save trait IDs resolve correctly.
- Adds generated `permanent_injury_effects.json`, discovering permanent-injury scripts by save hash/type and applying exact unconditional permanent stat effects to projections.
- Temporary injuries remain deliberately excluded from projection semantics and no longer invalidate projection/context incremental fingerprints.
- Permanent injury IDs do affect effective stats and invalidate affected cached projections.
- Bumps role-projection cache semantics to v3 and summary semantics to v2.
- Splits downstream incremental artifacts: structural paths and Level-Up Advisor can now be reused independently when a classification-only change invalidates the final summary.
- Adds `--cache-debug` with cache-miss reasons and per-artifact reuse/computation counters.
- `--verify-cache` now reports the first exact differing path/value instead of a generic mismatch.
- Adds incremental-manifest pruning (latest 10 manifests for the same save path; normal run outputs are never deleted).
- Adds diagnostic-only future-roll suffix continuity helpers for cross-save identity research. They are intentionally NOT used for cache identity until real before/after-level-up saves prove the invariant.

## v3.83 — Permanent trait stat effects
- Adds generated `references/trait_effects.json`, extracted from vanilla `scripts/skills/traits/*_trait.nut` using the same exact/unconditional core-stat parser used for perk effects.
- Applies exact permanent trait stat modifiers to effective current stats and projected level-11 stats.
- Trait effects are keyed by serialized `TraitID`, not display name.
- Keeps temporary injuries excluded from projection stat transforms.
- Adds `TraitIDs` to projection-context and incremental-cache fingerprints so trait changes invalidate cached results correctly.
- Bumps incremental role-projection engine compatibility from v1 to v2; v3.82 projection rows are therefore not reused under the new trait-aware semantics.
- Adds regression tests for Strong-style Fatigue bonuses, Tough-style HP bonuses, positive/negative defense modifiers, trait+perk composition, future-gain projection, temporary-injury exclusion, vanilla-script extraction, and cache invalidation.

## v3.82 — Incremental role-projection reuse
- Adds conservative SHA-256 fingerprints for brother projection state and normalized archetypes.
- Reuses `brother × archetype` role rows and unchanged brother summaries only on exact, unambiguous dependency matches.
- Names and save-local `HumanOffset` are excluded from reuse fingerprints.
- Adds atomic `*-incremental-manifest.json` output and restricts discovery to the same resolved save path.
- Adds `--full-recompute` and `--verify-cache`.
- Strategic classification reports reused versus computed role projections.
- Cache reuse is an orchestration optimization only; projection/scoring semantics are unchanged.

## v3.81 — Configurable archetype stat ceilings
- Adds optional per-archetype/per-stat `ceiling` configuration for Fit valuation only.
- Evaluates utility from `min(effective projected value, ceiling)` while preserving uncapped projections, displayed stats, roll allocation, and Battle Brothers mechanics.
- Validates ceilings as numeric, finite, and `>= target`; `ceiling == target` is allowed.
- Missing ceilings preserve the previous scoring behavior exactly.
- Propagates `value`, `fit_value`, `ceiling`, and `capped` explainability fields into projected Fit components.
- HTML archetype details show the Fit ceiling and capped value when applicable without rewriting the projection.
- Adds regression coverage for below/exact/above ceiling, ceiling==target, invalid configuration, backward compatibility, classification contribution saturation, trajectory behavior, and report explainability.

## v3.80 — Five-stat trajectory performance
- Replaces the exponential recursive 3-of-N future lookahead for 5+ Fit stats with an exact bounded drop-count composition solver.
- The optimization exploits order-independence of fixed-average future lookahead: only each stat's number of skipped future rounds affects terminal Fit.
- Keeps the established four-stat trajectory results unchanged and generalizes the same mathematical reduction to five-stat archetypes.
- Collapses Level-Up Advisor projections that are Fit-equivalent: all 56 legal 3-pick combinations are still represented, but only one trajectory is evaluated per distinct Fit-stat decision.
- Adds an exact-reference regression test comparing the optimized five-stat policy against the original recursive definition on small horizons.

## v3.79 — Module-by-module mutation campaigns
- Reworks `-Target all` / `-All` into an orchestrator over individual Python modules instead of one monolithic `bbtool` Cosmic Ray execution.
- Each module independently resolves its import/name-matched pytest dependencies and runs its own baseline, mutation session, reports, and source restoration.
- A failed module is recorded and the campaign continues with the remaining modules; the overall command exits non-zero if any target failed.
- Performs one planning-only Cosmic Ray inventory to obtain authoritative per-module mutant counts.
- Adds persistent `tests/mutation/mutation-history.json` timing history after successful target runs.
- Adds qualitative runtime scales (`minutes`, `hours`, `days`) to `-ListTargets`, using measured history when available and a conservative mutants × dependencies fallback otherwise.
- Orders `all` campaigns from estimated cheaper targets toward expensive targets.

## v3.78 — Structural brother identity
- Adds `BrotherID` derived from the serialized company `HumanOffset`.
- Visible brother names are now display-only and may be duplicated.
- Propagates `BrotherID` through roster JSON, fit rows, classification summaries, projection validation, and HTML joins/anchors.
- Removes the application stop condition for duplicate brother names.
- Keeps `Name` in user-facing artifacts for readability.
- `BrotherID` is unique within one parsed save; no cross-save stability claim is made.

## v3.77 — Mutation target inventory
- Enhances `run_mutation.ps1 -ListTargets` with selected test-dependency counts.
- Adds authoritative `mutants=` counts from one global Cosmic Ray initialization, without executing mutants.
- Aggregates the global work queue into module and package totals.
- Displays full-suite fallback explicitly as `deps=FULL/N`.
- Adds a schema-tolerant Cosmic Ray session inventory helper and regression tests.

## v3.76 — Fix recruit internal-tail trait pairing
- Filters `perk` and `internal` circle-tail entries before strict pairing with player-facing `Traits`.
- Preserves strict validation for the entries contractually represented in `Traits`.
- Fixes a real-save recruit parsing crash where two internal tail records made raw `Tail` longer than `Traits`.
- Corrects an old candidate-record fixture that incorrectly exposed an internal entry as a public trait.
- Adds a regression test matching the real two-trait plus two-internal shape.

## v3.75 — Fix ambiguous roster identity detection
- Requires a valid serialized level-up roll stream before an identity+stars candidate can count as a company brother identity.
- Fixes a real-save ambiguity where an incidental payload block looked like a second brother identity.
- Adds regression coverage for one valid and one false identity+stars candidate in the same structural record.

## v3.74 — Kill final runner mutant
- Adds the missing contract for an absent `generated_perks` key when dictionary/background generation flags are both false.
- Locks the `.get(..., False)` default so the runner reports the reference step as cached.

## v3.73 — Harden runner workflow contracts
- Adds full mutation-contract coverage for `app/runner.py`.
- Locks total elapsed-time subtraction and rendered total duration.
- Locks `ensure_references(verbose=False)` and all dictionary/background/perk generation combinations.
- Locks cached/generated Step details.
- Locks report-opening branch semantics and `Opened: yes/no` rendering.

## v3.72 — Eliminate remaining console mutants
- Strengthens console contract fixtures so arithmetic and numeric-constant mutations are observably distinct.
- Locks `Step.started` initialization and uses timing values that distinguish subtraction from modulo.
- Uses fractional KiB/MiB fixture values to distinguish `/` from `//`.
- Uses larger byte counts to distinguish 1024 from 1023/1025 after formatting.
- Deduplicates selected mutation tests before execution.

## v3.71 — Harden console output contracts
- Adds strict output-contract tests for `app/console.py`.
- Locks `Step` elapsed-time semantics, success-path context-manager behavior, and detail rendering.
- Locks all reference-status sections, conversions, counts, timings, and optional-section guards.
- Locks unresolved-sample truncation to the first 10 items.
- Locks projection-profile values, defaults, cache counters, and call counters.
- Leaves console production logic unchanged; the mutation gap was missing output assertions.

## v3.70 — Harden CLI contracts and zero-mutant runs
- Adds dedicated mutation-hardening tests for `app/cli.py`.
- Locks the CLI repository root to exactly `Path(__file__).resolve().parents[2]`.
- Locks `CliOptions` as an immutable/frozen dataclass.
- Treats a Cosmic Ray session with `0/0` jobs as a successful no-mutant target instead of an incomplete execution error.
- Skips mutation report generation for zero-job sessions while preserving source restoration and verification.

## v3.69 — Eliminate final planner mutation gaps
- Removes an equivalent mutation in `_first_round_ranges()` by representing a missing `LevelPoints` attribute explicitly as `None` instead of a numeric fallback that was indistinguishable under `> 0`.
- Adds a precision-sensitive ProjectedFit contract that distinguishes four-decimal rounding from five-decimal rounding.
- Keeps the functional planner behavior unchanged for valid Brother instances while making the missing-attribute contract explicit.

## v3.68 — Harden projection planner contracts
- Adds dedicated mutation-hardening tests for `projection/planner.py`.
- Locks ProjectedFit percent-to-ratio conversion and decimal precision.
- Locks exact payload percentage/range fields and per-stat rounding.
- Locks `_first_round_ranges()` to positive LevelPoints plus non-empty CurrentRolls, including zero/negative/missing boundaries.
- Locks fast/full projection profiling increments separately.
- Locks full projected ranges/state metadata and fast payload equivalence.
- Leaves planner production logic unchanged; the 26 surviving mutants were test-contract gaps.

## v3.67 — Harden projection runtime profile contracts
- Adds dedicated mutation-hardening tests for `projection/runtime.py`.
- Locks the exact PROFILE key set, zero initialization values, and int/float type split in a fresh Python process.
- Verifies `reset_profile_values()` resets every entry after non-zero contamination.
- Verifies `get_profile_values()` returns a detached snapshot rather than the live dict.
- Leaves runtime production logic unchanged; the 30 surviving mutants were test-contract gaps.

## v3.66 — Harden projection context cache contracts
- Adds dedicated mutation-hardening tests for `projection/context.py`.
- Locks the cache capacity contract at exactly 256 entries.
- Verifies preservation below the threshold and clearing at or above it, including defensive over-limit states.
- Locks perk participation and order-independence in `bro_fingerprint()`.
- Locks zero defaults for missing `Level` and `LevelPoints`.
- Leaves production context logic unchanged; the 15 mutation findings were test-contract gaps.

## v3.65 — Import-driven mutation test selection
- Makes direct Python import dependency the primary automatic signal for selecting mutation tests.
- Keeps the `test_<module>*.py` naming convention as a complementary project convention instead of a hard dependency.
- Unions import-based and name-based matches; full-suite fallback is used only when both are empty.
- Adds AST-based selector tests and documents the selection hierarchy.
- Prevents `levelup_advisor` from silently falling back to the entire pytest suite merely because its historical tests use `advisor` rather than `levelup_advisor` in filenames.

## v3.64 — Harden projection/perks from first mutation audit
- Addresses all 71 survivors from the first 211-job `projection/perks.py` campaign as audit findings.
- Adds exhaustive unit contracts for operator dispatch, invalid operators, division signs/zero, finalization properties, structural filtering, loop continuation, error paths, explicit effect maps, and profile multipliers.
- Replaces postponed `dict[...] | None` annotations with `Optional[...]` so Cosmic Ray no longer spends 22 mutants on inert annotation operators.
- Splits the structural-model tuple `except` into explicit missing/invalid JSON branches, eliminating the Cosmic Ray `ExceptionReplacer` incompetent site and clarifying errors.
- Preserves structural model declaration order internally before final sorted output for deterministic hardening tests.

## v3.63 — Make scoring lower clamp explicit
- Replaces the redundant first-point `value <= first_x` branch in `curve_value()` with `value = max(value, first_x)` before interpolation.
- Preserves the lower-clamp and exact-first-point behavior while removing the equivalent `<` / `<=` mutation site.
- Adds a hardening regression test using a non-zero first X/Y pair and values below, just below, exactly on, and inside the first segment.
- Removes the now-obsolete `projection__scoring` equivalent-mutant registry entry.

## v3.62 — Scoring hardening over cosmetic mutation score
- Reverts the v3.61 `curve_value()` structural refactor and restores the simpler v3.60 implementation.
- Expands scoring contract coverage across endpoint clamping, exact knots, interpolation, monotonicity, empty/single-point curves, input immutability, weighted averaging, non-fit skipping, zero-weight handling, and score lower-bound clamping.
- Explicitly locks the existing contract that scores may exceed 1.0 when the configured utility curve does.
- Registers the first-boundary `<=` -> `<` scoring mutant as a reviewed equivalent with a behavioral proof.
- Establishes the hardening rule: future-regression protection first; raw mutation score second.

## v3.60 — Close projection/scoring survivors
- Refactors `curve_value()` first-point handling to explicit `first_x` / `first_y`.
- Handles `value <= first_x` in one early return, eliminating the prior equivalent `<` / `<=` mutation site.
- Adds first-point tests with deliberately different X/Y values so `NumberReplacer` index mutations are observable.
- Keeps the v3.59 UTF-8 Cosmic Ray fix and console INCOMPETENT summary.

## v3.59 — Scoring mutation hardening and visible INCOMPETENT outcomes
- Strengthens `projection/scoring.py` tests for first-point semantics, continue-vs-break behavior, default weights, component rounding, negative-score clamping, and auxiliary return contracts.
- Removes the unreachable duplicate-x branch in `curve_value()` and changes the equivalent first-boundary check from `<=` to `<`.
- Forces Python/pytest UTF-8 output during Cosmic Ray runs to prevent false `INCOMPETENT` outcomes caused by Windows legacy code-page bytes.
- Mutation report console summary now prints KILLED / SURVIVED / INCOMPETENT / TOTAL and lists every INCOMPETENT mutant by module/operator/occurrence.
- Updates mutation documentation accordingly.

## v3.58 — Eliminate classification equivalent comparison
- Rewrites `perk_compatibility()` affinity labeling as explicit ordered intervals (`<1`, `<2`, `<5`, else HIGH).
- Eliminates the equivalent `total == 1` / `total >= 1` mutation pair rather than merely reversing its direction.
- Adds an additional negative-total boundary regression case.
- No intended behavior change.

## v3.57 — Remove classification equivalent mutation site
- Refactors `perk_compatibility()` final label branch from `total >= 1` to `total == 1`.
- This is behavior-preserving because earlier branches already consume all integer totals >= 2.
- Adds a negative-total regression case to guarantee that non-positive totals remain `NEUTRAL`.
- Removes the now-obsolete `classification` entry from the equivalent-mutant registry.
- The equivalent-mutant infrastructure remains available for future genuinely unavoidable cases.

## v3.56 — Equivalent mutant accounting
- Adds `tests/mutation/equivalent_mutants.json` for reviewed semantically equivalent mutants.
- Registers `classification.py` `GtE_Eq` occurrence 5 in `perk_compatibility`.
- Adds `tests/mutation/effective_score.py`.
- `run_mutation.ps1` now prints raw survivors, equivalent count, meaningful survivors, and effective mutation score after report generation.
- Documents the policy not to alter production code or invent artificial tests solely to force a raw 100% mutation score.
- No production behavior change.

## v3.55 — Close final classification survivor
- Adds the missing `perk_compatibility()` boundary case for affinity total 3.
- This distinguishes the intended `total >= 2` MEDIUM contract from the surviving `total == 2` mutant.
- No production-code behavior change.
- Keeps the v3.54 mutation launcher fixes and automatic test discovery.

## v3.54 — Classification mutation hardening and runner completion fix
- Expands automatic mutation test discovery from `test_<module>*` to any `test_*<module>*.py` under unit/integration tests.
- `classification.py` now automatically selects both `test_classification_contract_full.py` and `test_planner_classification.py`.
- Rebuilds classification contract tests around threshold boundaries, defaults, conflict handling, affinity accumulation, sort keys, percentage conversion, and fallback behavior.
- Full pytest suite rises from 405 to 441 passing tests.
- Fixes the false `cosmic-ray exec failed with exit code` crash on Windows PowerShell after a fully completed session.
- Final Cosmic Ray success is now determined from the authoritative session state (`complete == total`), while incomplete sessions still fail loudly.
- Updates mutation-testing documentation for the broadened filename convention.
- No intended application behavior change.

## v3.53 — TOML-safe dynamic test paths and naming convention docs
- Normalizes dynamically selected pytest paths to forward slashes before embedding them in generated Cosmic Ray TOML.
- Fixes Windows backslash escape parsing errors such as `Invalid escape sequence`.
- Documents the automatic mutation test naming convention in the project README and `tests/mutation/README.md`.
- Defines preferred patterns: `test_<module>.py` and `test_<module>_*.py` under unit and integration tests.
- Documents package-target union behavior, full-suite fallback, and explicit `-Tests` overrides.
- Console output now shows the normalized paths Cosmic Ray receives.
- No application behavior change.

## v3.52 — Automatic mutation test discovery and interval timing
- Automatically selects mutation tests by target/module basename and `test_<module>*.py` naming conventions.
- Package targets union matching unit/integration tests for contained modules.
- Prints the selected test files before mutation starts; explicitly warns on full-suite fallback.
- Keeps `-Tests` as an explicit override.
- Live progress now displays observed seconds/job for jobs completed since the previous useful sample, alongside total elapsed time and ETA.
- No application behavior change.

## v3.51 — Correct Cosmic Ray live progress
- Fixes live mutation progress for Cosmic Ray 8.7 sessions.
- `session_progress.py` now counts total jobs from `work_items` and completed jobs from `work_results`, matching Cosmic Ray's actual SQLite schema.
- Adds a regression test using a minimal Cosmic Ray-compatible SQLite schema.
- Rolling ETA now has real completed-job data to work from.
- No application behavior change.

## v3.50 — BOM-safe generated Cosmic Ray configs
- Fixes dynamic mutation profiles on Windows PowerShell 5.1.
- Generated TOML files are now written as UTF-8 without BOM via `System.IO.File.WriteAllText`.
- Prevents Cosmic Ray/TOML `invalid character in key name` errors caused by the BOM.
- No application behavior change.

## v3.49 — Dynamic mutation targets
- Removes the fixed PowerShell `ValidateSet` for mutation targets.
- `-Target` now accepts any Python module or package under `bbtool`.
- Adds `-ListTargets` to enumerate every currently available target.
- Supports canonical paths (`projection/scoring`), `bbtool/...` paths, optional `.py`, and unique short module names (`scoring`).
- Generates Cosmic Ray TOML configuration at runtime under `tests/mutation/generated/`.
- Adds optional `-Tests` so a target can be paired with an explicit pytest subset without rebuilding.
- Keeps the optimized dedicated progression test suite automatically.
- Keeps `-All` for the complete package.
- Generalizes safety backup/restoration to arbitrary module targets.
- No application behavior change.

## v3.48 — Safe interruption and robust live progress
- Replaces fragile embedded `python -c` SQL polling with `tests/mutation/session_progress.py`.
- Adds `-Restore` for manual recovery from an interrupted mutation run.
- Detects abandoned mutation backups automatically at startup and restores sources before a new run.
- The normal `finally` path now stops the Cosmic Ray child process before restoring sources.
- Keeps live completed/total, percentage, elapsed time, and ETA reporting.
- No application behavior change.

## v3.47 — Live mutation progress
- `run_mutation.ps1` now executes Cosmic Ray in a child process and polls its SQLite session while it runs.
- Displays completed/total mutants, percentage, elapsed time, and rolling ETA every few seconds.
- ETA is derived from observed average seconds per completed mutant and becomes meaningful after the first completed jobs.
- Mutation behavior and report generation are unchanged.
- No application behavior change.

## v3.46 — Global mutation campaign
- Adds `run_mutation.ps1 -All` to mutate the complete `bbtool` package.
- Keeps the progression campaign as the default profile and preserves its independent reports.
- Global mode runs the full pytest suite with `-x` and a 60-second per-mutant timeout.
- Separates reports under `tests/mutation/results/<profile>/`.
- Displays the initialized work-queue summary before execution and total elapsed time at the end.
- Backs up and restores the complete `bbtool` tree for global runs, then verifies restored file hashes.
- Renames the original mutation config to `tests/mutation/progression.toml`; adds `tests/mutation/all.toml`.
- No application behavior change.

## v3.45 — Explicit missing LevelPoints handling
- Refactors `development_rounds_to_11()` to handle absent `LevelPoints` explicitly via `None -> 0`.
- Removes the mutation-equivalent numeric fallback where `0 -> -1` was masked by `max(0, ...)`.
- Preserves behavior for normal, absent, zero, positive, and negative `LevelPoints`.
- Intended to eliminate the final surviving mutation in the progression campaign without weakening semantics.

## v3.44 — Mutation survivors hardening
- Adds a value-vs-identity contract test for `gain_range()` so an accidental `==` -> `is` mutation is detected.
- Adds a missing-attribute contract test for `development_rounds_to_11()` so absent `LevelPoints` is explicitly verified to default to zero.
- These two tests are expected to kill all three surviving mutants from the first progression mutation campaign.
- Full functional suite rises to 404 passing tests.
- No application behavior change.

## v3.43 — Cosmic Ray launcher path fix
- `run_mutation.ps1` now resolves `cosmic-ray`, `cr-report`, and `cr-html` from the current Python user's Scripts directory before falling back to PATH.
- Fixes Microsoft Store / user-site Python installs where Cosmic Ray is installed but console scripts are not on PATH.
- No application behavior change.

## v3.42 — Mutation-testing harness
- Adds Cosmic Ray 8.7.x as the mutation-testing dependency for native Windows/Python 3.13 compatibility.
- Adds `run_mutation.ps1`, initially targeting only `bbtool/projection/progression.py`.
- Adds a mandatory unmutated baseline before mutant execution.
- Uses the focused progression unit suite with pytest `-x` to keep mutant runs small.
- Writes SQLite, text and HTML artifacts under `tests/mutation/results/`.
- Backs up, restores and SHA-256 verifies the mutated source after each run.
- No application behavior change.

## v3.41 — Ruff cleanup I
- Resolves the first 10 Ruff findings from the conservative rule set.
- Splits a combined import and removes unused loop variables.
- Adds explicit exception chaining suppression for the user-facing duplicate-name exit path.
- Adds explicit `strict=` semantics to two `zip()` calls.
- Replaces unbounded `lru_cache(maxsize=None)` decorators with `functools.cache`.
- No application behavior change intended; full suite remains at 402 passing tests.

## v3.40 — Ruff static-analysis harness
- Adds Ruff 0.16.x to `tests/requirements.txt`.
- Adds `tests/ruff.toml` with a conservative quality-oriented rule set: F, selected E, B, UP, SIM and RUF100.
- Adds `run_ruff.ps1`, with optional `-Tests`.
- Keeps Pyflakes as a separate, minimal static-analysis baseline.
- Ruff cache is redirected to `tests/cache/ruff/`.
- No application behavior change.

## v3.39 — Pyflakes cleanup
- Removes six dead local assignments reported by Pyflakes from `html_report.py` and `save_parser.py`.
- Removes all unused imports reported by Pyflakes across the test suite.
- Improves `run_lint.ps1` so missing-Pyflakes and actual lint failures are reported separately.
- Full functional suite remains at 402 passing tests.
- No application behavior change.

## v3.38 — Static analysis harness
- Adds Pyflakes 3.4.x to `tests/requirements.txt`.
- Adds `run_lint.ps1` for static analysis of application code, with optional `-Tests` coverage of the test suite.
- Keeps Pyflakes separate from pytest instead of depending on the older `pytest-flakes` integration layer.
- Removes one genuinely unused `PROFILE` import from `bbtool.projection`.
- No application behavior change.

## v3.37 — Coverage campaign III
- Adds direct coverage for paired deterministic trajectory comparison, including win/loss/tie and zero-upside/downside paths.
- Covers projection-validation, debug-bundle, HTML output and workspace archive writers.
- Expands parser validation coverage for star metadata, serialized roll metadata, company roster boundaries, human-header validation and recruitment-roster detection.
- Expands lightweight Advisor coverage for degenerate roll ranges, no-legal-combination handling, single-candidate handling, non-gamble alternatives and Fit-neutral pick reasons.
- Fast branch-aware coverage rises from 88.2% to 91.9%.
- Full functional suite rises to 402 tests.
- No application behavior change.

## v3.36 — Coverage campaign II
- Adds focused branch tests for save-parser economy loading, circle-tail decoding, candidate-record decoding and skip paths.
- Adds end-to-end HTML report rendering tests, recruitment rendering branches, structural-path rendering and formatter edge cases.
- Adds targeted tests for projection public API resets/profile, config validation/normalization, context cache overflow/reset, CLI missing-save handling and first-round exact rolls.
- Fast branch-aware coverage rises from 76.0% to 88.2%.
- Full functional suite rises to 378 tests.
- No application behavior change.

## v3.35 — Coverage campaign I
- Adds lightweight branch-focused tests for the Level-Up Advisor without invoking expensive trajectory workloads under coverage tracing.
- Adds direct coverage for strategic analysis path selection and structural path orchestration.
- Adds coverage for console diagnostics, application entry point, workspace/output/archive helpers, formatting, and recruitment HTML helpers.
- Functional suite: 345 tests passed.
- Instrumented branch-aware coverage profile: 313 passed, 32 deselected, 76.0% total (up from 64.0%).
- No application behavior change.

## v3.34 — Test dependencies housekeeping
- Moves `requirements-dev.txt` from the project root to `tests/requirements.txt`.
- Development/test dependencies are now colocated with the test harness.
- Install them with `python -m pip install -r .\tests\requirements.txt`.
- No application behavior change.

## v3.33 — Test tooling housekeeping
- Moves `pytest.ini` to `tests/pytest.ini`.
- Moves `.coveragerc` to `tests/.coveragerc`.
- Pytest cache is redirected to `tests/cache/pytest/`.
- Coverage artifacts remain under `tests/coverage/`.
- Removes the `.bat` test/coverage launchers; PowerShell `.ps1` launchers are the supported Windows entry points.
- No application behavior change.

## v3.32 — Coverage artifacts directory
- All generated coverage artifacts now live under `tests/coverage/`.
- Raw coverage data: `tests/coverage/.coverage`.
- JSON report: `tests/coverage/coverage.json`.
- HTML report: `tests/coverage/html/index.html`.
- No application behavior change.

## v3.31 — Machine-readable coverage report
- Coverage runners now generate `coverage.json` in addition to terminal and HTML output.
- The direct reference command includes `--cov-report=json:coverage.json`.
- No application behavior change.

## v3.30 — Open generated report
- Adds opt-in CLI flag `--open-report`.
- After a normal analysis run, opens the generated HTML report in the system default browser.
- Default behavior is unchanged when the flag is absent.
- Adds CLI and runner tests for the new behavior.
- No projection, Advisor, Fit, classification, or report-content change.

## v3.29 — Branch coverage baseline
- Adds `pytest-cov` and branch-aware coverage configuration.
- Adds `run_coverage.bat` / `run_coverage.ps1` and a `coverage` selector in the shared test runners.
- Keeps the fast correctness suite unchanged at 327 tests.
- Marks 32 highly combinatorial test cases as `coverage_slow`: they still run normally, but are excluded from instrumented coverage because tracing makes them pathologically slow.
- Establishes a conservative branch-coverage baseline of 60.0% across `bbtool` (295 instrumented tests, 32 deselected).
- Generates an inspectable HTML coverage report at `htmlcov/index.html` on demand.
- No application behavior change.

## v3.28 — Contract-complete test coverage
- Added item-by-item traceability for all 30 test series.
- Expanded deterministic parser, trajectory, Advisor, validation, recruits, UI and architecture coverage.
- Added release ZIP cleanliness verifier.
- 327 executable pytest cases, with release archive audit run at packaging.

## v3.27 — Comprehensive test suite
- Expanded the shared pytest suite to 243 passing tests covering the remaining test plan.
- RelevantRollRankPct now explicitly ignores stats marked fit=false.
- Seeded validation can report out-of-normal-range hidden rolls without crashing; blind projection behavior is unchanged.

## v3.25 — Shared test harness

## v3.26

- Added exhaustive unit tests for `gain_range()` across all 8 stats and 0–3 stars.
- Added midpoint tests for `average_gain()`.
- Added boundary tests for `development_rounds_to_11()`, including pending points and levels above 11.
- No application behavior changed.

- Promotes the common pytest test harness to an official release version.
- Adds `tests/unit`, `tests/integration`, and `tests/fixtures` structure plus shared pytest configuration.
- Adds `run_tests.ps1` so the same test suite can be run from PowerShell or directly with `python -m pytest`.
- Moves the existing regression tests under the unit-test structure without changing their assertions and adds one infrastructure smoke test.
- Adds `tests\requirements.txt` and test-harness documentation.
- No intended Fit, projection, classification, Advisor, parser, or UI behavior change.

## v3.24 — Housekeeping / architecture pass
- Refactors full and fast role projection wrappers onto one shared payload builder; projection semantics and output values are unchanged.
- Removes obsolete compatibility `**_ignored` parameters from active role-projection call paths.
- Cleans the projection package public API so `project_fit_trajectory` is exported explicitly with the other trajectory entry points.
- Removes a malformed dead historical CSS selector and stale version-layer comments without changing active report styles.
- Updates architecture/TODO housekeeping and adds a regression proving fast projection is an exact subset of full projection.

# v3.23

- Strategic Classification: P(Fit) now uses the exact same category palette and typography as Path and Fit/ranges; removed heat-map styling from that cell.
- Level-Up Advisor wiring audit: one implementation (`advise_levelup`) remains the source for base and structural-path advice; HTML only renders stored advice.
- Added regression tests proving hidden FutureRolls cannot alter the current Advisor recommendation and P(Fit) uses category styling.

## v3.22

- Archetype detail copy made explicit: `Expected` replaces `EV`; `Fit development — Level 11` carries the horizon.
- `Weight` moved to the lower-right corner of each development chip and the redundant `FIT` badge removed.
- Archetype summary KPIs are right-aligned.
- Every archetype title now shows its own Invest / Use / Fodder / Trash class and icon.
- Removed the obsolete `range_chips()` helper and `.focus-build` CSS.

## v3.21
- UI-only: unified Strategic Classification row styling and rich archetype detail bodies.

## v3.20 — Strategic table alignment and archetype detail cleanup

- Strategic Classification now renders one real table row per classification path, keeping Paths / Fit-range / P(Fit≥100) vertically aligned.
- The selected path highlight is applied across the logical row instead of independently inside each metric cell.
- Fit/range rows regain the same frame, typography, and label treatment as the other strategic columns.
- Archetype cards are neutral by default; only retained base/structural trajectories use the gold treatment.
- Projected level-11 EV is folded into Development focus; the redundant Projected level 11 range block is removed.
- Removed two additional CSS leftovers confirmed unused by the generated report (`.lu-roll`, `.col-fit`).

## v3.19 — CSS purge and UI hygiene

- Purges obsolete report CSS left by historical v2.x UI iterations; 43 confirmed-dead class families are removed.
- Removes shadowed declarations for repeated identical selectors while preserving the winning cascade and keeps all live dynamic `band-*` classes.
- Removes obsolete version-layer comments from the stylesheet; report CSS drops by roughly 11 KiB without changing Python projection/classification logic.
- Fixes two stale report tooltips that still described the Likely Fit range as P10–P90 / ~80%; they now correctly say P5–P95 / ~90%.
- Regression: 7/7 Python tests pass and all remaining non-dynamic CSS classes are referenced by the current report generator/JS.

## v3.18 — Cleanup and architecture hygiene

- Cleanup-only release: no intended Fit, trajectory, classification, Advisor, validation, or UI behavior change.
- Removes four confirmed-unreferenced helpers and the obsolete immediate-Fit scoring block left in the Level-Up Advisor after v3.15.
- Removes inert parameters/imports from projection and validation internals so signatures reflect actual dependencies.
- Removes the obsolete root `archetypes_v37.json`; `config/archetypes.json` remains the single active archetype configuration.
- Updates architecture/docs to describe final level-11 Fit lookahead and deterministic low-discrepancy sampling accurately.
- Excludes Python/pytest cache directories from the release archive.
- Regression: 7/7 tests pass and canonical complete analysis output on the multi-bro fixture is byte-identical to v3.17.

## v3.17 — P5–P95 calibration + iso-performance pass

- Changes the displayed/validated Likely Fit range from P10–P90 to P5–P95; Expected Fit, full simulated range, trajectory generation, scoring, and classification logic are unchanged.
- Reuses base-role projections for structural-perk paths when the perk cannot affect any Fit stat of that role (currently most visible with Colossus on non-HP roles).
- Speeds up the exact four-stat final-Fit lookahead by precomputing each stat's contribution for every possible future drop count within a state; candidate values and deterministic iteration/tie behavior are unchanged.
- One-brother 9-role regression comparison against unoptimized v3.16 + P5–P95 produced byte-identical analysis outputs while reducing classification time from ~5.09 s to ~1.48 s on the local fixture.
- All 7 regression tests pass.

## v3.16 — Iso-performance optimization of final-Fit lookahead

- No intended semantic change versus v3.15.
- Reuses one memoized final-Fit lookahead policy across all deterministic sampled trajectories of the same projection context instead of rebuilding it per scenario.
- Adds an exact four-stat specialization: with 3 picks among 4 stats and fixed average future rolls, only the number of future drops per stat matters, not their order. The optimizer enumerates those drop-count compositions instead of the full recursive order tree.
- Added a golden regression test locking the v3.15 512-sample BF Frontline DPS result.
- Reference benchmark on the regression fixture: ~8.95 s -> ~0.42 s for 10 rounds / 512 samples (~21.6x), with all 512 outcome values and traces identical.

## v3.15 — Final-Fit lookahead for level-up selection

- Current picks are valued by projected final Fit at level 11, not immediate Fit gain.
- Future unknown rolls used for pick decisions are represented by normal-range midpoints; hidden serialized future rolls are never exposed to the policy.
- This lets low current stats receive investment before crossing their Fit baseline.
- Level-Up Advisor ranks current 3-pick combinations by expected final Fit through the same blind trajectory engine.

## v3.14 — Fit-consistent level-up selection
- Projection and Level-Up Advisor now rank rolls by their actual marginal contribution to archetype Fit (`weight × utility-curve gain`) instead of `weight × effective-stat gain / target`.
- This makes pick decisions respect baseline→target spacing, non-linear projected curves, saturation, and perk-adjusted effective values.
- Blind projection and validation oracle still share the exact same trajectory engine.
- Added a regression test proving that for Battle Forged Frontline DPS at baseline, Fatigue +3 correctly outranks HP +4 when its Fit contribution is larger.

## v3.13 — Level-11 roll-luck correlation

- Adds `roll_luck_to_level11` to `*-projection-validation.json`, with an exact cumulative-roll percentile for every stat of every brother through level 11.
- Per-stat ranks are computed from the exact vanilla discrete roll distribution implied by that stat's talent stars and remaining development rounds.
- Adds `RelevantRollRankPct` to every Bro×Archetype row: the archetype-Fit-weighted average of those per-stat roll ranks.
- Keeps raw RNG luck deliberately separate from Fit outcome: the rank ignores pick competition, targets, perk transforms and Fit curves, making `RelevantRollRankPct` vs `ActualPercentilePct` a direct diagnostic of how raw luck is translated into Fit.
- Bumps the validation artifact format to `bbtool.projection_validation.v3`.
- No classification, Advisor, Fit projection, sampling, or scoring behavior change.

## v3.12 — Projection percentile calibration

- Adds `ActualPercentilePct` to every Bro×Archetype row in `*-projection-validation.json`: the mid-rank percentile of the serialized real future inside the exact blind deterministic trajectory distribution used by classification.
- Adds `ActualPercentileSampleCount` so percentile resolution is explicit (normally 512, or 2048 for adaptively refined projections).
- Reuses the cached blind trajectory outcomes; no second projection algorithm and no hidden future rolls can influence the percentile distribution.
- Bumps the validation artifact format to `bbtool.projection_validation.v2`.

## v3.11 — Quarantined projection validation

- Moves all seeded-future / hidden-roll Ground Truth data out of the normal debug bundle into a dedicated `*-projection-validation.json`.
- Removes `FutureRolls` from normal `*-debug.json` roster serialization and `*-roster.json`; `CurrentRolls` remain because they are visible current-level data used by the Advisor.
- The validation artifact contains the 81 Bro×Archetype comparison rows, Expected Fit, Likely Range, simulated Full Range, actual seeded Fit, range-membership flags, feasibility, and exact seeded round choices.
- Classification and Advisor remain upstream of validation generation; validation is write-only diagnostic output and cannot influence recommendations.

## v3.10 — Single trajectory engine proof path

- Removes the parallel seeded-future level-up loop introduced for v3.9 diagnostics.
- Extends `project_fit_trajectory()` with per-round range overrides. Known future rolls are encoded as degenerate ranges (`X-X`).
- Ground truth now calls the exact same public trajectory engine as blind projection (`samples=1`, all future rounds fixed to their serialized `X-X` values).
- Optional trace capture is implemented inside the shared simulator, so Ground Truth level-by-level picks are produced by the same generic/specialized hot paths rather than reconstructed afterward.
- `first_round_ranges` remains supported and is normalized into the same per-round range plan, preserving existing projection and Advisor behavior.
- Strict regression on the real 17:43 save/debug: normal `fits` and `summaries` are identical to v3.9; all 81 seeded Fit values and all recorded level-by-level choices are identical to v3.9.
- Additional regression on a prior debug with Hilmar pending a level-up confirms the Level-Up Advisor output is unchanged.

## v3.9 — Seeded future-roll projection validation

- Parse the complete serialized future level-up roll arrays for every roster brother.
- Add `FutureRolls` to roster/debug data. This is diagnostic ground truth only and never feeds classification or Level-Up Advisor recommendations.
- Add `projection_ground_truth` to the debug bundle: exact seeded Fit for every Bro×Archetype, delta vs Expected, Likely/Full range coverage, and exact level-by-level picks chosen by the same Fit investment rule.
- Validate every serialized roll against the vanilla star-adjusted roll range.
- Cross-save validation confirms that spending a pending level-up removes exactly the first serialized roll from each stat array while preserving the remaining sequence.

## v3.8 — Fit-only architecture cleanup

- Removed all active v2-era analytical concepts that no longer contribute to the retained v3 model: Development Burden, Patch/Support/Core picks, Current Readiness, role gates, viability `min`/`ready`, exact Burden uncertainty, and the fixed `_role_alloc` planner.
- Archetype JSON is now strictly human-facing Fit data: `target`, `weight`, optional `baseline`, plus future perk metadata.
- Strategic Classification now consumes only Expected Fit and simulated Fit ranges: Invest/Use from Expected Fit; Fodder when only the full-range ceiling can still reach the Use threshold; Trash otherwise.
- Best-role/path tie-breaks now use Fit Feasibility and Likely Fit floor instead of Burden/Readiness.
- Level-Up Advisor output no longer carries legacy N/A Burden/Patch/AdvisorScore fields.
- Report and debug outputs now expose only v3 Fit concepts.
- Deleted the unused deterministic allocation planner, Burden uncertainty module, dead progression helpers, and legacy `bbtool.engine` facade.
- Profiling output was simplified so internal Fit trajectory time is visibly nested rather than mixed with obsolete counters.

## v3.7 — Shared projection context + allocation-free trajectory loop

- No scoring, archetype, classification, Advisor, sampling-count, or UI behavior change.
- Caches role-independent brother projection inputs (raw/current stats, exact perk effects, development horizon, expected gains and vanilla roll ranges) across all archetypes for the same brother state.
- Reuses the compiled Bro×Role trajectory context between the 512 fast pass and any 2048 adaptive refinement instead of rebuilding transforms and utility tables.
- Low-discrepancy sampling now caches individual dimensions, so different trajectory dimensionalities reuse previously generated Halton columns instead of recomputing them from dimension zero.
- Rewrites the common exactly-four-Fit-stat trajectory loop around four scalar raw values/rolls and direct deterministic drop-one comparisons, eliminating per-round rolls/keys container allocation while preserving the exact v3.6 ordering semantics.
- Strict regression checks on two real debug bundles produced identical `fits` and `summaries` to v3.6.

## v3.6 — Classification hot-loop + profiling visibility

- Specialized the common four-Fit-stat trajectory case without changing selection semantics: each level-up still chooses the best 3 of 4 by the exact historical `(weighted progress toward target, deterministic tie-break)` ordering.
- Removed per-round dict/list/tuple allocation from that hot path; raw values and rolls are held in compact local vectors.
- Verified strict non-regression against the v3.5 reference bundle: `fits` and `summaries` are byte-equivalent after JSON canonicalization.
- Expanded Strategic Classification profiling so top-level wall time is split into Base role matrix, structural paths, Level-Up Advisor and summary assembly.
- Added Fit trajectory cache hit/miss and adaptive-refinement counters.
- Renamed the old `base projection` timing to `projection setup` and marks trajectory/setup timings as subcomponents, preventing the probabilistic trajectory cost from appearing as unexplained wall time.

## v3.5 — Trajectory hot-loop optimization

- No scoring, archetype, classification, Advisor, sampling-count, or UI behavior change.
- Precompiles exact effective-stat transforms for every reachable raw Fit-stat value per Bro×Role projection.
- Precompiles projected utility values for the same reachable states, removing repeated perk transforms and curve scoring from sampled trajectories.
- Trajectory final scoring now uses those precompiled tables while preserving generic projected gates.
- Exactly-four-Fit-stat selection uses an equivalent drop-the-minimum path instead of sorting four candidates every round.
- Reference regression: `fits` and `summaries` are byte-for-byte-equivalent as parsed JSON to v3.4, excluding runtime timing/profile metadata.

## v3.4 — Performance cleanup + single-path projection model

- Removes the legacy alternate-perk stat simulation from projection, classification, debug output and UI.
- Keeps vanilla perk recognition in raw save/reference parsing only; the analyzer no longer computes a separate alternate-perk scenario.
- Caches deterministic low-discrepancy coordinates and repeated Bro×Role trajectory projections.
- Precomputes trajectory invariants (roll ranges, Fit-stat configuration, stat ordering).
- Adds a no-choice fast path for archetypes with at most three Fit stats.
- Removes repeated effective-stat reconstruction in the Level-Up Advisor.
- Keeps v3.3 Fit, ranges, Feasibility, BestRole, classification and Advisor recommendations unchanged on the reference debug after excluding the deliberately removed alternate-perk fields.

# Changelog

## v3.3 — Adaptive Fit sampling + Roster path-state fix

- Fit trajectory projection now uses a deterministic 512-sample fast pass and refines to 2048 only near the 100% threshold or when non-zero feasibility is detected.
- Explicit `samples=` calls remain fixed-size for benchmarks and paired comparisons.
- Gamble comparison starts at 512 and refines to 2048 only for potential gambles / close contests.
- Fixed Roster development-focus rows mixing hypothetical selected-path effective stats (e.g. Colossus HP) with base-path projections, which could display impossible decreases such as Svein Crossbow HP 71→57.
- No archetype scoring or target changes.


## v3.2 — Paired gamble diagnostics + Strategic Fit ranges

- Level-Up Advisor now compares Primary and Runner-up against the exact same deterministic future-roll scenarios.
- A Runner-up is labelled `GAMBLE` when its Expected Fit is lower than Primary but it still wins in some paired scenarios.
- Gamble diagnostics expose chance to beat Primary, average/max upside when it wins, expected Fit difference, and paired scenario count. No new AdvisorScore is introduced.
- Level-Up UI now separates Likely Fit Range (P5–P95) from Full Fit Range (explicit extremes) and adds explanatory tooltips.
- Strategic Classification now shows, per Base/structural path, Expected Fit, Likely Fit range, Full Fit range, and P(Fit >= 100%).
- Projection sample count remains 2048 in this release; the previously measured 512/adaptive optimization is deliberately deferred until gamble-probability convergence is validated.

## v3.1 — Probabilistic Fit trajectories + Fit-only Level-Up Advisor

- Replaces the base Projected Fit range with a deterministic real-level-up trajectory projector.
- Each simulated level-up rolls every Fit stat and selects up to three investments using archetype `weight × progress/target`.
- Adds `FitFeasibilityPct = P(ProjectedFit >= 100%)`; 100% is the archetype target standard.
- Pending known level-up rolls are represented as degenerate ranges (`X-X`) so the same projection semantics apply to normal analysis and Advisor what-ifs.
- Rebuilds the Level-Up Advisor around archetype Fit only. The historical AdvisorScore formula (Fit/Burden/Feasibility/Patch/RollQuality coefficients) is no longer used.
- Advisor still evaluates all 56 legal current 3-pick combinations, but only Primary/Runner-up receive a full future trajectory render.
- Historical Advisor Burden/Patch outcome slots remain in the UI as `N/A` instead of being silently repurposed.
- Fit distribution uses a deterministic low-discrepancy sample (2048 trajectories) plus explicit all-min/all-max anchor paths. This is deterministic but the feasibility percentage is an approximation of the full combinatorial distribution.

## v3.0 — Archetype Fit / Patch model refactor

- Replaced editable archetype `core/support` flags with human-facing `target`, `weight`, `baseline`, `ready`, and `min` fields.
- `target + weight` defines Core/Fit stats; `min` defines non-Core viability stats that generate Patch work.
- Added `perks.required` and `perks.recommended` metadata to archetypes; this metadata is intentionally not used by scoring yet.
- Fit now excludes min-only viability stats.
- Patch Picks are computed directly from configured viability minima; Burden remains Patch Picks divided by remaining stat-pick capacity; Feasibility uses exact future-roll distributions against those minima.
- Projection allocation patches unmet viability minima before spending remaining picks on Fit.
- Added `PatchPicks`, `PatchPickDetail`, `FitPicks` fields while retaining v2.66 Support/Core aliases for compatibility.
- Level-Up Advisor formula and coefficients are unchanged; it now consumes the new Patch metrics.
- Archetype values are initial calibration and are intentionally editable in JSON for iterative testing.

## v2.66 — Restore Level-Up brother panel
- Restores `levelup_bro_panel()`, accidentally removed during the v2.65 UI refactor.
- Keeps the v2.65 Base/Colossus trajectory segmentation and full runner-up display.
- Adds an actual report-render regression check against a supplied real run before packaging.
- No scoring, projection, or classification changes.

## v2.65 — Level-Up trajectory segmentation + full runner-up
- Rebuilds Level-Up presentation around visually distinct trajectory containers.
- Base and Colossus paths now have dedicated banners and enclosing borders, preventing
  their roll boards from visually blending together.
- Each trajectory contains a clearly separated PRIMARY and RUNNER-UP candidate.
- Runner-up now uses the same complete 8-roll board as the primary recommendation.
- Runner-up now exposes the same Fit, Burden, Patch Picks, and Feasible outcomes.
- Displays AdvisorScore for primary and runner-up to make close decisions auditable.
- Keeps roll ranges/quality and notable-skip explanations from v2.64.
- No Advisor scoring, projection, or BestRole changes.

## v2.64 — Level-Up roll board integrated into recommendations
- Removes the separate `Available Rolls` section introduced in v2.63.
- Replaces each recommendation's three-card pick strip with the complete current
  roll board.
- All available rolls now appear directly inside each trajectory recommendation,
  with roll value, legal star-adjusted range, and MIN/LOW/AVG/HIGH/MAX quality.
- The three recommended stats are highlighted; non-selected rolls remain visible
  for comparison.
- Notable skipped role/core stats are explained immediately beneath the same board.
- This applies independently to Base and structural-perk trajectories, so differing
  pick recommendations remain directly comparable.
- Keeps the v2.63 single-file debug JSON output unchanged.
- No Advisor scoring or BestRole changes.

## v2.63 — Level-Up transparency + single debug bundle
- Level Up now shows every available stat roll, not only recommended picks.
- Each roll displays its star-adjusted legal range and a relative quality label
  (`MIN`, `LOW`, `AVG`, `HIGH`, `MAX`).
- Recommended rolls remain visually highlighted.
- Adds a deterministic explanation when an important/core role stat is available
  but skipped, including its current roll quality and legal range.
- Adds `<save>-debug.json` to every analyzed run. The single file contains roster,
  recruits, role-fit data, classification data, active archetype/classification
  config, reference-generation diagnostics, and projection profiling.
- The debug bundle is designed to be shared directly for troubleshooting instead
  of sending the whole output ZIP.
- No Level-Up scoring weights or BestRole logic changed.

## v2.62 — Duplicate brother-name handling
- Adds a dedicated `DuplicateBrotherNameError` for duplicate company names.
- Replaces the raw Python traceback with a clear, user-facing stop message.
- Explains that brother names are currently used as analysis/report identifiers.
- Instructs the user to rename one duplicate brother in-game, save, and rerun.
- Exits with status code 2 for this expected, user-fixable input condition.
- No parsing heuristics, scoring, projection, or UI behavior changes.

## v2.61 — Fodder classification cleanup
- Simplifies Fodder to its effective rule: after Invest and Use have already failed, Current Readiness only needs to meet the configured Fodder floor.
- Removes the redundant `Fodder.max_projected_fit` configuration key.
- No classification behavior change; the removed Fit test was implied by the preceding Use branch.

## v2.60 — Patchable-Burden Fit protection
- Adjusts Level-Up Advisor scoring when Burden feasibility is 100% both before
  and after a candidate pick.
- In that fully patchable regime, a negative Fit delta receives an additional
  equal penalty, so the Advisor no longer sacrifices role quality merely to
  resolve non-urgent support Burden faster.
- Burden reduction, support-pick savings, feasibility and roll quality retain
  their existing weights; only avoidable Fit loss is discouraged.
- Adds `FullyPatchable` and `FitLossPenaltyPct` diagnostics to Advisor candidates.
- Theudobald regression: Crossbow/Gunner now prefers HP + FAT + RAtk over
  HP + FAT + Resolve on the supplied level-up.
- No BestRole or projection changes.

## v2.59 — Fortified Mind removed from BestRole reveal
- Reclassifies Fortified Mind from `Structural BestRole perk` to `Archetype-enhancing perk`.
- BestRole reveal paths are now driven by the reviewed allow-list in `config/perk_model.json`, not inferred solely from exact vanilla stat effects.
- Colossus remains the only BestRole reveal perk. Fortified Mind no longer generates `Fortified Mind` or `Colossus + Fortified Mind` classification paths.
- Fortified Mind still applies normally when a brother actually owns the perk; this change only removes hypothetical FM reveal branches.
- Updates `PERK_MODEL.md`, architecture and TODO documentation to record the non-circular modeling rule.

## v2.58 — Strategic Paths compression


- Reduced the Paths column and reassigned width to Fit, Ready, and Burden.
- Added explicit classification icon + label to every Path row.
- Reworked Path rows into a compact two-line layout with role ellipsis/tooltips.

## v2.53 — Strategic table identity rebalance
- Fixes a legacy Paths cell width override that was defeating colgroup sizing.
- Allocates 14% Brother, 18% Background, 8% Paths, and 20% each to Fit / Ready / Burden.

## v2.52
- Strategic Classification table now allocates 20% width each to Fit, Ready, and Burden, 25% to Paths, and the remainder to identity columns.
- No change to path-selection logic.

## v2.50 — Path-first roster table

- Removed the redundant Class column from Strategic Classification.
- Paths now expand to use the available table width.
- Each path row uses its classification color (Invest / Use / Fodder / Trash).
- The selected path remains separately highlighted.
- Versioning returns to x.xx format.


## v2.49 — Configurable Invest threshold + path-aware KPI columns
- Raises `thresholds.Invest.min_projected_fit` from 0.82 to 0.95 in `config/classification.json`.
- Classification thresholds remain data-driven: Invest/Use/Fodder limits are read from JSON, not hardcoded in Python.
- Main-table Fit, Ready, and Burden columns now show one value per classification path instead of only the selected path.
- Selected path is highlighted consistently across Paths, Fit, Ready, and Burden.
- No archetype scoring changes beyond the already-shipped Banner Resolve soft gate of 100.


## v2.48 — Classification paths in the main roster table
- Built directly from v2.47; no v2.48 UI-detail changes are carried forward.
- Adds a dedicated Paths column to the first Strategic Classification table.
- Shows Base and every structural path with its Class, role, Fit, Readiness, and Burden.
- Marks the path that actually determines the final classification as SELECTED.
- Shows the selected path label under Best archetype for immediate attribution.
- No scoring, classification, archetype, or detailed-panel behavior changes.

## v2.47 — Classification across structural perk paths
- Strategic classification now evaluates the Base path plus every available structural-perk path (currently Colossus, Fortified Mind, and their combination).
- Each path is classified independently with the existing Invest/Use/Fodder/Trash thresholds.
- The summary selects the highest strategic class across paths; ties prefer fewer hypothetical perks, then higher Fit, lower Burden, and higher Readiness.
- Paths are evaluated even when the best archetype does not change, because a structural perk can improve classification without role-flapping.
- Adds `ClassificationPaths` and `SelectedClassificationPath` to classification JSON for auditability.
- Keeps existing `StructuralPerkAlternatives`, `ColossusBestRole`, and `FortifiedMindBestRole` fields for report/backward compatibility.
- Carries forward the current Banner calibration: projected Resolve soft gate = 100.
- Regression targets on the supplied 2026-08-16 save: Ruthard Fodder -> Invest via Fortified Mind/Banner; Thilmann remains Trash.

## v2.46 — Reference/cache policy and perk audit cleanup
- Clarifies reference-data ownership: static bootstrap/catalog files ship;
  network-derived caches are generated on first run and reused afterwards.
- Documents that `perk_effects.json` is required runtime data, not an optional
  feature, while keeping it out of release ZIPs as a generated cache.
- Projection now fails loudly if `perk_effects.json` is missing when called
  outside the normal runner, instead of silently disabling structural perks.
- Adds `config/perk_model.json`, the machine-readable BestRole classification.
- Adds offline `references/perk_catalog.json`: 50 standard/save-visible vanilla
  perks, all 50 reviewed, 0 remaining.
- Adds generated `references/perk_audit.json`, which reconciles every perk script
  found in the downloaded vanilla source against the model and reports any
  additional/unreviewed source perks.
- Updates PERK_MODEL/TODO/reference docs to make the audit state and next action
  unambiguous.

## v2.45 — BestRole perk exclusion ledger
- Expands `docs/PERK_MODEL.md` with the perks reviewed during the manual audit.
- Adds a persistent BestRole exclusion list grouped by stat/resource,
  offensive, defensive, tactical and weapon/build effects.
- Records all weapon masteries as build-dependent exclusions.
- Keeps Colossus and Fortified Mind as the only structural BestRole allow-list
  entries identified so far.
- Adds a TODO to reconcile the actual vanilla perk source list against this
  exclusion ledger and discuss only genuinely unreviewed core-stat modifiers.
- No scoring, projection or UI changes.

## v2.44 — Persistent perk-model decisions
- Adds `docs/PERK_MODEL.md` as the source of truth for perk/BestRole modeling.
- Records the core anti-circularity rule used to decide whether a perk may
  influence BestRole.
- Records decisions and reasoning for Colossus, Fortified Mind, Dodge, Brawny,
  Reach Advantage and Lone Wolf.
- Updates `docs/TODO.md` so completed perk decisions survive conversation context.
- No scoring, projection or UI behavior changes.

## v2.43 — Correct default archetype panel
- Fixes the real cause of the wrong default archetype opening: the first base
  archetype still carried a server-rendered `open` attribute before structural
  trajectories were merged and sorted.
- Removes all pre-opened base archetype state.
- The marked highest-Fit card from the merged base + structural trajectory list
  is now the authoritative default.
- Makes the JS defensive against stale open state when entering a Brother Detail.

## v2.42 — Archetype default-open and burden clarity
- Marks the highest-Fit archetype card after merging normal and structural-perk
  trajectories, so the true best Fit card opens by default.
- Updates the archetype accordion JS to prefer that marked card rather than the
  first normal/base archetype.
- Restores a visible border around Burden KPI areas in archetype headers.
- Replaces unreachable Burden KPI content with a centered, high-contrast
  `CANNOT BE COMPLETED` stamp in the header.
- No scoring or projection changes.

## v2.41 — Roster Management and archetype UX
- Adds a `Roster Management` tab between Level Up and Recruits.
- Moves the Brother × Archetype matrix into Roster Management and makes matrix
  brother names static rather than links to Brother Details.
- Uses equal fixed-size trajectory cards aligned to the right of Brother headers;
  role names are anchored top-left and single cards no longer stretch.
- Removes injury names from the Traits display to avoid duplication.
- Adds tooltip-ready rendering for perks, traits and injuries; descriptions are
  shown when a source-backed description cache contains them.
- Removes Development Plan and Gate Diagnostics blocks from archetype details;
  Development Focus remains the actionable projection view.
- Gives Fit, Ready and Burden equal-width, wider KPI zones in archetype headers.
- Makes archetype panels exclusive accordions inside each Brother Detail. When a
  brother is opened and no archetype is expanded, the first (highest-Fit) one
  opens automatically.
- Structural/bonus archetype headers now use the same components and visual style
  as normal archetype headers.

## v2.40 — Unified archetype detail list
- Removes the separate `Alternate Trajectory Details` section.
- Removes `Current` from the archetype-detail section label.
- Structural-perk trajectory cards now live directly alongside normal archetype
  cards under a single `Archetype Details` section.
- Sorts normal and structural trajectory cards together by Projected Fit,
  highest to lowest.
- Structural trajectory cards inherit the same rounded yellow archetype-card
  presentation as the rest of the list.

## v2.39 — Unified archetype cards and development focus
- Fixes overlap in the Brother Detail trajectory summary cards by replacing
  absolute-positioned labels with a responsive grid layout.
- Applies the same rounded yellow visual language to every archetype detail card,
  including the default/current archetypes and structural alternatives.
- Adds a `Development focus` block to each archetype detail.
- Development focus shows only stats the projection plans to invest level-up picks
  in, as `current → lvl 11 min–max`, with the projected pick count.
- Distinguishes normal build investment from patch/support investment.
- Keeps the complete projected level-11 range underneath for deeper inspection.

## v2.38 — Trajectory ordering and archetype stats
- Orders Default and structural-perk trajectory cards from highest Fit to lowest Fit.
- Highlights stats configured as important for the current archetype in Current
  Brother Details.
- Highlights the corresponding important stats independently inside each alternate
  trajectory detail, so a role switch visibly changes which attributes matter.
- Keeps Default visually equivalent to alternate trajectory cards.

## v2.37 — Horizontal trajectory cards
- Displays Default and structural-perk archetype trajectories side by side on one row.
- Gives the Default trajectory the same rounded yellow frame as alternatives.
- Adds an explicit `DEFAULT` path label for visual symmetry.
- Preserves prominent Fit, Ready and Burden metrics and all detailed trajectory
  information below the Brother header.
- Falls back to horizontal scrolling on narrower layouts rather than stacking cards.

## v2.36 — Brother Detail trajectory header
- Restores the compact stacked trajectory presentation in Brother Details instead
  of the v2.35 comparison table.
- Removes the misleading `Best Archetype` label when multiple valid structural
  trajectories are shown.
- Gives each alternate structural trajectory a rounded yellow frame.
- Makes Fit, Ready and Burden substantially more prominent in the Brother header.
- Keeps the richer alternate-trajectory details introduced in v2.35 below the
  header: effective stats, level-11 ranges, development plan, gates and perk fit.
- No scoring or projection changes.

## v2.35 — Structural trajectory details
- Moves structural-perk comparison into the expanded Brother Details panel, where
  there is enough space to explain alternatives properly.
- Adds a baseline-vs-alternative comparison table for BestRole, Fit, Readiness and
  Burden, including deltas versus the current trajectory.
- Enriches every shown structural alternative with its winning role's full
  projection, current effective stats, level-11 ranges, development allocation,
  support-pick plan, gates and perk compatibility.
- Keeps the Brother header compact: current BestRole plus a count of alternate
  structural trajectories.
- Clearly separates Current Brother, Alternate Trajectories and Current Archetype
  Details inside the expanded panel.

## v2.34 — Fortified Mind structural projection
- Treats Fortified Mind as a structural projection perk, on the same footing as
  Colossus.
- Applies `BraveryMult ×1.25` after aggregate raw Resolve progression rather than
  multiplying individual future rolls.
- Structural perk discovery is source-driven from exact, unconditional
  `perk_effects.json` core-stat modifiers; no Colossus/Fortified-Mind whitelist
  is required.
- Generalizes BestRole alternatives from a Colossus-only field to structural-perk
  scenarios.
- With current vanilla data, evaluates Colossus, Fortified Mind, and their combined
  scenario when applicable; only scenarios that actually change BestRole are shown.
- Each shown structural scenario gets its own Level-Up Advisor trajectory.
- Adds `docs/TODO.md` for the ongoing stat-impact perk audit.

## v2.33 — UI polish + Colossus level-up trajectory
- Moves recommendation reasons to the lower-right of each recommended stat card.
- Makes `before → after (delta)` the primary display for Fit, Burden, patch picks
  and feasibility, removing the redundant large final value.
- Adds a separate level-up recommendation for the hypothetical Colossus BestRole
  whenever Colossus changes the projected role.
- Makes `Optimized for <role>` more prominent.
- Right-aligns Best Archetype content in Roster brother-detail headers.
- No change to the existing advisor scoring formula.

## v2.32 — Level Up panel behavior
- Lets the Level Up tab use the full report width, matching Roster and Recruits.
- Level Up brother panels now behave like the other report accordions: only one
  can be open at a time.
- Opening a Level Up panel smoothly scrolls it into position.
- Level Up panels no longer auto-open on page load.
- Adds proper `#levelup` tab hash handling alongside `#roster` and `#recruits`.
- No scoring or advisor changes.

## v2.31 — Level Up UX redesign
- Rebuilds the Level Up tab around the decision itself rather than two generic
  stacked boxes.
- Makes the recommended three stat picks the primary visual focus.
- Shows Fit, Burden, patch-pick and feasibility outcomes as a compact before/after
  strip; Burden is explicitly labeled with a downward-good direction.
- Moves the full roll board below the recommendation and highlights the selected
  rolls in context.
- Demotes the runner-up recommendation to a compact secondary row.
- Adds a denser brother header with BestRole, current Fit/Ready/Burden and optional
  Colossus alternate-role context.
- Removes the accumulated legacy v2.19/v2.21/v2.30 Level Up CSS and replaces it
  with one coherent responsive component set.
- No advisor scoring changes.

## v2.30 — Dedicated Level Up tab
- Adds a top-level `Level Up` tab between Roster and Recruits.
- Shows `Roster`, `Level Up`, and `Recruits` counters in the navigation.
- The Level Up tab is disabled and non-clickable when no brother has a pending
  level-up with parsed current rolls.
- A non-zero Level Up counter is visually emphasized so pending decisions are
  hard to miss.
- Moves current rolls and Level-Up Advisor recommendations out of Brother Details
  into the dedicated Level Up workspace.
- Keeps Brother Details focused on roster/status/archetype analysis.
- No scoring or advisor-algorithm changes.

## v2.29 — Full architecture refactor
- Reduces `bb_analyze.py` from ~400 lines to a tiny executable entry point.
- Introduces `bbtool.app` for CLI, config loading, tracing, strategic analysis,
  run output and top-level orchestration.
- Splits the former 1000+ line projection engine into `bbtool.projection`:
  runtime, perks, progression, scoring, uncertainty and planning.
- Keeps `bbtool.engine` as a small compatibility facade for older imports.
- Renames the obsolete `exports.py` helper module to `formatting.py`.
- Adds separate full/fast projection counters to profiling.
- Preserves the existing full and fast projection behavior; no scoring-policy
  change is intended in this release.
- Updates architecture documentation to describe dependency direction and module
  ownership explicitly.

## v2.28 — Repository housekeeping
- Moves `archetypes.json` and `classification.json` into `config/`.
- Resolves default configuration paths relative to `bb_analyze.py`, so launch
  working directory does not matter.
- Moves `ARCHITECTURE.md` and `CHANGELOG.md` into `docs/`; keeps `README.md` at root.
- Removes `analyze.cmd`, which was only a Windows wrapper around `bb_analyze.py`.
- Removes obsolete `VALIDATION.txt`, a v0.2 validation-output snapshot referencing
  old CSV/Markdown output and an old external save.
- Rewrites the stale architecture document to describe the current repository.
- Normalizes the changelog to a single top-level heading.
- No scoring or classification behavior changes.

## v2.27 — Performance / housekeeping
- Makes the alternate Colossus BestRole much more visible in the first table with
  a dedicated `♥ COLOSSUS → role` badge.
- Adds `project_role_fast()` for internal what-if calculations.
- Level-Up Advisor now performs 56 fast evaluations of the current BestRole only,
  instead of a full 9-archetype sweep for every combination.
- Removes CSV files from run output and removes dead CSV export code.
- Full visible archetype calculations remain unchanged.

## v2.26 — Colossus role in overview
- Fixes the overview table showing only the current BestRole even when a different
  `ColossusBestRole` had already been computed.
- The Best Role column now shows the current role plus `↳ Colossus: <role>` when
  the hypothetical Colossus branch diverges.
- Brother Details keeps the existing full `WITH COLOSSUS` metrics block.
- No scoring changes.


## v2.25 — Aggregate Colossus projection + dual BestRole
- Colossus HP is now modeled exactly as Battle Brothers does it:
  `floor(total raw HP × 1.25)`.
- Future HP rolls are summed in raw HP first; the multiplier and floor are
  applied once to the aggregate, never roll-by-roll.
- Allocation, Fit uncertainty, Burden and Burden uncertainty now use the same
  aggregate perk transform.
- While Colossus is still available but not taken, the analyzer also evaluates
  a hypothetical Colossus branch across all archetypes.
- If that branch has a different BestRole, Brother Details shows both roles.
- Once Colossus is taken, or no future perk point can be earned, the alternate
  branch disappears.


## v2.24 — Decompiled perk scanner fix
- Fixes perk effects not being applied in real runs despite working in the synthetic test.
- The vanilla script repository is decompiled and uses signatures such as
  `function onUpdate(this, _properties)` rather than the one-argument form.
- Supports decompiled arithmetic such as
  `_properties.HitpointsMult = _properties.HitpointsMult op42 1.25`.
- Infers perk display names from script stems when `m.Name` references
  `Const.Strings.PerkName.*` instead of a string literal.
- Bumps perk-effect cache format to v2, forcing regeneration of older broken caches.
- Regression target: Colossus must resolve to HP ×1.25 and affect HTML/analytics.

## v2.23 — HTML effective-stat binding
- Binds analytics-layer effective stats into Brother Details.
- Stat chips now show the perk-adjusted value when it differs from the raw save value.
- The raw serialized stat remains visible as `raw N`.
- Fixes Colossus appearing to have no visible HP effect in the HTML even though Fit/Ready/Burden used it.
- Raw roster JSON is unchanged; classification JSON now includes `EffectiveStats`.


## v2.22 — Perk effect registry
- Generates `references/perk_effects.json` from vanilla scripts when absent.
- Scans every vanilla perk script and catalogues core-stat mutations.
- Distinguishes exact permanent from conditional/dynamic stat effects.
- Only unconditional literal numeric `onUpdate` effects are auto-applied.
- Acquired exact modifiers now feed Fit, Readiness, Burden and projections.
- Raw roster stats remain faithful to the save.
- Colossus is the first regression target.
- No Perk Advisor yet.


## v2.21 — Level-Up Advisor
- Evaluates all 56 combinations of 3 current level-up rolls.
- Anchors advice to the brother's current best archetype to avoid role-flapping.
- Objective combines projected Fit gain, Burden reduction, Burden feasibility,
  support/patch picks saved, and roll quality as a tie-breaker.
- Shows recommendation, alternative, and before/after metrics in Brother Details.
- Future rolls remain hidden.

## v2.20 — Pending level-up projection fix
- Fixes projected Fit/Burden dropping when a brother has leveled but has not yet
  spent the pending stat points.
- LevelPoints now count as still-available development rounds through level 11.
- Example: a level-2 brother with one unspent level-up correctly has 10 stat
  allocation rounds remaining, not 9.
- Current Readiness remains based on actually applied stats only.
- Regression target: Einar must not change category merely by opening/holding
  his level-up without spending it.
- No changes to current-roll parsing or future-roll visibility.

## v2.19 — Current level-up rolls
- Parses the eight currently available level-up stat rolls.
- Exposes only the current roll for each stat; future queue entries stay hidden.
- Shows a LEVEL UP AVAILABLE block in the brother panel when points are pending.
- Regression-tested on the supplied Einar before/after level-up saves.

## v2.18 — Ranged core-stat gate correction
- Fixes ranged archetypes being overvalued when mediocre projected RAtk was
  compensated by excellent HP/Fatigue/Resolve.
- Adds an optional point-based `span` mode to smooth role gates. Existing gates
  without `span` retain their previous behavior.
- Crossbow/Gunner and Thrower now require stronger projected RAtk quality.
- Archer keeps the highest RAtk standard and receives the same point-based gate.
- Regression target: Einar (47 base RAtk, 0 stars) must no longer be classified
  as Crossbow/Gunner ahead of his non-ranged options.
- Strong true ranged candidates such as Wilderich and Kalle remain premium.
- No save parsing, recruit parsing, reference generation, or economy changes.

## v2.17 — Structural roster record bounds
- Fixes roster parsing when a serialized brother contains an incidental ASCII
  `human` string inside its own payload before the identity block.
- `parse_roster()` no longer treats the next raw `human` occurrence as the end
  of the current brother.
- Identity parsing is now bounded by the serialized `battleBrother` record and
  requires a valid talent-star block immediately after the identity metadata.
- Strict parsing remains in place: no fallback or guessed identity is added.
- Reproduced against the supplied failing `Leto.sav` (Asbjorn case).

## v2.16 — Recruitment table polish
- Removes the redundant Tryout column; trait visibility now communicates the
  same information directly (`Hidden` means no paid tryout).
- Harmonizes recruit-table column widths with a fixed layout.
- Adds lightweight visual cues:
  - level pills,
  - trait visibility icons,
  - hire-cost and daily-wage symbols,
  - settlement icon in panel headers.
- Keeps the UI compact and readable without changing any recruit data.
- Settlement accordion behavior from v2.15 is unchanged.
- No parsing, reference-generation, economy or roster analytical changes.

## v2.15
- Recruitment UI accordion.
