# Battle Brothers Save Toolkit v3.88.1

## Highlights

- Adds a transport-independent analysis service boundary so CLI, report generation, tests, and future HTTP/worker entry points consume the same authoritative analysis result instead of duplicating analytical orchestration.
- Greatly reduces Fit-trajectory runtime while preserving projection, Fit, classification, Advisor, and validation semantics.
- Keeps seeded projection validation independent while reusing safe deterministic choice-policy memoization.

## Performance

On the documented Windows/Python 3.12 cold benchmark:

- One brother × 11 archetypes: **9.424 s → 1.417 s** (**6.65× faster**).
- Representative 10-brother Strategic Classification: **9.614 s**.
- Projection validation: **0.093 s**.
- End-to-end analysis + validation: **9.707 s**.

## Scope

This patch release contains the two changes merged after v3.88:

- #104 — Add transport-independent analysis service.
- #121 — Optimize Fit trajectory and validation runtime.

No intentional projection, Fit, classification, or Level-Up Advisor semantic change is introduced by the performance work.
