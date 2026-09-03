---
description: Leave a durable GitHub handoff or completion record for the current task
---

# Finish task

1. Inspect `gh pr view --json state,mergeStateStatus,statusCheckRollup,url`.
   If the PR is mergeable-green (required checks passing; any advisory red
   verified pre-existing on the base branch) but unmerged and qualifies for
   self-merge (every linked issue labeled `fast-lane`, or any `chore/<slug>`
   PR, including `chore/policy-sync`), merge it now with `gh pr merge --merge`
   (`--rebase` if the repo forbids merge commits; never squash) before
   continuing.
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

## Concurrent-lane cleanup (mandatory, immediately after `pre-dev` → `dev` merges)

Run this checklist, not an ad hoc subset — only branches whose commits are now
on `dev` are deleted; an unmerged branch is reported, never deleted:

```
git push origin --delete pre-dev
git branch -D pre-dev
for b in <merged-worker-branch-1> <merged-worker-branch-2> ...; do
  git push origin --delete "$b"
  git branch -D "$b"
done
git worktree remove <pre-dev-worktree>
git worktree remove <worker-worktree-1>
git worktree remove <worker-worktree-2>
...
git worktree prune
git worktree list   # verify nothing from the wave lingers
git branch -a       # verify nothing from the wave lingers
```
