# Render-only web previews

The `Render-only preview build` workflow turns the approved public JSON fixture
catalog into static interactive reports. It validates the same
`bbtool.reference_analysis.v3` contract as local `--render-only` mode and never
opens a save or invokes references, projection, Fit, classification, cache, or
Level-Up Advisor computation.

## URLs and lifecycle

After GitHub Pages is configured once to deploy from the `gh-pages` branch,
previews are available under the repository Pages base URL:

```text
/pr-123/standard/
/pr-123/level-up/
/pr-123/recruits/
/main/standard/
```

Every push refreshes the same PR path. Merges refresh `main`; closing a PR
removes its complete `pr-<number>` directory. A manual workflow dispatch can
preview a branch, tag, or exact commit under `ref-<normalized-branch>/`.
Before writing, the publisher rechecks the PR's live state and head SHA: a late
run for a closed PR cleans rather than republishes, while a stale run for an
older open-PR head is ignored.
Published pages identify render-only mode, source, exact SHA, fixture scenario,
dataset contract, and generation timestamp.

The maintained catalog is `tests/fixtures/report_previews.json`. A scenario has
a safe URL name, an approved dataset path below `tests/fixtures`, and an initial
report tab. Incompatible, missing, corrupt, or path-escaping inputs fail the
build instead of publishing partial output.

## Security and permissions

The build workflow has read-only repository access and publishes only a
short-lived Actions artifact. A separate workflow, loaded from the default
branch through `workflow_run`, holds the narrow `contents: write` permission
needed to update `gh-pages`; it never executes code from the preview artifact.
Fork pull requests build an inspectable artifact but are not published. The
cleanup path uses `pull_request_target` only to remove the known PR-number
directory and never checks out or executes pull-request code.

The preview workflow is presentation-only and separate from PR correctness CI,
release validation, release ZIPs, coverage, mutation testing, and full-save E2E
work. The generated site contains only rendered public data and the selected
revision's tracked report CSS/JavaScript; it contains no save, FutureRolls,
runtime references, cache, or diagnostic artifacts.

## Full-application previews

`Full application preview build` is a separate, manually triggered workflow.
It accepts a pull-request number, branch, tag, or exact commit plus an approved
fixture identifier. The current allowlist contains `reference-save`, whose
provenance, approval, and SHA-256 are recorded in
`tests/fixtures/full_preview/catalog.json`. Pull-request numbers are resolved to
their exact current head, and fork heads are refused. Branches, tags, and SHAs
must resolve inside this repository.

The analysis job executes the selected revision's normal `bb_analyze.py` entry point
from the approved `.sav`, with either a full recomputation or optional
`--verify-cache --cache-debug`. It validates the resulting public manifest and
JSON contract, renders the interactive HTML, and uploads two short-lived
artifacts: a public-JSON-only dataset and separate diagnostic logs. A second,
isolated job checks out `main`, receives the exact SHA, label, and destination
through immutable job outputs from the pre-execution resolution steps, and
reconstructs the allowlisted publication payload. Selected-revision code cannot
declare or replace the published route or visible revision metadata.
This workflow is deliberately not part of routine PR CI because a cold complete
analysis is comparatively expensive and may prepare runtime references.
The analysis job has a 30-minute hard timeout and records its elapsed time and
public-dataset byte count in the run summary. Packaging and publication each
have a 10-minute timeout. These limits are intentionally well above the
reference run observed while introducing the fixture (12 brothers, 52 recruits,
132 role projections) while still failing a stuck preview with a useful job log.

Publication uses a second default-branch workflow with `contents: write`. It
does not execute selected-revision code or logs. The unprivileged artifact is
restricted to the validated public JSON dataset and carries no deployable
HTML, CSS, or JavaScript. The privileged job loads that dataset through the
trusted contract reader from `main`, independently binds it to the approved
save catalog, and reconstructs every deployable HTML/CSS/JS asset with trusted
default-branch code. Unexpected paths, non-dataset files, FutureRolls, binary,
non-UTF-8, oversized, validation, cache, debug, log, save, and archive files
fail closed. The resulting route is:

```text
/pr-123/full/reference-save/
/ref-branch-name/full/reference-save/
```

Every page visibly records full-application mode, exact commit SHA, approved
fixture ID and safe fingerprint, toolkit/output-contract versions, generation
time, and whether incremental verification ran. The source `.sav` is never
included in either the publication artifact or the deployed site. Preview runs
are retained as Actions artifacts for seven days; published routes are replaced
by later runs for the same destination, and PR routes are removed when the PR
closes through the existing preview cleanup lifecycle.

For a pull-request source, the trusted publisher also creates or updates one
bot comment on that PR. The comment links directly to the report and records the
exact 40-character head SHA and approved fixture ID. Re-running the preview
updates the same marked comment instead of creating duplicates. Before either
publishing or commenting, the workflow verifies that the PR remains open and
that its current head still equals the analyzed SHA; stale runs fail closed.

To validate a PR manually, dispatch `Full application preview build`, enter the
PR number as `source_ref`, keep `reference-save`, and optionally enable cache
verification. Open the link added to the PR after both workflows succeed, then
exercise the Roster, Level Up, Roster Management, and Recruits tabs along with
filters, details, accordions, and links. Missing output, invalid JSON, unsafe or
oversized publication data, analysis errors, stale PR heads, packaging errors,
or publication errors fail the workflow. Diagnostic logs are retained for
seven days separately from the public payload.
