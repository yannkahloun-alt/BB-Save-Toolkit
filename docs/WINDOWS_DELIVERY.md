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

The reference caches are generated from the repository-pinned immutable source
revisions during packaging and bundled into the application. They remain
untracked/reproducible build inputs; they are not committed to the repository.
An installed normal analysis therefore starts with validated references already
present instead of requiring a first-run reference download.

The installed executable is built as a **windowed** executable. Start Menu and
startup shortcuts therefore do not create a terminal window.

## Runtime and duplicate-instance behavior

`BB-Save-Toolkit.exe` supports these lifecycle commands:

```text
open        start if needed and open the local UI in the default browser
background  start if needed without opening a browser
stop        stop the verified installed process
restart     stop, start, and open the UI
status      exit success only when a toolkit loopback instance is healthy
```

At sign-in, the per-user Startup shortcut invokes `background`.

The launcher owns a Windows per-session mutex and a small bounded port range on
`127.0.0.1`. It prefers the first available port and records only volatile
runtime metadata (`pid`, port, executable path) below the user's temporary
directory. A second launch probes the exact toolkit health contract and reuses
the existing instance instead of binding another port. An unrelated process
occupying one candidate port is skipped. If the recorded PID does not resolve
to the same installed executable, `stop` refuses to terminate it.

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
replacing binaries the installer asks the existing launcher to stop. Durable
state is not under `{app}` and therefore survives the replacement. State schema
migration remains owned by `bbtool.app.user_state`; packaging must never edit
feature files directly.

Interactive uninstall asks whether to keep user-owned state and defaults to
**keep**. Silent uninstall also keeps it. Automated/explicit removal may pass
`/DELETEUSERDATA` to the uninstaller to remove
`%LOCALAPPDATA%\BB-Save-Toolkit\` after application files are removed. This
makes binary removal and user-data deletion separate choices.

## Building an installer

Install the packaging dependency and Inno Setup 6, then run:

```powershell
python -m pip install -r packaging\windows\requirements.txt
.\tools\build_windows_installer.ps1 -Version 3.89.0
```

The build script validates/generates all required reference caches, invokes the
PyInstaller spec, locates `ISCC.exe`, and writes:

```text
dist\windows\BB-Save-Toolkit-<version>-setup.exe
```

For a future signed release, supply the repository-approved Inno Setup signing
command through `-SignCommand`. No signing credential or certificate is stored
in this repository.

## Validation

`.github/workflows/windows-installer.yml` runs for packaging changes and may
also be dispatched manually. It builds the installer, installs it into a clean
Windows runner profile, and proves the ticket lifecycle against the deterministic
`tests/fixtures/full_preview/reference-save.sav` fixture:

- per-user install and startup shortcut;
- healthy loopback startup;
- duplicate launch reuses the same PID;
- save selection through the real bounded API;
- successful background analysis using the installed runtime;
- restart retains the selected-save preference;
- installer repair/update retains the preference;
- default uninstall preserves durable user state;
- explicit `/DELETEUSERDATA` uninstall removes it.

The repository's normal `tests`, `ruff`, and `pyflakes` checks remain the stable
merge guards. The Windows-installer job is additional ticket-specific evidence;
it does not redefine those stable identities.
