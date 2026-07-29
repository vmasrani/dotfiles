---
description: Deduplicate, consolidate, and fast-lane-label open issues, then emit the batches to start
---

# Triage

The missing front half of the lifecycle. `/start-task` assumes an issue that is
already the right size and already correctly labeled; nothing else makes that
true. This does.

Run it when a session has filed **3 or more** issues it did not start with, or
at the head of a work block over whatever accumulated since the last pass.
Triage is a separate ACT from implementation: it runs over **two or more**
unlabeled issues, **before any branch exists for them**. Never label an issue
whose branch you are already holding, and never label a lone issue to unlock
light ceremony for work already underway — that is the one thing the
separate-act rule exists to prevent.

Arguments: optional issue numbers to restrict the pass to. Default: every open,
unassigned, unlabeled issue.

## Phase 1 — Load

1. `gh auth status`, then
   `gh issue list --state open --limit 200 --json number,title,labels,assignees,createdAt,body`.
2. Drop issues that are assigned, already labeled `fast-lane`, or already have
   a branch (`git branch -a --list '*issue-<n>-*' '*batch-*<n>*'`). Those are
   claimed; triage does not touch claimed work.
3. Also load the last ~30 days of CLOSED issues
   (`gh issue list --state closed --limit 100 --json number,title,closedAt`).
   Deduplication that only looks at open issues re-files everything that was
   just fixed.

## Phase 2 — Deduplicate by invariant, not by symptom

This is the phase that pays for the command. Issues arrive worded as the
symptom the agent tripped over, so near-duplicates do not look alike:

> `zsh shebang, ubuntu has no zsh` · `npm ci skipped when node_modules exists`
> · `six vitest files no recipe runs` · `test-engine exits 0 when tests skip`

Four titles, one invariant: **a check that cannot run reports success.** Those
were four separate branches, PRs, CI runs, and reviews.

For each issue ask: *what rule does this violate?* Group by the answer, not by
the words. Then for each group of 2+:

- Keep the lowest-numbered issue. Retitle it to name the invariant.
- Fold the others in as a checklist of instances, each citing its issue number.
- Close the folded issues as duplicates
  (`gh issue close <n> --reason "not planned" --comment "Folded into #<lead> — same invariant: <rule>"`).
- Say in the lead issue's body what the shared fix is, if one exists. Four
  recipes that each need the same guard want one guard, not four patches.

## Phase 3 — Class-vs-instance sweep

For each surviving issue that describes a *specific* defect, ask whether it is
one instance of a rule the codebase should enforce everywhere. When it is:

1. Sweep for the siblings — one `rg` over the pattern, bounded (`-n -m 40`).
2. Rewrite the issue as the invariant, with the inventory of current violations
   as its checklist.
3. If the sweep returns only the one hit, say so in the issue. That is evidence
   the instance IS the class, and it is worth recording.

A fix that lands for one filename and leaves the same defect for every other
filename is not a fix; it is a second issue, filed later, by someone else.

## Phase 4 — Label by predicate

Apply `fast-lane` only when ALL four hold. Post the four answers as a comment
on the issue so the grant is auditable and a later reviewer can check it:

1. Is the complete file list knowable before writing any code, and ≤3 files?
2. No new public interface, no schema/data-format change, no new dependency?
3. Is the acceptance criterion an existing check, or one new assertion?
4. Is it independent of the design work of the session that filed it?

Any "no", or any uncertainty, means no label — the strict lane is the default
and costs nothing but a review. Then
`gh issue edit <n> --add-label fast-lane`.

Do not label an issue you are about to implement in the same act. File, triage,
then start — in that order, as three distinct steps.

## Phase 5 — Emit the batches

Group the newly labeled issues into batches of **2–4** by the subsystem they
touch, not by number order — a batch whose issues touch disjoint files is a
batch whose commits cannot conflict. Print the commands to run:

```
/start-task 131 136 137      # web test gate: lockfile, shebang, freshness
/start-task 150 164          # fail-loud guards: test-engine, hydrate
```

Leave everything unlabeled in the strict lane and say how many stayed there.
A triage pass that labels everything has not triaged; it has capitulated.

## Report

Terse, to the user:

- issues examined, and how many were skipped as already-claimed
- duplicate groups found, with the invariant each names, and the cycle count
  saved (a folded group of N saves N-1 full issue→PR→CI→review cycles)
- issues rewritten from instance to class, with the sweep counts
- issues labeled `fast-lane`, and how many stayed strict
- the `/start-task` batch commands, ready to run

Never open a branch, never start work, never edit code in this pass. Triage
that slides into implementation is not a separate act.
