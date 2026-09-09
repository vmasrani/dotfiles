# agents
> Codex subagent definitions symlinked to `~/.codex/agents/` and selected by the harness from their `description` trigger text.
`12 files | 2026-09-07`

| Entry | Purpose |
|-------|---------|
| `context-researcher.md` | Analyzes one directory and writes a `*-context.md` file |
| `structural-completeness-reviewer.md` | Reviews post-change hygiene: dead code, incomplete integrations, and dev artifacts |
| `plan-writer.md` | Converts research findings and success criteria into an implementation plan |
| `spec-interviewer.md` | Interviews the user to produce a declarative spec; reads no code |
| `codebase-researcher.md` | Maps a codebase to find integration points |
| `test-generator.md` | Generates focused failing tests and verifies the red phase |
| `perf-reviewer.md` | Reviews an uncommitted diff for performance regressions without running code |
| `podcast-chapter-generator.md` | Generates and publishes chapters for one podcast video |
| `vault-analyst.md` | Read-only Dendron daily-notes pattern detector |
| `modern-translation.md` | Rewrites archaic English into clear modern English |
| `terra-worker.md` | General implementation, benchmarking, test, and review worker |

<!-- peek -->

## Conventions

Each agent file uses YAML front matter with `name`, `description`, and `model` fields. The `description` field is what the harness matches against to auto-invoke the agent — it doubles as the trigger condition and must be precise. Every agent explicitly uses `gpt-5.6-terra`.

These files are the source of truth — edits must be made here in `codex/agents/`, never directly in `~/.codex/agents/`, which is a symlink target managed by `setup.sh`.

## Gotchas

- `spec-interviewer` explicitly does NOT read code — it only interviews the user. Do not ask it to analyze files.
- `structural-completeness-reviewer` does NOT check functional correctness, test quality, or style — only structural hygiene (dead code, missing integrations, dev artifacts).
- `vault-analyst` is read-only by design; it must never modify Dendron vault files even if asked.
- Several agents (`plan-writer`, `spec-interviewer`, `codebase-researcher`, `test-generator`) are designed to be orchestrated together by the `create-plan` skill — they are not meant to be standalone entry points in most workflows.
