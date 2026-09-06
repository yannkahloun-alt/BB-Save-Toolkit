# Selected-save watching

`bbtool.app.save_watcher.SaveWatcher` is the filesystem stabilization boundary
for the persisted selected save. The loopback application starts it at process
startup, so an existing selection is restored without changing its durable
revision. Missing, locked, and unreadable files never clear the selected path.

On Windows, the supported user-facing launchers initialize a first-run profile
whose `preferences.json` does not yet exist to:

```text
<Windows Documents>\Battle Brothers\savegames\quicksave.sav
```

`Documents` is resolved through the current user's Windows known-folder setting,
so configured redirection such as OneDrive-backed Documents is respected. The
initial path is persisted even when `quicksave.sav` is not yet present; the
normal `unavailable` state then reports that condition and the watcher can
observe the same path if it appears later. No directory scan, newest-save guess,
or alternative-save fallback is performed.

A present preferences payload is always authoritative, including a persisted
explicit selection and a persisted `selected_save_path = null` after a user
forgets/resets the selection. The first-run default therefore never overwrites
user state and never becomes save, campaign, brother, cache, or continuity
identity.

## Detection and identity

The watcher polls both the selected path and its parent directory. It reopens
the selected pathname on every probe, which detects the game's replace-style
writes as well as in-place modifications. Directory notifications, file
identity, size, and modification time are wake-up and stability evidence only.
SHA-256 of the immutable bytes is the authority for logical content identity.
Consequently duplicate notifications and same-content replacement do not
request another analysis.

A candidate must be readable and have unchanged file identity, size, and mtime
across its read, then produce the same content fingerprint on two consecutive
probes. A missing file, sharing violation, changing read, or different second
fingerprint resets stabilization. Only the newest candidate that completes
this sequence becomes the stable desired snapshot. This proves the contract
without sleep-based tests; production probes are spaced by the bounded watcher
poll interval.

## Freshness and scheduling

The observable watcher states are:

| State | Meaning |
| --- | --- |
| `detected` | Stable changed content is available in notify-only mode |
| `stabilizing` | A change was observed but no new snapshot is accepted yet |
| `queued` | Stable bytes were submitted for automatic refresh |
| `analyzing` | The coordinator is running the desired job |
| `current` | The accepted fingerprint is unchanged / analysis succeeded |
| `unavailable` | Selection is absent, missing, locked, or unreadable |
| `failed` | Analysis of the stable desired snapshot failed |

On the first changed/unavailable observation, the application marks the old
desired generation stale. The active worker is allowed to finish but can no
longer publish. Stable bytes are then submitted to `AnalysisCoordinator`,
which remains the sole owner of duplicate identity coalescing, one-active /
newest-pending scheduling, and stale-result rejection. Notify-only mode keeps
the stable snapshot for an explicit refresh and does not submit automatically.
The existing local API exposes this freshness through followed-save and result
responses; no filesystem or generic state endpoint is added.

## Windows game-write evidence

The implementation covers both in-place writes and temp-file replacement and
models Windows sharing violations explicitly. Repository tests manufacture
both patterns with temporary files. No captured trace of an actual Battle
Brothers save operation (temporary filename, rename sequence, sharing flags,
and maximum quiet interval) is currently stored in the repository. Capturing
that trace on Windows remains desirable to tune the poll interval or require a
longer quiet window; the implementation does not guess a game-specific event
order.
