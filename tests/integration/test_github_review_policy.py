from pathlib import Path

import pytest


pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pr_validation_keeps_stable_routine_checks_and_safe_scope():
    workflow = _read(".github/workflows/pr-validation.yml")

    assert "pull_request:" in workflow
    assert "branches:\n      - main" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "group: pr-validation-${{ github.event.pull_request.number }}" in workflow
    assert "cancel-in-progress: true" in workflow

    for check in ("tests", "ruff", "pyflakes"):
        assert f"  {check}:\n    name: {check}" in workflow

    assert "  coverage:\n    name: coverage" not in workflow
    assert "run_coverage.ps1" not in workflow
    assert '-m "not coverage_slow"' in workflow
    for forbidden in ("run_tests.ps1", "run_mutation.ps1", "verify_release_zip"):
        assert forbidden not in workflow


def test_release_workflow_is_manual_auditable_and_packages_verified_zip():
    workflow = _read(".github/workflows/pre-release.yml")

    assert "workflow_dispatch:" in workflow
    assert "release_version:" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "group: release-validation-${{ github.ref }}" in workflow
    assert "cancel-in-progress: false" in workflow

    for job in ("release-tests", "release-quality", "release-package", "release-summary"):
        assert f"  {job}:\n    name: {job}" in workflow

    assert 'python-version: "3.12"' in workflow
    assert 'python -m pytest -c tests/pytest.ini' in workflow
    assert '-m "not coverage_slow"' in workflow
    assert "run_tests.ps1" not in workflow
    assert "run_coverage.ps1" in workflow
    assert "run_lint.ps1 -Tests" in workflow
    assert "run_ruff.ps1 -Tests" in workflow
    assert "git archive --format=zip" in workflow
    assert "python tools/verify_release_zip.py" in workflow
    assert "actions/upload-artifact@65462800fd760344b1a7b4382951275a0abb4808" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "${{ github.sha }}" in workflow
    assert "run_mutation.ps1" not in workflow
    assert "Select-String -Path docs/CHANGELOG.md" in workflow
    assert "$env:RELEASE_VERSION -cne $declaredVersion" in workflow
    assert "does not match changelog version" in workflow


def test_release_workflow_pins_every_action_to_a_commit():
    workflow = _read(".github/workflows/pre-release.yml")
    action_lines = [line.strip() for line in workflow.splitlines() if "uses:" in line]

    assert action_lines
    for line in action_lines:
        revision = line.split("@", 1)[1].split()[0]
        assert len(revision) == 40
        assert all(character in "0123456789abcdef" for character in revision)


def test_release_workflow_matches_repository_release_gate():
    workflow = _read(".github/workflows/pre-release.yml")
    agent_instructions = _read("AGENTS.md")
    testing_policy = _read("docs/TESTING.md")

    command = (
        'python -m pytest -c tests/pytest.ini -o cache_dir=tests/cache/pytest '
        '-m "not coverage_slow" -q'
    )
    assert command in workflow
    assert "docs/TESTING.md" in agent_instructions
    assert command in testing_policy
    assert "coverage_slow" in testing_policy
    assert "explicit" in testing_policy.lower()


def test_render_preview_workflows_separate_unprivileged_build_and_publication():
    build = _read(".github/workflows/render-preview-build.yml")
    publish = _read(".github/workflows/render-preview-publish.yml")
    docs = _read("docs/WEB_PREVIEWS.md")

    assert "permissions:\n  contents: read" in build
    assert "tools/build_web_previews.py" in build
    assert "tests/fixtures/report_previews.json" in build
    for forbidden in ("bb_analyze.py", "run_tests.ps1", "run_mutation.ps1"):
        assert forbidden not in build

    assert "workflow_run:" in publish
    assert "pull_request_target:" in publish
    assert "contents: write" in publish
    assert "head_repository.full_name == github.repository" in publish
    assert "pr-$CLOSED_PR" in publish
    assert "preview/preview-context.json" in publish
    assert "ref-[a-z0-9._-]+" in publish
    assert "rm -rf -- \"$DESTINATION\"" in publish
    assert 'state=$(gh api "repos/$GITHUB_REPOSITORY/pulls/$number" --jq .state)' in publish
    assert 'current_sha=$(gh api "repos/$GITHUB_REPOSITORY/pulls/$number" --jq .head.sha)' in publish
    assert '[[ "$current_sha" != "$RUN_HEAD_SHA" ]]' in publish
    assert "steps.build_destination.outputs.apply == 'true'" in publish
    assert "GITHUB_STEP_SUMMARY" in publish
    assert "/standard/" in publish and "/level-up/" in publish and "/recruits/" in publish
    assert "never executes code from the preview artifact" in docs
    assert "Fork pull requests" in docs

    for workflow in (build, publish):
        for line in workflow.splitlines():
            if "uses:" not in line:
                continue
            revision = line.split("@", 1)[1].split()[0]
            assert len(revision) == 40
            assert all(character in "0123456789abcdef" for character in revision)


def test_full_preview_is_manual_exact_revision_bound_and_fail_closed():
    build = _read(".github/workflows/full-preview-build.yml")
    publish = _read(".github/workflows/full-preview-publish.yml")
    docs = _read("docs/WEB_PREVIEWS.md")

    assert "workflow_dispatch:" in build
    assert "pull_request:" not in build
    assert "source_ref:" in build and "fixture:" in build
    assert "contents: read" in build
    assert "bb_analyze.py" in build
    assert "--full-recompute" in build
    assert "--verify-cache --cache-debug" in build
    assert "tools/build_full_preview.py" in build
    assert "full-preview-logs" in build

    assert "workflow_run:" in publish
    assert "contents: write" in publish
    assert "ref: main" in publish
    assert "tools/validate_full_preview_artifact.py" in publish
    assert 'select(.name == "full-preview"' in publish
    assert "preview/preview-context.json" in publish
    assert 'test "$current_sha" = "$source_sha"' in publish
    assert "rm -rf -- \"$DESTINATION\"" in publish
    assert "GITHUB_STEP_SUMMARY" in publish

    assert "Full-application previews" in docs
    assert "never" in docs and "source `.sav`" in docs
    assert "FutureRolls" in docs and "separate diagnostic logs" in docs

    for workflow in (build, publish):
        for line in workflow.splitlines():
            if "uses:" not in line:
                continue
            revision = line.split("@", 1)[1].split()[0]
            assert len(revision) == 40
            assert all(character in "0123456789abcdef" for character in revision)


def test_agent_b_contract_is_fresh_task_exact_sha_bound_and_fail_closed():
    policy = _read("docs/AGENT_B_REVIEW.md")
    policy_lower = policy.lower()
    agent_instructions = _read("AGENTS.md")

    assert "automatically creates a fresh Codex task" in policy
    assert "isolated worktree" in policy_lower
    assert "Independent review — PR #<number>" in policy
    assert "$review-bb-pr" in policy
    assert "full 40-character" in policy
    assert "APPROVE" in policy
    assert "DO NOT APPROVE" in policy
    assert "malformed" in policy
    assert "new commit" in policy_lower
    assert "wait for agent b" in policy_lower
    assert "not a github-enforced status check" in policy_lower
    assert "no openai api key" in policy_lower
    assert "remain strictly read-only" in policy_lower
    assert "docs/AGENT_B_REVIEW.md" in agent_instructions
    assert "state transition belongs exclusively to Agent A" in policy
    assert "After the exact current head passes every" in policy
    assert "verifies that it is" in policy and "non-draft" in policy
    assert "after the pull request has been pushed" not in policy
    assert "DO NOT APPROVE" in policy
    assert "if the PR is still a draft" in policy
    assert "never mark a PR ready" in policy
    assert "Automatically squash-merge" in policy
    assert "Do not wait for a separate" in policy
    assert "owner confirmation" in policy


def test_selected_ticket_deferral_requires_traceable_comment_without_closure():
    agent_instructions = _read("AGENTS.md")
    workflow = _read("docs/DEVELOPMENT_WORKFLOW.md")

    assert "docs/DEVELOPMENT_WORKFLOW.md" in agent_instructions
    assert "## Ticket selection and deferral" in workflow
    assert "selects, claims," in workflow
    assert "meaningfully investigates" in workflow
    assert "must leave a concise GitHub" in workflow
    assert "comment before switching" in workflow
    assert "Deferral does not mean" in workflow
    assert "before switching to another ticket or ending the task" in workflow
    assert "the ticket remains open" in workflow
    assert "Do not post a" in workflow and "duplicate deferral comment" in workflow


def test_branch_protection_requires_all_checks_without_native_approval():
    protection = _read("docs/GITHUB_BRANCH_PROTECTION.md")

    for check in ("tests", "ruff", "pyflakes"):
        assert f"`{check}`" in protection

    assert "Coverage is" in protection
    assert "temporarily excluded" in protection
    assert "zero required approving reviews" in protection
    assert "not a GitHub-enforced status check" in protection
    assert "exact current head SHA" in protection
    assert "Require branches to be up to date before merging" in protection
    assert "Restrict who can push to matching branches" in protection
    assert "Do not allow bypassing the above settings" in protection
