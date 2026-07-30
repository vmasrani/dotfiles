# testq — full reference

Split out of the global `CLAUDE.md` (2026-07-27) so the Rust-only queue manual stops
riding along on every Python/frontend session. The four rules that prevent real
mistakes stayed in `CLAUDE.md`; everything below is lookup material — read it when you
actually need it.

## This machine (Linux VM — verified 2026-07-24)

64 threads (2×16-core Xeon Platinum 8280L, 2 threads/core), **503 GB RAM**, ext4 on `/` (497 G)
and `/data` (1 T). Present: `cargo`, `clippy`, `miri`, `rustfmt`, `rust-analyzer`, `just`,
`tsp`/`testq`. **NOT installed: `cargo-nextest`, `sccache`.** Everything below marked *M4* was
measured on the macOS laptop and has **not** been reproduced here — the hardware gap is large
enough to invalidate the reasoning, not just the constants.

- **No nextest.** Archive fan-out (`cargo nextest archive --archive-file …`), `-E 'test(...)'`
  filter expressions and `--no-fail-fast` output shapes all fail loudly here. Correct responses:
  `cargo install cargo-nextest`, or deliberately write the `cargo test` form and say so. Never
  substitute silently.
- **No sccache**, so the M4 sccache bullets are moot. Don't set `CARGO_INCREMENTAL=0` reasoning
  about sccache — with no sccache in play it only makes cold builds slower. (Kept so nobody
  re-derives it: sccache hashes the compile's `cwd`, so two worktrees never share cache work;
  `SCCACHE_BASEDIRS` covers only the C/C++ path, issue #2652, Rust fix unmerged, PR #2678.)
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
- **`TESTQ_BUDGET=12` is almost certainly far too conservative here — but do not change it without
  measuring.** Its justification was 10 cores / 16 GB where the 1 GB bench alone peaked ~7.5 GB
  RSS, so two suites thrashed. That constraint is absent: 503 GB makes eight concurrent suites
  (~60 GB at the M4's own peak) ~12% of memory, and a suite at ~9x parallelism is about a seventh
  of the CPU. The binding constraint here is CPU oversubscription alone, biting around 6–7
  concurrent suites, not two. Suite peak RSS has never been recorded on *either* machine — until
  someone measures it, 12 stands and suites stay serialized. Change the budget and you must
  re-derive the weight table, and vice versa.

## What the hook does

A PreToolUse hook rewrites heavy cargo/just commands (`cargo nextest|test|build|check|clippy|bench|install|miri`, `just test*|bench*|lint*|ci-fast|ci-deep`) into `testq zsh -c '<cmd>'` — a machine-wide weighted queue shared by every agent and repo. **Never add the prefix yourself** — the hook applies it quote-safely and never double-wraps. Trivial verbs (`fmt`, `metadata`, `tree`, `add`, …) stay instant and unqueued.

The hook must wrap in `zsh -c` (a bare prefix breaks `cd … && cargo test` and `RUST_LOG=1 cargo test`), so testq unwraps `sh|zsh|bash -c '<string>'` before weighing anything — otherwise every real job would classify as `other 1`. `testq --selftest` checks the classifier against its table (30 cases, no daemon needed); `hooks_selftest.py` checks the cross-component invariant that nothing the hook queues weighs 1.

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

Jobs are weighted against `TESTQ_BUDGET` (default 12: fmt/doc 1, check/clippy/build 3 and `just lint*|check*` 3, test/nextest 9 and `just test*|ci-fast*` 9, bench/miri 12 and `just bench*|ci-deep*` 12) — one suite plus one check overlap, two suites never do, a bench runs alone. `ci-fast` fans out to the full suite and `ci-deep` is a superset of it, hence 9 and 12. Don't raise the budget without measuring — on the M4 the binding constraint was RAM; on this box it is CPU oversubscription (see the machine section above).

Classification looks only at words in COMMAND position, so `rg -n 'cargo test' justfile` stays weight 1, while `cd`, `FOO=bar` and `cargo +nightly` prefixes are seen through. A chain takes its **heaviest** segment, not its first: `cargo build && cargo nextest run` weighs 9, because under-weighting a chain silently lets two suites overlap.

Byte-identical commands in an unchanged tree coalesce: followers attach to the leader's output and exit code instead of re-running. Scheduling round-robins across sessions, so one agent's fan-out can't starve others.

## Settled — don't re-investigate

Measured, closed questions:

- clippy does NOT thrash build artifacts (cargo hashes the workspace wrapper into the artifact
  filename — `build → clippy → build` in one shared target dir recompiled 0 crates; a separate
  `target/clippy` buys nothing)
- sccache never shares across worktrees (upstream gap) — *moot here, sccache isn't installed*
- CoW-seeding a target dir saves only ~12 s — not worth orchestration; *and it is impossible here,
  ext4 has no reflink*
- Agents share one warm `target/` per worktree — `cargo-slot` only matters if you raise the budget
