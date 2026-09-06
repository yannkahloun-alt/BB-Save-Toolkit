# BB Save Toolkit v3.89.2

v3.89.2 is a focused Windows/local-app hotfix built on v3.89.1.

## What changed

- **Repair/update no longer depends on a bootable previous launcher when the app is not running.** The installer now checks the BB Save Toolkit application mutex before invoking the previous `stop` lifecycle command. A genuinely running instance still follows the verified safe-stop path.
- **The Windows app can export one coherent debug evidence ZIP after analysis.** `Export debug JSON` includes CLI-equivalent roster/Fit/classification/Target/validation evidence together with the exact backend read models consumed by Company, Level Up, Recruitment, shell/freshness, followed-save, analysis-result, and archetype UI surfaces.
- **Unavailable/unknown UI states are triageable.** `diagnostic-inventory.json` records explicit Unknown/Unavailable/degraded/warning/reason evidence with stable JSON paths so real-campaign gaps can be turned into focused follow-up tickets.
- **Debug sharing is deliberately bounded.** The export is generation-bound and session-protected, never includes save bytes, redacts the selected-save path and toolkit user-state root, and refuses to return a mixed-generation archive if a newer analysis publishes during capture.

## Analytical behavior

The core level-11 natural-stat Fit model, classification, Level-Up Advisor, AssignedBuild, Company planning, identity/cache semantics, and the v3.89.1 production disablement of the unvalidated Recruitment Background × Archetype prior are unchanged by this hotfix.

## Player workflow

Install `BB-Save-Toolkit-3.89.2-setup.exe`, run an analysis, then use **Export debug JSON**. The resulting ZIP can be shared for algorithm/UI triage without sharing the `.sav` itself.
