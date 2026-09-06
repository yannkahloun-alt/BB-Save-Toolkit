# Windows delivery

## Product boundary

Issue #101 packages the existing local-first application for **Windows 10 and
Windows 11 x64**. The package does not change analytical semantics, save
identity, durable user-state schemas, or the loopback API. It only supplies an
installed runtime and lifecycle around the existing `127.0.0.1` application.

The initial distribution channel is a directly downloadable installer attached
to a GitHub Release. The initial installer is allowed to be unsigned because no
repository-authoritative Authenticode certificate is available. The build
script accepts an optional signing command so signing can be added later without
changing the installation/state contract.

Starting with v3.89, the installer is the primary player-facing release asset.
The verified tracked-file ZIP may still be published as a secondary source/archive
asset, but it is not the recommended Windows installation path.

Updates are explicit and user-initiated: download and run a newer installer.
There is no silent updater and normal application startup performs no mandatory
network version check.

## Packaging architecture

The Windows package uses:

1. **PyInstaller one-directory mode** to bundle Python 3.12, application code,
   frontend assets, configuration, and generated immutable reference caches;
2. **Inno Setup 6** for a per-user installer under
   `%LOCALAPPDATA%\Programs\BB-Save-Toolkit\`;
3. the existing durable-state root at
   `%LOCALAPPDATA%\BB-Save-Toolkit\`, which remains outside the installation
   directory and is preserved across repair/update by design.

Before packaging, the build removes the generated runtime-cache paths and
regenerates every required cache from the repository-pinned immutable source
revisions. It therefore does not trust or package a pre-existing developer,
worktree, bootstrap, or legacy tracked generated cache merely because its schema
looks valid. PyInstaller then bundles the newly generated caches into the
application. An installed normal analysis therefore starts with complete,
validated references already present instead of requiring a first-run reference
download.

The installed executable is built as a **windowed** executable. Start Menu and
startup shortcuts therefore do not create a terminal window.

## Runtime and duplicate-instance behavior

On a clean start the documented local URL is:

```text
http://127.0.0.1:41571/
```

The launcher prefers port `41571`. If another process already owns that port it
tries `41572` through `41579` in order; the Open shortcut discovers and opens
the actual healthy toolkit origin, so users do not need to discover a fallback
port manually.

`BB-Save-Toolkit.exe` supports these lifecycle commands:

```text
open        start if needed and open the local UI in the default browser
background  start if needed without opening a browser
stop        stop the verified installed process
restart     stop, start, and open the UI
status      exit success only when a toolkit loopback instance is healthy
```

At sign-in, the per-user Startup shortcut invokes `background`.

### First-run save selection

When the installed application starts with no existing `preferences.json`, it
initializes the selected save to:

```text
<Windows Documents>\Battle Brothers\savegames\quicksave.sav
```

The application resolves the current user's Windows **Documents known folder**,
so normal Windows folder redirection is respected. If Documents is redirected
to OneDrive, the default naturally follows that redirected location; no username
or OneDrive root is hard-coded into the package.

The default is only first-run convenience. A persisted selected save always
wins, and an explicit user selection remains authoritative across restarts. An
explicitly persisted no-selection state is also respected and is not silently
replaced on a later launch. If the default quicksave is missing or unreadable,
the application keeps that path and reports the normal unavailable state; it
does not scan for another save or choose a newest save implicitly.

The selected path remains preference/provenance only. It is not CampaignIdentity,
BrotherIdentity, snapshot identity, or an incremental-cache identity input.

The launcher owns a Windows per-session mutex and a small bounded port range on
`127.0.0.1`. It prefers the first available port and records only volatile
runtime metadata (`pid`, port, executable path) below the user's temporary
directory. A second launch probes the exact toolkit health contract and reuses
the existing instance instead of binding another port. An unrelated process
occupying one candidate port is skipped. If the recorded PID does not resolve
to the same installed executable, `stop` refuses to terminate it. If a healthy
toolkit origin exists but the volatile runtime record is missing or unusable,
`stop` also fails closed rather than guessing which process to terminate.

The volatile launcher log contains only timestamps, lifecycle events, PID/port,
and bounded error text. It never logs save bytes, selected-save content, or
complete durable state.

## Install, update, repair, and uninstall

The installer is per-user and requires no elevation. It supports Windows 10+
x64, installs immutable application files separately from durable state, and
creates:

- Start Menu shortcuts for Open, Restart, and Stop;
- a per-user Startup shortcut (selected by default) for automatic startup.

Running the same or a newer installer is the **repair/update** operation. Before
replacing binaries the installer asks the existing launcher to stop. If the
launcher cannot verify and stop a healthy existing instance, repair/update
aborts instead of replacing files underneath a running process. Durable state
is not under `{app}` and therefore survives the replacement. State schema
migration remains owned by `bbtool.app.user_state`; packaging must never edit
feature files directly.

Uninstall runs the same verified stop guard before removing application files;
it aborts if a healthy toolkit instance cannot be safely identified and stopped.
Interactive uninstall then asks whether to keep user-owned state and defaults to
**keep**. Silent uninstall also keeps it. Automated/explicit removal may pass
`/DELETEUSERDATA` to the uninstaller to remove
`%LOCALAPPDATA%\BB-Save-Toolkit\` after application files are removed. This
makes binary removal and user-data deletion separate choices.

## Building an installer

Install the packaging dependency and Inno Setup 6, then run:

```powershell
python -m pip install -r packaging\windows\requirements.txt
.\tools\build_windows_installer.ps1 -Version 3.89
```

The build script cleanly regenerates all required reference caches, invokes the
PyInstaller spec, locates `ISCC.exe`, and writes:

```text
dist\windows\BB-Save-Toolkit-<version>-setup.exe
```

For the v3.89 release candidate the expected filename is:

```text
dist\windows\BB-Save-Toolkit-3.89-setup.exe
```

For a future signed release, supply the repository-approved Inno Setup signing
command through `-SignCommand`. No signing credential or certificate is stored
in this repository.

## Validation

`.github/workflows/windows-installer.yml` runs for packaging changes and may
also be dispatched manually. It builds the installer and installs it into a
clean Windows runner profile.

The installed-runtime smoke creates a deterministic **synthetic structural
`.sav`** in the runner's temporary directory using the same minimal byte layout
covered by the parser regression tests: one brother and no recruit records. It
also reduces the effective catalog to one durable custom build. This is
intentional: the smoke must prove the installed parser -> worker -> analysis
service -> publication path, not duplicate the comparatively expensive approved
real-save full-application preview workload. The latter remains covered by the
separate full-preview workflow and its approved real fixture.

The installer smoke proves:

- per-user install and startup shortcut;
- healthy loopback startup;
- duplicate launch reuses the same PID;
- synthetic `.sav` selection through the real bounded API;
- successful background analysis and result publication using the installed
  runtime, bundled references, real parser, worker process, and analysis service;
- durable custom-archetype state plus selected-save preference survive restart;
- installer repair/update preserves that durable state;
- default uninstall preserves durable user state;
- explicit `/DELETEUSERDATA` uninstall removes it.

The repository's normal `tests`, `ruff`, and `pyflakes` checks remain the stable
merge guards. The Windows-installer job is additional ticket-specific evidence;
it does not redefine those stable identities.

For a public release, installer validation and the repository's separate release
validation must both be bound to the exact release candidate before publication.
The validated installer executable is attached to the GitHub Release as the
primary Windows asset; downloading a workflow artifact alone is not publication.
