# Commands
> Custom Claude slash commands for workflows: code review, testing, research, and parallel processing.
`4 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| arewedone.md | Structural completeness review workflow using reviewer agent |
| generate-tests.md | Exhaustive test generation from specs, diffs, or features |
| research.md | Context file generation and progressive disclosure framework |
| process-parallel.md | Parallel processing pipeline template (worker, runner, prompt) |

## Patterns
- **Slash command workflow:** Each file defines a multi-step command that orchestrates agents and tasks
- **Agent-driven automation:** Commands launch specialized agents (structural-completeness-reviewer, test-generator, context-researcher) via Task tool
- **Multi-stage processes:** Workflows include context discovery, execution, and reporting phases
- **Tool-based discovery:** Commands use shell tools (ctx-stale, ctx-index, git diff) to detect what needs processing

## Dependencies
- **Internal agents:** structural-completeness-reviewer, test-generator, context-researcher (defined in ~/.claude/agents/)
- **Shell tools:** ctx-index, ctx-tree, ctx-peek, ctx-stale, ctx-skip (in ~/tools/)
- **External:** OpenAI API (for process-parallel), uv (for script execution)

## Entry Points
- `/arewedone` — Trigger structural completeness review
- `/generate-tests` — Create failing test suite
- `/research` — Generate or refresh context files across project
- `/process-parallel` — Set up parallel processing pipeline (worker, runner, prompts)

## Subdirectories
None (commands is a flat directory of markdown definition files).
