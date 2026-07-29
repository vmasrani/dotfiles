---
description: Run fast checks and open the current issue-owned or batch branch as a PR into dev
---

# Open PR

1. Confirm the current branch is not `dev` or `main`, and read the linked
   issue — for a `batch-*` branch, every issue in the batch.
2. Run `just ci-fast` in the current worktree. It must be green before you go on.
   A check that cannot run must be visibly absent from the recipe, never a step
   that prints `not applicable` and passes; a broken check must fail loudly.
3. Inspect `git diff origin/dev...HEAD`, commit only the intended files, and
   push with `git push -u origin HEAD`. On a batch branch, verify each issue's
   change is its own commit referencing that issue number before pushing.
4. Open the PR with `gh pr create --base dev --fill --body-file .github/pull_request_template.md`.
   Replace template placeholders with the issue link, verification, and handoff.
   For a batch PR the body must carry one `Closes #<n>` line per batched issue
   plus a per-issue checklist — what changed, which commit, how verified — so
   the reviewer reviews per issue, not one blob.
5. Report the PR URL with `gh issue comment`: on the issue (strict lane) or on
   the batch's lowest-numbered issue only (fast lane).

## Chore branches

On a `chore/<slug>` branch there is no issue: skip the issue read in step 1 and
the issue comment in step 5. The PR body carries NO `Closes #` line. Instead it
states in one or two lines what changed and that the chore-lane criteria are
met — no behavior change, no decision to explain, mechanically re-derivable or
externally forced, nobody would search for why it happened. `just ci-fast` must
still be green before pushing, and the author self-merges on mergeable-green
per rule 6, same bar as the fast lane.

Never bypass a required check. Merge the PR yourself only when it qualifies
for self-merge — every linked issue carries the `fast-lane` label, or it is
any `chore/<slug>` PR (including `chore/policy-sync`) — AND it is
mergeable-green (required
checks passing; an advisory red blocks only if this PR introduced it): then
`gh pr merge --merge`, or `--rebase` if the repo forbids merge commits
(never squash; per-issue commits must survive).
Everything else waits for a separate review agent.
