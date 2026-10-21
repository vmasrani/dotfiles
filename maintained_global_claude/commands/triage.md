---
description: Deduplicate, merge issues that touch the same files, fast-lane-label, then emit parallel waves of batches to start
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

## Phase 4 — Consolidate by file overlap

Phase 2 merges issues that break the same rule. This phase merges issues that
**touch the same files**, even when they break different rules. Run it
automatically on every pass; do not ask first. Two open issues that edit the
same files cannot run in parallel anyway, because they would conflict. Giving
them to one owner on one branch turns that hidden conflict into a planned
sequence.

1. **Map files.** For every surviving issue, record the files or modules its
   remaining work will edit, in a table of issue / files / subsystem. Take them
   from the issue body, linked PRs, and one bounded `rg` per named symbol
   (`-n -m 20`). Mark rows whose file list comes from issue text alone as
   unconfirmed.
2. **Group.** Build groups from shared files. Merge a group of two or more only
   when at least one of these holds, and name which one in the new issue:
   - **Faster implementation:** one owner, one worktree, one gate where there
     would have been several, for example a shared fixture, a shared test
     harness, or one fix that settles several issues.
   - **More parallelism:** after merging, the groups that remain touch
     disjoint files, so separate workers can take them at the same time
     without conflicts.
   - **Less overlap:** the issues repeat, contradict, or depend on each
     other's to-dos, for example "B is A's candidate fix".
3. **Do not merge** when any of these holds; leave the issue on its own and
   give the reason in the report:
   - **Different states:** ready work would be tied to parked, blocked, or
     experimental work. Merge parked with parked only.
   - **Too big:** the merged issue would no longer fit one branch and one PR
     (more than about 5–6 separable features), or would cross crate or package
     boundaries that otherwise split cleanly.
   - **Shared theme only:** the issues share a subject but no files. Merging
     them would serialize work that could run in parallel.
   - **Claimed or excluded:** the issue is claimed (assigned, has a branch, is
     in flight, or is named by an open PR), is an epic, or is a bot-managed
     tracker. An epic stays a parent; point the merged issue at it.
4. **Write the merged issue** so no work is lost:
   - Its title names the shared files or subsystem and what the group
     delivers.
   - Its body opens with the combined plan and the order of work. Then add one
     `### From #N` section per original, carrying every open to-do, number,
     acceptance criterion and owner decision.
   - Copy the to-dos verbatim; rewording loses detail.
   - Mark any open owner decision `**OWNER DECISION:**`.
   - Add a `Supersedes #a, #b, …` line.
   - Union the originals' labels and assignees.
   - If the body would go over GitHub's limit (about 60,000 characters), keep
     the plan in the body and post each `From #N` section as a comment.
5. **Check before closing.** Re-fetch each original and confirm it is still
   OPEN. Check every cross-reference you rely on ("A's leftover work lives in
   B") by reading both issues; never infer the direction. Then create the
   merged issue and close each original:
   `gh issue close <n> --reason "not planned" --comment "Superseded by #<new>, which merges it with issues that touch the same files. Every open to-do, number and decision is carried into #<new>."`
   Script the create-and-close step when there are more than three groups.
   Without a flag the script prints only the plan; it applies it only when
   given an explicit `--go`. Run the dry run first.
6. **Record the parallel plan.** List the issues that remain, single or
   merged, as **waves**. Within a wave, no two issues share a file, so they
   can run at the same time. Phase 6 builds on these waves.

Leaving an issue unmerged is the default when unsure. A merge that hides one
issue's to-do inside another issue's prose costs more than the duplicate
issue did.

## Phase 5 — Label by predicate

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

## Phase 6 — Emit the batches

Group the newly labeled issues into batches of **2–4** by the subsystem they
touch, not by number order — a batch whose issues touch disjoint files is a
batch whose commits cannot conflict. Lay the batches over Phase 4's waves, so
batches in the same wave can start at the same time. Print the commands to
run:

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
- file-overlap merges: one line per merged issue (new number ← originals,
  shared files, which reason from Phase 4 step 2). Also the open-issue count
  before and after, and each candidate group left unmerged with its
  step-3 reason.
- the parallel waves: which issues can run at the same time
- issues labeled `fast-lane`, and how many stayed strict
- the `/start-task` batch commands, ready to run

Then, ALWAYS, a **"What's left"** section: the full inventory of every issue
still open after the pass — not just the ones this pass touched. The user
reads this to know the state of the backlog, so it must be complete and it
must group by what happens next, not by number:

- **Ready to start** — `fast-lane` batches (the commands above) and any strict
  issue that is fully specified and unblocked. One line each: number, a
  plain-language name, and why it is in this bucket.
- **Needs a decision from the user** — issues whose next step is a choice
  only the maintainer can make (cost, scope, API shape). Name the decision
  and give a recommendation.
- **Blocked / waiting on something external** — issues gated on another repo,
  a measurement, or an upstream verdict. Name the gate and how to check it.
- **Parked / experimental** — explicitly deferred or "do not start without
  a go". One line each; do not re-argue them.

Close the section with the non-issue leftovers the pass noticed in passing —
stale branches and worktrees whose PRs merged, downstream pins that lag
`dev`, an unmerged integration branch — each with a one-line verdict
(safe to delete / needs a re-pin / still live). Report these; never act on
them in this pass.

Never open a branch, never start work, never edit code in this pass. Triage
that slides into implementation is not a separate act.
