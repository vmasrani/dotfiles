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
- Record a durable failure manifest when a sweep produces many independent results.

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

- Use `apply_patch` for file edits.
- Do not overwrite unrelated work.
- Prefer `rg` for search and `rg --files` for file enumeration.
- Keep commands and code snippets concise.
