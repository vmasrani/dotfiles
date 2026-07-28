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
5. Claim the work:
   - Strict lane: post a concise claim comment through `gh issue comment`
     naming the branch and worktree.
   - Fast lane: assign every batched issue with
     `gh issue edit <n> --add-assignee @me`, then post ONE claim comment on
     the lowest-numbered issue listing the full batch, the branch, and the
     worktree. No per-issue claim comments.
   No other session may work on a claimed issue without an explicit handoff.

Do not create a PR yet. Work only in the new worktree. In a fast-lane batch,
land each issue as its own commit referencing its issue number, and eject any
issue that turns out non-mechanical (drop its commits, remove its `fast-lane`
label, unassign it, comment why) rather than letting it stall the batch.
