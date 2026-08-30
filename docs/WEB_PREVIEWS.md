# Render-only web previews

The `Render-only preview build` workflow turns the approved public JSON fixture
catalog into static interactive reports. It validates the same
`bbtool.reference_analysis.v1` contract as local `--render-only` mode and never
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
