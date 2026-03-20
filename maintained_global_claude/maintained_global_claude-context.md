# maintained_global_claude
> Global Claude Code configuration (agents, commands, hooks, skills) maintained in dotfiles and symlinked to ~/.claude.
`6 files | 2026-03-18`

## Key Files
| File | Purpose |
|------|---------|
| `settings.json` | Claude Code global settings: permissions, hooks, plugins (context7 enabled), plan mode default, statusline config |
| `statusline.sh` | Zsh status display showing directory, git branch, time, and context window usage percentage with color coding |
| `CLAUDE.md` | Meta-documentation about context files, Python/shell guidelines, and Pydantic patterns (referenced only, not part of live config) |

## Conventions
- **Symlink hub**: Everything here is symlinked to `~/.claude/` during `setup.sh` execution. Changes here update the live config.
- **Subdirectory structure**: Four main directories each with context files:
  - `agents/` — Custom agent definitions (context-researcher, codebase-researcher, structural-completeness-reviewer, etc.)
  - `commands/` — Custom slash commands (research, arewedone, generate-tests, process-parallel)
  - `hooks/` — Python scripts triggered by Claude events (PostToolUse, Stop, SubagentStop, PreCompact)
  - `skills/` — Reusable skill modules (explain, create-plan, design-principles, dotfiles-tweaker, log-to-daily, polish, data-visualization-techniques)
- **Plan mode default**: `defaultMode: "plan"` in settings.json means Claude starts in plan mode by default.
- **Hook execution**: All hooks use `uv run` with Python scripts; ensure uv is available at runtime.
- **Permissions model**: settings.json explicitly whitelists allowed tools and skills rather than defaulting to allow-all.

## Gotchas
- **Context file duplication**: Many subdirectories have their own `*-context.md` files (agents-context.md, commands-context.md, hooks-context.md, skills-context.md). These are independent docs and not generated/maintained by the parent context file.
- **Statusline timing**: The statusline recalculates context window percentage on every call, using `current_usage` not cumulative totals. High percentages (80%+) turn bold red.
- **Large file count**: ~2461 total files in this directory (mostly generated/cached data in history.jsonl, stats-cache.json). Only 6 tracked configuration files at root level.
- **FastMode enabled**: `fastMode: true` skips permission prompts; dangerous operations assume approval without asking.
- **Hook order dependency**: PostToolUse, PreCompact, and Stop hooks all run; if any fail, downstream behavior may be silent (check logs).
