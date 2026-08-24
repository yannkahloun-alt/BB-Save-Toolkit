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

Generated caches are intentionally NOT part of release ZIPs. On the first run,
bb_analyze.py -> ensure_references() downloads the vanilla script archive once
and builds every missing cache. Subsequent runs reuse them.

perk_effects.json IS REQUIRED for owned-perk effective combat stats. It is
generated, not optional. The effective-stat layer fails loudly if called
directly without this cache instead of silently ignoring owned perk effects.

perk_audit.json reconciles every perk script found in the downloaded vanilla
source with config/perk_model.json. Any source perk not yet classified appears
under its `unreviewed` list.

DESCRIPTION CACHE
- descriptions.json is currently a best-effort UI cache. Missing descriptions
  simply mean no tooltip; they do not affect analysis.
