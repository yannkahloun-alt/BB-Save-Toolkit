# Background × Archetype prior

`bbtool.background_archetype_prior.v1` is the intrinsic population prior used
as the input boundary for Recruitment. It answers only: given a vanilla
background and a stable build definition, what level-11 natural Fit outcomes
does the model assign before anything is known about a particular candidate?

## Inputs and identity

The generated `bbtool.backgrounds.v2` reference is derived from the immutable
vanilla scripts revision declared in `references/update_references.py`. It
contains exact level-1 integer stat ranges, background bonuses/maluses,
excluded talents, and the untalented flag. Base ranges are parsed from
`character_background.nut`; they are not copied into the model. Static values
inherit through the background script hierarchy. A dynamic or incomplete
definition has no `PotentialProfile` and is explicitly unsupported. Background
scripts that directly mutate the actor talent array are also unsupported even
when the assignments look deterministic: treating `IsUntalented` as an
all-zero-star result would otherwise discard those post-generation overrides.
Generated entries expose `PotentialUnsupportedReason` as either
`talent_mutation` or `non_static_attribute_offsets`.

The build is identified by authoritative `BuildIdentity` plus its observed
`BuildDefinitionHash`. Id-less legacy roles are rejected for this durable
contract. Output also records the existing role-projection and validation-
oracle engine versions.

## Model v1 assumptions

- The reference profile uses the lower integer midpoint of every source-defined
  level-1 stat range. This keeps the profile inside the game's integer stat
  domain, makes bonuses and maluses comparable, and deliberately does not
  pretend to model the full joint starting-roll population. Starting-roll
  dispersion is an explicit future model extension.
- Talent allocation follows vanilla: three distinct eligible stats, uniformly
  selected; each receives one/two/three stars with 60%/30%/10% weight.
  Untalented backgrounds receive the single all-zero-star outcome.
- Each weighted talent profile is projected by the existing blind natural
  level-11 trajectory engine. Its deterministic low-discrepancy outcome oracle,
  not merely its expected Fit, is incorporated into the histogram.
- No traits, injuries, tryout facts, observed stats/stars, equipment, candidate
  level, roster need, assignment, price, wage, or other candidate/company/
  economic evidence enters this prior. #111 may condition on legitimate known
  candidate evidence without mutating this object; #112 may separately combine
  plausible roles with Company need.

## Machine-readable distribution

`background_archetype_prior(background_save_hash, role, reference)` returns:

- model schema/version and pinned background-source revision;
- background save hash/source ID;
- BuildIdentity, BuildDefinitionHash, and projection engine versions;
- explicit assumptions;
- integer-weight ten-point Fit histogram with one shared
  `weight_denominator`, plus the talent and trajectory denominators;
- mean Fit rounded to one decimal, matching existing projection precision.

Integer weights are the authoritative probability representation. Consumers
divide a weight by `weight_denominator` only when a displayed probability is
needed, and should not display precision finer than the model/sample supports.
The histogram uses ten-point Fit bands; the final band is explicitly `90-100`.

`supported_backgrounds(reference)` enumerates only exact profiles. Missing save
hashes and source entries without an exact profile fail explicitly instead of
falling back to display names or guessed values.

## Versioning

Version 1 fixes the reference-midpoint, vanilla-talent, and shared-trajectory
semantics above. A change to those assumptions or output meaning requires a
model schema/version bump. A change inside existing projection semantics is
separately visible through the centralized engine versions and does not require
inventing a second projection formula here.
