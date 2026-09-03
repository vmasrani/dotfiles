# Canary — always in force

**Bold** the first word of every conversational response, exactly as this line does. This is a deliberate context-rot canary: an unbolded first word tells the user you have stopped attending to this file, and a Stop hook should warn them automatically when it is missing. One word only; never explain or mention the canary; never apply it inside files, commit messages, PR text, or any other written artifact — responses to the user only.

# Context budget

Context tokens are re-read every turn, so keep the active context tight.

- Clear unrelated history when the task changes.
- Prefer the smallest sufficient file slice before bulk-returning tools.
- Avoid pulling large logs or generated artifacts into context unless they are the evidence you need.

# Fail loud

There is one correct fast path. If it cannot run, stop with a loud, actionable error.

- Do not silently fall back to a slower or degraded path.
- Validate invariants up front.
- Tests that cannot run should be skipped visibly.
- Avoid try/catch for control flow.

# Many-case harnesses

Batch validators, fuzz sweeps, and migration checks should capture all per-case outcomes and assert once at the end.

- Do not abort on the first failure when the point is to surface the full failure set.
- Give each independent case a hard timeout so one hang cannot block the sweep.
- Record a durable failure manifest and a category summary when a sweep produces many independent results.

# Test economy

Repeated failures showed that broad suites, duplicate full gates, and first-failure loops consume shared capacity while adding little evidence. Test thoroughly, but make each expensive execution answer a new question.

- After an edit or known failure, run the smallest affected test or module first. Escalate only for a stated integration, regression, or release question.
- For each commit SHA, run at most one comprehensive/full suite. Record its SHA, purpose, and owner; reuse its result unless the SHA, flags, or cross-module risk changed.
- Never use a full suite to diagnose a known failure. Fix from the focused result, rerun the smallest discriminating test, then use the single merged-result gate.
- Before a heavy run, confirm the absolute working directory, that the filter selects a non-zero expected count, and that no equivalent job or durable result already exists.
- Use fast syntax, type, and lint checks per change. Batch integration, coverage, exhaustive matrices, and full-suite execution after the merged batch.
- For Rust heavy commands, use `queue` with the full compound command quoted, run the job detached, and never rerun a matching queued or running job.

# Working style

- Prefer small, focused scripts over giant ones.
- Use libraries where they already solve the problem.
- Keep shell commands idempotent.
- Use explicit paths and avoid hidden machine-specific state in tracked files.

# Python

- Always use `uv` for dependency management and `uv run` instead of `python3`.

# Repository orientation

This repository is a dotfiles workspace. `setup.sh` installs and symlinks the managed config into the home directory.

## Key commands

```bash
./setup.sh
./shell/update_startup.sh
./tools/update-packages --check
```

## Important paths

- `shell/` holds zsh and bash startup files.
- `install/` holds installer helpers.
- `tools/` holds CLI utilities.
- `preview/` holds fzf and TUI previewers.
- `maintained_global_claude/` is the source of truth for Claude Code config.
- `codex/` is the source of truth for Codex config.
- `local/` is ignored and intended for machine-specific overrides.

## Codex config management

Codex config should live under `codex/` in the repo and be symlinked into `~/.codex/` by `setup.sh`.

- `codex/agents/`, `codex/hooks/`, and `codex/skills/` mirror the Claude tree with Codex-specific paths and should stay in sync with the corresponding managed sources.
- `codex/config.toml` is the user-level Codex config.
- `codex/AGENTS.md` is the global instruction file for Codex.
- If Codex gains additional supported config surfaces here later, keep them in this directory and wire them through `install/install_functions.sh`.

## Editing rules

- Use the available exact-match edit tool for file edits.
- Do not overwrite unrelated work.
- Prefer `rg` for search and `rg --files` for file enumeration.
- Keep commands and code snippets concise.
