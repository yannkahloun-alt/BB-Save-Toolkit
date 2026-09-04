# Recruit known-evidence estimates

`bbtool.recruit_candidate_estimate.v1` is the candidate-specific intrinsic
layer over `bbtool.background_archetype_prior.v1`. It never changes or relabels
the population prior.

## Public evidence audit

The current pre-hire recruit contract contains settlement, name, title,
background, level, tryout state, traits revealed by tryout, hire cost, and daily
wage. Only background and revealed traits are justified intrinsic inputs:

- the exact `BackgroundSaveHash` selects the #110 population prior; it is the
  machine identity of the background already visible to the player;
- after `TryoutDone == true`, `RevealedTraitEvidence` supplies exact serialized
  trait hashes plus display names. Hashes, never names, resolve mechanics;
- settlement, name, and title carry no established potential effect;
- public level is not used because the toolkit lacks a calibrated distribution
  for the hidden rolls already consumed by a higher-level recruit;
- hire cost and wage are economics, not candidate potential.

The parser may decode stats, talent stars, unrevealed traits, and future rolls
while locating a serialized candidate. None is admitted to the public recruit
contract or this model. Trait evidence is emitted only after tryout.

## Model and fallback

For each archetype, the model resolves revealed trait hashes against the pinned
trait-effect reference. An exact, unconditional permanent effect on one of that
archetype's Fit stats is applied to the same reference brother and exact
talent/trajectory outcome space used by #110. This produces a conditioned
distribution; it does not duplicate or alter the background prior.

Unknown traits, conditional or unsupported effects, effects only on non-Fit
stats, missing tryout state, and partial/missing evidence do not justify a
candidate percentage. If any revealed trait is unresolved or unusable for the
archetype, the model does not partially condition on the remaining traits. The
result remains `prior_only` and
`candidate_estimate` is `null`. There is no interpolation, confidence score,
Bayesian-sounding adjustment, or added display precision.

## Machine-readable contract

Every result contains:

- `schema`, `model_version`, and a structural `state` equal to `prior_only` or
  `known_evidence_estimate`;
- the unchanged `background_prior` object from #110;
- nullable `candidate_estimate`, containing the conditioned distribution and
  exact applied trait hashes only when evidence is sufficient;
- `evidence_basis.public_fields_considered`, per-item status/effects, and an
  explicit list of excluded categories.

The API accepts no roster or Company input. Extra recruit fields are ignored,
and tests prove that roster need, assignment, economics, hidden stats, stars,
and future rolls cannot affect the result.

## Relevant roster need (#112)

`bbtool.relevant_roster_need.v1` is a downstream mixed artifact. It first
marks a role candidate-plausible when the existing #110/#111 prior or known-
evidence distribution has mean Fit at or above the configured viable-fit
threshold. It then intersects that set with #166 `NeedBases` only:
`assigned_but_no_viable_holder`, `single_point_of_failure`, and
`contested_backup_only`. `NoIntent` therefore contributes no need.

The result exposes deterministic `relevant_need_matches`, an explicit
`relevant_need` or `no_match`, and separately inspectable `other_company_gaps`.
Need bases are ordered by the fixed basis precedence and then BuildIdentity.
Company intent cannot alter candidate evidence, potential, intrinsic Fit, or
BestRole. Its signature includes the viability threshold, candidate evidence,
and distinct authoritative intrinsic-coverage and intended-coverage artifact
signatures, so either Company input invalidates only this mixed artifact (and
its transitive dependents). Target presentation integration remains #174.

## Known prerequisite limits

The current contract has no legitimately public observed base stats or talent
stars. Public level alone is insufficient without a separately validated model
of already-consumed hidden rolls. Accordingly, untried recruits and tried-out
recruits whose traits have no supported Fit-stat effect remain prior-only. A
future stronger candidate model requires a new legitimately observed and
calibrated evidence source; it must not infer one from raw hidden save fields.
