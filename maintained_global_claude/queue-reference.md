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
- `queue --cancel <id|label|--last>` — drop a **queued** job. Always use this rather than a bare `ts -r <id>`: `ts` on its own talks to task-spooler's *default* socket, not the queue's, so the removal is addressed to a daemon that never heard of the job and fails with "The job cannot be removed" — which reads as a stuck job rather than a misaddressed one. It refuses a job that is already **running** and prints the exact `TS_SOCKET=… ts -k <id>` to run instead; it never kills anything itself. A foreign job with no queue record is still cancellable by id.
- `queue --triage` — **report only**, exits 0, cancels nothing. Walks the queued+running jobs and flags three things: *duplicates* (same effective cwd and same command, normalised for a trailing `2>&1`) with the `queue --cancel` line for the later ones; *same target dir* (distinct jobs contending for one `target/` — overlap, reviewed by a human, since true subset detection would need test-filter semantics); and *needn't be queued* (`cargo clippy|check|build`, `just lint*` — the keep-instant category). A job with no record is listed as unidentifiable, never guessed at. A clean queue prints an explicit "nothing to flag" line.
- `queue --slots [N]` shows, or sets for this session, how many jobs may run at once; `queue -- <cmd>` if the command starts with a flag; `--clear` forgets finished jobs; `--kill` stops the daemon (not a running job)
- Env knobs: `QUEUE_SLOTS` (default 1), `QUEUE_NO_DEDUP=1` opts out of coalescing, `QUEUE_QUIET=1` silences the heartbeat, `QUEUE_QUICK_RATIO` (default 3) is the shortest-job-first threshold below
- Obsolete: `queue --budget` errors outright; `QUEUE_BUDGET`/`TESTQ_BUDGET` and `QUEUE_WEIGHT`/`TESTQ_WEIGHT` are ignored with a loud warning rather than honoured — a `12` that meant twelve weight units would now mean twelve concurrent suites. `testq` itself is a gravestone script that exits 127 pointing at `queue`.

## Slots — the whole scheduling model

`QUEUE_SLOTS` (default 1) jobs run at once. Every job costs exactly one slot; `--solo` costs all of them, so it runs with the machine to itself. That is the entire policy — there is no weight table and nothing inspects your command to decide what it is.

The weighted budget it replaced existed only because the old PreToolUse hook FORCED `cargo check` into the queue, where a flat FIFO could park it 9 minutes behind a suite; weights (check 3, suite 9, bench 12, against a 12-unit budget) plus a classifier were the fix for that. Queueing is now explicit, and nobody types `queue cargo check` — it never enters the queue, so it cannot queue behind anything. The latency the weights bought is recovered by NOT queueing rather than by weighing, and both classifiers became answers to a question no longer asked.

The default is 1, not 2, because a single suite already runs at ~9x parallelism on 10 cores (MEASURED 2026-07-20: 2,930 s CPU / 323 s wall) and memory is the real cliff — the 1 GB bench peaks near 7.5 GB RSS against ~13 GB usable, so two heavy jobs mean swap, and swap means suites that never finish. With nothing classifying commands, a slot count of 2 means "two SUITES may overlap", precisely the collision this tool exists to prevent. Raise it only after measuring peak RSS, and prefer `--solo` over lowering it again.

An empty queue is deliberately not fast-pathed: "nothing is running, so exec directly" is a check-then-act race where two agents both observe an empty queue and both start heavy jobs, unaccounted — and it would save milliseconds of socket round-trip against jobs measured in minutes.

Byte-identical commands in an unchanged tree coalesce: followers attach to the leader's output and exit code instead of re-running. The key includes HEAD plus a dirty-file fingerprint, so a tree that has moved never coalesces. A **trailing `2>&1` is normalised away** before hashing — merging the streams changes what the caller sees, never what the run produces, and the follower is replayed the leader's separately-captured stdout and stderr either way. Nothing else is normalised: `> file` and `2>/dev/null` are genuinely different work. Scheduling round-robins across sessions, so one agent's fan-out can't starve others.

### Shortest-job-first promotion, and what the duration history is keyed on

A queued job may jump the jobs ahead of it when **every** queued job ahead has a measured median at least `QUEUE_QUICK_RATIO` (default 3) times its own, and its `target/` is not already locked by something running. It is the third promotion rule, after anti-affinity and fair-share, and all three share one flag: **at most one promotion per job, ever**, whichever rule fires. That single-shot budget is what bounds starvation — a suite can be jumped once, not repeatedly by a stream of quick jobs.

This is not the deleted weight classifier returning. The classifier read the command *text* and decided what it must be; this reads `history_median` for the exact keys involved and nothing else. A command the queue has never run has **no** median, and an unknown median blocks the promotion rather than defaulting — an unseen command is far likelier to be a suite than a one-liner.

Which means the history has to actually accumulate, so a job's duration key is `<repo> <display command>`: the repo is git's *common* dir (shared by every worktree of one repo), and the command is the unwrapped, `cd`-stripped form. Worktrees here are created per issue and deleted with it, and the old key — the submitter's `$PWD` plus the raw argv — gave every fresh worktree an empty history for a command that had run twenty times next door, and keyed `queue 'cd /wt-9 && just ci-fast'` apart from `just ci-fast` on top of that. Rows written under the old key simply orphan and age out with the weekly prune.

## Settled — don't re-investigate

Measured, closed questions:

- clippy does NOT thrash build artifacts
- sccache never shares across worktrees (upstream gap)
- CoW-seeding a target dir saves only ~12 s — not worth orchestration
- Agents share one warm `target/` per worktree — `cargo-slot` only matters if you raise the slot count
