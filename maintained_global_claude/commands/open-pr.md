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

Never bypass a required check. Merge the PR yourself only when it qualifies
for fast-lane self-merge — every linked issue carries the `fast-lane` label,
or it is a `chore/policy-sync` PR — AND every check on it is green: then
`gh pr merge --merge` (never squash; per-issue commits must survive).
Everything else waits for a separate review agent.
