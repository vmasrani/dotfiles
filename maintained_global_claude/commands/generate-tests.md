---
description: Generate an exhaustive failing test suite from specs, plans, git diffs, or a user interview.
---

# Generate Tests

Generate a comprehensive, initially-failing test suite for the current project.

## Context Discovery

Determine what to test, using the first source that yields results:

1. **Arguments provided:** If `$ARGUMENTS` is non-empty, treat it as a spec path, plan path, or feature description.
2. **Spec files:** Glob for `.claude/specs/*-spec.md`. If specs exist, use AskUserQuestion to ask which spec to generate tests for (show filenames as options).
3. **Git diff:** Run `git diff --stat`. If there are changes, use AskUserQuestion to ask whether tests should cover the changed files.
4. **User interview (fallback):** Use AskUserQuestion to ask:
   - What feature or module needs tests?
   - What are the key functions and their expected inputs/outputs?

## Execution

Launch the `test-generator` agent via the Task tool:

```
Task(subagent_type="general-purpose", model="sonnet",
     prompt="You are a test-generator agent. [Read maintained_global_claude/agents/test-generator.md for full instructions]. Generate tests for: {discovered context}")
```

The agent will:
- Detect language and test framework
- Generate tests across 5 categories (happy path, boundary, error, edge, integration smoke)
- Create/update justfile with test recipes
- Install test dependencies
- Run `just test` to verify the red phase
- Produce a structured report

## Output

Present the test generation report to the user. If the user wants changes (more tests, different focus, remove tests), re-launch the agent with updated context.
