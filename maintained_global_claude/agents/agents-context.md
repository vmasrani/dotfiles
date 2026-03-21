# Claude Code Agents
> Specialized agent definitions for structured product development workflows: discovery, specification, testing, planning, code review, and codebase analysis.
`8 files | 2026-03-18`

## Key Files
| File | Purpose |
|------|---------|
| context-researcher.md | Generates structured context markdown files by analyzing directories for non-obvious conventions, gotchas, and key entry points (YAML + algorithm-heavy instructions) |
| spec-interviewer.md | Conducts structured interviews to extract requirements and produce declarative success criteria in `SC-N:` format (testable, verifiable, independent statements) |
| test-generator.md | Generates exhaustive failing test suites across 5 categories (happy path, boundary, error, edge, integration) with phase-based workflow covering context discovery, framework detection, and justfile generation |
| plan-writer.md | Breaks specifications into actionable subtasks with dependencies, delivery order, and implementation guidance |
| structural-completeness-reviewer.md | Audits code for correctness, test coverage, edge cases, architectural alignment; identifies risks and missing requirements |

## Conventions
- **YAML frontmatter:** Each agent file starts with `name`, `description`, and `model` (e.g., `model: haiku`, `model: sonnet`)
- **Markdown instruction format:** All agents use markdown-based instructions (not JSON configs) following "Phase N --" structure for multi-step workflows
- **Success criteria format:** `SC-N: {When X, Y should result}` — atomic, testable, verifiable statements extracted by spec-interviewer
- **Tool usage:** Agents use AskUserQuestion for interactive discovery; other agents use Bash, Glob, and Read tools for context gathering
- **SKIP marker pattern:** Context files (including agents-context.md itself) support `> SKIP` on line 2 to prevent overwriting during regeneration

## Gotchas
- **Phase ordering:** test-generator requires completed spec files with `SC-N:` success criteria in `.claude/specs/` — passing vague requirements causes test generation to fail silently or produce weak tests
- **Framework detection:** test-generator auto-detects Python/JS/Rust/Go; JS projects must have either `vitest.config.*` or `jest.config.*` present, or it defaults to pytest (Python)
- **Justfile idempotency:** test-generator preserves existing recipes in justfile; new recipes are appended only if missing — re-running with a modified justfile risks creating duplicates if not careful
- **Model assignments:** context-researcher uses haiku (small context), others use sonnet (larger); don't swap models without testing token budgets for large codebases
