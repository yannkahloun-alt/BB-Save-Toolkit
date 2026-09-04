# Durable per-user application state

`bbtool.app.user_state` is the persistence authority for application-owned
mutable state. Generated reports, run archives, incremental manifests,
reference caches, and source-controlled configuration are not durable state.

## Location and layout

`resolve_user_state_root()` chooses the OS per-user application-data location:

- Windows: `%LOCALAPPDATA%\BB-Save-Toolkit\`
- macOS: `~/Library/Application Support/BB-Save-Toolkit/`
- other platforms: `$XDG_DATA_HOME/BB-Save-Toolkit/`, falling back to
  `~/.local/share/BB-Save-Toolkit/`

The resolver accepts an explicit override. Tests and embedded callers must use
that injection point and must not redirect generated output into this root.

The v1 bounded layout is:

```text
UserStateRoot/
  metadata.json
  preferences.json
  last-success.json
  archetypes/catalog-state.json
```

Every file declares a schema, integer schema version, and monotonic revision.
A small redundantly mirrored sibling revision high-watermark prevents a token
from being reused when the primary JSON is corrupt or a write was interrupted
after reserving its next revision. Ordinary mutation rejects corrupt or
disagreeing copies. Explicit recovery operations can repair from one valid
copy; loss of both copies fails conservatively.
Preferences contain the selected-save path hint and auto-refresh preference.
Last-success state contains source/config fingerprints and source/completion
timestamps. The archetype file is only a versioned catalog container; #96 owns
custom/override semantics and validation. Paths are preferences/provenance, not
stable domain identity. Downstream persistent build references must use the
BuildIdentity contract in `docs/BUILD_IDENTITY.md`.

## Writes, concurrency, and recovery

A feature mutation takes an exclusive OS file lock, validates the on-disk
revision against the caller's expected revision, validates the complete typed
replacement, writes and fsyncs a sibling temporary file, then atomically
replaces the feature file. Canonical sorted UTF-8 JSON makes serialization
stable. A revision mismatch is an explicit conflict; there is no silent
last-writer-wins fallback. If locking is unavailable or times out, the write
fails.

Before replacement, the previous valid bytes are atomically copied to the
feature's `.bak` file. An interrupted replacement therefore leaves the old
file valid. Malformed state, an unsupported future version, or a failed/missing
migration is a visible error and is never interpreted as first-run state.
`recover_from_backup()` is an explicit, feature-scoped recovery action; loading
never silently discards or resets state.

Migrations are feature-local, explicit one-version steps. They run in memory,
the final payload is validated, the pre-migration bytes are backed up, and only
then is the file atomically replaced. A missing/failing migration leaves the
original bytes untouched. Future schemas are rejected for both reads and
writes; downgrade guesses are unsupported.

## Lifecycle boundary

Back up the complete `UserStateRoot` to preserve all non-reproducible toolkit
state. `backup()` copies the complete root except volatile lock/temp files;
it first rejects degraded or revision-inconsistent recognized features so the
result cannot silently masquerade as a valid portable backup.
`restore()` validates all recognized source files before replacing any of them
and applies their explicit migrations in memory before replacing any of them.
It preserves additional bounded domain files for forward extensibility.
Restored content receives a new local revision, so historical/cross-machine
revision values cannot admit a stale writer; the pre-restore local payload is
the recovery backup.

Restore and all-state reset preflight every recognized payload and revision
copy before changing feature content. Their commit phase remains a sequence of
feature-atomic replacements rather than an unsupported cross-file transaction.
An operating-system write failure is visible and may leave a completed prefix;
each replaced feature retains its pre-operation `.bak` for explicit recovery.
Unavailable selected-save paths after moving machines require re-selection but
do not invalidate identity-bearing domain data.

Feature reset and all-state reset are explicit destructive operations. They
keep recovery backups and persist empty revision tombstones so a writer that
predates the reset cannot resurrect stale data. All-state reset also removes
future bounded domain payloads under `UserStateRoot` while retaining sibling
recovery backups. Cache clearing, output
deletion/retention, analysis reruns,
updates, and rendering never call them. Updates retain this schema and migrate
explicitly when needed. Uninstall also retains `UserStateRoot` unless a user
separately chooses to remove application data.

Generated report/debug JSON is derived state and is never persistence
authority. Complete user state is not copied to diagnostics or public reports.
