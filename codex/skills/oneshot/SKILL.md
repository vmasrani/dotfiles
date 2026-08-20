---
name: oneshot
description: Explicit ceremony waiver for a single change — skip issue filing, TDD red phase, review agent, and PR gates; one-shot implement, build, and empirically verify. Use ONLY when the user invokes /oneshot; never self-invoke.
---

# Oneshot mode

The user has explicitly waived the process ceremony for this one task. That
waiver covers: GitHub issue filing, the TDD red phase / new-test requirement,
the independent review agent, and PR/CI gating. It is a per-invocation waiver —
it does not carry to the next task, and it is not an invitation to lower code
quality.

## What is waived

- No issue, no triage, no claim comments.
- No new tests required (write one anyway only if it is genuinely free).
- No review agent, no PR unless the user asks afterward.
- No full-suite chain by default — targeted suites suffice.

## What is NEVER waived

- **Fable never writes code.** One implementation subagent (opus; sonnet for
  trivial mechanical edits) gets a precise, self-contained brief.
- **A branch.** Work in a spike worktree on `spike/<slug>` (or the repo's
  equivalent) off the integration branch. Never edit dev/main's tree directly,
  never commit to dev/main, never push or merge without being asked.
- **Existing tests stay green.** The agent runs the targeted existing suites
  touching the changed path; filters must select >0 tests; exact result lines
  reported.
- **Fail-loud doctrine.** No silent fallbacks, no degraded paths left behind.
- **Evidence discipline.** Build/test exit codes read from logs, not inferred;
  a conditional action gets a conditional marker.
- **An empirical demonstration.** "It compiles and old tests pass" is not the
  deliverable — demonstrate the change doing its job on a real artifact
  (benchmark before/after binaries, run the repro, exercise the actual CLI).
  Keep a copy of the *before* binary/artifact when the claim is comparative.

## Flow

1. **Scope precisely first.** Name the files, functions, and the one design
   decision. If the design is genuinely undecided (interface change, format
   change, multiple defensible shapes), STOP and say oneshot is the wrong tool
   for this task — a waiver of ceremony is not a waiver of design.
2. **Spike worktree**: `git worktree add ../<repo>-spike-<slug> -b spike/<slug>`
   off the integration branch.
3. **Dispatch one agent** with: the exact change, invariants to preserve
   (output ordering, error propagation, profiling/instrumentation semantics,
   doc comments updated to stay truthful), the targeted verification commands,
   and "do not commit, do not add tests, report exact result lines".
4. **Lead verifies**: build, run the targeted suites yourself or read the
   agent's logs skeptically, then run the empirical demonstration
   (before/after on the same inputs; restart any caching daemons between
   binaries).
5. **Report**: diff summary, suite results, the demonstration numbers, and the
   branch name. Leave the work committed on the spike branch (commit message
   notes it was a oneshot). Offer — do not perform — the retrofit: if the
   change should land durably, the paved path (issue backfill, tests, review,
   PR) can be applied afterward.

## When to refuse

Public API or on-disk format changes, security-sensitive surfaces, anything
multi-day, or work the user clearly wants durable-by-default: say so and
recommend the standard lane instead. Oneshot is for well-scoped, reversible
spikes where the design is already known.
