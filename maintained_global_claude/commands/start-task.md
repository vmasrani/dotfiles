---
description: Start one GitHub Issue-owned task in an isolated worktree
---

# Start task

Arguments: issue number, optionally followed by a short branch suffix.

1. Run `gh auth status`; stop if the account cannot access this repository.
2. Read `gh issue view $ARGUMENTS` and confirm it has one clear goal and
   acceptance criteria. If it does not, improve the issue before coding.
3. Confirm the repository uses the project workflow with:
   `~/dotfiles/maintained_global_claude/project-workflow/bin/project-workflow check --dir .`
4. Fetch `dev`, then create a worktree outside the primary checkout named for
   the issue and branch `issue-<number>-<short-suffix>` from `origin/dev`.
5. Post a concise claim comment through `gh issue comment` naming the branch
   and worktree. No other session may work on that issue without an explicit
   handoff.

Do not create a PR yet. Work only in the new worktree.
