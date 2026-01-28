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

1. Auto-detect the project's test framework (look for `pytest.ini`, `jest.config.*`, `vitest.config.*`, `go.mod`, `Cargo.toml`, etc.)
2. Generate test files from the success criteria. Each SC maps to one or more test cases.
3. Tests should fail initially (red-green-refactor).
4. Present the test structure for user approval.

Write tests to the project's standard test directory.

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
1. Run the relevant tests
2. If tests fail, give the subagent the failure output to fix
3. Continue to the next subtask

After all subtasks complete:
1. Run the full test suite
2. Launch the `structural-completeness-reviewer` agent for a final review
3. Address any review findings
4. Report final status to the user
