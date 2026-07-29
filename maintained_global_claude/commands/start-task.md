---
description: Start one issue-owned task, or a fast-lane batch of 2-4 labeled issues, in an isolated worktree
---

# Start task

Arguments: one issue number (strict lane) or 2–4 issue numbers (fast-lane
batch), optionally followed by a short branch suffix.

1. Run `gh auth status`; stop if the account cannot access this repository.
2. Strict lane (one issue): read `gh issue view <n>` and confirm it has one
   clear goal and acceptance criteria. If it does not, improve the issue
   before coding.
   Fast lane (2–4 issues): confirm EVERY issue is open, unassigned, and
   carries the `fast-lane` label. If any issue lacks the label, stop — do not
   add the label yourself (eligibility is a triage decision); run that issue
   as its own strict-lane task instead. Never batch more than 4.
3. Confirm the repository uses the project workflow with:
   `project-workflow check --dir .`
4. Fetch `dev`, then create a worktree outside the primary checkout, branched
   from `origin/dev`: `issue-<number>-<short-suffix>` for a single issue,
   `batch-<n1>-<n2>[-<n3>[-<n4>]]-<short-suffix>` for a batch.
5. Hydrate the worktree. From the PRIMARY checkout (the script resolves the
   primary from the current directory, not from its argument), run
   `.agent-workflow/tools/hydrate-worktree.sh <worktree-path>` whenever that
   script exists. It provisions the gitignored artifacts the suite needs, which
   a new worktree does not have — without them tests SKIP and a skip and a pass
   look identical. A project with no `.agent-workflow/hydrate.manifest` is a
   legitimate case: the script says so on stdout and exits 0. Any NONZERO exit
   is a blocker — the worktree is half-built and its test counts will not match
   the baseline. Fix what it names, or delete the worktree; never start work on
   a tree it refused.
6. Claim the work:
   - Strict lane: post a concise claim comment through `gh issue comment`
     naming the branch and worktree.
   - Fast lane: assign every batched issue with
     `gh issue edit <n> --add-assignee @me`, then post ONE claim comment on
     the lowest-numbered issue listing the full batch, the branch, and the
     worktree. No per-issue claim comments.
   No other session may work on a claimed issue without an explicit handoff.

## Chore mode: `/start-task chore <slug>`

Work too small for an issue — a formatter run, a lockfile regen, a comment
typo, a dependency repin, a regenerated artifact — takes the chore lane. Skip
steps 2 and 6 entirely: there is no issue to read, assign, or comment on.
Run step 3's `project-workflow check`, then create the worktree branched from
`origin/dev` as `chore/<slug>`, and hydrate it per step 5. Confirm all four
eligibility criteria first (no behavior change, no decision to explain,
mechanically re-derivable or externally forced, nobody would search for why it
happened); if any is in doubt, file the issue and use the strict lane instead.

Do not create a PR yet. Work only in the new worktree. In a fast-lane batch,
land each issue as its own commit referencing its issue number, and eject any
issue that turns out non-mechanical (drop its commits, remove its `fast-lane`
label, unassign it, comment why) rather than letting it stall the batch.
