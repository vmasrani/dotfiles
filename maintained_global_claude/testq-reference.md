# testq — full reference

Split out of the global `CLAUDE.md` (2026-07-27) so the Rust-only queue manual stops
riding along on every Python/frontend session. The four rules that prevent real
mistakes stayed in `CLAUDE.md`; everything below is lookup material — read it when you
actually need it.

## What the hook does

A PreToolUse hook rewrites heavy cargo/just commands (`cargo nextest|test|build|check|clippy|bench|install|miri`, `just test*|bench*|lint*`) into `testq zsh -c '<cmd>'` — a machine-wide weighted queue shared by every agent and repo. **Never add the prefix yourself** — the hook applies it quote-safely and never double-wraps. Trivial verbs (`fmt`, `metadata`, `tree`, `add`, …) stay instant and unqueued.

## Semantics

`testq X` behaves exactly like `X` — it blocks until there's capacity, then runs in-process: live streamed stdout/stderr, the command's own exit code, inherited cwd/env/stdin. While waiting, a heartbeat line on stderr (every 30 s) names the job blocking you and estimates the remaining wait.

## Flags

- `testq -l` (or `--watch` for live view) — show waiting / running / finished jobs
- `testq --status --last` — full record of your own most recent job: command, cwd, weight, timings, exit code
- `testq --exit-code --last` — ground-truth exit code (use after any piped output)
- `testq --explain <cmd>` — what a command would weigh; `testq --ahead` — how many jobs a new submission waits behind
- `testq --priority <cmd>` — jump the queue (for work a human is waiting on)
- `testq --events <cmd>` — detached mode emitting machine-readable `QUEUED`/`RUNNING`/`DONE` lines (pairs with Monitor); output goes to the `out=` file instead of streaming
- `testq -- <cmd>` if the command starts with a flag; `testq --budget` shows the current budget; `--clear` forgets finished jobs
- Env knobs: `TESTQ_WEIGHT=<n>` overrides one job's weight, `TESTQ_NO_DEDUP=1` opts out of coalescing, `TESTQ_QUIET=1` silences the heartbeat

## Scheduling model

Jobs are weighted against `TESTQ_BUDGET` (default 12: fmt/doc 1, check/clippy/build 3, test/nextest 9, bench/miri 12) — one suite plus one check overlap, two suites never do, a bench runs alone. Don't raise the budget without measuring RAM; that's the binding constraint.

Byte-identical commands in an unchanged tree coalesce: followers attach to the leader's output and exit code instead of re-running. Scheduling round-robins across sessions, so one agent's fan-out can't starve others.

## Settled — don't re-investigate

Measured, closed questions:

- clippy does NOT thrash build artifacts
- sccache never shares across worktrees (upstream gap)
- CoW-seeding a target dir saves only ~12 s — not worth orchestration
- Agents share one warm `target/` per worktree — `cargo-slot` only matters if you raise the budget
