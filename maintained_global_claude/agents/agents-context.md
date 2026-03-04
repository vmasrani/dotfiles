# Claude Code Agents
> Specialized Claude Code agent definitions implementing domain-specific workflows for feature research, specification, planning, testing, and code review.
`8 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| codebase-researcher.md | Analyzes codebases using progressive disclosure with ctx-index/ctx-peek to identify integration points and patterns |
| spec-interviewer.md | Conducts structured interviews to extract requirements and testable success criteria |
| test-generator.md | Generates exhaustive test suites across 5 categories (happy path, boundary, error, edge, integration) |
| plan-writer.md | Breaks specifications into actionable implementation subtasks with dependencies |
| structural-completeness-reviewer.md | Audits code for correctness, test coverage, edge cases, and architectural alignment |

## Patterns
- **Phased workflows:** Each agent implements distinct phases (discovery, analysis, generation, validation)
- **Progressive disclosure:** Codebase research uses cheap index operations before loading full context files
- **Declarative spec format:** Success criteria extracted as testable `SC-N: {condition}` statements
- **Test-first mentality:** Tests define contracts before implementation; five test categories ensure comprehensive coverage
- **Tool-agnostic:** Test generation adapts to detected project language/framework (Python/pytest, JS/vitest/jest, Rust, Go)

## Dependencies
- **External:** None — these are agent definition files (YAML frontmatter + markdown instructions)
- **Internal:** Assumes Claude Code environment with context file system (`ctx-index`, `ctx-peek`, context files in `*-context.md` format)

## Entry Points
Each agent definition is loaded as a custom Claude Code agent with:
- `name`: Agent slug for spawning via `/agent-name` command
- `description`: One-sentence summary displayed in agent list
- `model`: Model to use (sonnet, opus, etc.)
- Markdown instructions: Detailed workflow and output format specifications

## Subdirectories
N/A — all agents defined as individual `.md` files in this directory.
