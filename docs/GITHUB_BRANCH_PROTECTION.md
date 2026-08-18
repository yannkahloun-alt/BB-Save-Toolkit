# GitHub branch protection

GitHub Actions provides the deterministic validation gates and the automated
Agent B verdict for pull requests into `main`, as documented in
`docs/AGENT_B_REVIEW.md`. Repository owners must configure branch protection
separately; workflows do not change repository settings.

In **Settings > Branches > Add branch protection rule**, use the branch name
pattern `main` and enable:

- **Require a pull request before merging**;
- **Require status checks to pass before merging**;
- **Require branches to be up to date before merging**;
- the exact required checks `tests`, `coverage`, `ruff`, `pyflakes`, and
  `agent-b-review`;
- GitHub Actions as the expected source of `agent-b-review` (do not accept an
  unrelated status source with the same name);
- **zero required approving reviews**; the same human account cannot provide a
  distinct native approval, and the required Agent B check is the review gate;
- **Do not allow bypassing the above settings**, where appropriate for the
  repository owner;
- **Restrict who can push to matching branches**, so routine changes reach
  `main` through pull requests rather than direct pushes;
- block force pushes and branch deletion.

The four validation checks appear after PR validation has run. The Agent B check
appears after the trusted workflow exists on `main`, `OPENAI_API_KEY` is
configured, and a subsequent same-repository PR triggers it. Configure
strict/up-to-date checks so a success on an old head SHA cannot satisfy a changed
pull request. Restrict bypass permission to an explicitly documented emergency
owner path; routine automation identities must not bypass the rule. If the
repository plan does not support the required restriction, treat explicit owner
confirmation and the visible five-check state as an additional merge control.

The manually dispatched `pre-release` job is deliberately not a required PR
check. It includes the expensive pre-release tier and is run only when a release
or production handoff is being prepared.
