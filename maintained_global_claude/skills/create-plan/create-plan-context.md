# create-plan Skill
> RPI workflow: conducts feature interviews, writes specs, generates tests, researches codebase, creates implementation plans, and executes with subagents.
`2 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| SKILL.md | Skill definition with 6-phase workflow (Feature Interview → Success Criteria → Test Suite → Codebase Research → Implementation Plan → Implementation) |
| spec-template.md | YAML-frontmatter markdown template for feature specs (Problem Statement, Success Criteria, Constraints, Out of Scope, Test Locations, Implementation Subtasks) |

## Patterns
- **Multi-phase orchestration:** Enforces strict 6-phase sequence with user confirmations between phases.
- **Spec-driven development:** Success criteria extracted before coding; tests and plan derived from spec.
- **Parallel research:** Phase 4 spawns 2-3 background researcher agents to investigate different codebase areas.
- **Subagent delegation:** Each phase delegates to specialized agents (spec-interviewer, test-generator, codebase-researcher, plan-writer, implementation subagents).
- **Test-first verification:** Tests generated before implementation; `just test` used to track progress at each subtask.

## Dependencies
- **Internal:** Subagent types: spec-interviewer, test-generator, codebase-researcher, plan-writer, structural-completeness-reviewer. Claude Code Task tool for agent spawning.

## Entry Points
- **SKILL.md**: Main workflow instruction file; referenced when `/create-plan` is invoked.
- **spec-template.md**: Template for Phase 2 output; copied to `.claude/specs/{feature-name}-spec.md`.

## Notes
- Workflow assumes `just` command available for test orchestration (`just test`, `just test-verbose`, `just test-cov`).
- Test file locations and implementation subtasks are filled in by subsequent phases (not in initial template).
- Structural completeness reviewer called after implementation completes for final validation.
