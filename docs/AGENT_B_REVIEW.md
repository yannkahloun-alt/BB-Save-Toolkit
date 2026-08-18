# Independent Agent B review

## Enforcement boundary

The repository uses one human GitHub account, so native pull-request approvals
cannot represent the independent Agent B verdict. The enforced verdict is a
GitHub Check Run named exactly `agent-b-review`, created directly by a dedicated
GitHub App. A pull-request comment may summarize the review, but it is never an
authorization signal.

The App is external trusted infrastructure. Repository workflows, pull-request
files, comments, labels, and the pull-request author's credentials cannot create
or complete this check. Until the App is installed and branch protection is
configured, the repository changes in this document define the contract but do
not enforce it.

## Review protocol

1. Agent A implements the task, runs the routine gates, performs an adversarial
   self-review, fixes every finding, and opens or updates the pull request.
2. The App receives the pull-request `opened`, `reopened`, or `synchronize`
   webhook. It reads the pull request through GitHub's API and creates an
   `agent-b-review` Check Run with `status: in_progress` on the exact current
   `pull_request.head.sha`.
3. A separate Agent B receives an immutable review request containing the
   repository identity, pull-request number, base SHA, and exact head SHA. It
   independently obtains and reviews the complete `base...head` diff and all
   commits. Agent B must not rely on Agent A's summary as evidence.
4. Agent B returns exactly one structured verdict: `APPROVE` or
   `DO NOT APPROVE`, plus concrete findings and the reviewed head SHA.
5. The App authenticates the Agent B service, fetches the pull request again,
   and compares all 40 hexadecimal characters of the submitted SHA with the
   current `pull_request.head.sha` using exact equality.
6. Only an authenticated, complete, well-formed `APPROVE` for that exact current
   SHA completes the check with `conclusion: success`. `DO NOT APPROVE`
   completes it with `conclusion: failure`. Missing evidence, malformed
   verdicts, authentication failures, and incomplete reviews fail closed: the
   check remains in progress or completes with `failure` or `action_required`.
7. Every new commit produces a different head SHA and therefore a new
   in-progress check. A successful check attached to an older commit cannot
   satisfy branch protection for the latest commit. Agent B must review again.
8. Passing checks only establish technical readiness. Merging still requires a
   new, explicit confirmation from the repository owner.

The App should use an idempotency key of repository ID, pull-request number,
and head SHA. It should reject duplicate terminal verdicts rather than allowing
a successful result to be overwritten without a new review request.

## GitHub App configuration

Create one private GitHub App dedicated to Agent B and install it only on
`yannkahloun-alt/BB-Save-Toolkit`.

Required repository permissions:

- **Checks: read and write**, to create and complete `agent-b-review`;
- **Contents: read**, to obtain commits and the complete diff;
- **Pull requests: read**, to obtain PR metadata and the current head SHA;
- **Metadata: read**, granted automatically by GitHub.

Subscribe only to the **Pull request** and **Check run** events. The check-run
event is needed only if the App supports the GitHub **Re-run** control. Do not
grant Administration, Actions, Issues, Members, Secrets, or repository write
permissions.

Keep the App private key and webhook secret in the external reviewer service's
secret store. Mint short-lived installation tokens per operation. Never put
these credentials in this repository, GitHub Actions secrets, PR workflows, PR
comments, or an Agent A environment.

The webhook receiver must validate GitHub's signature before processing an
event. The verdict endpoint must separately authenticate the Agent B workload,
bind its request to the immutable review request, and retain an audit record of
the reviewed SHA, verdict, findings, reviewer workload identity, timestamps,
and resulting check-run ID.

For forked or otherwise untrusted pull requests, the App may read public diff
data but must never execute, import, source, or evaluate code or configuration
from the pull-request head. It must not expose an installation token or any
other secret to the reviewer sandbox. If this separation cannot be guaranteed,
leave `agent-b-review` incomplete and require a manual trusted review.

## Check Run contract

The App creates and updates the check through the Checks API with:

```text
name: agent-b-review
head_sha: <exact current pull_request.head.sha>
status: in_progress | completed
conclusion on APPROVE: success
conclusion on DO NOT APPROVE: failure
conclusion on invalid/incomplete evidence: failure or action_required
```

The output summary must state the PR number, reviewed head SHA, verdict, and
findings (or explicitly state that there are no findings). It must not disclose
credentials or sensitive reviewer metadata.

The App must derive this policy from its deployed trusted code. It must not use
a workflow, script, schema, policy file, comment, label, artifact, or other
content selected by the pull-request head to decide whether the check passes.

## Repository changes versus administrator work

Implemented in the repository:

- four PR-scoped validation jobs named `tests`, `coverage`, `ruff`, and
  `pyflakes`;
- the independent-review and fail-closed Check Run contract;
- branch-protection instructions and automated contract tests.

Required outside the repository:

1. deploy and secure the GitHub App and independent Agent B service;
2. install the App on this repository and let it create at least one
   `agent-b-review` check;
3. configure `main` protection as documented in
   `docs/GITHUB_BRANCH_PROTECTION.md`, selecting this App as the expected source
   for `agent-b-review`;
4. verify webhook delivery, signature checks, exact-SHA rejection, malformed
   verdict rejection, and new-commit invalidation before relying on the gate.

Neither App installation nor branch-protection changes are performed by the
repository workflows.
