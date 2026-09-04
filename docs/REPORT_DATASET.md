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
directory. On success it writes a timestamped directory containing the seven
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

## Versions and required files

New analysis runs use `bbtool.reference_analysis.v3`. The loader also accepts
the prior `bbtool.reference_analysis.v2` contract without migration. Version 2
retains its exact seven logical files and all name-based `Role` / `BestRole`
joins. The original `bbtool.reference_analysis.v1` is a frozen six-file
historical boundary: it is not accepted, upgraded, or reinterpreted. In
particular, its names never become BuildIdentity and its `BrotherID` never
becomes durable identity.

The manifest must declare exactly these logical files, each with a relative,
dataset-local `path` and the exact lowercase SHA-256 of its bytes:

| Key | JSON root | Purpose |
| --- | --- | --- |
| `roster` | array | Public brother current state, `BrotherID` joins, and factual `PerkGearFacts` |
| `recruits` | array | Public recruit display state, including exact background identity and exact revealed-trait evidence only after tryout |
| `role_fit` | array | One projection row per brother and archetype |
| `classification` | array | One summary and Advisor payload per brother |
| `archetypes` | object with non-empty `roles` | Displayed archetype definitions |
| `classification_config` | object | Displayed classification thresholds/configuration |
| `analysis_health` | `bbtool.analysis_health.v1` object | Public analysis status, result-warning counts, warning category codes, and separate projection-validation status |
| `presentation` (v3 only) | `bbtool.target_presentation.v1` object | Target UI identities, build metadata, Mechanical Facts, Run Health, Recruitment analysis, provenance and result-local validity |

The first seven payloads remain byte-level and semantic compatibility surfaces
for the existing report renderer. Target UI consumers use `presentation` for
durable joins and must not infer those joins from the legacy display fields.

## Target presentation v1

`bbtool.target_presentation.v1` contains only established semantics:

- exact-or-explicitly-unavailable CampaignIdentity and BrotherIdentity;
- BuildIdentity, BuildDefinitionHash and display name as separate fields;
- current-state `PerkGearFacts` copied coherently from the roster payload;
- the exact public `bbtool.analysis_health.v1` payload;
- Background prior / known-evidence Recruitment results from the versioned
  #110/#111 models, with an explicit unavailable state when required evidence
  is absent or unsupported;
- authoritative intrinsic Company coverage from the completed #128 slice,
  including its own ArtifactSignature;
- source-content and effective-configuration fingerprints;
- exact hashes of all seven component artifacts plus a deterministic
  publication coherence signature; and
- separate result-local dependency signatures for role projection, strategic
  classification and Level Advisor artifacts.

These signatures are result-local #122 evidence. They do not use a global
user-state revision and do not imply that an artifact depends on unrelated
mutable intent. A presentation artifact is accepted only when its bound hashes,
health, build definitions, Brother/recruit relations and coherence signature
match the other files in the same manifest.

The following fields are intentionally absent until their owning semantics are
complete: AssignedBuild (#107), intent-aware Advisor (#108), intended Company
Planning/gap semantics (remaining #128), and Relevant Roster Need (#112). The
payload carries this bounded pending map so absence cannot be mistaken for a
negative result.

The health payload is deliberately summary-only. Debug bundles, diagnostic
samples, incremental manifests, projection-validation artifacts, source saves,
generated runtime references, absolute paths, and hidden `FutureRolls` are not
inputs to the public report contract.

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
- exact health schema, non-negative counts, supported category codes, and
  consistency among health status, category counts, and projection-validation status;
- a full renderer-contract preflight, which exercises every field and type
  consumed by the shared report renderer before an output directory exists.
- for v3, exact presentation-to-artifact hash binding, deterministic coherence
  signature, Campaign/Brother and Build identity shapes, Mechanical Facts and
  Run Health equality, recruit/build joins, and result-local signature shapes.

The server binds to an ephemeral port on `127.0.0.1`, serves only the rendered
page and its two fixed local assets, disables browser caching, and exposes no
arbitrary file path. It has no network dependency.

Missing, corrupt, incompatible, contradictory, or unsafe input raises an
`Invalid render dataset` error naming the relevant file or relation. The
renderer never recalculates missing analysis data to repair an invalid dataset.

The maintained synthetic example in `tests/fixtures/reference_analysis` is the
canonical v3 fixture and can be regenerated with its adjacent `generate.py`.
Approved browser previews and their least-privilege publication lifecycle are
documented in [WEB_PREVIEWS.md](WEB_PREVIEWS.md).
