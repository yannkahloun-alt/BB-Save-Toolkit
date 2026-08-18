# Automated independent Agent B review

## Enforcement boundary

The repository uses one human GitHub account, so native pull-request approvals
cannot represent an independent Agent B verdict. The compromise enforcement is
a trusted GitHub Actions job named exactly `agent-b-review`.

The workflow uses `pull_request_target`, so GitHub loads its definition from the
trusted base branch rather than from the pull-request head. It never checks out,
imports, sources, or executes pull-request files. It retrieves the complete diff,
commit inventory, changed-file inventory, and trusted base-branch policies as
text through GitHub's API and submits them to the OpenAI Responses API.

This is weaker identity separation than a dedicated GitHub App because the
check source is GitHub Actions. It is nevertheless enforceable for this
single-owner repository when changes to `main` are protected and the workflow
definition and repository secrets remain trusted.

## Review protocol

1. Agent A implements the task, runs the routine gates, performs an adversarial
   self-review, fixes its findings, and opens or updates the pull request.
2. Pull-request `opened`, `reopened`, `synchronize`, and `ready_for_review`
   events start the trusted `agent-b-review` workflow.
3. The workflow rejects fork pull requests and actors other than the configured
   repository owner before any step receives `OPENAI_API_KEY`.
4. The workflow fetches the PR again and requires the event head SHA to equal
   the current full 40-character `pull_request.head.sha`.
5. Agent B reviews every commit and the complete `base...head` diff against
   policy files read from the trusted base SHA. PR text is explicitly treated as
   untrusted data rather than instructions.
6. The Responses API enforces a strict JSON schema containing the reviewed SHA,
   review completeness, findings, summary, and exactly `APPROVE` or
   `DO NOT APPROVE`.
7. The workflow fetches the PR again after review. It succeeds only if the PR is
   still at the reviewed SHA, review completion is true, the verdict is
   `APPROVE`, and no blocking finding exists.
8. `DO NOT APPROVE`, blocking findings, missing credentials, API errors,
   malformed or incomplete responses, oversized or incomplete diffs, and stale
   SHAs fail the job.
9. PR-scoped concurrency cancels an obsolete run after a new commit. The new
   head starts a fresh review; the older check cannot satisfy protection for the
   new SHA.
10. Passing checks establish technical readiness only. Merging still requires a
    new, explicit confirmation from the repository owner.

## Secret and model configuration

Create the repository Actions secret `OPENAI_API_KEY`. The workflow passes it
only to the trusted inline review step. PR code is never checked out or run, and
fork or untrusted-actor requests fail before that step.

The default model is `gpt-5.6-terra` with high reasoning effort. An owner may
set the repository Actions variable `AGENT_B_MODEL` to another Responses API
model that supports strict structured outputs. A missing, unauthorized, or
unsupported model fails closed.

OpenAI API usage is billed to the API project associated with the secret. The
workflow sets `store: false`, but normal API data-handling terms still apply.

## Trust and prompt-injection limitations

The pull-request diff must be visible to Agent B to be reviewed, so malicious
text in code or documentation is an unavoidable model input. The trusted system
instruction labels all PR-derived material as untrusted data and prohibits
following embedded instructions. The workflow, schema, authorization rules,
SHA checks, and pass/fail logic remain trusted base-branch code outside the
model's control.

Only the exact structured verdict influences the job. Comments, labels, PR
descriptions, commit messages, filenames, and text resembling `APPROVE` cannot
directly set the result. The model is not given a shell, checkout, GitHub token,
OpenAI key, tool, or function call.

This compromise does not provide the distinct check-source identity of a
dedicated GitHub App. Repository administrators who can modify `main`, Actions
secrets, or protection settings remain inside the trust boundary.

## One-time setup

1. Create an OpenAI API project key with an appropriate spend limit.
2. In GitHub, open **Settings > Secrets and variables > Actions > Secrets**.
3. Create `OPENAI_API_KEY` with the API key as its value.
4. Open a temporary same-repository PR from the trusted owner and confirm the
   `agent-b-review` job appears, reviews the exact SHA, and fails closed when the
   key is absent or invalid.
5. Configure `main` protection as described in
   `docs/GITHUB_BRANCH_PROTECTION.md`.

The workflow introduced by a pull request cannot run via `pull_request_target`
until it exists on the base branch. Its rollout PR therefore requires explicit
owner review and merge using the existing four green CI gates. All subsequent
same-repository PRs receive the automated Agent B gate.
