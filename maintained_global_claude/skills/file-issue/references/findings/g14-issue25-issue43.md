# #25 (phase-7 close-out) & #43 (epic #42 phase P1 fit-bound) — sessions f3ac138d… & 742d2ea9…

## Session A overview — epic #25 phase-7 close-out (f3ac138d-ebc7-4ff2-958e-3cbb736bf337)
Dispatch: own phase-7 close-out of epic #25 end-to-end (wire tuned scoring config into shipped
path, flip Table 4 to author scale, rewrite README Results, sweep stale prose, ci-fast, PR,
wait for sibling #32 merge, regen reports, merge, close #25). Span: 04:05:41 → 04:58:27 (~53 min).
Tool calls: ~153 in the main session + 20 (Explore scout subagent) + 73 (docstring-sweep
subagent) = ~246 total. Did NOT finish: 4 commits landed and green (tier0 523/1 skipped, fmt/lint/
type clean), but a genuine blocker was found (see F1) and the agent held the PR/regen pending
team-lead input. Before it could act on the reply, the team-lead sent a **PIVOT** message: the
user superseded the whole epic close-out with a new epic (#42, learned sparse weight table) —
"stop all work now, commit WIP as-is, push, handoff comment on #25, no PR." The transcript ends
*at the moment the pivot message arrives* (no commit/push/handoff visible in this transcript —
session was cut before it could execute the pivot instructions). Lead interventions: 2 (both
part of the same pivot exchange — first pivot message, then a follow-up correcting the agent not
to have started implementing before reading it).

## Session B overview — issue #43 (742d2ea9-bb91-4b0b-91c4-7d79ad7aeb35)
Dispatch: build cached uni+bigram TRAIN count matrices, add a per-fold sparse-linear-fit (L1-LR /
linear-SVM) evaluator (`csekit/tune_fit.py` + `scripts/tune_fit.py`), harvest≡ship parity, a
tripwire check, the bound table vs #29's 0.649/0.682, tier0 tests, justfile recipes, PR against
`dev`. Span: 04:40:01 → at least 05:08:13 (~28+ min, session **unfinished** — mid-implementation).
Tool calls: 68. Where it stopped: new module `csekit/tune_fit.py` and `scripts/tune_fit.py`
written, tier0 tests written and green (30 passed), lint/format/typecheck on the new files clean,
a timing run for the full 192-config grid in progress in the background — but no `just ci-fast`
run yet, no commit, no PR. Zero lead interventions (still solo at cutoff).

---

## Friction events (chronological, both sessions)

### F1: Dispatch prompt's headline number ("1533 admitted terms") was itself wrong for the code path it named
- Session: A (#25) — When: [04:47]–[04:57] (turn ~60)
- What the agent was trying to do: regenerate `data/lexicon/grooming_lexicon.parquet` via
  `scripts/mine_lexicon.py --min-df 2` and assert it reproduces **1533** admitted terms, exactly
  as the dispatch prompt specified as ground truth ("must reproduce 1533 admitted (positive side)
  terms — assert it").
- What it assumed / where it looked: took the prompt's 1533 figure at face value, wired an
  `--expect-admitted` guard into `mine_lexicon.py`, then ran the real mine to verify.
- What was actually true: `mine_lexicon(min_df=2)` (message-level mining, the only thing
  `scripts/mine_lexicon.py` can do) admits **1196**, not 1533. The dispatch prompt's 1533 comes
  from a *different, unit-level* computation (`tune_weights.weight_config_final`, over
  `conversation_author`/`author` rows) that overlaps the message-level lexicon by only 899/1533
  terms. The prompt conflated two distinct artifacts as if they were the same number produced by
  the same function.
- Cost: ~6 tool calls and ~10 minutes of empirical diagnosis (two throwaway diag scripts run
  through `queue`) before the agent could state the discrepancy precisely enough to escalate.
- Category: SPEC-AMBIGUITY / ACCEPTANCE-UNCLEAR (the prompt's own acceptance criterion was
  internally inconsistent with the codebase it described)
- Evidence:
  - `"admitted 1196 of 2813 scored terms"` (mine_lexicon direct run) vs prompt's `"...must
    reproduce 1533 admitted..."`
  - `"weight_config_final n_admit: 1533 ... unit-admitted: 1533 msg-admitted(on-disk): 1005
    overlap: 899 unit-only: 634"`
  - Agent: *"The assertion correctly caught a real discrepancy... I must not guess; let me
    diagnose empirically against the cached superset."*
- What in the issue/prompt would have prevented it: name the **exact function** that produces the
  headline number, not just the number — e.g. "1533 comes from
  `tune_weights.weight_config_final` at the **unit** level (conv_author/author rows), NOT from
  `mine_lexicon` at the message level; these are two different artifacts and 1533 is not a
  `mine_lexicon` output." The dispatch author should verify a load-bearing number against the
  actual code path before writing "assert it" as an acceptance criterion.

### F2: `pmap` (the CLAUDE.md-mandated parallelism primitive) is broken for process-based work in this sandbox
- Session: B (#43) — When: [04:53]–[04:56] (turn ~45)
- What the agent was trying to do: parallelise the per-fold sklearn fits (threads gave zero
  speedup — liblinear holds the GIL) using `pmap` from `mlh.parallel`, per the standing
  instruction "Parallelism only via `pmap`."
- What it assumed: `pmap(..., prefer="processes")` would just work, mirroring the CLAUDE.md rule.
- What was actually true: `pmap`'s process mode raises `EOFError` from
  `multiprocessing.Manager()` in this sandbox — reproduced even for a trivial `x*x` function, so
  it's an environment property, not a bug in the fit code.
- Cost: ~4 tool calls / ~3 minutes (thread trial → pmap process trial → raw pmap.core trial →
  trivial-function isolation trial) before falling back to joblib's `loky` backend directly
  (which `pmap` itself wraps) with a worker-reload pattern.
- Category: ENV/TOOLING (versions, uv, queue, gh, worktree, CI)
- Evidence:
  - `File "pmap/core.py", line 51, in prepare_parallel_mode manager = multiprocessing.Manager()`
  - Agent: *"pmap's process mode is fundamentally broken in this env (Manager EOFError even for
    trivial functions). I'll use a worker-reload pattern over joblib's loky (which pmap itself
    wraps)..."*
- What in the issue/prompt would have prevented it: a one-line environment note ("pmap's process
  mode (`prefer="processes"`) is broken on this box — `multiprocessing.Manager()` raises
  `EOFError`; use `prefer="threads"` for GIL-releasing code or joblib `loky` directly for
  CPU-bound sklearn fits") in CLAUDE.md or the dispatch prompt would have saved the whole
  detour. This is a durable environment fact, not per-issue — worth promoting to shared notes.

### F3: Two 2-minute timeouts from an unbudgeted per-process superset re-mine
- Session: B (#43) — When: [05:01]–[05:05] (turn ~48)
- What the agent was trying to do: time the full 192-config fit grid on real cached matrices with
  a short one-off `uv run python -c` probe.
- What it assumed / where it looked: assumed the probe would run in well under 2 minutes since
  the matrices are supposed to be *cached* (`data/tune/counts/...`).
- What was actually true: `superset_sha("train", min_df=2)` — called at the top of the probe —
  re-mines the lexicon from scratch every time a fresh Python process calls it (~45s), which
  isn't obvious from the API and isn't cached across process invocations; combined with the
  actual timing loop this exceeded the tool's default 2-minute Bash timeout twice before the
  agent isolated the cost with an explicit `timeout 110` + narrower probe.
- Cost: ~4 tool calls / ~6 minutes of dead time (two full 2-minute timeouts) before diagnosing.
- Category: SCALE/RUNTIME (job too slow, OOM, killed)
- Evidence:
  - `Exit code 143  Command timed out after 2m 0s` (×2)
  - Agent: *"The mine for `superset_sha` is the cost (~45s, cached per process); workers get the
    sha passed so they skip it."*
- What in the issue/prompt would have prevented it: note that `superset_sha`/mining is expensive
  (~45s) and not cross-process cached, so timing probes must pass the sha explicitly rather than
  recomputing it, and should set an explicit `timeout N` on any exploratory `uv run python -c`
  invocation rather than relying on the tool's 2-minute default.

### F4: Pre-existing tier0 test suite broke under the intended behavior change, for 3 distinct undocumented reasons
- Session: A (#25) — When: [04:27]–[04:36] (turn ~30)
- What the agent was trying to do: get `tests/tier0` green after wiring the tuned scorer in as
  the new default (exactly what the dispatch prompt told it would happen: "the expected values
  MOVE because the behaviour changed").
- What it assumed / where it looked: expected simple fixture-value updates; instead hit three
  independent mechanisms: (1) a `pmap`-installed `loguru_routing` shim silently strips/reinjects
  loguru handlers, breaking the `caplog` bridge only when the saturation-guard test runs *after*
  a `pmap`-using test (an ordering-dependent false failure, not a real regression); (2) a typer
  `OptionInfo` sentinel breaking a direct (non-CLI) call to `mine_script.main` in a test; (3) an
  `lr_diagnostic`-forbidden-import test tripped on the string "lr_diagnostic" appearing in a
  comment, not an actual import.
- What was actually true: none of these were regressions in the new code — all were either
  latent test-suite fragility (loguru/pmap interaction) or overly literal test assertions.
- Cost: ~15 tool calls / ~9 minutes chasing three distinct root causes across 4 successive full
  `pytest tests/tier0` runs.
- Category: ENV/TOOLING (versions, uv, queue, gh, worktree, CI) / DATA-SHAPE-SCHEMA (test fixture
  assumptions)
- Evidence:
  - `AssertionError: assert 'logistic saturation' in ''` — passes in isolation, fails in full run
  - `pmap has loguru_routing (strip/reinject) that reconfigures loguru handlers, breaking caplog`
  - `My own comment in score.py contains the literal lr_diagnostic. Let me reword it`
- What in the issue/prompt would have prevented it: a standing project note ("running `pmap`
  anywhere in a pytest session corrupts the loguru→caplog bridge for tests later in the same
  session — capture loguru output via a direct sink, not `caplog`, near any `pmap`-using test")
  would have cut the first and costliest of the three roughly in half. The other two are
  reasonably discoverable and not worth pre-documenting.

---

## What went smoothly because the prompt/issue supplied it
- **Exact worktree path + branch + base sha given up front** ("Work ONLY in
  `.../parot-cse-wt/issue-25`, branch `issue-25-closeout`, from origin/dev at 38a711b") → zero
  time spent locating or verifying the workspace in either session; first tool call in both was a
  direct `cd` + `pwd`/`git status` confirmation, not a search.
- **Named exact functions to read/reuse** ("`build_context`, `weights_and_admit`,
  `score_with_weights`, `_rollup_author`, `derive_unit_vocab_shape`, `evaluate_config_dual`" in
  A; "`mine_superset, build_full_counts, derive_unit_vocab_shape, weights_and_admit,
  build_context, score_with_weights, evaluate_config_dual, _rollup_author`" in B) → the agent
  went straight to the right primitives instead of re-implementing scoring/counting logic; no
  duplicate-tokenizer or duplicate-scorer risk materialized in either session.
- **File-ownership boundaries stated explicitly** ("ONE sibling is still running: w32 ... owns
  `csekit/lines.py`, `csekit/stages.py`, `csekit/tune_lines.py` — do NOT edit those files") → both
  agents actively cross-checked the sibling's code read-only (session A even opened
  `parot-cse-wt/issue-32/csekit/tune_lines.py` to verify a schema claim) without ever touching it,
  and dispatched their own parallel subagents with confirmed no-file-overlap reasoning.
- **`queue` semantics and box constraints spelled out** ("this box OOM-killed three heavy runs
  today", "n_jobs ≤ 6", single-slot serialization) → both agents pre-emptively used `queue` for
  heavy commands and never triggered an OOM; when the harness hook intercepted an un-queued
  `just ci-fast` in session A, the agent adapted in one turn because the *reason* (memory cliff,
  not cores) had already been given, not just the rule.
- **"Reuse one implementation, don't duplicate a tokenizer/primitive"** stated as an explicit
  constraint in B → the agent explicitly reused NGRAMS/span-based mining machinery for bigram
  enumeration instead of writing a third tokenizer, and called this out inline.
- **Exact target numbers with source attribution** ("honest CV F0.5 0.6489±0.080 (optimistic
  0.7388); test touch #2 F0.5 0.581" in A; "0.649 (#29) vs its LR bound 0.682" in B) → gave both
  agents a concrete, checkable target instead of a vague "improve the score" goal, and made it
  possible to catch the F1 discrepancy at all (the agent could tell 1196 ≠ 1533 immediately).
- **"If you find that wiring the winner changes a number that a sibling's report depends on, say
  which" (session A) and "say so, don't narrow quietly" (both)** → when the agent hit the F1
  blocker it held the PR and escalated with a precise, evidence-backed message instead of
  guessing which artifact was "right" — exactly the behavior the prompt asked for.
- **Explicit "no Co-Authored-By" + focused-commit-per-scope-item instruction** → both sessions
  produced clean, single-purpose commits (A: 4 commits, one per scope item) with no cleanup
  needed.

## Generalizable lessons (imperatives for the next issue/dispatch prompt)
1. **Verify any headline number against the actual function that produces it before writing "assert it."** If a number could come from two code paths (message-level vs unit-level, train vs test, etc.), name the exact function/module, not just the figure.
2. **Maintain one durable "known-broken environment" note** (e.g. `pmap` process mode raising `EOFError` on this box) and reference it from every dispatch prompt — this is a fact about the machine, not the issue, and re-discovering it costs the same few minutes every time.
3. **Warn when a "cached" value is actually per-process** (e.g. `superset_sha`/mining not cached across `uv run python -c` invocations) so agents don't write timing probes that silently re-pay a ~45s setup cost and blow the default tool timeout.
4. **When a test suite is known to have ordering-dependent fragility** (e.g. a parallelism library corrupting `caplog` for later tests), say so up front rather than letting each worker re-derive it via a bisection hunt.
5. **Naming exact functions/files to read and reuse is high-leverage** — both sessions here show near-zero wrong-path exploration specifically where the prompt named primitives explicitly; keep doing this even when it makes the prompt long.
6. **State file-ownership boundaries and in-flight siblings explicitly** ("don't edit X, owned by sibling Y still merging") — this prevented any cross-worktree edits and let both agents safely read (never write) sibling code to verify shared-artifact claims.
7. **Give agents explicit permission (and expectation) to hold and escalate on a real blocker rather than guess** — the prompt's "don't narrow quietly, say which sibling report is affected" produced exactly the right escalation behavior when the F1 discrepancy surfaced.
8. **A mid-flight scope pivot from the user should be sent with enough runway for the worker to actually execute the wind-down instructions** — session A's transcript cuts off at the moment the pivot arrives, before the requested commit/push/handoff comment could happen; if the session is expected to be killed/replaced immediately after a pivot, do the wind-down (commit WIP, push) via a fresh short-lived agent instead of trusting the same session to finish it.

## Stats
- Friction events by category: SPEC-AMBIGUITY/ACCEPTANCE-UNCLEAR: 1 (F1); ENV/TOOLING: 2 (F2, F4); SCALE/RUNTIME: 1 (F3). No WRONG-PATH, FALSE-ASSUMPTION-ABOUT-CODE (agent-side), MISSING-DOMAIN-CONTEXT, PROCESS, LEAD-CORRECTION, USER-CORRECTION, or SCOPE-CREEP/UNDER-SCOPE events met the ≥2-tool-call bar in either session (the pivot in session A is an external redirection, not a correction of agent error, and is captured as lesson #8 rather than a friction event).
- Rough share of session spent on friction vs productive work: Session A ≈ 15% (the F1 diagnosis + F4 test-suite chase, against ~53 min and ~246 tool calls of otherwise smooth, well-targeted implementation). Session B ≈ 20% (F2 + F3, against ~28+ min and 68 tool calls, weighted higher because the session is short and unfinished).
