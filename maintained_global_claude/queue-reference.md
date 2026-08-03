# queue — full reference

Split out of the global `CLAUDE.md` (2026-07-27) so the Rust-only queue manual stops
riding along on every Python/frontend session; rewritten for the `testq` → `queue` rename
(2026-08-03). The four rules that prevent real mistakes stayed in `CLAUDE.md`; everything
below is lookup material — read it when you actually need it.

## Semantics

`queue X` behaves exactly like `X` — it blocks until a slot frees, then runs in-process: live streamed stdout/stderr (kept separate), the command's own exit code, inherited cwd/env/stdin. It is a queue, not a sandbox. While waiting, a heartbeat line on stderr (every `QUEUE_HEARTBEAT` seconds, default 30) names the job blocking you and estimates the remaining wait from that command's median runtime — without it the wrapper goes silent for the length of the queue, which reads as a hang and provokes callers into re-running the job.

You type the prefix yourself; nothing rewrites your command. `unqueued_heavy_guard.py` (PreToolUse) **denies** — never rewrites — an unqueued `cargo test|nextest|bench|miri` or `just test*|bench*|ci-fast|ci-deep`, and names the corrected form. It deliberately does NOT flag `cargo check|clippy|build|install` or `just lint*`: those are meant to stay unqueued and instant. A denier is allowed to be an imperfect keyword table because both of its error directions are cheap — a miss is just "no hook", an over-match costs one retype and shows its reasoning. The old rewriter was not allowed to be imperfect, which is why it grew a classifier that had to stay in sync with a second one inside the queue.

A queued job runs with `QUEUE_ACTIVE=1`; `queue` seeing that set runs the command directly instead of enqueuing, so a queued `just test` whose recipe itself calls `queue` can't deadlock waiting on capacity its own parent holds.

## The `&&` trap

    queue cd /repo && cargo nextest run     # WRONG

The shell splits on `&&` before `queue` is ever exec'd, so `queue` receives only `cd /repo`, queues that, exits — and the suite then runs completely unqueued. `queue` is structurally blind to this; the operator never reaches it. Pass the whole thing as ONE quoted argument instead — a single argument containing whitespace or shell metacharacters is run via `zsh -c`:

    queue 'cd /repo && cargo nextest run'

The same applies to `|`, `;` and `>`. A leading `FOO=bar` is fine either way, since the assignment is exported into the queue process and inherited by the job. The hook is the second defence: it sees the raw command string, the only vantage point from which "you queued the wrong half" is visible at all.

## Flags

- `queue -l` (or `--watch` for live view) — show waiting / running / finished jobs
- `queue --status --last` — full record of your own most recent job: command, cwd, slot cost, timings, exit code
- `queue --exit-code --last` — ground-truth exit code (use after any piped output)
- `queue --ahead` — how many jobs a new submission would wait behind
- `queue --solo <cmd>` — take every slot and run alone; `queue --priority <cmd>` — jump the queue (for work a human is waiting on)
- `queue --events <cmd>` — detached mode emitting machine-readable `QUEUED`/`RUNNING`/`DONE` lines (pairs with Monitor); output goes to the `out=` file instead of streaming — notifications or streaming, not both
- `queue --slots [N]` shows, or sets for this session, how many jobs may run at once; `queue -- <cmd>` if the command starts with a flag; `--clear` forgets finished jobs; `--kill` stops the daemon (not a running job)
- Env knobs: `QUEUE_SLOTS` (default 1), `QUEUE_NO_DEDUP=1` opts out of coalescing, `QUEUE_QUIET=1` silences the heartbeat
- Obsolete: `queue --budget` errors outright; `QUEUE_BUDGET`/`TESTQ_BUDGET` and `QUEUE_WEIGHT`/`TESTQ_WEIGHT` are ignored with a loud warning rather than honoured — a `12` that meant twelve weight units would now mean twelve concurrent suites. `testq` itself is a gravestone script that exits 127 pointing at `queue`.

## Slots — the whole scheduling model

`QUEUE_SLOTS` (default 1) jobs run at once. Every job costs exactly one slot; `--solo` costs all of them, so it runs with the machine to itself. That is the entire policy — there is no weight table and nothing inspects your command to decide what it is.

The weighted budget it replaced existed only because the old PreToolUse hook FORCED `cargo check` into the queue, where a flat FIFO could park it 9 minutes behind a suite; weights (check 3, suite 9, bench 12, against a 12-unit budget) plus a classifier were the fix for that. Queueing is now explicit, and nobody types `queue cargo check` — it never enters the queue, so it cannot queue behind anything. The latency the weights bought is recovered by NOT queueing rather than by weighing, and both classifiers became answers to a question no longer asked.

The default is 1, not 2, because a single suite already runs at ~9x parallelism on 10 cores (MEASURED 2026-07-20: 2,930 s CPU / 323 s wall) and memory is the real cliff — the 1 GB bench peaks near 7.5 GB RSS against ~13 GB usable, so two heavy jobs mean swap, and swap means suites that never finish. With nothing classifying commands, a slot count of 2 means "two SUITES may overlap", precisely the collision this tool exists to prevent. Raise it only after measuring peak RSS, and prefer `--solo` over lowering it again.

An empty queue is deliberately not fast-pathed: "nothing is running, so exec directly" is a check-then-act race where two agents both observe an empty queue and both start heavy jobs, unaccounted — and it would save milliseconds of socket round-trip against jobs measured in minutes.

Byte-identical commands in an unchanged tree coalesce: followers attach to the leader's output and exit code instead of re-running. The key includes HEAD plus a dirty-file fingerprint, so a tree that has moved never coalesces. Scheduling round-robins across sessions, so one agent's fan-out can't starve others.

## Settled — don't re-investigate

Measured, closed questions:

- clippy does NOT thrash build artifacts
- sccache never shares across worktrees (upstream gap)
- CoW-seeding a target dir saves only ~12 s — not worth orchestration
- Agents share one warm `target/` per worktree — `cargo-slot` only matters if you raise the slot count
