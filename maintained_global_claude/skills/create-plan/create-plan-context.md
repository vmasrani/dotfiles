# create-plan
> Six-phase spec-driven development skill: interviews user, writes spec, generates tests, researches codebase, plans, and executes via subagents.
`2 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `SKILL.md` | Skill definition with all 6 phases — the executable workflow invoked by `/create-plan` |
| `spec-template.md` | Markdown template for `.claude/specs/{feature}-spec.md`; Phase 2 reads this before writing specs |

<!-- peek -->

## Conventions

- Phases must run sequentially and require user confirmation before advancing — never auto-proceed.
- Specs are written to `.claude/specs/{feature-name}-spec.md` (relative to the project root), not inside this directory.
- Phase 3 (test generation) delegates entirely to the `test-generator` agent and expects a `justfile` with `test`, `test-verbose`, and `test-cov` recipes. If the project has no justfile, the agent creates one.
- Phase 4 launches 2-3 parallel `codebase-researcher` agents via Task tool with `run_in_background=true` — each covers a distinct layer (data, UI, API, etc.).
- Phase 6 runs `just test` after every subtask to catch regressions incrementally, not just at the end.

## Gotchas

- The `spec-template.md` file must be read during Phase 2 before writing specs — the skill references it by path relative to the skill directory, so if the skill directory moves, the path breaks.
- Success criteria (SC) written in Phase 2 must be verifiable and specific — vague criteria silently produce tests that pass without real validation.
- Subtasks in Phase 5 must each stay under 40% context window so the implementation subagents can read all required files without truncation.
- The `structural-completeness-reviewer` agent is run at the very end of Phase 6 as a final gate — skipping it means the plan may be "green" on tests but structurally incomplete.
