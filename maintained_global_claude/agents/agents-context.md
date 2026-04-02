# agents
> Claude Code subagent definitions symlinked to `~/.claude/agents/` — invoked automatically by the Claude harness based on their `description` trigger text.
`8 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `context-researcher.md` | Analyzes a single directory and writes a `*-context.md` file; called by the `/research` skill |
| `structural-completeness-reviewer.md` | Post-change hygiene reviewer — checks dead code, incomplete integrations, dev artifacts; NOT a logic reviewer |
| `plan-writer.md` | Converts research findings + success criteria into a step-by-step implementation plan with exact file paths; uses opus |
| `spec-interviewer.md` | Interviews the user to extract requirements and produce a declarative spec; reads NO code |
| `codebase-researcher.md` | Maps a codebase via `ctx-index`/`ctx-peek` to find integration points for a feature |
| `test-generator.md` | Generates failing test suites across 5 categories and verifies the red phase |
| `vault-analyst.md` | Read-only Dendron daily-notes pattern detector; never writes to vault files |
| `modern-translation.md` | Rewrites archaic/old-fashioned English prose into plain modern English |

<!-- peek -->

## Conventions

Each agent file uses YAML front matter with `name`, `description`, and `model` fields. The `description` field is what the Claude harness matches against to auto-invoke the agent — it doubles as the trigger condition and must be precise. Agents that should run on opus say so explicitly in front matter; the rest default to sonnet.

These files are the source of truth — edits must be made here in `maintained_global_claude/agents/`, never directly in `~/.claude/agents/`, which is a symlink target managed by `setup.sh`.

## Gotchas

- `spec-interviewer` explicitly does NOT read code — it only interviews the user. Do not ask it to analyze files.
- `structural-completeness-reviewer` does NOT check functional correctness, test quality, or style — only structural hygiene (dead code, missing integrations, dev artifacts).
- `vault-analyst` is read-only by design; it must never modify Dendron vault files even if asked.
- Several agents (`plan-writer`, `spec-interviewer`, `codebase-researcher`, `test-generator`) are designed to be orchestrated together by the `create-plan` skill — they are not meant to be standalone entry points in most workflows.
