---
description: Leave a durable GitHub handoff or completion record for the current task
---

# Finish task

1. Inspect `gh pr view --json state,mergeStateStatus,statusCheckRollup,url`.
2. If the task is incomplete, add a concise handoff to both the PR and issue
   (for a batch, the lowest-numbered issue): current state, exact blocker,
   completed verification, remaining action, and worktree/branch name. Apply
   the `handoff` or `blocked` label with `gh issue edit`.
3. If the PR has merged:
   - Strict lane: close the issue with `gh issue close` only when its
     acceptance criteria are met; include the merged PR URL in the closing
     comment.
   - Fast lane: the PR's `Closes #<n>` lines auto-close the batch on merge.
     Verify every batched issue actually closed
     (`gh issue view <n> --json state`) and close stragglers with the merged
     PR URL. If a batched issue's acceptance criteria are NOT met, reopen it,
     remove its `fast-lane` label, and comment what remains.
4. Do not delete worktrees or branches with uncommitted work. Cleanup is local
   and only after the branch is safely merged.
