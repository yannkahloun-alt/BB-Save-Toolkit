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

    for check in ("tests", "coverage", "ruff", "pyflakes"):
        assert f"  {check}:\n    name: {check}" in workflow

    assert '-m "not coverage_slow"' in workflow
    for forbidden in ("run_tests.ps1", "run_mutation.ps1", "verify_release_zip"):
        assert forbidden not in workflow


def test_agent_b_contract_is_exact_sha_bound_and_fail_closed():
    policy = _read("docs/AGENT_B_REVIEW.md")
    policy_lower = policy.lower()

    assert "name: agent-b-review" in policy
    assert "head_sha: <exact current pull_request.head.sha>" in policy
    assert "all 40 hexadecimal characters" in policy
    assert "APPROVE" in policy
    assert "DO NOT APPROVE" in policy
    assert "conclusion on APPROVE: success" in policy
    assert "conclusion on DO NOT APPROVE: failure" in policy
    assert "malformed" in policy
    assert "Every new commit" in policy
    assert "must not use" in policy and "pull-request head" in policy
    assert "comment" in policy_lower
    assert "never" in policy_lower and "authorization signal" in policy_lower


def test_branch_protection_requires_all_checks_without_native_approval():
    protection = _read("docs/GITHUB_BRANCH_PROTECTION.md")

    for check in ("tests", "coverage", "ruff", "pyflakes", "agent-b-review"):
        assert f"`{check}`" in protection

    assert "zero required approving reviews" in protection
    assert "expected source" in protection
    assert "do not accept **any source**" in protection
    assert "Require branches to be up to date before merging" in protection
    assert "Restrict who can push to matching branches" in protection
    assert "Do not allow bypassing the above settings" in protection
