# Signed Fit Soft Floors

## Contract

Issue #40 changes each archetype Fit stat from a non-negative utility into a
bounded signed contribution without adding configuration fields.

For value `x`, baseline `b`, target `t`, and weight `w`:

```text
utility = clamp((x - b) / (t - b), -1, +1)
contribution = w * utility
```

Thus `baseline` is neutral, `target` is the positive saturation point, and a
value one baseline-to-target interval below baseline reaches the negative
floor. This is a soft floor, not an eligibility gate.

The aggregate is the signed weighted mean, clamped only at the externally
visible lower bound of 0%. A profile at every baseline remains 0%; a profile
at every target remains 100%. Existing optional `ceiling` values remain
valuation-only and do not alter projected or displayed stats.

The trajectory engine and Level Advisor consume the same compiled curves, so
improvements below baseline have value without downstream special cases.
Persisted role projection, advisor, and summary artifacts use bumped semantic
engine versions.

## Regression evidence

`test_signed_fit_roster_regression.py` records deterministic old-versus-new
rows containing brother/profile, archetype, Fit, Fit delta, classification,
and rank. The matrix covers every configured archetype and includes the known
melee-heavy Hybrid profile (`RAtk 42`, `MAtk 89`, `Fatigue 138`, `HP 103`), a
ranged-heavy inverse, a genuine dual-attack candidate, and a slightly
sub-baseline candidate. Both one-sided Hybrid profiles must lose at least 20
Fit percentage points, while the comparison remains continuous and
score-based rather than becoming an eligibility gate.
