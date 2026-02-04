# agents

_Last updated: 2026-01-27_

## Purpose

Defines Claude agent configurations for spec-driven development workflows. Each agent specializes in one phase of the spec-to-implementation pipeline: interviewing requirements, researching codebases, writing plans, and reviewing structural integrity.

## Key Files

| File | Role | Model | Key Responsibility |
|------|------|-------|-------------------|
| spec-interviewer.md | Phase 1: Requirements gathering | sonnet | Conducts feature interviews and extracts testable success criteria |
| codebase-researcher.md | Phase 2: Code analysis | sonnet | Analyzes codebase structure, patterns, and integration points using progressive disclosure |
| plan-writer.md | Phase 3: Planning | opus | Generates detailed implementation plans with subtasks and code snippets |
| structural-completeness-reviewer.md | Phase 4: Change review | sonnet | Reviews code changes for structural integrity, dead code, and technical debt |
| context-researcher.md | Utility: Directory analysis | haiku | Generates structured context markdown files for codebase directories |

## Patterns

**Multi-phase Workflow Coordination:**
Sequential execution: spec-interviewer → codebase-researcher → plan-writer → (implementation) → structural-completeness-reviewer. Each phase produces artifacts fed to the next.

**Progressive Disclosure Strategy (codebase-researcher):**
- Phase 1: Run `ctx-tree . 3` for high-level directory overview
- Phase 2: Run `ctx-peek . 8` to scan context file headers without loading full files
- Phase 3: Read only 1-3 most relevant context files (max budget)
- Phase 4: Use Grep for targeted pattern searches
- Phase 5: Read specific source files as needed

**Agent Structure:**
YAML frontmatter (name, description, model) followed by detailed role instructions with explicit input/output specifications and decision frameworks.

**Read-only Constraints:**
codebase-researcher and plan-writer use only Glob, Grep, Read, and Bash tools; never modify code.

**Scoped Responsibilities:**
- spec-interviewer: Requirements only (no code reading)
- codebase-researcher: File discovery and pattern identification (no implementation)
- plan-writer: Task decomposition and architecture (no code execution)
- structural-completeness-reviewer: Structural integrity only (NOT functional correctness, tests, docs, or style)

## Dependencies

- **External:** None (agent definitions are markdown; executed by Claude Code platform)
- **Internal:**
  - Expects `.claude/specs/{feature-name}-spec.md` output from spec-interviewer
  - Expects `.claude/plans/{feature-name}-plan.md` output from plan-writer
  - Relies on `*-context.md` files in project directories for codebase-researcher's progressive disclosure
  - Works with project's gitignore and directory structure

## Entry Points

Agents are invoked via Claude Code's agent system. Typical workflow:
1. `/spec-interviewer` → Start new feature with requirements interview
2. `/research` → Run codebase-researcher on a feature scope
3. `/create-plan` → Generate implementation plan from spec + research
4. Manual implementation based on plan
5. `/arewedone` → Run structural-completeness-reviewer on completed changes

## Notable Design Decisions

**Model Selection:**
- spec-interviewer, codebase-researcher: Claude Sonnet (balanced speed/capability/cost)
- plan-writer: Claude Opus (complex reasoning for architecture decisions)
- context-researcher: Claude Haiku (fast analysis for utility operations)

**Isolation Principle:**
Each agent has narrowly scoped responsibilities. Example: structural-completeness-reviewer explicitly excludes functional correctness, test quality, documentation, and code style reviews.

**Success Criteria Format:**
spec-interviewer produces verifiable, testable criteria in format `SC-N: {When X happens, Y should result}` to enable measurable implementation verification.

**Context Window Protection:**
codebase-researcher enforces strict context budget (~2-3 full context files) via progressive disclosure to maintain analysis capacity for complex codebases.

**Plan Atomicity:**
plan-writer decomposes features into independently verifiable subtasks, each touching 3-5 files max, with dependency ordering for execution by subagents.

**Structural Focus:**
structural-completeness-reviewer categorizes findings as "blocking" (breaks builds/deploys) or "debt-inducing" (future maintenance issues) for triage.
