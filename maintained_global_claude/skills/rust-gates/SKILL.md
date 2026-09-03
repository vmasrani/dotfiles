---
name: rust-gates
description: Rust build/test/bench doctrine — the `queue` prefix rules, sccache/cargo-clean policy, test-count reconciliation, benchmark economy (never re-measure stored numbers), and the multi-worker integration-branch workflow. Load BEFORE the first cargo test/nextest/bench, `just test*|ci-fast|ci-deep`, `queue` call, benchmark/profile run, or Rust wave dispatch in a session — and put "run /rust-gates first" in every Rust worker prompt. Self-invoke; do not wait to be asked.
---

# Rust / build-gate doctrine

Binding for any Rust repo or queued build/test/bench gate. Kept out of the always-loaded `CLAUDE.md` only because most sessions never touch Rust. The incident log behind each rule: `~/dotfiles/maintained_global_claude/notes/lessons.md`.

## The job queue (`queue`)

**Add the `queue` prefix yourself** on `cargo test|nextest|bench|miri` and `just test*|bench*|ci-fast|ci-deep` — nothing rewrites your command; a PreToolUse hook only DENIES unqueued ones. `queue X` behaves exactly like `X` (waits for a free slot, streams live output, returns X's own exit code). Leave `cargo check|clippy|build` and `just lint*` unqueued — that's what keeps them instant.

- Compound commands go as ONE quoted string — `queue 'cd /repo && cargo test'`, never `queue cd /repo && cargo test` (the shell splits on `&&` first).
- A pause before output is the QUEUE, not a hang — check `queue -l`, never re-run. Run long suites detached (`run_in_background`).
- `| tail` destroys the exit code — read `queue --exit-code --last` before claiming a pass.
- Agents write, the lead builds — ONE process compiles and runs the suite.
- Everything else — cancel/`--triage` semantics, SJF jumping, `--solo`, slots, coalescing, the settled don't-re-investigate list: `~/dotfiles/maintained_global_claude/queue-reference.md`.
- **Prefer `queue cargo nextest run --workspace` over `cargo test`.** Fail-fast is off via the seeded `.config/nextest.toml` (sweep-then-assert); per-job parallelism is capped by `NEXTEST_TEST_THREADS` (cpus/`QUEUE_SLOTS` from `.zshenv`) — never pass `-j`/`--test-threads` ad hoc. Reconcile counts from nextest's `Summary [ … ] N tests run: N passed` line. `cargo nextest list|--version|show-config` and `cargo test --list` are read-only and run unqueued.

## Cargo — never compile the same dependency twice

sccache is wired machine-wide (`~/.cargo/config.toml` → `rustc-wrapper`): it de-dupes rebuilds WITHIN one worktree+target dir (branch switch, `cargo clean -p`, profile flip), NOT across worktrees or agents: measured 2026-09-02 on fast-delta, 62 Rust units — same worktree+same target dir 62/62 hits (24 s → 8.5 s), different worktree 0 hits, same worktree but a different explicit `CARGO_TARGET_DIR` 0 hits. sccache 0.15–0.17 hashes rustc’s cwd and every `CARGO_*` env var into the key; the upstream fix (mozilla/sccache PR #2794) is unmerged. Each worktree pays its own dependency build once. Workspace crates stay incremental per target dir (`CARGO_INCREMENTAL=0` only inside `cargo-slot`; do not export it globally — it buys no cross-agent reuse and slows the edit loop). On a machine where `command -v sccache` fails, install it and add the wrapper line before any Rust work.

- **One worktree per batch** — N worktrees × cold `target/` is where the remaining rebuild time goes.
- **Never `cargo clean` to "fix" a problem** — it discards hours of workspace compilation on a hunch. The sanctioned forced rebuild (test count went DOWN → binary lacks your code) is `cargo clean -p <crate>` scoped to the suspect crate, never a full wipe.
- **Keep flags stable.** Ad-hoc `RUSTFLAGS`, feature-set changes, and profile edits invalidate caches tree-wide; flags live in `.cargo/config.toml`/justfile, never per-command env vars.
- **Pin the toolchain** (`rust-toolchain.toml`) so sibling worktrees don't silently rebuild the world on rustc drift.
- **Settled — don't re-investigate a shared `CARGO_TARGET_DIR` across worktrees:** cargo's target-dir lock would serialize the unqueued `check`/`clippy` calls that are kept instant on purpose; sccache already de-dupes the expensive part without lock contention.

## Evidence discipline for build/test gates

The language-agnostic core (never pipe a run, grep the log, conditional markers) lives in `CLAUDE.md`. These are the gate-specific additions:

- **Reconcile the test COUNT against an explicit baseline every run** (e.g. `main @ 4ee8817 = 1502`). A count that goes DOWN without deletions means the binary doesn't contain your code — force a rebuild (`cargo clean -p <crate>`).
- **Capture in full and end the command with the run's own status:**

      <cmd> > /tmp/run.log 2>&1; rc=$?; echo "exit=$rc" | tee -a /tmp/run.log; exit $rc

  The `echo "exit=$?"`-only form leaves the SHELL exiting 0, and a `run_in_background` completion notification carries only that process status — it will announce success for failed runs. The trailing `exit $rc` is the entire fix; a `( … )` subshell does not help.
- **A background task's reported exit code is the wrapper's, not the command's.** Grep the log for both the status line and `rg -n 'FAIL|test run failed|^error'`.
- **Verify a test filter selected what you think.** A pass over zero tests is a pass. Prefer positional filters; with `-E` expressions, confirm a non-zero expected count first.
- **Re-run the full suite on the MERGED result** — per-branch greens don't cover the combination. Run it ONCE, by the agent who merges; never two identical full gates on the same SHA.

## Benchmark economy — never re-measure what you already have

Every solo-queue benchmark/profile run must be justified by a question ONLY that run can answer — an unnecessary 30–60 min solo job stalls every session on the machine, twice over when it later gets re-run.

- **Before enqueueing any expensive run, check for existing numbers first** — search the durable results dir (experiment CSVs/logs) for the same (commit SHA, corpus, flags). Re-measuring stored results is a bug, not diligence.
- **Baseline (control) runs are gated on evidence the change can affect them.** Run the treatment build FIRST with mechanism counters enabled; run the baseline ONLY for inputs where the counters show the changed code path actually executed. A pre/post pair where the diff'd code never runs measures noise at full price.
- **Persist every expensive result durably at birth** — CSV/log named with commit SHA + corpus + flags, in the shared experiment dir, never only /tmp or a session transcript. A number that isn't stored WILL be re-bought at full price.
- **Plans and handoffs must carry the reuse map:** which numbers already exist, where, and at what SHA — so the next session extends the dataset instead of regenerating it.

## Multi-worker waves — pre-dev integration FIRST, measure, THEN review

Standard workflow for every multi-worker wave (user mandate 2026-08-20; this
is the Rust instance of the global "Concurrent work = pre-dev integration"
rule in CLAUDE.md — same branch name, same single-gate discipline, plus the
perf-specific measurement step below):

- Workers push branches that compile + pass the exact clippy line + their narrow tests, and NEVER run their own full gates (ci-fast / test-sql / yardstick), queued or not.
- An integrator builds ONE `pre-dev` branch = dev + every worker branch (stacked ones in order, `git merge --no-ff` per worker so per-issue commits survive), flips whatever fixture/feature switches the wave needs, and runs the wave's HEADLINE measurement first (perf wave → the release benchmark/yardstick on re-pressed fixtures; other waves → the acceptance harness that motivated them).
- Only if that result is worth shipping: ONE full gate on that SHA (`queue just ci-fast` in the pre-dev worktree), then the integrator (or each author) merges `pre-dev` into `dev` via a single PR — no separate review agent. Not good → fix on the worker branches, re-merge into `pre-dev`, re-measure.
- Review effort is never spent on a result that doesn't move the number; the `pre-dev` branch IS the batch.
- **No author≠merger rule.** The agent that wrote a PR may review and merge it into `dev` itself once the pre-dev gate is green. The ONLY merge that needs someone else is `dev → main`, which remains the user's alone. Repos still carrying the old "separate review agent" clause in `.agent-workflow/AGENT_WORKFLOW.md` are stale — sync the kit policy rather than obeying them.
- Cleanup after the merge is mandatory, not optional: delete `pre-dev` and every merged worker branch locally and on the remote, remove their worktrees, `git worktree prune`.
