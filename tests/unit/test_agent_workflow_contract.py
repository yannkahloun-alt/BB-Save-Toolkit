from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / ".agent-workflow"


def test_shared_workflow_is_pinned_and_available() -> None:
    gitmodules = (ROOT / ".gitmodules").read_text(encoding="utf-8")

    assert 'path = .agent-workflow' in gitmodules
    assert "codex-agent-workflow.git" in gitmodules
    assert (SHARED / "AGENTS.md").is_file()
    assert (SHARED / "IMPLEMENTATION_AGENT.md").is_file()
    assert (SHARED / "REVIEW_AGENT.md").is_file()


def test_shared_startup_and_instruction_precedence_contract() -> None:
    workflow = (SHARED / "AGENTS.md").read_text(encoding="utf-8")

    assert "Which issue would you like to work on?" in workflow
    assert "without a task, do not scan the repository" in workflow.lower()
    assert "user's explicit request" in workflow
    assert "bypasses this default" in workflow


def test_project_agent_file_is_an_adapter() -> None:
    project = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert ".agent-workflow/AGENTS.md" in project
    assert "git submodule update --init --recursive" in project
    assert "docs/INVARIANTS.md" in project
    assert "docs/TESTING.md" in project
    assert "docs/AGENT_B_REVIEW.md" in project


def test_shared_policy_does_not_embed_project_specific_details() -> None:
    shared_text = "\n".join(
        path.read_text(encoding="utf-8") for path in SHARED.glob("*.md")
    )

    for project_detail in (
        "Battle Brothers",
        "coverage_slow",
        "run_ruff.ps1",
        "ProjectedFitPct",
        "FutureRolls",
    ):
        assert project_detail not in shared_text


def test_ci_initializes_shared_workflow() -> None:
    workflows = (
        ROOT / ".github/workflows/pr-validation.yml",
        ROOT / ".github/workflows/pre-release.yml",
        ROOT / ".github/workflows/render-preview-build.yml",
    )

    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8")
        assert text.count("submodules: recursive") == text.count("actions/checkout@")
