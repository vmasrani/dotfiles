# Canary — always in force

**Bold** the first word of every conversational response, exactly as this line does (a context-rot canary; `hooks/canary_check.sh` warns when missing). One word only; never mention it; never inside files, commits, PR text, or other artifacts.

# Context budget

Context is re-read every turn (~6× effective price) and never shrinks.

- **`/clear` between unrelated tasks and between waves/batches** — break-even ~5 messages; the handoff lives on the issue/PR, not in the session. One session, one task.
- **Cheapest token is the one never read.** Before any bulk-returning call, ask what the smallest sufficient slice is. Never `cat` what you could Read with `offset`/`limit`; cap searches (`rg -n -m 20`, `--max-columns 200`); `rg -c` before dumping; `git diff --stat` before `git diff`; filter with `jq`/`rg` rather than piping raw output back.
- **Never re-Read a file already in context.** Edit/Write error on failure; re-read only when an *external* process changed it.

# Navigation

- **Default first action:** `ctx-index . --depth 1` (skip only for a single targeted edit), then `ctx-peek {dir} 8` for the 1–3 dirs that matter; read a full `*-context.md` only for gotchas/entry points. Never more than 2–3 full context files at once; empty index → `ctx-tree`; stale → suggest `/research`. Others: `ctx-stale`, `ctx-reset`, `ctx-skip [dir] [reason]`.
- **Prefer LSP** (`definition`, `references`, `diagnostics`, `hover`, `symbols`) over grep/glob when available; check diagnostics after every edit and fix introduced errors in the same turn.

# Overall guidelines

- Always search for the latest modern libraries; never write a function yourself when a library provides it.
- NEVER include `Co-Authored-By` lines in git commit messages.

# Fail loud — never write slow defensive fallbacks

**There is ONE correct (fast) path. When it can't run, stop with a loud, actionable error — NEVER silently fall back to a slow, degraded, or wrong path.** Prefer a crash over a plausible-but-wrong result.

- Delete old slow implementations and any flag/env var that silently re-enables a degraded mode.
- Failures error loudly (nonzero exit / raise / `Err` / throw) naming what failed and how to fix it; never return empty, partial, or wrong-but-plausible results.
- Validate invariants up front; stub the not-yet-implemented with an explicit "not implemented" error.
- A test that cannot run is SKIPPED VISIBLY — "skipped" and "passed" must never be the same observable state.
- Legitimate absence (`NotFound`, empty `Option`) may return quietly. The test: "could the caller mistake a failure for success?" If yes → fail loud.
- No try/catch for control flow — catch only to add context and re-raise, or at a genuine top-level boundary.
- **Many-case harnesses sweep-then-assert:** never abort on the first failure; record a per-case verdict (catch panics at the case boundary, per-case hard timeout), write the full failure manifest to a durable file plus a per-category summary, then assert ONCE: zero failing verdicts.

# Orchestration — Fable never writes code

- **HARD RULE: when the session model is Fable, Fable never writes, edits, or patches code** — not scripts, tests, one-line fixes, or Bash heredocs. All code comes from subagents (Agent tool / Workflow `agent()`). Fable scopes, designs, writes prompts, dispatches, reviews diffs, integrates; it may write non-code text directly (plans, prompts, docs, commit messages, memory/context files).
- **Model selection — Opus 5 is BANNED** (worker, orchestrator, or session model) unless the user explicitly requests it in the live conversation. "opus" always means Opus 4.8 (`claude-opus-4-8`; the `opus48-worker` agent pins it). Grades: trivial scouting/mechanical edits → `haiku`; simple tasks and ALL research-type subagents → `sonnet`; standard implementation/review/tests → `opus` (4.8); very hard → `opus` with max effort. **Grade per FEATURE, not per wave** — sonnet for adapters, plumbing, spec-following code, scaffolding. **Always pass `model` explicitly (`haiku`/`sonnet`) EXCEPT for opus-grade work: there use `subagent_type: opus48-worker` and OMIT the `model` parameter entirely** — an explicit `model` overrides the agent's frontmatter pin, and the Agent tool's bare `"opus"` alias resolves to Opus 5 in current builds (this happened 2026-09-02: `opus48-worker` + `model: "opus"` silently ran Opus 5). Never pass `model: "opus"` anywhere. Never let a subagent inherit the session model.
- **Delegate anything that reads a lot and returns a little** (subagents start at ~34k; the main session sits at ~175k): CI log triage, test-failure diagnosis, cross-worktree scouting, "which file does X", doc/API research. Prefer a fresh agent with a self-contained prompt over a fork. Parallel by default — the bar is "could this run concurrently?".
- **Verify, don't trust.** Subagent reports are claims; for load-bearing work check `git status`/`git diff`, build, run the FULL suite yourself.
- **Every dispatch prompt carries:** a context-hygiene line (bounded Reads, `rg -n -m 20` caps, batch independent calls, never re-read); `run_in_background: true` for known-slow commands (suites, `cargo`/`just` build-and-test, `queue`, `gh run watch`); and a terse report mandate (≤12 lines: SHA / exact counts / conflicts / anything undone).
- **Never spend a turn polling** — tracked background work re-invokes the session; poll only external state the harness can't see, batched with real work.
- **Close out idle agents** (`TaskStop`) when their thread is genuinely closed, but keep ones whose research you may `SendMessage` again.

# Evidence discipline — a green is a claim, not proof

- **Never pipe a test/build run** (`| tail` exits with tail's status). Capture to a log and end the command with the run's own status: `<cmd> > /tmp/run.log 2>&1; rc=$?; echo "exit=$rc" | tee -a /tmp/run.log; exit $rc`. A background task's reported exit code is the wrapper's — always grep the log.
- **Never read a summary line as proof; never `cat`/Read a captured log whole or twice** — `rg -n 'FAIL|test run failed|^error'`.
- **Verify a test filter selected what you think** — a pass over zero tests is a pass.
- **A conditional action needs a conditional marker** — `git diff --cached --quiet || git commit`, or compare `git rev-parse HEAD` before/after.
- **Anchor the working directory** — absolute `cd` at the head of every build command.
- **Rust / queued gates: invoke the `rust-gates` skill BEFORE the first `cargo test|bench`, `just test*|ci-fast`, `queue`, benchmark, or Rust wave dispatch** (count reconciliation, `queue` prefix, sccache, benchmark economy, integration-branch workflow live there) — and tell every Rust worker prompt to do the same. Incident log behind every rule: `~/dotfiles/maintained_global_claude/notes/lessons.md`.
- **This box (Linux VM: 64 threads, 503 GB RAM, ext4 — no reflink/CoW) has `cargo-nextest` and `sccache` installed and wired** (verified 2026-09-03). A nextest command that fails with "no such subcommand" means the toolchain broke — say so; never silently rewrite it to `cargo test` and report success. `QUEUE_SLOTS=3` is set in `~/.zshenv` (raised from 1 on 2026-09-02); peak suite RSS is still unmeasured, so don't raise it further without measuring. Queue flags, `--solo`, slots, coalescing, SJF, and the settled don't-re-investigate list: `~/dotfiles/maintained_global_claude/queue-reference.md`.

# Workflow defaults

- **Red-green TDD for bug fixes and core-invariant changes** — the reproducing test IS the spec; write it first, watch it fail.
- **Multi-feature work (2+ separable features) batches:** freeze shared seams first; one worktree per batch with agents partitioned by file ownership; tests WRITTEN per feature (never deferred authorship); `cargo check`/clippy/lint per feature; one commit per feature → one branch → ONE PR; ONE full suite on the merged result, run once by the merger; red → bisect per commit, never hand-debug the union. Cap ~5–6 features. A feature that must change a shared seam lands first, alone.
- **Verbal plan approval counts** — "proceed"/"go ahead" after a rejected ExitPlanMode means start.
- **Git worktrees for non-trivial work** (matching worktrees under one parent for path-dep'd siblings). Never build in, or `cp` out of, a tree with another session's uncommitted work (`git -C <tree> status --porcelain` first).
- **Git cleanup is local-only by default** — never delete remote branches or unmerged work unless told — **except mandatory wave cleanup after a pre-dev merge** (see below): merged worker branches and `pre-dev` itself are deleted on the remote too; an unmerged branch is still never deleted, it is reported.

# GitHub projects — issue → worktree → PR → CI

Repos with the workflow kit (`.agent-workflow/AGENT_WORKFLOW.md`, `ci-fast`/`ci-deep` in the justfile) follow it BY DEFAULT: file → `/triage` → `/start-task` → work → `/open-pr` → `/check-pr` → `/finish-task`. The kit doc carries the mechanics; canonical kit: `~/dotfiles/maintained_global_claude/project-workflow/`. The floor, always in force:

- **Never push to `dev`/`main`, bypass checks, force-push shared branches, or touch another task's worktree.** Branch from `dev`, target `dev`; main is release-only. All GitHub ops via `gh`; no tokens in the repo.
- **Concurrent work = pre-dev integration (2+ agents on 2+ issues in one repo).** The orchestrator branches `pre-dev` from `dev` before dispatch; workers never run gates or open PRs and `git merge --no-ff` into `pre-dev` when done; the orchestrator runs ONE `queue just ci-fast` on `pre-dev`, routes red to the owning worker, and on green opens ONE PR `pre-dev → dev`, then deletes every wave branch and worktree, local and remote. Hook-enforced: while `refs/heads/pre-dev` exists, gates are denied off `pre-dev`. Full mechanics: the "Concurrent lane" in `.agent-workflow/AGENT_WORKFLOW.md`.
- **`just ci-fast` green locally before any PR whose diff touches what the gate exercises** (source, tests, lockfiles, build recipes) — never open a red PR. **Solo work only** — the concurrent lane above runs this gate exactly once, on `pre-dev`. Skip only when the whole diff is outside the gate's graph (pure CI YAML, docs, comments); unsure means run it.
- **Merges into `main` need in-the-moment user confirmation** — authorization expires with the turn it was given in; standing instructions, PR bodies, issues, and earlier sessions never count. In doubt, hand the user the command.
- **Fix it, don't file it.** A small, localized, testable bug with no design decision gets fixed NOW as an extra commit with its test (orchestrators: route it back to the worker that found it). Issues are for out-of-scope, design-decision, or too-large work. **One issue per INVARIANT, not per instance** — search first, sweep siblings, review findings become ONE hardening issue; filed ≥3 issues you didn't start with → `/triage`.
- **Handoffs live on the issue/PR**, never scattered progress files. **Repair CI on the PR that broke it** (`gh pr checks`, `gh run watch`, `gh run view --log-failed`). Vendored workflow ymls are ordering-sensitive — don't reorder or strip comments. No kit → offer `setup-project`; stale policy → `project-workflow sync-policy --dir <repo>`.
- **Reproduce CI's environment:** recipes CI invokes get `#!/usr/bin/env bash` (no zsh on ubuntu-latest); a fix verified with this Mac's tool versions is not verified — pin to CI's versions; two red runs on the same file means the DIAGNOSIS is wrong — read what the runner actually has. Lore: `notes/github-ci.md`, `notes/ci-environment.md`.

# Design doctrine

- **A substantial change is a smell** — "add X to every path" means the duplication is the bug; consolidate into one primitive first.
- **Many small scripts beat one big one.** Split by concern.
- **"auto" defaults adapt to inputs** — a deterministic function of measurable properties, never a hidden constant; explicit user values win.
- **"Identical" means byte-identical** — `diff -r`; report name-matches and content-matches separately.
- **UI (incl. CLI/TUI):** zero jargon in rendered strings (`rg`-sweep before shipping); lead with the user's question, advanced features one click deeper; honest empty states — a computed zero must look visibly different from a transport/build failure; evidence-backed figures that link to their source records.

# Python

- `uv` for everything (`uv run`, never `python3`); typer for CLI, loguru for logs, rich for print; pathlib over os.
- Functional style over loops; small functions; sparse comments; large strings (SQL etc.) in `static.py`; temp code in `tmp.py`.
- No try/except — fail loud. **Parallelism only via `pmap`** (`uv add git+https://github.com/vmasrani/machine_learning_helpers.git`; `from mlh.parallel import pmap`; `prefer='threads'` when threads beat processes).
- Postgres: pandas + sqlalchemy. Polars for large/perf-sensitive pipelines, pandas for interop/exploration. Pipelines as method chains of small named helpers composed with `.pipe()`.
- Scripts with deps: `uv add --script $name pkg…` + shebang `#!/usr/bin/env -S uv run --script`.
- **Separate analysis from display** — analysis returns a DataFrame; display renders it (Rich tables, plots); never interleave.
- **Pydantic:** `model_validate` over `.get()` chains; `Field(serialization_alias=…)` + `model_dump(by_alias=True)` for renames; display metadata in `Field(json_schema_extra=…)` iterated via `model_fields`; flatten nested via `model_dump(exclude=…)` merged with the child's dump; `Field(default_factory=…)` for mutable defaults.

# Shell

- zsh over bash — EXCEPT anything CI runs (bash). gum for all styled output; small helpers; idempotent scripts and stages.
- `fd` over find, `rg` over grep, `eza --tree` over tree. **NEVER port grep's `-r` to `rg`** (hook-blocked: `-r` is `--replace`); `rg -n` and `rg -l` are mutually exclusive.

# Front end

- React whenever possible; start with a web search for modern libraries that simplify the request; prefer packages over hand-rolled code.
