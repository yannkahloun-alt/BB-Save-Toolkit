# Shared agent workflow dependency

Battle Brothers Save Toolkit consumes the reusable
[`codex-agent-workflow`](https://github.com/yannkahloun-alt/codex-agent-workflow)
repository as the `.agent-workflow` Git submodule. The gitlink recorded by each
toolkit commit is the authoritative workflow revision.

## Why a submodule

A submodule provides a visible, reviewable commit pin without copying shared
policy into this repository. It works with clones, Codex worktrees, and CI once
initialized, and updating it produces a small explicit toolkit diff. A subtree
would make the policy available automatically but duplicate its files and blur
ownership. A custom synchronization tool would add more code and failure modes
without improving reproducibility.

The trade-off is initialization: a fresh clone or worktree may initially have
an empty `.agent-workflow` directory. Root `AGENTS.md` supplies the bootstrap
command, and GitHub workflows request submodules during checkout.

## Policy boundary

The shared repository owns generic coordinator and role lifecycles, Git and
worktree ownership, context isolation, independent-review execution and
exact-head generations, handoffs, pre-ticket freshness and workflow bumps,
post-merge cleanup, instruction precedence, and taskless startup. This
repository owns application architecture and invariants, concrete tests and CI
checks, issue-history requirements, project-specific review criteria and merge
guards, and release procedures.

Project policy may explicitly specialize shared defaults. It must not silently
duplicate or contradict them.

For routine autonomous tickets, GitHub PR CI owns execution of the normal
deterministic suite and static-quality checks. Project documentation records
the stable check names and their commands as a CI contract; it does not require
agents to duplicate equivalent local execution before a pull request is
created or updated. Local-only validation remains available where CI cannot
reasonably perform it, or when explicitly requested.

## Initialization and approved selector

Initialize after a clone or in a new worktree:

```powershell
git submodule update --init --recursive
```

The authoritative upstream is `yannkahloun-alt/codex-agent-workflow`. The
approved stable selector is the greatest non-prerelease Semantic Version tag in
the `v1.x` series. The shared workflow owns the pre-ticket freshness and
dedicated workflow-bump lifecycle that resolves this selector to an exact
commit, validates and reviews the gitlink-only proposal, merges it under
BB-Save's guards, refreshes the default branch, and verifies the resulting pin.
A new major series requires an explicit BB-Save policy change and review. Never
configure the effective workflow to follow a floating branch.

## Migration summary

- Generic orchestration, implementation, review, context, handoff, precedence,
  and startup rules moved to the shared repository.
- Domain invariants, repository commands, CI names, release rules,
  issue-history rules, review criteria, and merge guards remain
  project-specific.
- `AGENTS.md` and `CODEX_START_HERE.md` were rewritten as concise entry points.
- Repeated generic lifecycle text was removed from the project entry point;
  project documents now link to the shared policy where appropriate.
- The remaining limitation is the standard submodule initialization step,
  handled explicitly by agent bootstrap instructions and CI checkout settings.
