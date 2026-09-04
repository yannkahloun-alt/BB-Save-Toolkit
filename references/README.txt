Battle Brothers reference data
================================

SHIPPED STATIC FILES
- dictionary_core.json
  Stable bootstrap/save-ID dictionary.
- perk_catalog.json
  Offline catalog of the standard/save-visible vanilla perks and their
  BestRole review status.
- update_references.py
  Reference/cache generator.

GENERATED RUNTIME CACHES
- dictionary.json
- backgrounds.json
- perk_effects.json
- perk_audit.json

backgrounds.json uses bbtool.backgrounds.v2. In addition to independently
resolved economy fields it carries exact static level-1 PotentialProfile inputs
for the intrinsic Background x Archetype prior. Base ranges and background
offset/talent rules are source-derived through explicit inheritance or an exact
parent-background `create()` constructor call; dynamic/incomplete profiles and scripts
that directly mutate actor talents are omitted explicitly with a
PotentialUnsupportedReason while their reference entries remain available.

Generated caches are intentionally NOT part of release ZIPs. On the first run,
bb_analyze.py -> ensure_references() downloads the vanilla script archive once
and builds every missing cache. Subsequent runs reuse them.

BACKGROUND GENERATION COUNTERS
The background summary reports non-overlapping origin categories separately
for HiringCost and DailyCost: local, inherited, or unresolved. Each field's
three categories total the decoded scripts that completed inheritance
resolution. Script scan counters separately report decode and inheritance
resolution failures, so those totals reconcile with all scanned scripts.
Scripts with a missing parent or an inheritance cycle are counted as resolution
failures and excluded from generated entries and economy-field origin totals.
Explicit and inferred background IDs are a separate dimension and may overlap
the economy-field categories; they total the scripts that completed resolution.
Economy use requires both economy fields. Potential use is independent and
requires an exact PotentialProfile; neither capability gates retention of the
other in the generated reference.
The end-of-run health summary separately reports unknown backgrounds actually
encountered among the current save's brothers and recruits.

perk_effects.json IS REQUIRED for owned-perk effective combat stats. It is
generated, not optional. The effective-stat layer fails loudly if called
directly without this cache instead of silently ignoring owned perk effects.

perk_audit.json reconciles every perk script found in the downloaded vanilla
source with config/perk_model.json. Any source perk not yet classified appears
under its `unreviewed` list.

DESCRIPTION CACHE
- descriptions.json is currently a best-effort UI cache. Missing descriptions
  simply mean no tooltip; they do not affect analysis.
