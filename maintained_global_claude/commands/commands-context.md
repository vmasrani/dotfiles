# commands
> Custom Claude Code slash commands for context generation, testing, and parallel pipelines — symlinked to `~/.claude/commands/`.
`4 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `research.md` | Generates/refreshes `*-context.md` files project-wide; orchestrates `context-researcher` agents in bottom-up order (leaves first, then parents) |
| `arewedone.md` | Runs structural completeness review via `structural-completeness-reviewer` agent, then auto-commits with `committer` agent |
| `generate-tests.md` | Generates exhaustive failing test suites via `test-generator` agent; discovers what to test from args, specs, git diff, or user interview |
| `process-parallel.md` | Scaffolds a 3-file parallel pipeline (worker.py, run.py, system_prompt.md) using `pmap` + `uv run` scripts |

<!-- peek -->

## Conventions

Commands are plain markdown files — the first line (or frontmatter `description`) becomes the command description in `/help`. Files with a `---` YAML frontmatter block use `description:` for that.

`research.md` uses `$ARGUMENTS` to scope `ctx-stale` to a subdirectory; omit args to scan the whole project.

`process-parallel.md` hardcodes `gpt-5.2` as the model and `n_jobs=50, prefer="threads"` — edit these when scaffolding if different concurrency is needed.

## Gotchas

`research.md` must NOT run in plan mode — it begins with an explicit `ExitPlanMode` instruction. If invoked while plan mode is active, the command will stall unless that tool is called first.

The `.claude/logs/` subdirectory inside this directory is runtime log state (post_tool_use, stop, chat, subagent_stop JSON files) — not command definitions. Do not confuse it with command source files.

Commands are symlinked from this directory into `~/.claude/commands/`; edit files here, never in `~/.claude/commands/` directly.
