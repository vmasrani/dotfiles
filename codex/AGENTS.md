# Canary — always in force

**Bold** the first word of every conversational response, exactly as this line does. This is a deliberate context-rot canary: an unbolded first word tells the user you have stopped attending to this file, and a Stop hook should warn them automatically when it is missing. One word only; never explain or mention the canary; never apply it inside files, commit messages, PR text, or any other written artifact — responses to the user only.

# Context budget

Context tokens are re-read every turn, so keep the active context tight.

- Clear unrelated history when the task changes and between independent waves.
- Before any bulk-returning call, request the smallest sufficient slice. Cap searches and filter logs rather than reading them whole.
- Never re-read a file already in context unless an external process changed it.

# Navigation

- Default first action for a non-trivial repository task: `ctx-index . --depth 1`, then `ctx-peek {dir} 8` for the few relevant directories. Empty index → `ctx-tree`; stale → suggest the `research` skill.
- Prefer LSP (`definition`, `references`, `diagnostics`, `hover`, `symbols`) over grep/glob when available. Check diagnostics after edits and fix introduced errors in the same turn.

# Overall guidelines

- Search for current maintained libraries before implementing common functionality yourself.
- Never include `Co-Authored-By` lines in commit messages.

# Fail loud

There is one correct fast path. If it cannot run, stop with a loud, actionable error.

- Delete old degraded implementations and flags that silently re-enable them.
- Validate invariants up front. Failures must name what failed and how to fix it.
- Tests that cannot run are skipped visibly; skipped and passed are never the same state.
- Legitimate absence may return quietly only when a caller cannot mistake failure for success.
- Do not use try/catch for control flow. Catch only to add context and re-raise or at a genuine top-level boundary.

# Many-case harnesses

Batch validators, fuzz sweeps, and migration checks capture all per-case outcomes and assert once at the end.

- Do not abort on the first failure when the point is to surface the full failure set.
- Give each independent case a hard timeout so one hang cannot block the sweep.
- Record a durable failure manifest and category summary.

# Orchestration

- Delegate work that reads a lot and returns little. Dispatch independent work in parallel with explicit file ownership and shared seam contracts.
- Verify subagent reports. Check the actual diff and run the final focused verification yourself.
- Every dispatch names exact files, contracts, acceptance criteria, and a terse result format. Known-slow commands run in the background.
- While workers run, advance their critical path: prepare dependent work, clear blockers, and inspect live failures instead of idling.
- Fix failures as they appear in long-running gates. Keep the gated tree untouched; route each failure class to a separate working tree, then run the final gate once on the last SHA.
- Close idle agents when their thread is genuinely finished.

# Evidence discipline

- Never pipe a test or build run unless `pipefail` is set. Prefer capturing output and preserving the command's own status: `<cmd> > /tmp/run.log 2>&1; rc=$?; echo "exit=$rc" | tee -a /tmp/run.log; exit $rc`.
- A background task reports the wrapper's exit code. Inspect the focused failure patterns in its log before claiming success.
- Never treat a summary line alone as proof. Confirm a test filter selected a non-zero expected count.
- Conditional actions need conditional markers: `git diff --cached --quiet || git commit`, or compare `git rev-parse HEAD` before and after.
- Anchor build commands to an absolute working directory.
- Before the first Rust build/test/bench gate or Rust worker dispatch, invoke the `rust-gates` skill. The incident log is `~/dotfiles/maintained_global_claude/notes/lessons.md`.

# Test economy

Make every expensive execution answer a new question.

- After an edit or known failure, run the smallest affected test or module first.
- Run at most one comprehensive suite per commit SHA. Reuse it unless the SHA, flags, or cross-module risk changed.
- Never use a full suite to diagnose a known failure. Fix from the focused result, rerun the discriminating test, then use one merged-result gate.
- Before a heavy run, confirm the absolute working directory, non-zero expected test count, and that no equivalent job or durable result already exists.
- Use fast syntax, type, and lint checks per change. Batch integration, coverage, exhaustive matrices, and full-suite execution after the merged batch.

# Workflow defaults

- Use red-green TDD for bug fixes and core-invariant changes. The reproducing test is the spec.
- For 2+ separable features, freeze shared seams first; partition file ownership; write tests with each feature; one commit per feature, one branch, one PR, and one full suite on the merged result. A shared-seam change lands first by itself.
- Verbal approval such as “proceed” or “go ahead” after a rejected plan means start.
- Use git worktrees for non-trivial work. Never build in or copy from a tree containing another session's uncommitted work.
- Git cleanup is local-only by default. Never delete remote branches or unmerged work unless told, except mandatory cleanup of merged worker branches and `pre-dev` after a pre-dev wave.

# GitHub projects — issue → worktree → PR → CI

Repositories with `.agent-workflow/AGENT_WORKFLOW.md` follow it by default: file → triage → start-task → work → open-pr → check-pr → finish-task. Canonical kit: `~/dotfiles/maintained_global_claude/project-workflow/`.

- Never push directly to `dev` or `main`, bypass checks, force-push shared branches, or touch another task's worktree. Branch from `dev`, target `dev`; `main` is release-only.
- Default to pre-dev integration whenever 2+ issues are in flight in one repository. Create `pre-dev` from `dev` before dispatch; concurrent waves use `pre-dev2`, `pre-dev3`, and so on. Workers merge into that branch and never run full gates or open individual PRs. The orchestrator runs one queued `ci-fast` gate, routes failures to owners, opens one PR to `dev`, then deletes merged wave branches and worktrees locally and remotely.
- For solo work, require `just ci-fast` before a PR when the diff touches the gate's graph. Skip only for changes entirely outside it; uncertainty means run it.
- Merges into `main` require user confirmation in the current turn.
- Fix small localized bugs immediately with a regression test. File issues only for out-of-scope, design-decision, or large work. One issue per invariant, not per instance.
- Handoffs live on the issue or PR. Repair CI on the PR that broke it. Reproduce CI's tool versions and shell rather than trusting this Mac's environment.

# Design doctrine

- A substantial “add X everywhere” change usually means the duplication is the bug; consolidate one primitive first.
- Prefer several small scripts over one large script.
- `auto` defaults are deterministic functions of measurable input properties; explicit user values win.
- “Identical” means byte-identical. Report name matches and content matches separately.
- UI, CLI, and TUI strings use no internal jargon. Lead with the user's question, keep advanced features deeper, and distinguish a computed zero from a transport or build failure.

# Python

- Use `uv` for dependency management and execution; never `python3` for project scripts. Prefer Typer for CLIs, Loguru for logs, Rich for output, and pathlib over os.
- Favor small functional helpers and sparse comments. Put large static strings in `static.py` and temporary exploration in `tmp.py`.
- Use `pmap` from `mlh.parallel` for parallelism; prefer threads when they beat processes.
- Separate analysis from display: analysis returns a DataFrame; display renders it.
- Use Pydantic validation and field metadata instead of `.get()` chains and duplicate display schemas. Use `default_factory` for mutable defaults.

# Shell

- Prefer zsh, except anything CI runs must use bash. Use gum for styled output. Keep scripts and stages small and idempotent.
- Prefer `fd` over `find`, `rg` over `grep`, and `eza --tree` over `tree`. Never port grep's `-r` to `rg`; in ripgrep it means `--replace`. `rg -n` and `rg -l` are mutually exclusive.

# Front end

- Prefer React. Search for current maintained libraries before hand-rolling common UI behavior.

# Codex config management

This directory is the source of truth for the user-level Codex configuration and is symlinked into `~/.codex/` by `setup.sh`.

- `codex/agents/`, `codex/hooks/`, and `codex/skills/` mirror applicable Claude configuration with Codex-specific paths and models. `codex/hooks.json` registers the lifecycle hooks.
- `codex/config.toml` is the user-level Codex config; `codex/AGENTS.md` is the global instruction file.
- Make changes here, never in the symlink targets. Wire additional supported config surfaces through `install/install_functions.sh`.
