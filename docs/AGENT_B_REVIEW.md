# Independent Agent B review

## Free single-account compromise

The repository uses one human GitHub account. GitHub therefore cannot treat a
second Codex agent as a distinct native approving reviewer, and a trustworthy
required `agent-b-review` status check would require an external service or
credential. This project deliberately avoids that paid integration.

Instead, Agent A automatically creates a fresh Codex task for Agent B after the
pull request has been pushed. The task runs independently in an isolated
worktree, reviews the GitHub pull request at its exact current head SHA, and
returns `APPROVE` or `DO NOT APPROVE`. Agent A waits for that result before
reporting readiness to the owner.

This is an operational Codex gate, not a GitHub-enforced status check. GitHub
branch protection enforces the deterministic `tests`, `coverage`, `ruff`, and
`pyflakes` checks. Explicit owner confirmation remains mandatory before merge.

## Agent A protocol

1. Implement the requested change and run the appropriate routine validation.
2. Perform an adversarial self-review of the complete diff and fix every
   finding.
3. Commit and push the coherent change, then create or update the draft pull
   request with its full description.
4. Wait for all required checks on the exact current head to pass.
5. Mark the pull request **Ready for review** and verify it is no longer a draft.
   This state transition belongs exclusively to Agent A.
6. Resolve and record the pull request's full 40-character current head SHA.
7. Automatically create a **fresh Codex task** titled
   `Independent review — PR #<number>` in an isolated worktree.
8. Give Agent B only the repository, pull-request URL/number, and instruction to
   use `$review-bb-pr`. Do not give it Agent A's conclusions as trusted facts.
9. Wait for Agent B to inspect the complete GitHub diff, required checks, and
   repository policy at that exact SHA.
10. Accept only an explicit `APPROVE` for the same head SHA. Treat a draft PR,
    missing, incomplete, malformed, stale, or `DO NOT APPROVE` response as a
    failed review.
11. If Agent B reports findings, fix them, rerun affected validation, push a new
    commit, complete the ready-state gate again, and launch a **new** exact-SHA
    Agent B review. A verdict for the old SHA is invalid.
12. Report readiness and the verdict to the owner. Never merge or change branch
    protection without the owner's explicit confirmation.

The separate task may run entirely in the background. It appears in the Codex
sidebar, and the owner may open it in another app window for observation, but
opening a physical window is not required for the review to run.

## Agent B protocol

Agent B must:

- be a fresh task that did not produce the change;
- inspect PR metadata first and return `DO NOT APPROVE` without performing the
  full review if the PR is still a draft;
- use `$review-bb-pr` and obtain the pull request directly from GitHub;
- record the exact current head SHA before reviewing;
- inspect the complete diff and all commits rather than trusting Agent A's
  summary;
- verify `tests`, `coverage`, `ruff`, and `pyflakes`;
- verify that routine PR CI excludes `coverage_slow`, mutation testing,
  real-save smoke tests, and release ZIP generation;
- return concrete findings and exactly `APPROVE` or `DO NOT APPROVE`;
- refuse approval if the SHA changes or required evidence is incomplete; and
- remain strictly read-only: never mark a PR ready, modify code or metadata,
  submit a GitHub review or comment, apply labels, merge, or change settings.

## Trust boundary and limitation

The fresh task and isolated worktree provide real separation between the
producing and reviewing agent. Exact-SHA comparison prevents a verdict from
being reused after a new commit. The review transcript also remains visible as
a separate Codex task.

GitHub itself cannot authenticate this Codex verdict under a single human
account. A comment, label, or manually fabricated status would not make it
enforceable. Consequently, someone with direct push or branch-protection bypass
rights could ignore the Codex review. Branch restrictions and the owner's merge
discipline are part of this compromise.

No OpenAI API key, GitHub App, second human account, paid API usage, repository
secret, or local installation is required for this workflow.
