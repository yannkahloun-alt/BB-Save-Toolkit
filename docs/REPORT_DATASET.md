# Public report dataset contract

`--render-only` generates the normal interactive HTML report from public JSON
that was produced previously. This path is presentation-only: it never reads a
Battle Brothers save and never runs reference preparation, projection, Fit,
classification, incremental-cache, or Level-Up Advisor computation.

## Usage

Pass either the dataset directory or its manifest:

```powershell
python .\bb_analyze.py --render-only .\tests\fixtures\reference_analysis
python .\bb_analyze.py --render-only .\tests\fixtures\reference_analysis\manifest.json --open-report
```

`--out` selects the destination. Analysis-only switches (`--no-projection`,
`--full-recompute`, `--verify-cache`, and `--cache-debug`) are rejected so the
execution mode cannot be mistaken for a save analysis.

The command validates every input before creating its output directory. On
success it writes a timestamped directory containing the six public JSON
files, `manifest.json`, `report.html`, `report.css`, and `report.js`, plus a ZIP
of that directory. The same renderer and assets are used by full and
presentation-only runs. Opening a report directly inside a ZIP is unsupported;
extract the ZIP first.

## Version and required files

The accepted manifest schema is exactly `bbtool.reference_analysis.v1`.
Compatibility is explicit: another or missing schema version is rejected
rather than guessed or migrated silently.

The manifest must declare exactly these logical files, each with a relative,
dataset-local `path` and the exact lowercase SHA-256 of its bytes:

| Key | JSON root | Purpose |
| --- | --- | --- |
| `roster` | array | Public brother display state and `BrotherID` joins |
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

Missing, corrupt, incompatible, contradictory, or unsafe input raises an
`Invalid render dataset` error naming the relevant file or relation. The
renderer never recalculates missing analysis data to repair an invalid dataset.

The maintained synthetic example in `tests/fixtures/reference_analysis` is the
canonical v1 fixture and can be regenerated with its adjacent `generate.py`.
