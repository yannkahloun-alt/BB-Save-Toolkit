# Perk/gear mechanical facts

`PerkGearFacts` is an additive list on each public roster brother. Entries are
emitted only for owned perks whose current mechanics are in this inventory.
Every entry has `Perk`, `State`, and `Basis`; numerical fields are mechanics,
not ratings or warning thresholds. The contract contains no advice or UI text.

These facts are current-state output only. They must never feed natural
projection, Brother × Archetype Fit, BestRole, classification, or archetype
definitions.

## Supported mechanics

The formulas below come from the repository-pinned vanilla scripts commit in
`docs/REFERENCE_SOURCES.md`.

- **Nimble:** body plus head armor fatigue penalty `p`; excess `e=max(0,p-15)`;
  hitpoint-damage multiplier `min(1, 0.4 + e^1.23 * 0.01)`. Missing either
  equipped item's fatigue value produces `unknown`.
- **Battle Forged:** current body plus head armor `a`; armor-damage multiplier
  `1 - a * 0.0005`, equivalent to `a * 0.05%` reduction. Missing current armor
  on either equipped item produces `unknown`.
- **Brawny:** vanilla multiplies each armor stamina modifier by `0.7`, then
  floors the negative body modifier and ceils the negative head modifier.
  With public positive penalties this is `ceil(body*0.7)` and
  `floor(head*0.7)`. The contract exposes before/after penalties and the exact
  maximum-Fatigue benefit. It intentionally does not claim a live Initiative
  value.
- **Shield Expert:** `active` for a resolved equipped shield, `inactive` for an
  empty offhand, and `unknown` for unresolved offhand data. This reports only
  activation, not tactical value.
- **Weapon masteries:** the generated vanilla reference follows exact
  `scripts/...` dependencies from each weapon into item/active-skill code and
  records the supported `IsSpecializedIn*` properties those scripts consume.
  These are exposed as `WeaponMasteryFamilies`, which is intentionally a list:
  vanilla has hybrid weapons whose available skills consume more than one
  mastery. An owned mastery is `active` when its family is in that list,
  `inactive` for an empty main hand or a proven different family set, and
  `unknown` when authoritative family metadata is unavailable. The one pinned
  vanilla Weapon record without supported mastery evidence is the barbarian
  drum; it remains unknown rather than being guessed.

## Intentionally unavailable mechanics

- Reach Advantage requires authoritative melee and two-handed flags.
- Duelist requires authoritative weapon handedness/class plus offhand rules.
- Dodge depends on live combat Initiative after accumulated Fatigue and other
  transient effects.

The normalized item contract now provides source-derived mastery-family
applicability only; it still does not claim general melee/two-handed/handedness
facts, and parsed saves do not provide the required live combat state.
Accordingly, Reach Advantage, Duelist, and Dodge remain `unknown` where their
separate evidence is unavailable. Display names and archetype names are never
used as substitutes. Empty armor slots are known zero values; unresolved
equipped armor or weapon-family evidence is not.
