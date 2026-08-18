# GitHub branch protection

GitHub Actions provides deterministic validation gates for pull requests into
`main`. Independent Agent B review is orchestrated automatically by Agent A as
a separate Codex task, as documented in `docs/AGENT_B_REVIEW.md`.
It is not a GitHub-enforced status check in the free single-account design.
Repository owners must configure branch protection separately; workflows do
not change repository settings.

In **Settings > Branches > Add branch protection rule**, use the branch name
pattern `main` and enable:

- **Require a pull request before merging**;
- **Require status checks to pass before merging**;
- **Require branches to be up to date before merging**;
- the exact required checks `tests`, `ruff`, and `pyflakes`;
- **zero required approving reviews**; the same human account cannot provide a
  distinct native approval, and Agent B instead reviews in a separate Codex
  task;
- **Do not allow bypassing the above settings**, where appropriate for the
  repository owner;
- **Restrict who can push to matching branches**, so routine changes reach
  `main` through pull requests rather than direct pushes;
- block force pushes and branch deletion.

The three validation checks appear after PR validation has run. Coverage is
temporarily excluded from PR CI and branch protection until its runtime is
optimized. Configure
strict/up-to-date checks so success on an old head SHA cannot satisfy a changed
pull request. Restrict bypass permission to an explicitly documented emergency
owner path; routine automation identities must not bypass the rule. After the
separate Codex Agent B task returns `APPROVE`, Agent A verifies the exact
current head and required checks again, then automatically squash-merges.
GitHub cannot enforce the Agent B verdict without a distinct external identity
or service.

The manually dispatched `pre-release` job is deliberately not a required PR
check. It includes the expensive pre-release tier and is run only when a release
or production handoff is being prepared.
