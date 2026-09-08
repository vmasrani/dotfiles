---
name: create-plan
description: Spec-driven development workflow. Interviews the user, writes success criteria, generates tests, researches the codebase, produces a detailed implementation plan, and executes it with subagents.
---

# RPI Development Workflow

Execute the following phases in order. Do not skip phases. Confirm with the user before proceeding to the next phase.

## Phase 1 -- Feature Interview

Use the `ask` tool to probe directly. If a delegated interviewer is useful, launch one `task` agent and tell it to read `codex/agents/spec-interviewer.md` before interviewing.
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

Write the spec to `.codex/specs/{feature-name}-spec.md` using the template from `spec-template.md` in this skill's directory. Read the template first.

Present the spec to the user and confirm before continuing.

## Phase 3 -- Test Suite

Launch one `task` agent. Tell it to read `codex/agents/test-generator.md`, execute all seven phases, and use the spec at `.codex/specs/{feature-name}-spec.md`.

The agent handles:
- Reading the spec and extracting success-criterion test targets
- Detecting the language and framework
- Generating the smallest contract-complete failing test set
- Creating only the needed `justfile` test recipes
- Installing missing test dependencies
- Running the narrowest command that proves the red phase
- Updating the spec's `## Test File Locations` section

Present the test generation report to the user. Confirm all success criteria are covered before proceeding.

## Phase 4 -- Codebase Research

Launch 2–3 `scout` agents in one `task` call so they run in parallel. Give each a distinct area and require a bounded file:line map of relevant patterns and integration points.

Each agent researches a different area relevant to the feature (e.g., data layer, UI layer, API layer).

Agents should FIRST read `*-context.md` files for progressive disclosure, then selectively read specific files.

Collect research findings: relevant files, patterns to follow, integration points, potential conflicts.

## Phase 5 -- Implementation Plan

Launch one `task` agent, tell it to read `codex/agents/plan-writer.md`, and give it the success criteria, research findings, and test structure.

The plan must include:
- Exact file paths for every change
- Code snippets (not pseudocode)
- Subtask breakdown where each subtask stays under 40% context
- Dependency ordering between subtasks

Present the plan to the user for approval.

## Phase 6 -- Implementation

For each subtask from the plan, launch a `task` agent with exact files, code contracts, relevant success criteria, and explicit non-goals. Independent subtasks go in one `task` call with disjoint file ownership; dependent subtasks run in dependency order.

After each subtask completes (NO full suite here — one full run per plan, at the end):
1. Run ONLY the subtask's own tests (a name/path filter: `just test <filter>`, `cargo nextest run -E 'test(/<mod>/)'`, `pytest path::test`) and compare to the previous run (new passes? new failures?)
2. If the subtask's tests still fail, give the subagent that filtered output to fix
3. Continue to the next subtask

After all subtasks complete:
1. Run `just test` ONCE (or, when an integration branch `pre-dev*` exists, merge into it and let the orchestrator run the wave's single gate) -- all tests should pass (green phase)
2. If failures remain, launch a focused fix subagent with `just test-verbose` output
3. Run `just test-cov` to check coverage
4. Launch the `structural-completeness-reviewer` agent for a final review
5. Report to the user: passed/total tests, coverage %, structural review status
