---
name: create-plan
description: Spec-driven development workflow. Interviews the user, writes success criteria, generates tests, researches the codebase, produces a detailed implementation plan, and executes it with subagents.
---

# RPI Development Workflow

Execute the following phases in order. Do not skip phases. Confirm with the user before proceeding to the next phase.

## Phase 1 -- Feature Interview

Launch the `spec-interviewer` agent via the Task tool to conduct a structured interview:

```
Task(subagent_type="general-purpose", prompt="You are a spec-interviewer agent. [paste spec-interviewer.md instructions]. Interview the user about: $ARGUMENTS")
```

Or use AskUserQuestion directly to probe:
- What problem is being solved?
- Who consumes this feature?
- What does success look like?
- Constraints (performance, compatibility, dependencies)?
- What integrations or existing systems does this touch?
- What is explicitly out of scope?

Ask 2-3 questions at a time. Do not overwhelm.

## Phase 2 -- Success Criteria

Extract declarative, testable success criteria from Phase 1. Each criterion must be:
- **Verifiable:** Checkable programmatically or by inspection
- **Specific:** No ambiguous terms
- **Independent:** Stands alone

Write the spec to `.claude/specs/{feature-name}-spec.md` using the template from `spec-template.md` in this skill's directory. Read the template first.

Present the spec to the user and confirm before continuing.

## Phase 3 -- Test Suite

Launch the `test-generator` agent via the Task tool with the spec path from Phase 2:

```
Task(subagent_type="general-purpose", model="sonnet",
     prompt="You are a test-generator agent. Read the agent instructions at maintained_global_claude/agents/test-generator.md, then execute all 7 phases. Spec file: .claude/specs/{feature-name}-spec.md")
```

The agent handles:
- Reading the spec and extracting SC test targets
- Language/framework detection
- Generating exhaustive tests across 5 categories (happy path, boundary, error, edge, integration smoke)
- Creating/updating the justfile with `test`, `test-verbose`, `test-cov` recipes
- Installing test dependencies
- Running `just test` to verify the red phase
- Updating the spec's `## Test File Locations` section

Present the test generation report to the user. Confirm all success criteria are covered before proceeding.

## Phase 4 -- Codebase Research

Launch 2-3 `codebase-researcher` agents in parallel via the Task tool:

```
Task(subagent_type="general-purpose", model="sonnet", run_in_background=true,
     prompt="You are a codebase-researcher. First read *-context.md files, then dive into specific files. Research: {area}")
```

Each agent researches a different area relevant to the feature (e.g., data layer, UI layer, API layer).

Agents should FIRST read `*-context.md` files for progressive disclosure, then selectively read specific files.

Collect research findings: relevant files, patterns to follow, integration points, potential conflicts.

## Phase 5 -- Implementation Plan

Launch the `plan-writer` agent with all gathered context:

```
Task(subagent_type="general-purpose", model="sonnet",
     prompt="You are a plan-writer. Create a detailed implementation plan. Success criteria: {SC list}. Research: {findings}. Tests: {test structure}")
```

The plan must include:
- Exact file paths for every change
- Code snippets (not pseudocode)
- Subtask breakdown where each subtask stays under 40% context
- Dependency ordering between subtasks

Present the plan to the user for approval.

## Phase 6 -- Implementation

For each subtask from the plan, launch a general-purpose subagent:

```
Task(subagent_type="general-purpose",
     prompt="Implement subtask N: {description}. Files: {paths}. Code: {snippets}. Success criteria: {relevant SCs}")
```

After each subtask completes:
1. Run `just test` and compare to the previous run (new passes? new failures? regressions?)
2. If the subtask's tests still fail, give the subagent `just test-verbose` output to fix
3. Continue to the next subtask

After all subtasks complete:
1. Run `just test` -- all tests should pass (green phase)
2. If failures remain, launch a focused fix subagent with `just test-verbose` output
3. Run `just test-cov` to check coverage
4. Launch the `structural-completeness-reviewer` agent for a final review
5. Report to the user: passed/total tests, coverage %, structural review status
