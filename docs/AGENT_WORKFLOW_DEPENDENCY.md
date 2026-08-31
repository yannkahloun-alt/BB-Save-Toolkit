# Shared agent workflow dependency

Battle Brothers Save Toolkit consumes the reusable
[`codex-agent-workflow`](https://github.com/yannkahloun-alt/codex-agent-workflow)
repository as the `.agent-workflow` Git submodule. The gitlink recorded by each
toolkit commit is the authoritative workflow revision; the initial integration
pins tag `v1.0.0` at commit `a77aa5f7884adaede37e2929ef6ebb28e2862ff1`.

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

The shared repository owns generic role lifecycles, context isolation, handoffs,
instruction precedence, and taskless startup. This repository owns application
architecture and invariants, concrete tests and CI checks, release procedures,
issue-history requirements, and the exact single-account Agent B/merge protocol.

Project policy may explicitly specialize shared defaults. It must not silently
duplicate or contradict them.

## Initialize and update

Initialize after a clone or in a new worktree:

```powershell
git submodule update --init --recursive
```

To update, fetch tags inside `.agent-workflow`, check out a reviewed tag or
commit, run the toolkit validation gates, and commit the changed gitlink. Do not
configure the effective workflow to follow a floating branch.

## Migration summary

- Generic orchestration, implementation, review, context, handoff, precedence,
  and startup rules moved to the shared repository.
- Domain invariants, repository commands, CI names, release rules, and the exact
  Agent B trust boundary remain project-specific.
- `AGENTS.md` and `CODEX_START_HERE.md` were rewritten as concise entry points.
- Repeated generic lifecycle text was removed from the project entry point;
  project documents now link to the shared policy where appropriate.
- The remaining limitation is the standard submodule initialization step,
  handled explicitly by agent bootstrap instructions and CI checkout settings.
