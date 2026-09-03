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
