# External reference sources

Normal cold reference generation uses two external inputs. Their full commit
SHAs and requested URLs are defined once in `REFERENCE_SOURCES` in
`references/update_references.py`. Runtime code requests those immutable objects
directly; it never resolves or falls back to an upstream branch head.

| Source | Upstream | Pinned commit | Previously mutable input | Generated references |
| --- | --- | --- | --- | --- |
| BB-Edit dictionary | `scarglamour/bb-edit` | `bdab5a8216090506a33e8263b8fb112ebf12b361` | `master` dictionary JSON | `dictionary.json` |
| Battle Brothers vanilla scripts | `ninkjin/Battle-Brothers-Scripts` | `162f498ac7c49b4c317bbf54718a595ecef6a65a` | `main` source ZIP | `dictionary.json`, `backgrounds.json`, `perk_effects.json`, `trait_effects.json`, `permanent_injury_effects.json`, and the derived `perk_audit.json` |

The `bbtool.reference_status.v1` runtime payload exposes the configured source
repository, immutable requested revision, requested URL, and relevant generated
reference schemas. When a source is downloaded, its entry in `download_sources`
also records the downloaded byte count and SHA-256.
Existing valid caches remain preferred and usable offline, so a cache-only run has no downloaded-content-digest to report for that run.

## Intentional upgrade workflow

Reference-source upgrades are reviewed repository changes:

1. Choose and review a new upstream commit, then update its full 40-character
   revision constant. `REFERENCE_SOURCES` derives the SHA-addressed URL from
   that single pin definition.
2. Remove only the disposable local generated references that must be rebuilt,
   then run `python references/update_references.py` to regenerate them.
3. Run the deterministic reference tests and the normal repository quality
   gates documented in `docs/TESTING.md`.
4. Inspect the generated-data diff and explain every meaningful change. Do not
   alter analytical semantics just to accommodate upstream drift.
5. Commit the pin change, documentation, tests, and only the generated artifacts
   allowed by current project policy together. Runtime reference caches that the
   repository excludes must remain uncommitted.

If the pinned object is unavailable, generation fails with the source name,
commit SHA, and exact requested URL. Do not substitute `main`, `master`, a tag,
or another newer revision.
