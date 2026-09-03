# Ticket 75 unresolved-reference investigation

## Reproduction

The 2026-09-02 `quicksave.sav` reproduction (SHA-256
`92699fac1fd825493685a8a785e10eaefcbd171a2b1d8a8a8fa1bcd43f22ca6f`)
reported 12 save-visible unresolved references, 65 cache fallbacks, and 65
conservative recomputations. The private save is not committed.

All 12 unresolved hashes were attached to the roster brother Sigmar as perks:

```text
00005C42 00803F36 0000005C 0000C0C0 47000000 42000080
4C000000 BE420635 CABD0000 00000042 00803F16 00000007
```

They were not serialized perk identifiers. `find_circle_metadata()` had accepted
a false metadata candidate beginning inside equipment state. The candidate
contained a known equipment hash before the real background. Its longer run of
arbitrary four-byte values beat the real circle block under the old score.

The same save exposed invalid equipment identifiers (`00000001`, `00000013`,
`000000C0`, and `00000080`). BB-Edit's vanilla source establishes that common
item state occupies 14 bytes; the roster decoder advanced 20 bytes and therefore
read later state bytes as item headers. Recruit valuation compounded the issue
by advancing with generated fixed lengths, which cannot represent named-item
strings.

## Classification and impact

| Values | Root cause | Affected path | Impact before fix |
| --- | --- | --- | --- |
| 12 hashes above | parser-boundary false circle candidate | roster perks / reference audit | Analysis-affecting: arbitrary bytes could be interpreted as owned perks. No direct cache fallback or recomputation effect. |
| `00000001`, `00000013`, `000000C0`, `00000080` | generic-item length mismatch | roster equipment | Display-only for current Fit semantics; equipment is exported but does not feed projection, classification, or Advisor inputs. No cache effect. |
| variable-length named items | static recruit-equipment advancement | recruit hiring-cost valuation | Analysis-affecting for recruit cost display/ranking inputs; a parse failure degrades explicitly. No incremental-cache effect. |

The fixes follow vanilla serialization contracts rather than save-specific hash
special cases: reject circle candidates containing any known non-perk before
the background, decode the 14-byte common item state, and use the shared item
decoder for recruit equipment. Unknown hashes and unsupported item types still
produce explicit diagnostics and conservative partial data.

## Cache-counter causality

Unresolved-reference counts are assembled from parser/reference diagnostics in
the run-health layer. Cache fallbacks and conservative recomputations are
assembled separately from incremental-cache miss reasons and computed artifact
statistics. No unresolved-reference diagnostic increments either cache counter.
For this reproduction, zero of the 65 fallback/recomputation increments are
attributable directly to the 12 unresolved values. They co-occurred with cold or
incompatible cache work; resolving them does not promise a trajectory runtime
improvement. Tickets 70 and 83 should treat the cache counts independently.

## Before and after

```text
                                      before   after parser/reference rerun
unresolved references relevant to save   12       0
unresolved backgrounds                     0       0
recoverable parsing failures              11       0
result-affecting warnings                 22       0
```

The after run used the same save bytes with `--no-projection` to isolate parsing
and reference resolution. It consequently reported zero cache fallbacks and
conservative recomputations because incremental projection was not invoked;
that zero is not presented as a performance improvement. The code-path audit
above is the causal evidence concerning the original 65 counters.
