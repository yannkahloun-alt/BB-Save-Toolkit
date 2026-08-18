# GitHub branch protection

GitHub Actions provides the independent pre-merge judge for pull requests into
`main`. Repository owners must configure branch protection separately; the
workflow does not change repository settings.

In **Settings > Branches > Add branch protection rule**, use the branch name
pattern `main` and enable:

- **Require a pull request before merging**;
- **Require status checks to pass before merging**;
- **Require branches to be up to date before merging**;
- the exact required checks `tests`, `coverage`, `ruff`, and `pyflakes`;
- **Do not allow bypassing the above settings**, where appropriate for the
  repository owner;
- **Restrict who can push to matching branches**, so routine changes reach
  `main` through pull requests rather than direct pushes.

The checks appear for selection after the PR validation workflow has run at
least once. GitHub administrators may still need emergency access according to
the repository's ownership policy.

The manually dispatched `pre-release` job is deliberately not a required PR
check. It includes the expensive pre-release tier and is run only when a release
or production handoff is being prepared.
