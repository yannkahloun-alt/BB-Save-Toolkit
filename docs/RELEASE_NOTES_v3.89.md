# Battle Brothers Save Toolkit v3.89

v3.89 is the local-first application release. It turns the post-v3.88 analysis engine into a persistent Windows application with the validated Target UI, durable player intent, recruitment/company planning, and an installed-runtime delivery path while preserving the natural-stat level-11 Fit model.

## Highlights

- **Windows application:** a per-user Windows 10/11 x64 installer packages the loopback-only local application, bundled runtime/reference data, lifecycle shortcuts, single-instance startup, repair/update behavior, and state-preserving uninstall defaults.
- **Target UI:** the local application now provides the Company, Level Up, and Recruitment workspaces plus Brother drill-down, responsive navigation, reload-safe state, freshness/health indicators, and direct build inspection.
- **Durable player intent:** stable BuildIdentity, exact native CampaignIdentity/BrotherIdentity, persistent AssignedBuild state, and versioned user-state storage make explicit build assignments survive restarts without redefining intrinsic Best Fit.
- **Company and recruitment planning:** intrinsic Company coverage, intent-aware holder/availability evidence, Background × Archetype priors, tryout-known candidate estimates, and Relevant Roster Need provide roster context without inventing hidden information.
- **Local-app reliability:** background analysis coordination, safe selected-save watching, typed loopback APIs, optimistic state revisions, migration/recovery support, pinned reference sources, Analysis Health, and integrated browser/privacy quality gates harden the application boundary.

## Windows application

The recommended player download is:

```text
BB-Save-Toolkit-3.89-setup.exe
```

The installer is per-user and installs under `%LOCALAPPDATA%\Programs\BB-Save-Toolkit\`. Durable application state lives separately under `%LOCALAPPDATA%\BB-Save-Toolkit\` and is preserved across normal repair/update and default uninstall flows.

The application serves only on IPv4 loopback (`127.0.0.1`) and opens the UI in the user's browser; there is no hosted analysis backend. Start Menu shortcuts provide Open, Restart, and Stop, and the optional Startup shortcut starts the application in the background at sign-in.

On a first run with no persisted save preference, v3.89 resolves the current Windows user's Documents known folder and initializes the selected save to:

```text
<Windows Documents>\Battle Brothers\savegames\quicksave.sav
```

Windows folder redirection, including OneDrive-backed Documents, is respected. If that quicksave is missing or unavailable, the application reports the normal unavailable state; it does not scan for or silently choose a different save. Any explicit later selection remains authoritative.

The initial installer may be unsigned because the repository has no approved Authenticode certificate. Windows may therefore show its normal publisher/reputation warning for a directly downloaded installer.

## Target UI

### Company and Brother

- Company presents roster-level Fit and planning context from the same analysis result used by the rest of the application.
- Brother drill-down separates intrinsic Best Fit from Assigned Build intent and exposes current equipment plus supported mechanical facts without feeding those presentation facts back into Fit.
- Build inspection uses durable BuildIdentity rather than display-name identity.

### Level Up

- Level-Up Advisor remains anchored to the shared trajectory/Fit engine.
- A valid Assigned Build becomes the Advisor anchor; intrinsic Best Fit is still reported independently.
- Primary and Runner-up recommendations carry backend-computed consequences for Assigned Build and Best Fit when those roles differ, with Conditional Branch represented separately.

### Recruitment

- Recruitment exposes the intrinsic Background × Archetype prior and the separately versioned candidate estimate conditioned only on supported known tryout evidence.
- Relevant Roster Need intersects recruitment evidence with current Company need instead of turning roster preference into intrinsic candidate quality.
- The workspace supports shortlist/comparison flows while keeping unknown evidence explicit.

## Identity, state, and planning

v3.89 completes the persistent local-application identity stack:

- shipped archetypes carry immutable BuildIdentity values and definition hashes;
- CampaignIdentity comes from the exact native serialized CampaignID;
- BrotherIdentity combines that campaign identity with the exact native container entity token for the brother;
- AssignedBuild stores campaign-global current player intent using those identities and the acknowledged build definition hash;
- versioned per-user state uses bounded feature files, file locking, optimistic revisions, atomic replacement, explicit migrations, recovery backups, and conservative reset/restore behavior.

These additions do **not** make filenames, save paths, brother names, HumanOffset, BestRole, or build display names durable identity.

Company planning now has distinct intrinsic and intent-aware artifacts. Assignment state can expose holders, free/contested availability, mismatch evidence, fragility, and structured need bases, but it does not rewrite intrinsic projection, Fit, BestRole, or recruitment potential.

## Reliability, observability, and privacy

- External reference inputs are pinned to full immutable upstream commit SHAs.
- The local API is loopback-only and uses typed operations plus host/origin/session protections for mutation requests.
- The selected-save watcher stabilizes replace-style and in-place writes, uses immutable content fingerprints as logical identity, and never clears a selection simply because a file is temporarily missing or locked.
- Analysis Health exposes bounded result-quality status without leaking diagnostic samples, save contents, paths, or hidden future rolls into the public report contract.
- Perk/gear mechanical facts are derived for display as current-state mechanics and remain outside projection/Fit inputs.
- Performance diagnostics and artifact dependency signatures are persisted for reproducibility and fine-grained invalidation.
- Integrated local-web quality gates exercise the production frontend/API boundary in addition to the repository's normal Python checks.

## Compatibility and analytical semantics

The central analytical contract remains level-11 natural-stat Fit to configured archetypes. Assigned Build is player intent, not a classifier: it does not change intrinsic projections, Fit, BestRole, Alternatives, or recruit intrinsic potential. Hidden serialized FutureRolls remain excluded from normal projection and Advisor decisions.

v3.89 does not introduce a hosted service, AI coaching, arbitrary save discovery, newest-save guessing, or the blocked future research items that remain outside the completed local-first milestone.

## Release artifacts

The GitHub Release is expected to publish:

1. `BB-Save-Toolkit-3.89-setup.exe` — primary Windows application installer.
2. `BB-Save-Toolkit-v3.89.zip` — secondary verified tracked-file source archive.

Both artifacts must be built and validated from the exact release commit before publication.
