# Public report dataset contract

The interactive report is generated from adjacent public JSON under the
versioned contract below. `--render-only` repackages a compatible dataset, and
`--serve-report` validates and displays either a generated run directory or an
existing dataset. These paths are presentation-only: they never read a
Battle Brothers save and never run reference preparation, projection, Fit,
classification, incremental-cache, or Level-Up Advisor computation.

## Usage

Pass either the dataset directory or its manifest:

```powershell
python .\bb_analyze.py --render-only .\tests\fixtures\reference_analysis
python .\bb_analyze.py --render-only .\tests\fixtures\reference_analysis\manifest.json --open-report
python .\bb_analyze.py --serve-report .\output\my-run --open-report
```

`--out` selects the destination. Analysis-only switches (`--no-projection`,
`--full-recompute`, `--verify-cache`, and `--cache-debug`) are rejected so the
execution mode cannot be mistaken for a save analysis.

The render-only command validates every input before creating its output
directory. On success it writes a timestamped directory containing the six
canonical public JSON files, `manifest.json`, a data-free report HTML shell,
`report.css`, and `report.js`, plus a ZIP of that directory. Full analysis uses
the identical contract. The local server reads and validates the JSON, then
uses the shared renderer and assets to produce the complete interactive page.

Browsers block reliable adjacent JSON loading from `file://`; direct HTML
opening is therefore not the supported data-loading path. It shows a clear
launch instruction and contains no roster, recruit, Fit, classification, or
Advisor payload. `--open-report` starts the loopback server automatically.
After moving a complete directory or extracting its ZIP, use `--serve-report`
as shown above. Opening from inside a ZIP is unsupported.

## Version and required files

The accepted manifest schema is exactly `bbtool.reference_analysis.v1`.
Compatibility is explicit: another or missing schema version is rejected
rather than guessed or migrated silently.

The manifest must declare exactly these logical files, each with a relative,
dataset-local `path` and the exact lowercase SHA-256 of its bytes:

| Key | JSON root | Purpose |
| --- | --- | --- |
| `roster` | array | Public brother current state, `BrotherID` joins, and factual `PerkGearFacts` |
| `recruits` | array | Public recruit display state |
| `role_fit` | array | One projection row per brother and archetype |
| `classification` | array | One summary and Advisor payload per brother |
| `archetypes` | object with non-empty `roles` | Displayed archetype definitions |
| `classification_config` | object | Displayed classification thresholds/configuration |

Debug bundles, incremental manifests, projection-validation artifacts, source
saves, generated runtime references, and hidden `FutureRolls` are not inputs to
the public report contract.

## Validation and failures

Before rendering, the loader verifies:

- manifest schema, exact file set, safe relative paths, existence, SHA-256, and
  valid UTF-8 JSON;
- expected JSON root types and required archetype roles;
- unique `BrotherID` values consistent with `HumanOffset`;
- exactly one role-fit row per brother/archetype pair;
- exactly one classification row per brother;
- all brother and role joins, including `BestRole`;
- absence of hidden `FutureRolls` from every public input.
- a full renderer-contract preflight, which exercises every field and type
  consumed by the shared report renderer before an output directory exists.

The server binds to an ephemeral port on `127.0.0.1`, serves only the rendered
page and its two fixed local assets, disables browser caching, and exposes no
arbitrary file path. It has no network dependency.

Missing, corrupt, incompatible, contradictory, or unsafe input raises an
`Invalid render dataset` error naming the relevant file or relation. The
renderer never recalculates missing analysis data to repair an invalid dataset.

The maintained synthetic example in `tests/fixtures/reference_analysis` is the
canonical v1 fixture and can be regenerated with its adjacent `generate.py`.
Approved browser previews and their least-privilege publication lifecycle are
documented in [WEB_PREVIEWS.md](WEB_PREVIEWS.md).
