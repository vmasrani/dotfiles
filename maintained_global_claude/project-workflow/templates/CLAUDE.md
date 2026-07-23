# Project agent instructions

This project uses the shared GitHub Issue and PR workflow. The canonical policy
is in `.agent-workflow/AGENT_WORKFLOW.md` and is binding.

## Required task lifecycle

1. Confirm access with `gh auth status`; create or claim one issue using `gh issue`.
2. Create an isolated, issue-named worktree and branch from `dev`.
3. Make focused changes; run `just ci-fast` from the project root.
4. Commit focused work, push the branch, and use `gh pr create --base dev`.
5. Use `gh pr checks`, `gh run watch`, and `gh run view --log-failed` to repair
   failed CI on this PR only. Comment the handoff or result on the PR/issue.

Never directly push to `dev` or `main`, merge your own PR, bypass required
checks, force-push shared branches, or leave untracked progress documents.

## Project-specific instructions

Add project architecture, development setup, and test-selection details below.
