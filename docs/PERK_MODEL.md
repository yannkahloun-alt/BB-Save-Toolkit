# Perk Model

This document is the source of truth for how Battle Brothers perks interact with
BestRole projection, separately displayed effective combat stats and, later,
the Perk Advisor.

The purpose is not merely to record the final classification. We keep the
reasoning here so future changes do not accidentally reverse decisions after
the conversation context is gone.

## Core rule

**BestRole and archetype Fit measure natural brother potential.** Owned and
hypothetical perk stat modifiers do not change the projected stats used for
that evaluation. Perks may still supply build-compatibility signals and
separately labelled effective combat stats.

This prevents circular reasoning such as:

`perk -> assume compatible build/gear/playstyle -> improved stats -> choose that build`

The intended direction is:

`brother -> plausible archetype -> build/playstyle -> perk synergy`

Perk transforms therefore remain downstream of archetype discovery.

## Classification

### Structural BestRole perk

A permanent, sufficiently deterministic modification of projected core stats.

These perks may create alternate build/effective-stat paths, but do not change
the natural-stat trajectory or Fit used to discover BestRole.

### Archetype-enhancing perk

The archetype must already be chosen before the perk can be evaluated
meaningfully. These perks belong in the future Perk Advisor and must not create
BestRole branches.

### Situational / tactical perk

The value depends primarily on combat state, positioning, target, equipment or
specific actions. These may still be excellent perks, but their value cannot be
treated as a stable projected core stat for BestRole.

---

## Decisions

### Colossus

**Classification:** Structural BestRole perk  
**BestRole impact:** No
**Current implementation:** Yes

Colossus permanently multiplies HP and affects both current HP and aggregated
future HP gains. Its value exists regardless of the eventual archetype, gear or
combat behavior.

The analyzer may expose a hypothetical Colossus build path and its effective HP,
but the natural HP trajectory and stat-derived Fit remain identical to the base
brother. Level-Up Advisor evaluates natural development rather than treating
Colossus as underlying talent.

The separately reported current effective HP continues to apply the game's
Colossus multiplier and integer rounding.

---

### Fortified Mind

**Classification:** Archetype-enhancing perk  
**BestRole impact:** No  
**Future/role projection impact:** No

Fortified Mind permanently multiplies Resolve, but unlike Colossus it is not a
role-agnostic development assumption. It is a normal/required part of a Banner
build and is rarely selected merely to improve a non-Banner brother.

Using Fortified Mind as a BestRole reveal perk creates circular reasoning:

`Fortified Mind -> much higher Resolve -> Banner wins -> therefore Fortified Mind`

The intended direction is instead:

`brother qualities -> Banner is plausible -> Banner build includes Fortified Mind`

Fortified Mind remains a real effective-combat-stat transform when the brother
actually has the perk, but it is not applied to natural Banner projection, Fit,
or BestRole discovery.

---

### Dodge

**Classification:** Archetype-enhancing / situational  
**BestRole impact:** No  
**Future Perk Advisor:** Yes

Dodge converts current Initiative into MDef and RDef. The bonus is not a stable
property of the brother because current Initiative depends heavily on gear and
Fatigue accumulated during combat.

Crediting Dodge in BestRole would force the model to assume equipment and combat
behavior before choosing the archetype. That reverses the intended causality.

The intended reasoning is:

`BestRole already chosen -> compatible Initiative/gear/Fatigue profile -> Dodge
may improve the build`

Relentless is an important synergy because it reduces the Initiative loss caused
by accumulated Fatigue. It does not change the BestRole decision.

We explicitly reject assigning Dodge a fabricated stable `+X MDef/RDef` value
for BestRole.

---

### Brawny

**Classification:** Archetype-enhancing  
**BestRole impact:** No  
**Future Perk Advisor:** Yes

Brawny's value depends on the Fatigue penalty of the armor and helmet the brother
will wear.

Using Brawny to create a Battle Forged/heavy-armor role would be circular:

`Brawny -> assume heavy gear -> more usable Fatigue -> choose heavy-gear role`

The role and expected gear must already be established before Brawny has a
meaningful value.

The intended reasoning is:

`heavy-gear role already chosen -> Brawny may improve that build`

---

### Reach Advantage

**Classification:** Archetype-enhancing / situational  
**BestRole impact:** No  
**Future Perk Advisor:** Yes

Reach Advantage is equipment- and action-dependent. The brother must already be
using a compatible two-handed weapon, and the defensive benefit depends on
successful attacks and the tactical situation.

The archetype and weapon concept therefore precede the perk.

Even if its potential MDef bonus is large, it must not be treated as stable MDef
for BestRole.

---

### Lone Wolf

**Classification:** Archetype-enhancing / tactical  
**BestRole impact:** No  
**Future Perk Advisor:** Yes

Lone Wolf can provide very large stat bonuses, but only while the brother is
sufficiently isolated from allies.

The size of the bonus is not the deciding factor. Its existence depends on how
the already-chosen archetype is positioned and played.

An Archer with Lone Wolf is still an Archer; a Duelist with Lone Wolf is still a
Duelist. Lone Wolf may improve those builds but must not create them.

---

## Audit status

The shipped `references/dictionary_core.json` contains **50 standard/save-visible
vanilla perks**. All 50 are now classified in this model:

- **1 structural effective-stat build path:** Colossus
- **49 excluded from structural build-path simulation**
- **0 standard perks remaining to review**

This does **not** assume that the vanilla source tree contains only those 50
scripts. On first run, `perk_effects.json` scans every perk script in the
downloaded vanilla source and `perk_audit.json` reconciles that larger source
set against `config/perk_model.json`.

If the source contains additional/special perk scripts, they appear
automatically in `perk_audit.json -> unreviewed` until we classify them.

Therefore the persistent rule is:

> Standard perk-tree audit: complete. Source-script audit: machine-checked on
> each reference generation.


---

## Combinatorics

Structural perk combinations are currently manageable because only a very small
number of perks qualify.

If the number of structural perks grows materially, revisit the branching
strategy before accepting exponential combinations.

Do not weaken the classification rule merely to simplify the implementation:
the modeling decision comes first; optimization comes after.


---

## BestRole exclusion list

The following perks have been reviewed and are explicitly excluded from
structural build-path simulation. This list is also the working checklist for the
remaining audit: do not revisit an excluded perk unless its vanilla mechanics
change or the modeling rule itself changes.

### Stat/resource effects that remain non-structural

- **Fortified Mind** — an owned Fortified Mind changes effective combat Resolve,
  but never the natural Resolve projection or Banner Fit.
- **Dodge** — derived MDef/RDef depends on Initiative, gear, accumulated Fatigue,
  combat behavior and possible Relentless synergy.
- **Brawny** — usable-Fatigue benefit depends on the heavy gear selected for an
  already-defined build.
- **Reach Advantage** — temporary MDef depends on compatible 2H equipment and
  attacks actually performed.
- **Lone Wolf** — large stat multiplier, but activation depends on tactical
  isolation and therefore on how an already-defined role is played.
- **Relentless** — preserves Initiative under accumulated Fatigue; its value is
  downstream of the role/playstyle and commonly synergizes with Dodge.
- **Recover** — manages accumulated Fatigue during combat; it does not increase
  the brother's structural Fatigue pool.
- **Pathfinder** — improves movement AP/Fatigue economy; terrain and role
  dependent, not structural Fatigue.
- **Bags and Belts** — inventory/gear-dependent Fatigue economy; the loadout must
  already be known.

### Accuracy / offensive conditional effects

- **Anticipation** — situational effect; not a stable projected core-stat change.
- **Fast Adaptation** — hit chance improves after misses and resets on a hit; not
  intrinsic MAtk/RAtk.
- **Backstabber** — hit chance depends on surrounding the target; not intrinsic
  MAtk.
- **Bullseye** — mitigates situational ranged obstruction penalties; not
  intrinsic RAtk.
- **Fearsome** — offensive morale mechanic using the already-existing Resolve;
  it does not add structural Resolve.
- **Crippling Strikes** — injury-enabling offensive mechanic.
- **Executioner** — damage bonus against already-injured targets.
- **Head Hunter** — conditional head-hit/damage sequencing mechanic.
- **Berserk** — AP refund after a kill.
- **Killing Frenzy** — temporary damage bonus after a kill.
- **Overwhelm** — applies a combat debuff to enemies; Initiative/action dependent.

### Defensive / survival conditional effects

- **Nine Lives** — survival trigger at lethal damage; does not increase the
  structural HP pool. Treat as survival/flavor for BestRole purposes.
- **Steel Brow** — changes head-hit damage handling; does not add HP or defense.
- **Resilient** — mitigates negative status duration/effects; situational.
- **Underdog** — mitigates surround pressure; does not add intrinsic MDef.
- **Indomitable** — activated defensive state; not permanent projected defense.
- **Nimble** — survivability depends directly on light-gear Fatigue penalties.
- **Battle Forged** — survivability depends directly on heavy armor.
- **Shield Expert** — defensive value depends on already choosing a shield build.

### Tactical / utility effects

- **Rotation** — tactical repositioning.
- **Taunt** — tactical enemy-control ability.
- **Adrenaline** — initiative/turn-order tempo ability, not structural Initiative.
- **Footwork** — tactical disengagement/repositioning.
- **Quick Hands** — loadout-switching utility; equipment/build dependent.
- **Rally the Troops** — tactical Banner/Rally function. A brother is selected
  as Banner from his underlying qualities; Rally does not create that role.
- **Student** — progression/XP perk, not a final-stat BestRole modifier.

### Weapon/build perks

- **All weapon masteries** — weapon-dependent by definition. The archetype/loadout
  must already be chosen before a mastery has value.
- **Duelist** — one-handed/free-offhand weapon-build dependency.
- **Shield Expert** — shield-build dependency (also listed under defensive perks).

### Explicit structural allow-list so far

Only this reviewed perk currently qualifies for a structural effective-stat
build path:

1. **Colossus**

Fortified Mind is explicitly archetype-enhancing: it belongs to Banner
development, not Banner discovery. Colossus likewise does not alter natural Fit;
its path communicates an effective HP build outcome. Everything else above is
excluded from BestRole and may be reconsidered later for the Perk Advisor.

## Audit rule going forward

When reading the remaining vanilla perk list, first compare the perk against the
exclusion list above. Only stop for discussion if a not-yet-reviewed perk
actually changes HP, Fatigue, Resolve, Initiative, MAtk, RAtk, MDef or RDef in a
way that might satisfy the Core rule.

This avoids re-reviewing ordinary tactical, gear-dependent, weapon-dependent or
situational perks one by one.


---

## Level-Up Advisor scoring principle

When the current role's Development Burden is **100% patchable both before and
after a candidate level-up**, Burden reduction is an efficiency benefit rather
than an urgent viability constraint.

In that regime, the Advisor explicitly discourages sacrificing Fit merely to
save patch/support picks. A negative Fit delta receives an additional equal
penalty (effectively double weight on the loss).

When feasibility is below 100%, the normal scoring remains unchanged: Burden and
feasibility can legitimately dominate because completing the archetype is no
longer guaranteed.

This rule is intentionally archetype-agnostic. It protects the configured Fit
signal rather than hard-coding premium stats such as RAtk for Crossbow/Gunner.
