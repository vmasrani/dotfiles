---
description: Run fast checks and open the current issue-owned branch as a PR into dev
---

# Open PR

1. Confirm the current branch is not `dev` or `main`, and read the linked issue.
2. Run `just ci-fast` in the current worktree. A check that does not apply must
   visibly report `not applicable`; a broken check must fail.
3. Inspect `git diff origin/dev...HEAD`, commit only the intended files, and
   push with `git push -u origin HEAD`.
4. Open the PR with `gh pr create --base dev --fill --body-file .github/pull_request_template.md`.
   Replace template placeholders with the issue link, verification, and handoff.
5. Report the PR URL to the issue with `gh issue comment`.

Never merge the PR yourself or bypass a required check.
