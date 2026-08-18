# Codex — Start Here

Use this repository directly. Do not ask for or produce source ZIP handoffs during development.

For a new task, first read:

```text
AGENTS.md
docs/INVARIANTS.md
docs/ARCHITECTURE.md
docs/DEVELOPMENT_WORKFLOW.md
docs/TESTING.md
```

For roadmap work, also read:

```text
docs/specs/REMAINING_WORK_v3.84.md
```

Then inspect the affected code/tests, reproduce the issue or establish the contract, implement the smallest coherent change, add regression tests, run the required gates, review the Git diff, and commit the task.

Never assume a cache/identity/projection optimization is safe without proving equivalence against the documented invariants.
