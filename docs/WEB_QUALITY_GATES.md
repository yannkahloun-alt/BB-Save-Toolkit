# Local web quality gates

Issue #102 is the cross-layer confidence gate for the local application.  It does
not introduce a second analysis engine or browser-owned analytical formulas.
The browser consumes typed read models produced from the authoritative
`LocalApplication` / analysis-service pipeline.

## Deterministic gate matrix

The required lifecycle is intentionally covered by a small set of complementary
gates plus one installed-runtime end-to-end fixture:

| Risk | Authoritative automated coverage |
| --- | --- |
| CLI and application-service analytical equivalence | `tests/unit/test_analysis_service.py::test_cli_request_and_direct_service_have_equivalent_public_results` |
| Manual and automatic refresh describe the same analytical generation for identical bytes/config/state | `tests/integration/test_web_quality_gates.py::test_manual_and_automatic_refresh_build_the_same_analysis_generation` |
| Incremental output must equal independent full recomputation | service `verify_cache` failure gate plus the existing incremental/full-recompute regression suites; semantic disagreement is `cache_verification_failed`, never silently reused |
| Save modification/replacement/locking/deletion/restoration | `tests/unit/test_save_watcher.py`, including same-content replacement, partial writes, locked/missing/restored paths, and stale manual-refresh rejection |
| Multiple changes and out-of-order worker completion | `tests/unit/test_analysis_coordinator.py`, including newest-only publication, stale completion rejection, crash recovery, cancellation, and supersession |
| Archetype edit/reset/disable/custom/import/invalid data | archetype catalog and local-API unit suites, with revision-checked mutation and stale-publication invalidation |
| Corrupt state, migration failure, restart, backup/recovery | `tests/unit/test_user_state.py`; recovery is feature-scoped and revisions remain monotonic |
| Successful durable intent write followed by refresh failure | `tests/integration/test_web_quality_gates.py::test_failed_post_write_refresh_preserves_durable_player_intent` |
| Mutation origin/capability/revision checks and bounded request shapes | `tests/unit/test_local_application_api.py` |
| Least-privilege browser projections | Company/Brother, Level Up, Recruitment, shell/API tests; target read models strip cache/provenance hashes and the shell omits filesystem paths |
| Production browser rendering with no external web dependency | `tests/ui/test_local_app_production_bundle_browser.py` and the static-shell local-only assertions |
| Installed runtime through displayed Company report, duplicate start, real worker analysis, restart/update/uninstall retention | `tools/smoke_windows_installer.ps1`, exercised by `.github/workflows/windows-installer.yml` |

The Windows installer smoke uses a generated deterministic synthetic `.sav`,
runs the installed executable through parser -> worker -> analysis service ->
publication/read-model, and then launches a headless installed Chromium browser
against the same loopback origin.  Its DOM assertion requires the synthetic
brother and the sole effective smoke archetype to appear in the shipped Company
surface before lifecycle testing continues.  This is the explicit installed
runtime -> displayed report gate.  The production browser suite separately
exercises richer HTML/CSS/JavaScript interactions against deterministic endpoint
payloads.  Neither gate reimplements parser, projection, Fit, Advisor, or
recruitment analysis in the browser.

## Freshness and diagnostics contract

A current or stale publication is always identified by the authoritative source
and configuration fingerprints carried by the application result.  Save watcher
state provides the trigger/reason vocabulary (`selected_save_changed`, content
change, stabilizing, unavailable, refresh available, and analysis progress).
Worker failures remain structured job errors.  A failed refresh never promotes a
stale generation and never rolls back a durable user-state write that already
succeeded.

For supportability, browser-facing state exposes bounded status/reason/error
codes rather than raw save contents or cache manifests.  Static application
assets are local, normal browser operation requires no external network, and
mutation requests require exact loopback Host/Origin, the per-session capability,
JSON content type, bounded payloads, and optimistic state revisions.

## Fixture and privacy boundary

Synthetic filesystem tests reproduce same-content replacement, partial writes,
sharing/permission failures, deletion, and restoration, so issue #102 does not
need an approved captured real-save sequence.  Real `.sav` files remain local-only
manual evidence unless separately approved with provenance.

Generated runtime reference caches are not test fixtures and must not be
committed.  Browser read models must not expose hidden rolls, raw save bytes,
cache/provenance hashes, or unrelated durable state.  The followed-save control
surface may identify the explicitly selected local save as required to manage
that selection; presentation shell/read models remain least-privilege.

## CI ownership

Routine deterministic pytest, Ruff, and Pyflakes validation remains owned by the
repository's required pull-request checks.  The Windows installer workflow owns
its Windows-only packaging/lifecycle and installed-display smoke.  Browser tests
remain deterministic, local-only, and network-free; any environment-specific
real-save smoke is optional manual evidence and is never a substitute for the
required exact-head CI gates.
