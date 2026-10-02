# Measured lessons behind the rules

Evidence log for `~/.claude/CLAUDE.md` and `notes/rust.md`. The rules are stated tersely there; the incident that earned each rule lives here so the always-loaded file stays small. Append a line when a new rule is born; never load this file into a session unless a rule is being questioned.

Format: **rule** — incident (date, repo/issue): measurement.

## Context budget / orchestration

- **`/clear` between waves, orchestrator included** — fast-dedup 2026-08-17: the orchestrator session alone cost 62M cache-read tokens at 159k average context, ~80% of what its entire 5-worker wave consumed, because wave-1 history rode along under every wave-2 turn.
- **Context tokens are ~6× amplified** — re-read ~43× per session; context never shrinks.
- **Context-hygiene line in every dispatch prompt** — wave workers averaged 100–126k context, ~70–90k of avoidable file/tool output on top of their 34k start; cost scales as turns × context.
- **Terse structured worker reports (≤12 lines)** — a worker's report lands in the orchestrator's context and is re-read every turn thereafter; prose narratives compound forever.
- **Polling turns buy nothing** — a `queue -l`/`git log` status-poll turn re-reads the full context (~159k) to learn what the harness would have pushed anyway.
- **No auto-background setting exists in Claude Code** (checked 2026-08-14) — `run_in_background: true` is a standing habit that must be stated in delegation prompts.
- **Grade model per feature, not per wave** — 2026-08-17: a 5-feature wave ran all-opus when at least 2 features were sonnet-shaped, ~30–40% of worker cost for no quality gain. Sonnet is ~1/5 the price of Opus.

## Evidence discipline

- **`exit $rc` must end every captured run** — three background `ci-fast` runs in one session announced success for failed runs because the `echo "exit=$?"`-only form leaves the shell exiting 0.
- **Sweep-then-assert in many-case harnesses** — cartridge #118 bring-up burned 5 runs surfacing one oracle-binding bug each before the harness was restructured to collect all verdicts first.
- **Never two identical full gates on the same SHA** — integrator-gate + reviewer-regate doubled a wave's gate cost for zero information.

## Benchmark economy

- **Expensive runs must answer a question only they can answer** — SEVERE measured dev-velocity sink (2026-08-17); an unnecessary 30–60 min solo job stalls every session on the machine.
- **Gate baseline runs on counter evidence** — fast-regex #18 sweep: 2 corpora × pre runs bought zero information; counters showed the new code path never fired.
- **Persist results at birth** — fast-dedup hero benches nearly re-ran 30–60 min baselines because no stored baselines existed.

## Workflow / GitHub

- **Fix it, don't file it** (user mandate 2026-08-21) — small issues filed by agents slow dev down and burn tokens on triage/re-dispatch.
- **No author≠merger rule** (user mandate 2026-08-20) — the separate-review-agent requirement was slowing waves down; killed entirely for `dev`, `dev → main` stays the user's.
- **Integration branch first, measure, then review** (user mandate 2026-08-20) — review effort spent on results that didn't move the number was the waste.
- **Concurrent work = pre-dev integration, ONE gate** — 2026-09-03: agents dispatched on issues #421/#423 each ran `ci-fast` and self-merged to `dev`; concurrent `ci-fast` jobs filled the queue and slowed every job on the box.
- **Unpinned `uvx <tool>` in CI** — measured 480 CI findings vs 0 local with ruff (see memory `uvx-unpinned-ci-reproducibility-trap`).
- **npm lockfile incident** — parot-radar #17; details in `notes/ci-environment.md`.
- **GIT_DIR leaks into pre-push hooks from linked worktrees** — 2026-09-03: `git push` from a worktree exports `GIT_DIR=<main>/.git/worktrees/<name>` to the hook; `just pre-push` ran `uv run`, uv fetched a git dependency with a nested `git init` that re-targeted the MAIN checkout and set `core.bare=true` (`git worktree list` showed `(bare)`, `git status` said "must be run in a work tree"). Reset with `git config core.bare false`; the kit pre-push template now `unset`s GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE/GIT_PREFIX before the recipe. Any hook that runs tools which shell out to git needs the same.

## 2026-09-07 — one flat `tests/*.rs` per binary made a 10-min gate take hours (cartridge)

76 flat integration-test files → 198 nextest binaries at ~70 MB each; nextest lists every binary twice per invocation and `ci-fast` invokes nextest ~5 times with 6 distinct `--features` spellings (each a full recompile). Under RAM starvation (16 GiB Mac, swap 2.8/4 GB, ~17 Claude agent processes at 250–530 MB each) every `--list` spawn took ~24 s at 0% CPU while the same binary listed in 0.00 s by hand. Rules added to `skills/rust-gates/SKILL.md` ("Test-binary layout"): one harness per crate (`tests/main.rs` + `autotests = false`), one compile tuple per gate, nextest once per gate, diagnose starvation before killing a gate. Kit follow-up: `_test-binary-layout` recipe in `project-workflow/templates/justfile.rust`.

## 2026-10-01: hand-rolled clippy instead of the gate recipe (cartridge, Epic B)
I ran `cargo clippy --workspace --all-targets --features cli,dev-nolicense,test-instrumentation,sql`, but the justfile gate is `--workspace --exclude sql-torture` without `sql`. The workspace run pulled in `sql-torture`, which builds `libduckdb-sys` (bundled C++ DuckDB), and the extra feature made a feature set no gate shares. It hit the 300 s tool cap; the gate command (`just ci-github`) avoids the DuckDB build and failed in 2 s on a real fmt diff. Rule: run the repo recipe or copy its exact flags, never improvise (global CLAUDE.md, Evidence discipline).

## 2026-10-01: unqueued builds stalled the external volume (cartridge, three concurrent epics)
All repos/worktrees live on the external 4 TB drive. With ~23 concurrent compilers/linkers from three epics — every `cargo build|check|clippy` ran outside `queue` because the guard only gated test execution — a small file create+unlink on that drive took a 451 ms median (max 3 s); with the builds drained it was a 2 ms median. The 2026-08-14 "compiles idled the Mac inside slots" finding had been over-applied: that is what the express pool (auto-join after 3 consecutive runs under 30 s) answers. Rule: every compile and every test run holds a queue slot, as ONE quoted string (`queue 'cd <wt> && cargo build ...'`). `unqueued_heavy_guard.py` now classifies "build" vs "test" kinds; the pre-dev integration guard still denies only tests/gates off the integration branch, so workers keep building (queued) on their own branches. omp enforces it via `omp/agent/hooks/pre/queue_guard.ts`, a thin adapter that pipes into the same Python guard.

## 2026-10-01: a bench worker ran rm -rf on the shared results dir (cartridge Epic B)
A bigvm bench worker ran `rm -rf ~/dev/bench/epic-B` on the Mac before copying its files back, deleting other workers' append-only results (b1, b2, b6, b8, b10, b14). There was no Time Machine backup; the files were rebuilt verbatim from agent transcripts. Rule: results dirs are append-only and shared; never `rm`, `mv` or overwrite under ~/dev/bench; copy with `rsync --ignore-existing` (or `cp -n`); state it in every bench brief.

## 2026-10-01: sccache 0.18.0 hangs after killed builds (mozilla/sccache#2874)
The sccache server shares one jobserver pipe of ncpu tokens with every rustc it spawns. Killing a cargo client mid-build (timeouts, pkill, killing a gate) SIGKILLs its rustc, which takes its tokens with it. Once the pool reaches 0, every later compile blocks forever in jobserver.acquire at 0% CPU. It hung 3 times in one night with 3 epics building. Fix: tools/sccache-watchdog under launchd kills a hung server (waiting clients fall back to local compiles; the next client starts a fresh one) and saves evidence to ~/.cache/sccache-watchdog/. Rule: avoid killing builds mid-compile; if you must, expect the watchdog to kill the server.
Never start the sccache server from launchd or any python/launchd-spawned process: macOS TCC makes that job the "responsible process", its rustc children touching /Volumes/volume raise a consent prompt (kTCCServiceSystemPolicyRemovableVolumes) nobody can answer, and every child blocks at 0% CPU (2026-10-02 01:22; our own watchdog caused it). Watchdog is detect-and-kill only; clients started from an ssh session start the server.

## 2026-10-01: never run two gate recipes at once in one worktree
Running `just ci-fast` and `just test-fast` concurrently in the same tree let ci-fast rebuild target/debug/cartridge mid-test; the `cartridge up` reuse tests compare the binary hash and failed (daemon replaced). It cost a gate round and a worker. Gate halves run in series, one tree at a time.
