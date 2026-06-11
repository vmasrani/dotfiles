---
description: Finish-line review of the current changes (parallel), then commit
---

Run after a major feature or refactor. Goal: the change is fully integrated,
passes the quality bars, the project's context files stay fresh, and the work
lands as a clean conventional commit — **without scope creep, and without
wasting wall-clock**.

The design principle: do the slow things **concurrently**. The two reviewers,
the build/test, and any context refresh are independent and all run in a single
fan-out, so adding review dimensions costs tokens but ~zero extra time. Never
serialize work that has no dependency.

# Phase 0 — Prep (cheap, sequential)

1. `git diff --stat` (and `git status`) — snapshot the change set every later
   step reviews. If the tree is already committed, diff against the feature's
   merge-base instead.
2. Compute the **context-refresh set**: the directories touched by this change
   (`git diff --name-only | dirname | sort -u`) **intersected with**
   `ctx-stale .` output (MISSING/STALE). This is usually 0–3 dirs. Do NOT
   refresh every stale dir in the repo — a repo can have dozens; you only own
   the ones this change touched.
3. Pick the **reviewer model tier** from the `git diff --stat` totals: default
   `sonnet`; use `opus` for a large or high-stakes change (rough trigger:
   > ~40 files or > ~2,000 changed lines). Match the tier to the cost of a
   missed bug, not to the line count alone — a small change to a
   security/payments/migration path also warrants `opus`.

# Phase 1 — Format (instant, mutating, sequential)

Apply the formatter only — it's instant and makes the diff the reviewers see
stable. Touch only files you changed; never `vendor/` or generated code.
- **Rust:** `cargo fmt --all`
- **Python:** `uvx ruff format .`

# Phase 2 — Parallel fan-out (ONE message, everything concurrent)

Launch all of the following **in a single message** so they run at once:

- **Build + test, backgrounded** (Bash `run_in_background`): the slow gate.
  - Rust: `cargo clippy --all-targets --all-features -- -D warnings` then the
    test recipe (`just test` if present, else `cargo test`; workspace-excluded
    crates need their own `--manifest-path` run). Zero warnings is the bar.
  - Python: `uvx ruff check . && uvx ty check` then the test runner
    (`uv run pytest` / project recipe).
- **`structural-completeness-reviewer` agent** — integration, dead code,
  duplication-that-should-be-consolidated, doc drift. Diff-scoped. Run at the
  Phase-0 reviewer tier (`model: sonnet`, or `opus` for a large/high-stakes diff).
- **`perf-reviewer` agent** — avoidable allocations/copies, complexity
  regressions, lost parallelism, parity-test gaps. Static (no benchmarks),
  diff-scoped. Run at the same Phase-0 reviewer tier as the structural reviewer.
- **`context-researcher` agent × the Phase-0 refresh set** — one per dir, each
  told to rewrite `{dir}/{dirname}-context.md`. Skip this entirely if the set
  is empty.

Reviewers and context agents read the diff, not the whole repo, and return
terse findings/status — that is what keeps token cost bounded.

# Phase 3 — Triage & apply (sequential)

1. Collect clippy/test results + both reviews.
2. Apply the **in-scope** fixes (genuine bugs, dead code the review found, perf
   regressions in this change). List but do NOT auto-apply anything that opens a
   new front — note it for follow-up instead of ballooning the commit.
3. If you changed code, re-run the Phase-1/2 gates (incremental, fast). Confirm
   tests are green before committing.

# Phase 4 — Commit the change

One **conventional commit**, scoped to the crate/module
(`feat(daemon):`, `perf(core):`, `fix(bloom):`, `refactor(...):`, `style:`):
- If on the default branch, create a topic branch first.
- Stage only the intended files (`git add -u` for tracked edits). Keep
  vendored/generated churn out unless it *is* the change.
- Imperative subject ≤ ~72 chars; body explains the **why** and notes what
  verification passed (gates green, reviews clean).
- **Never** add `Co-Authored-By` or any tool-advertisement trailer.

# Phase 5 — Commit refreshed context (only if any were refreshed)

If Phase 2 rewrote any `*-context.md`, commit them separately so the feature
diff stays clean: `docs(context): refresh context files for changed dirs`.
