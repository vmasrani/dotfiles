# queue — full reference

Split out of the global `CLAUDE.md` (2026-07-27) so the Rust-only queue manual stops
riding along on every Python/frontend session; rewritten 2026-10-01 for the flock slot gate. The four rules that prevent real mistakes stayed in `CLAUDE.md`; everything
below is lookup material — read it when you actually need it.

## This machine (Linux VM — verified 2026-07-24)

64 threads (2×16-core Xeon Platinum 8280L, 2 threads/core), **503 GB RAM**, ext4 on `/` (497 G)
and `/data` (1 T). Present: `cargo`, `clippy`, `miri`, `rustfmt`, `rust-analyzer`, `just`,
`queue`, `cargo-nextest` (0.9.143) and `sccache` (wired as `rustc-wrapper`) — both verified
2026-09-03; earlier notes saying they were missing are obsolete. Everything below marked *M4* was
measured on the macOS laptop and has **not** been reproduced here — the hardware gap is large
enough to invalidate the reasoning, not just the constants.

- **nextest is the runner here.** `queue cargo nextest run --workspace`; fail-fast is off via the
  seeded `.config/nextest.toml`; `NEXTEST_TEST_THREADS` = cpus / the slot count caps each job so three slots never oversubscribe the box. `cargo nextest
  --version|show-config|self` are read-only and run unqueued; `cargo nextest list|archive` and `cargo test --list|--no-run` compile, so they are queued.
- **sccache is live, so the M4 sccache bullets apply.** It still never shares across worktrees:
  sccache hashes the compile's `cwd` (`SCCACHE_BASEDIRS` covers only the C/C++ path, issue #2652,
  Rust fix unmerged, PR #2678). `SCCACHE_DIR` falls back to `~/.cache/sccache` on Linux
  (`shell/sccache-env.sh`, sourced from `.zshenv`).
- **No copy-on-write.** `/`, `/home` and `/data` are ext4; `cp --reflink=always` fails with
  `Operation not supported`, and macOS `cp -c -R` doesn't exist in GNU coreutils. Seeding a slot
  from a warm `target/` is a full multi-GB byte copy here, not 0.59 s at zero bytes — let slots
  build cold. (The M4 measurement showed only ~12 s of payoff even *with* free cloning, so
  nothing is lost.)
- **`cargo-slot` needs `CARGO_SLOT_ROOT=/data/.cargo-targets`** exported — its built-in default
  `/Volumes/external/.cargo-targets` does not exist here.
- **Cheap jobs overlapping a suite are genuinely free here.** On the M4 a concurrent `cargo check`
  really did take cores from a suite running ~9x parallel on 10 cores; at 64 threads that suite
  leaves ~55 idle.
- **Build-time numbers do not transfer and have not been re-measured.** Reference only: 573-crate
  cold build of parot-core ≈58 s on the M4 (59.8 / 58 / 58). This Xeon has many more cores at a
  much lower clock, so the figure here could land either side. Measure once (`time cargo build
  --workspace`) and write it down instead of reasoning from the M4 value.
- **`QUEUE_SLOTS=3` here since 2026-09-02 (`.zshenv`), still unmeasured.** The old weighted-budget
  reasoning (10 cores / 16 GB, 1 GB bench peaking ~7.5 GB RSS) doesn't describe this machine — 503 GB
  makes even several concurrent suites a small fraction of memory, and `NEXTEST_TEST_THREADS=21`
  keeps 3 slots inside 64 threads. That doesn't make raising it further safe: suite peak RSS has
  never been recorded on *either* machine. Don't change it without measuring.

## Usage

    queue <cmd> [args...]        wait for a free slot, then run cmd HERE, as your child
    queue 'cd /repo && cmd'      ONE argument = run with `zsh -c` (keeps the && inside the gate)
    queue --priority <cmd...>    skip the waiting line; take the next free slot
    queue --solo <cmd...>        take EVERY slot; the job has the box to itself
    queue --slots [N]            show, or set, the machine-wide slot count (live)
    queue -l | --list            who holds which slot, and who is waiting
    queue --exit-code --last     exit code of this session's last queued job
    queue --status --last        that job's record (cmd, cwd, times, rc)

Env: `QUEUE_SLOTS` (seeds the slots file on first use only), `QUEUE_SESSION` (keys `--last`; agents
set it, humans fall back to tty/pgid), `QUEUE_QUIET=1` (silence the wait heartbeat),
`QUEUE_HEARTBEAT` (seconds, default 30), `QUEUE_DIR` (default `/tmp/queue-$UID`), `QUEUE_STATE_DIR`
(default `~/.cache/queue`). Needs `flock(1)` (macOS: `brew install flock`).

Removed, and they exit 2 with a message: `--cancel`, `--triage`, `--ahead`, `--depth`, `--budget`,
`-C`. There is no task-spooler, no `QUEUE_SOCKET`, no coalescing, no shortest-job-first jumping.

## Semantics

- **The job is your child.** Live stdout/stderr (kept separate), the command's own exit code, your
  cwd, env and stdin. Nothing is spooled or tee'd. Exit codes are never lost.
- **A slot is a lock file** (`$QUEUE_DIR/slot.1..N`) held with `flock` on an fd of the `queue` process.
  Free slot = unlocked file. The kernel releases the lock when the holder dies, including `kill -9`,
  so there is no stale slot to clean up.
- **Leaked children can't pin a slot.** The lock fds are closed in the job's process, so a server or
  watcher the job leaves running does not hold the slot after the job exits.
- **Where the slot count comes from.** Machine-only settings live in the git-ignored
  `~/dotfiles/local/.zshenv.local`, sourced by `~/dotfiles/shell/.zshenv` for every zsh. The Mac sets
  `QUEUE_SLOTS=4` there; the shared default is 2. `QUEUE_SLOTS` only seeds `/tmp/queue-$UID/slots` on
  first use after a reboot; `queue --slots N` changes the live value.
- **Gates use `queue --solo`** (`ci-fast`, `test-fast`): the gate gets the whole box.
- **Fairness: a turnstile.** Waiters take `$QUEUE_DIR/turnstile` one at a time and only the holder
  may claim a slot, so normal jobs start roughly in arrival order. `--solo` holds the turnstile while
  it collects every slot (in order, so two solos can't deadlock): it waits for running jobs to
  finish, blocks new ones from starting while it waits and runs, and cannot be starved.
  `--priority` skips the turnstile and takes the next free slot.
- **Slots file:** `$QUEUE_DIR/slots`, machine-wide and live. Seeded from `QUEUE_SLOTS` once, then
  changed only by `queue --slots N`. Raising it lets waiters start at once; lowering it never stops a
  running job.
- **`QUEUE_ACTIVE=1`** is set inside every queued job; a nested `queue` (a just recipe that queues)
  sees it and runs its command directly instead of waiting on a slot its parent holds.
- **A pause before output is the wait.** A heartbeat line on stderr every 30 s says so. Don't re-run.

### See and stop waiters

`queue -l` lists slot holders (pid, since, cwd, cmd) and waiters. A waiter is an ordinary process:
Ctrl-C it or `kill <pid>` (the pid is in `queue -l`). Killing a *holder's* `queue` pid frees its slot
at once. There is nothing else to cancel.

### Why not a daemon (2026-10-01)

The task-spooler wrapper (1,430 lines, in git history) failed in ways a daemon makes inevitable:
slots re-pinned to stale jobs after crashes; one `ts -u` crash wiped every queued job; exit codes
were lost between the daemon and the caller. Locks held by the kernel on behalf of live processes
cannot go stale, and there is no job list to lose.

## The `&&` trap

    queue cd /repo && cargo nextest run     # WRONG

The shell splits on `&&` before `queue` runs, so `queue` gets only `cd /repo` and the suite runs
unqueued. Pass ONE quoted string: `queue 'cd /repo && cargo nextest run'`. Same for `|`, `;`, `>`.
`unqueued_heavy_guard.py` (PreToolUse; omp: `~/.omp/agent/hooks/pre/queue_guard.ts`, which pipes into the same Python guard) denies — never rewrites — every unqueued compile and test run, and names the corrected form.
The rule (2026-10-01): every compile and every test run holds a slot. Heavy = `cargo build|check|clippy|install|doc|rustc|run`,
`cargo test|nextest run|bench|miri` (`--no-run` included), `cargo nextest list|archive`, `cargo test --list`, `maturin build|develop`, and `just`
recipes `test*|bench*|ci-fast*|ci-deep*|build*|install*|lint*|check*|clippy*|fastdev*|*-release`. Not heavy: `cargo fmt|metadata|tree|update|add|search|--version`,
`cargo nextest --version|show-config|self`. Why: ~23 unqueued concurrent compilers made a small file create on the 4 TB volume take a 451 ms median
(vs 2 ms drained, 2026-10-01). Quick incremental checks auto-join the express pool, so they do not wait behind a suite. The pre-dev integration guard
still denies only TEST/GATE commands off the integration branch — workers build (queued) on their own branches.

## Settled — don't re-investigate

- clippy does NOT thrash build artifacts
- sccache never shares across worktrees (upstream gap)
- sccache server hang (macOS, 2026-10-02, root cause reproduced): the server's one shared jobserver pool (`ncpu`
  tokens) is drained for good when clients are killed mid-build — a killed rustc takes its tokens with it — so every
  later compile blocks forever (clients at 0% CPU, no rustc child; upstream mozilla/sccache#2874, no fix in 0.18.0).
  `tools/sccache-watchdog` (LaunchAgent `com.vmasrani.sccache-watchdog`) detects it (also all-children-silent), saves
  evidence to `~/.cache/sccache-watchdog/hang-*` and kills the server; it never starts one (launchd-started servers hit
  a TCC prompt). `sccache-watchdog status` shows pool/clients.
- CoW-seeding a target dir saves only ~12 s — not worth orchestration (and impossible on ext4)
- Agents share one warm `target/` per worktree
