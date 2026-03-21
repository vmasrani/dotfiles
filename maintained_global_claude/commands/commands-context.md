# Commands
> Custom Claude slash commands orchestrating agents and workflows for code review, testing, and research.
`4 files | 2026-03-18`

## Key Files
| File | Purpose |
|------|---------|
| arewedone.md | Trigger structural-completeness-reviewer agent to verify changes are fully integrated with no technical debt |
| generate-tests.md | Exhaustive test generation from specs, diffs, or features via test-generator agent |
| research.md | Generate or refresh `*-context.md` files across project; documents ctx-* shell tools (index, tree, peek, stale, skip, reset) |
| process-parallel.md | Template for parallel processing pipelines (worker, runner, system_prompt pattern) |

## Conventions
- **Command style:** Each `.md` file defines a multi-stage workflow (discovery → execution → report)
- **Agent orchestration:** Commands spawn specialized agents via Task tool (context-researcher, structural-completeness-reviewer, test-generator)
- **Shell tool integration:** Commands use `ctx-*` utilities for discovery (ctx-stale finds stale dirs, ctx-index maps context files)
- **Parallel pattern:** process-parallel uses `pmap(prefer="threads", n_jobs=50)` with worker scripts calling OpenAI API
- **Return values:** research.md expects agents to return single status lines ("SUCCESS: ..." or "ERROR: ..."), not file contents

## Gotchas
- `/research` requires full agent mode, not plan mode — must call ExitPlanMode first if in plan mode
- Context files must be committed to repo, not ignored — remove from .gitignore if present
- research.md explicitly forbids using TaskOutput or Read to check generated context files — only use Task return values
- process-parallel worker scripts must add jitter before API calls (`time.sleep(random.uniform(0.5, 5))`) to avoid rate limits
- test-generator expects 5 test categories (happy path, boundary, error, edge, integration smoke) and updates justfile
