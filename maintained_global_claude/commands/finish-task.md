---
description: Leave a durable GitHub handoff or completion record for the current task
---

# Finish task

1. Inspect `gh pr view --json state,mergeStateStatus,statusCheckRollup,url`.
2. If the task is incomplete, add a concise handoff to both the PR and issue:
   current state, exact blocker, completed verification, remaining action, and
   worktree/branch name. Apply the `handoff` or `blocked` label with `gh issue edit`.
3. If the PR has merged, close the issue with `gh issue close` only when its
   acceptance criteria are met; include the merged PR URL in the closing comment.
4. Do not delete worktrees or branches with uncommitted work. Cleanup is local
   and only after the branch is safely merged.
