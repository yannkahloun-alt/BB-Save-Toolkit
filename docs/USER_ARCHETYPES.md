# Effective user archetype catalog

`bbtool.app.archetype_catalog` owns user-editable archetype domain semantics.
The tracked `config/archetypes.json` remains immutable base data; no catalog
operation writes it. The effective catalog is constructed in base-file order as:

```text
current shipped base
  + validated sparse user overrides
  - disabled shipped IDs
  + complete custom user definitions in creation/import order
```

Only user intent is persisted through the durable-state substrate in
`archetypes/catalog-state.json`. Records are one of:

- `override`: shipped BuildIdentity, sparse recursive patch, and the exact
  shipped BuildDefinitionHash against which the patch was authored;
- `disabled`: shipped BuildIdentity;
- `custom`: a complete definition with an opaque authoritative BuildIdentity;
- `retired`: a deleted custom ID tombstone, preventing accidental ID reuse.

Display names are never identity. Effective display names remain unique while
the public report-v1 contract still joins by name. Custom creation and
duplication generate a new `custom_<uuid>` identity; duplication never retains
the source ID. Editing a custom definition cannot change its identity.

## Upgrades, reset, and conflicts

A shipped definition with no override is read directly from the current base,
so upgrades appear automatically. Disabled IDs remain disabled across semantic
base updates. An override is applied only when its authored-against definition
hash matches the current shipped definition. A mismatch is a visible catalog
conflict: the application must ask the user to reset or deliberately recreate
the override against the new base. It never silently merges changed semantics.

Reset-override removes the patch while preserving a separate disabled choice;
enable removes the disabled record. A full base reset removes both records and
exposes the current shipped definition. Missing shipped IDs referenced by durable
override/disabled records are also explicit conflicts; no name or definition
similarity migration is attempted.

## Validation and import/export

All mutations validate the complete prospective effective catalog before the
optimistic-revision write. Errors retain deterministic field paths. Invalid
state, duplicate IDs/names, retired-ID reuse, empty effective catalogs, stale
base hashes, and unsupported fields fail without persisting a partial change.

Export uses `bbtool.user-archetypes-export.v1` and contains only user-owned
records. Replace import round-trips that state. Merge import accepts identical
records idempotently and reports any same-kind/same-ID differing record as a
conflict; IDs are never remapped. Local retired-ID tombstones are monotonic and
survive replacement imports, so an older export cannot resurrect a deleted ID
as a different logical build. Explicit import of a
`bb-archetypes-v0.9` legacy object containing an id-less `roles` array is the
supported migration into managed state: each
id-less role receives an opaque ID once, and that ID is then persisted.
Missing, mistyped, unknown, and future schema identifiers are rejected; the
presence of a `roles` field alone never selects legacy migration.

The resulting normalized roles are supplied unchanged to `AnalyzerConfig` and
the transport-independent analysis service. Existing artifact-specific role
fingerprints therefore continue to include exact result-affecting definitions;
BuildIdentity or BuildDefinitionHash alone never validates cached output. The
catalog exposes per-ID definition hashes so downstream dependency declarations
can invalidate the changed build without treating the global durable-state
revision as a universal cache key.
