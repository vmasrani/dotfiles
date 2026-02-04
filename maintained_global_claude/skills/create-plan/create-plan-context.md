# create-plan

_Last updated: 2026-01-27_

## Purpose

A structured skill that implements a six-phase spec-driven development workflow. Guides users from feature interview through implementation, leveraging subagents for parallel research and code generation.

## Key Files

| File | Role | Notable Exports |
|------|------|-----------------|
| SKILL.md | Primary skill definition | Six-phase RPI workflow (Feature Interview, Success Criteria, Test Suite, Codebase Research, Implementation Plan, Implementation) |
| spec-template.md | Markdown template for specs | Feature name, Problem Statement, Success Criteria, Constraints, Out of Scope, Test Locations, Implementation Subtasks |

## Patterns

**Six-Phase Workflow (RPI - Requirements, Plan, Implement)**
1. Feature Interview: Structured questioning to capture requirements
2. Success Criteria: Declarative, testable criteria extracted from interview
3. Test Suite: Auto-detect framework and generate test cases
4. Codebase Research: Parallel subagent research of multiple areas
5. Implementation Plan: Detailed task breakdown with code snippets
6. Implementation: Subagent-driven execution with continuous testing

**Subagent Delegation**: Launches general-purpose agents in parallel via Task tool for interviews (spec-interviewer), research (codebase-researcher), planning (plan-writer), and implementation tasks.

**Progressive Disclosure**: Codebase researchers first read `*-context.md` files before diving into specific files.

## Dependencies

**Internal**:
- Subagent types: `spec-interviewer`, `codebase-researcher`, `plan-writer`, `structural-completeness-reviewer`
- Claude Code Task tool for agent spawning
- Framework auto-detection (pytest, jest, vitest, go.mod, Cargo.toml)

## Entry Points

SKILL.md is the primary entry point defining the create-plan skill workflow with mandatory phase execution and user confirmation between phases.

## Notes

- Each phase must be explicitly confirmed before proceeding
- Success criteria must be verifiable, specific, and independent
- Implementation subtasks should stay under 40% context size
- Parallel research agents accelerate codebase analysis
- Final review via structural-completeness-reviewer ensures quality
