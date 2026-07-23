---
description: Inspect and repair CI failures for the current pull request using gh
---

# Check PR

1. Run `gh pr checks --watch`; use `gh run list --branch "$(git branch --show-current)"`
   to identify a failed run.
2. Read only failed evidence with `gh run view <run-id> --log-failed`.
3. Fix the failure in this worktree, rerun the relevant local fast recipe, push,
   and use `gh pr checks --watch` again.
4. Post a short issue/PR comment when the failure was non-obvious: cause, fix,
   and verification.

Do not rerun a flaky check without understanding why it failed, and do not
modify a different task's branch.
