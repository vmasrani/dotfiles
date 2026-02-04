# Claude Skills

_Last updated: 2026-01-27_

## Purpose
Defines reusable Claude AI skills that implement structured workflows for complex development tasks. Currently contains the create-plan skill which orchestrates spec-driven development from requirements through implementation using multi-phase workflows.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| `create-plan/SKILL.md` | Main skill definition | Six-phase RPI workflow (interview, criteria, tests, research, planning, implementation) |
| `create-plan/spec-template.md` | Specification template | Markdown boilerplate for feature specs with problem statement, success criteria, constraints |
| `create-plan/create-plan-context.md` | Skill documentation | Contextual information about the create-plan skill |

## Patterns
- **Multi-phase workflow:** Orchestrates sequential development phases with user confirmation gates
- **Subagent delegation:** Launches specialized subagents (spec-interviewer, codebase-researcher, plan-writer, structural-completeness-reviewer) via Task tool for different concerns
- **Test-first approach:** Generates failing tests from success criteria before implementation (red-green-refactor)
- **Progressive disclosure:** Uses context files (*-context.md) to bootstrap codebase research before diving into specific files
- **Parallel research:** Launches 2-3 researcher agents in parallel to investigate different architectural areas

## Entry Points
- `create-plan` skill callable via `/create-plan` slash command in Claude Code
- Invokes six distinct phases: Feature Interview, Success Criteria, Test Suite, Codebase Research, Implementation Plan, Implementation

## Subdirectories
| Directory | Purpose | Has Context File |
|-----------|---------|-----------------|
| `create-plan/` | Spec-driven development workflow | Yes (create-plan-context.md) |
