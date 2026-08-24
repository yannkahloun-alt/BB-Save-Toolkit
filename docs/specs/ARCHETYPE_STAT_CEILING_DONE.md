# Specification --- Configurable Archetype Stat Ceiling

> **Amended by issue #40:** Fit now saturates positively at `target` and uses
> bounded signed contributions below `baseline`. The optional `ceiling`
> remains accepted, remains valuation-only, and never caps displayed/projected
> stats, but values between `target` and `ceiling` no longer earn surplus Fit.
> Statements below describing uncapped above-target utility are retained as
> historical context for the original completed feature.

## 1. Objective

Add an optional **`ceiling`** property to individual archetype stat
definitions.

The purpose is to let an archetype express that additional projected
points in a stat **stop increasing archetype fit after a configurable
value**.

This is an **archetype valuation mechanism**, not a
simulation/game-mechanics cap.

The feature must remain entirely configurable through the archetype
configuration.

## 2. Motivation

Current archetype stat definitions use:

``` json
"Fatigue": {
  "target": 115,
  "weight": 2.0,
  "baseline": 95
}
```

The classifier can continue rewarding a stat above its `target`.

This can distort comparisons between archetypes with different
development burdens.

### Observed example

A recruit produced approximately:

**Thrower**

``` text
HP       95.9
Fatigue 124.6
Resolve  48.6
RAtk     81
```

**Nimble Tank**

``` text
HP       93.7
Fatigue 102.3
Resolve  54.5
MDef     35
```

The Nimble Tank path has a substantial development burden because MDef
must receive many level-up rolls.

The Thrower has more freedom to invest those rolls into secondary stats
such as Fatigue.

Consequently, a Thrower can receive additional fit from values such as
**124.6 Fatigue**, even when the player considers Fatigue above, for
example, 115 or 120 to have little relevance when deciding whether the
recruit is a better Thrower.

A configurable ceiling allows the player to express that preference
directly.

## 3. Configuration format

`ceiling` is an **optional numeric property** of an archetype stat.

Example:

``` json
"Fatigue": {
  "target": 115,
  "weight": 2.0,
  "baseline": 95,
  "ceiling": 120
}
```

Existing definitions without `ceiling` remain valid:

``` json
"MDef": {
  "target": 35,
  "weight": 4.5,
  "baseline": 20
}
```

## 4. Semantics

The three thresholds have distinct meanings.

### `baseline`

Represents the lower quality/reference point already used by the
existing fit curve.

It answers approximately:

> At what value does this stat start becoming reasonably acceptable for
> this archetype?

Existing semantics must remain unchanged.

### `target`

Represents the desired value for the archetype.

It answers:

> What value does this archetype consider a strong/full target?

Existing semantics must remain unchanged.

### `ceiling`

Represents the maximum value that the archetype considers relevant **for
fit valuation**.

It answers:

> Beyond what projected value should additional points in this stat stop
> making this recruit look better for this archetype?

For a projected stat `x`:

``` text
effective_value = min(x, ceiling)
```

The existing fit/utility calculation then operates on `effective_value`.

This should be conceptually equivalent to evaluating:

``` text
utility(min(projected_value, ceiling))
```

rather than:

``` text
min(utility(projected_value), ...)
```

unless mathematical equivalence is explicitly established.

## 5. No ceiling

If `ceiling` is absent:

``` json
"RAtk": {
  "target": 88,
  "weight": 4.5,
  "baseline": 80
}
```

the stat must behave **exactly as it does today**.

This is important for backward compatibility.

Therefore:

``` text
missing ceiling = unlimited/current behavior
```

There must be no implicit/default ceiling.

## 6. Ceiling does NOT alter projections

The ceiling applies only to **archetype fit valuation**.

It must NOT modify:

-   projected level-up allocation;
-   projected final stats;
-   displayed projected stats;
-   roll selection;
-   level advisor behavior, unless that behavior explicitly consumes the
    capped fit valuation;
-   underlying Battle Brothers mechanics.

Example:

A Thrower may still project:

``` text
Fatigue = 124.6
```

even if its archetype configuration contains:

``` json
"ceiling": 120
```

The report must still show:

``` text
Projected Fatigue: 124.6
```

Only the value used when calculating archetype fit becomes:

``` text
120
```

## 7. Ceiling is NOT a game-mechanics claim

The setting must not imply that values above the ceiling are
mechanically useless in Battle Brothers.

For example:

``` json
"MAtk": {
  "target": 90,
  "baseline": 75,
  "ceiling": 100
}
```

does **not** mean MAtk above 100 has no gameplay effect.

It means:

> This player's configuration does not want MAtk above 100 to make a
> recruit score higher for this particular archetype.

This distinction is particularly important for MAtk/RAtk because Battle
Brothers caps final hit chance at 95%, but offensive skill above 95 can
still be useful against enemy defense and other hit-chance penalties.

## 8. Archetype-specific behavior

Ceilings belong to the **archetype/stat pair**, not globally to a stat.

For example:

``` json
{
  "name": "Thrower",
  "stats": {
    "Fatigue": {
      "target": 115,
      "baseline": 95,
      "weight": 2.0,
      "ceiling": 120
    }
  }
}
```

does not imply that Fatigue is capped at 120 for BF Tank, Nimble Tank,
Frontline DPS, or any other archetype.

Another archetype may specify a different ceiling or no ceiling at all.

## 9. Player customization

The feature deliberately allows different tactical philosophies.

### Player A

Values extremely high offensive skill:

``` json
"MAtk": {
  "target": 90,
  "baseline": 75,
  "weight": 4.0
}
```

No ceiling. MAtk above target continues contributing according to the
existing utility curve.

### Player B

Considers 100 MAtk sufficient for the role:

``` json
"MAtk": {
  "target": 90,
  "baseline": 75,
  "weight": 4.0,
  "ceiling": 100
}
```

MAtk above 100 no longer improves archetype fit.

Neither philosophy should be hardcoded by the toolkit.

## 10. Intended effect on archetype comparisons

The primary purpose is to prevent **low-burden archetypes from
accumulating excessive fit through surplus secondary stats**.

Example:

``` text
Thrower:
RAtk 81
Fatigue 124.6
```

If configured with:

``` text
Fatigue target  = 115
Fatigue ceiling = 120
```

the additional 4.6 Fatigue above 120 provides no additional Thrower fit.

Meanwhile, an archetype-defining stat such as MDef could deliberately
remain uncapped:

``` json
"MDef": {
  "target": 35,
  "baseline": 20,
  "weight": 4.5
}
```

A projected 40 MDef therefore remains more valuable than 35 MDef
according to the existing above-target utility curve.

This allows configuration to distinguish between stats where exceptional
values remain role-defining and stats where additional surplus
eventually stops being relevant to role selection.

## 11. Validation rules

At minimum:

``` text
ceiling must be numeric
ceiling must be finite
ceiling >= target
```

A configuration such as:

``` json
"target": 115,
"ceiling": 110
```

should be rejected as invalid rather than silently corrected.

Reason: `target` represents the desired full-value point. A ceiling
below target would make the semantics ambiguous.

`ceiling == target` is allowed.

Example:

``` json
"target": 50,
"ceiling": 50
```

means:

> Reach 50, then stop rewarding additional points entirely.

## 12. Backward compatibility requirement

This feature must be strictly backward compatible.

For every existing archetype configuration without `ceiling`:

``` text
fit_before_feature == fit_after_feature
```

subject only to existing floating-point tolerances.

Introducing support for `ceiling` must therefore cause **zero
classification changes** until ceilings are explicitly added to
configuration.

This should have a dedicated regression test.

## 13. Fit calculation tests

Tests should cover at least the following.

### No ceiling

Given an existing stat definition without ceiling, verify that
below-target, target and above-target utility are unchanged.

### Below ceiling

Given:

``` text
target  = 100
ceiling = 120
projection = 110
```

verify that utility is calculated from **110**.

### Exactly at ceiling

``` text
projection = 120
```

must use **120**.

### Above ceiling

``` text
projection = 130
```

must produce exactly the same fit contribution as:

``` text
projection = 120
```

### Ceiling equals target

Given:

``` text
target = ceiling = 100
```

verify:

``` text
utility(100) == utility(110) == utility(150)
```

for that archetype stat.

### Invalid configuration

Reject `ceiling < target` and invalid/non-numeric/non-finite ceiling
values.

## 14. Classification regression test

Create two otherwise identical projected recruits:

``` text
Recruit A:
RAtk 88
Fatigue 120

Recruit B:
RAtk 88
Fatigue 140
```

For a Thrower configuration containing:

``` json
"Fatigue": {
  "target": 115,
  "baseline": 95,
  "weight": 2.0,
  "ceiling": 120
}
```

their Fatigue contribution to archetype fit must be identical.

Therefore the extra 20 Fatigue on Recruit B must **not** improve his
Thrower fit.

Without the `ceiling` property, existing behavior must remain and the
two recruits may receive different fit values.

## 15. Reporting / explainability

Where practical, reports should preserve both pieces of information:

``` text
Projected: 124.6
Fit valuation capped at: 120
```

The projection itself should never be displayed as 120.

If component-level fit explanations already exist, a capped component
should ideally be identifiable, for example:

``` text
Fatigue
Projected: 124.6
Target: 115
Ceiling: 120
Value used for fit: 120
```

This prevents users from mistaking the ceiling for a projection bug.

## 16. Non-goals

This feature should NOT initially introduce:

-   global stat ceilings;
-   automatic ceilings derived from Battle Brothers mechanics;
-   hardcoded MAtk/RAtk/HP/Fatigue/etc. rules;
-   changes to stat projection;
-   changes to level-up allocation;
-   new archetype gates;
-   changes to `Invest` / `Use` / `Fodder` thresholds;
-   automatic recommendations for ceiling values;
-   diminishing-return curve redesign.

Those can be considered independently later.

The first implementation should remain deliberately narrow:

> **Add an optional saturation point to the existing archetype stat
> utility calculation.**

## 17. Design principle

The toolkit should not decide that:

> "120 Fatigue is enough."

Instead, the configuration should be able to say:

> "For this archetype, in my playstyle, I don't want values above 120
> Fatigue to influence role selection."

This keeps tactical assumptions in **configuration**, while the scoring
engine remains generic.
