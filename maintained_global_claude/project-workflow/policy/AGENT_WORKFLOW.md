# Agent project workflow policy

This is the canonical, client-neutral policy. The generated `CLAUDE.md` and
future `AGENTS.md` must preserve these requirements.

1. Work starts from one GitHub Issue. Create and update it with `gh issue`.
2. One issue owns one branch, one Git worktree, and one pull request. Branch
   from `dev` and target `dev` unless the issue explicitly is a release task.
3. Before opening a PR, run `just ci-fast` in that worktree. Open and inspect
   PRs with `gh pr`; inspect failed runs with `gh pr checks`, `gh run watch`,
   and `gh run view --log-failed`.
4. Keep the issue and PR as the durable handoff record. State the goal,
   verification, remaining risks, and the next concrete action. Do not create
   scattered progress markdown files.
5. Do not push directly to `dev` or `main`, force-push shared branches, bypass
   required checks, merge your own PR, or change another task's worktree.
6. Use only `gh` (including `gh api`) for GitHub operations. Validate access
   before work with `gh auth status`; never place tokens or credentials in the
   repository.
7. Fast CI must remain fast. Put full migrations, service integration, and
   browser checks in `ci-deep`; never disguise a failed or unavailable check as
   a passing check.
