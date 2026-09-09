---
name: quickly
description: Fast lane for small, low-risk changes (UI/cosmetic, output formatting, docs, tooling) — no issue, no worktree, no PR, no test run; make the change and commit directly on dev. Use when the user says "/quickly", "just do it on dev", "no PR", "skip the tests, it's UI only".
---

# /quickly — small change, straight onto `dev`

The user has explicitly opted out of the issue → worktree → PR → CI lifecycle
for THIS change. This skill is that standing authorization: do not re-ask, do
not file, do not branch, do not open a PR, do not run test suites.

Usage: `/quickly <what to change>` — optionally ending in `push` to also push.

## Eligibility (one-line judgment, then proceed)

Intended for changes no test asserts on: progress bars / spinners / rendered
strings, help text, log wording, docs, comments, scripts, tooling, small
refactors that move no expected value. If the change touches core logic, a
storage/wire format, or a test's expected value, say so in ONE line ("this
reaches past UI — still doing it on dev as asked") and continue. The user
chose the lane; your job is to flag, not to block.

## Steps

1. **Land on `dev`.** `git rev-parse --abbrev-ref HEAD`; if not on `dev`,
   `git checkout dev`. If the tree has unrelated uncommitted changes, leave
   them untouched and commit only the files you modify. Never create a
   worktree or a branch.
2. **Make the smallest diff that does the job.** Same code rules as always
   (fail loud, no defensive fallbacks, zero jargon in rendered strings). The
   session-model rules still apply: if the session model is Fable, a
   sonnet/opus worker writes the code; Fable reviews the diff.
3. **Static gate only — never a test run.**
   - Rust: `cargo check --all-targets && cargo clippy --all-targets -- -D warnings`
     (unqueued — these are the instant ones).
   - Python: `uv run ruff check` (+ `uv run pyright`/`mypy` if the project
     configures one).
   - Otherwise: whatever instant lint the justfile exposes (`just lint*`).
   - NEVER `cargo test`, `just test*`, `just ci-fast`/`ci-deep`, `pytest`, or
     any `queue`'d suite. If the static gate is red, fix it — it is the only
     gate, so it must be green.
4. **Commit on `dev`.** `git add <only the files you changed>` (never `-A`);
   conventional message (`feat(scope): …` / `fix(scope): …` / `docs: …`) with
   a 1–3 line body saying why. No `Co-Authored-By` line. Verify with
   `git rev-parse HEAD` before/after — a commit that didn't happen is not
   "done".
5. **Push only if asked.** Default is a local commit on `dev`. If the
   invocation or the conversation says `push`, `git push origin dev`
   (this is the one place a direct push to `dev` is authorized — by the
   user, for this change). Otherwise stop and tell the user it is local.

## Never

- File an issue, write a handoff/progress markdown, open a PR, run `/open-pr`
  or `/check-pr`.
- Run a test suite or queue anything "just to be safe".
- Rebase, squash, amend published history, or touch `main`.

## Report (≤6 lines)

`<short SHA>` · files changed · static gate: green/fixed · pushed: yes/no ·
one line on anything flagged (eligibility or left undone).
