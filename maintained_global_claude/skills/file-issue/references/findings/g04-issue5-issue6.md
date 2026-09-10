# Issues #5 & #6 — sessions 1e7cd655 (score, PR #13) / 2159f384 (lines, PR #12)

Session overview (#5, score): issue asked for author/conversation scoring + PAN12 Problem-1
F0.5 harness (`csekit/score.py`, `scripts/score_authors.py`). 21:29:19 → 21:56:12 (~27 min),
131 tool calls, 0 lead interventions after the initial dispatch. PR #13 opened, merged later
(2026-08-21, by a follow-up session/commit, not this one).

Session overview (#6, lines): issue asked for message trajectory / changepoint / line-flagging
/ Problem-2 F1/F3 / eSPD harness (`csekit/lines.py`, `scripts/lines_report.py`). 21:29:32 →
21:57:18 (~28 min), 128 tool calls, 0 lead interventions after the initial dispatch. PR #12
opened, merged later. Both ran concurrently as sibling worktrees off the same wave dispatch.

Both are genuine issue-implementing sessions (heavy code authoring + real-data verification),
not scoped-review sessions — full report follows.

## Friction events (one block each, chronological)

### F1 [#5]: `rg -r`/`rg -l -n` blocked twice while locating `slant_readout`
- When: [21:30:30–21:30:34] (turn ~13)
- What the agent was trying to do: find which `parot-bias` file defines `slant_readout` to reuse it.
- What it assumed / where it looked: tried `rg -rn 'slant_readout' .` (treating `-r` as recursive), then `rg -ln 'slant_readout' .` (treating `-l` + `-n` as combinable).
- What was actually true: `-r` is ripgrep's `--replace` (silently rewrites matches); `-l` and `-n` are mutually exclusive. Recursion is rg's default, no flag needed.
- Cost: 2 blocked tool calls before the 3rd (`rg -l`) succeeded.
- Category: ENV/TOOLING
- Evidence: `"BLOCKED: rg -r is --replace, NOT recursive... plausible, fabricated output, with a zero exit code."`; `"BLOCKED: rg -l (filenames only) and -n (line numbers) are mutually exclusive"`
- What would have prevented it: this is a standing global-CLAUDE.md rule already in the agent's own instructions — the hook caught it correctly. Nothing issue-specific to add; only a general system-prompt reinforcement would help (see lessons).

### F2 [#5 and #6, same root cause]: `just ci-fast` run directly, blocked by heavy-command hook
- When: [21:42:14] (#5, turn ~45) and [21:43:59] (#6, turn ~44)
- What the agent was trying to do: run the narrow CI gate the preamble told it to run (`ruff format/check`, `ty check`, `pytest tier0`) as one aggregate `just ci-fast` call.
- What it assumed: a plain foreground `just ci-fast` was fine, matching the preamble's literal wording ("uv run ruff format . && uv run ruff check . && uv run ty check . green, and uv run pytest tests/tier0 -q ... green").
- What was actually true: the box enforces a `queue` prefix for anything heavy ("Several of these at once on this box thrash rather than finish — memory is the cliff, not cores"); plain `just ci-fast` is rejected outright.
- Cost: 1 blocked call + rewrite, in both sessions independently (each worker discovered the same rule cold).
- Category: ENV/TOOLING
- Evidence: `"'just ci-fast' is heavy and was not sent to the queue... Run it as: queue just ci-fast > ..."`
- What would have prevented it: preamble/dispatch should state explicitly: "prefix `just ci-fast`/`just ci-deep` (and any full-suite command) with `queue`" — this rule was needed by every worker in the wave and none of them had it up front.

### F3 [#5]: assumed `biaskit` reuse-functions returned attribute-accessible objects, not plain tuples
- When: [21:35:41–21:35:51] (turn ~30)
- What the agent was trying to do: call `lexicon_spans`/`score_text`/`bias_score` from `biaskit` per the dispatch's explicit reuse list and wire their outputs into `score.py`.
- What it assumed / where it looked: wrote code accessing `._weights`, `.n_signals`, etc. as if the return values were namedtuples/objects.
- What was actually true: `ty check` reported `Object of type tuple[Any, ...] has no attribute '_weights'` — the reused functions return plain positional tuples, not attribute-bearing objects.
- Cost: 1 `ty check` round + 1 patch round (~2 tool calls) before signatures matched.
- Category: FALSE-ASSUMPTION-ABOUT-CODE
- Evidence: `"error[unresolved-attribute]: Object of type tuple[Any, ...] has no attribute '_weights'"`; `"error[unresolved-attribute]: Object of type tuple[Any, ...] has no attribute 'n_signals'"`
- What would have prevented it: the dispatch already named the exact functions to reuse — one more line giving the concrete return shape (e.g. "`score_text` returns a plain positional tuple `(raw, n_signals, weights)`, not a namedtuple — index by position") would have removed this round-trip entirely, since `ty check` is the only thing that caught it.

### F4 [#5]: real-data timing subprocess died mid-run + duplicate re-run collided
- When: [21:50:16–21:51:10] (turn ~78)
- What the agent was trying to do: measure real full-population scoring wall-clock (903,607 msgs / 97,689 authors) as the lead's dispatch asked ("measure and report wall-clock").
- What it assumed / where it looked: launched the timing script in the background and waited.
- What was actually true: the background process died (assistant's own diagnosis: "likely reaped with its parent shell"); the agent re-launched it, but a duplicate instance ended up running concurrently with the original.
- Cost: ~1 min wall clock + 3 extra tool calls (kill the younger duplicate, confirm one survivor, re-poll).
- Category: SCALE/RUNTIME
- Evidence: `"The timing process died (likely reaped with its parent shell). Re-running the full-population pass alone."`; `"Two duplicate runs are competing. Killing the younger one and letting the original finish."`
- What would have prevented it: not really preventable from the issue text — this is an infra footgun (backgrounding via `sleep N; cmd` inside one Bash call gets reaped). A dispatch-prompt-level reminder to always use `run_in_background: true` (not `sleep N; cmd` chains) for anything over ~1 min would reduce this class of failure across all workers.

### F5 [#5 and #6, shared]: queue contention on `just ci-fast` behind an unrelated wave-3 job
- When: [21:44:20–21:56:xx] (#5) and similar window (#6)
- What the agent was trying to do: get the final `just ci-fast` gate green before opening/finalizing the PR.
- What it assumed: the queued gate would return in roughly the time budgeted for CI.
- What was actually true: both sessions' `ci-fast` queued behind `job 47 (wave3-yardstick-warm: just sql-yardstick)`, which ran 500–800+s (well over its own 207s median) — an unrelated concurrent wave's job monopolized the single queue slot for most of both sessions' tail end.
- Cost: ~10+ minutes of both sessions' wall clock spent polling a gate blocked by someone else's job; both workers worked around it by running the 4 `ci-fast` components individually and reporting those as green instead of waiting for the aggregate.
- Category: SCALE/RUNTIME
- Evidence: `"queue: still queued — 449s elapsed, 1 ahead; blocked by job 47 (wave3-yardstick-warm...), running 550s; median 207s) — est. 0s"`
- What would have prevented it: not fixable from the issue text (it's a shared-infra capacity problem), but the dispatch/preamble could pre-authorize the workaround up front — "if the aggregate `just ci-fast` is queued behind another job for >2 min, run its 4 components individually and report those as green instead of blocking on the aggregate" — both workers had to invent this workaround independently.

### F6 [#6]: real-data assertion failure — flagged-line "belongs to a predator" invariant is false
- When: [21:48:34–21:55:31] (turn ~62)
- What the agent was trying to do: validate `flag_lines`/Problem-2 output against real PAN12 test data via a new tier1 test asserting every flagged predatory line is authored by a labelled predator (recall ceiling = 1.0).
- What it assumed / where it looked: wrote the test assuming the PAN12 gold annotation is internally consistent (`assert 0.9978... == 1.0`), since PLAN.md/fixtures gave no reason to doubt it.
- What was actually true: 14 of the 6,478 real flagged predatory lines are authored by non-predators (none of those 12 authors is a predator anywhere in the corpus) — a genuine PAN12 annotation quirk, only visible on the real corpus, not the fixtures.
- Cost: ~7 minutes of investigation (log polling, re-reading the failing assertion, pinning a named constant instead of `1.0`).
- Category: DATA-SHAPE/SCHEMA
- Evidence: `"AssertionError: every flagged line is authored by a predator ⏎ assert 0.9978388391478852 == 1.0"`; final report: `"14 of the 6,478 flagged lines are authored by non-predators... the all_predator_lines oracle baseline tops out at R = 0.99784, not 1.0"`
- What would have prevented it: not preventable up front — this was a first discovery on real data (the fixtures don't carry the anomaly). Once discovered here, it should be logged as a known corpus fact in PLAN.md/the tracking issue so issue #7 (or any downstream scorer assuming R=1.0 is achievable) doesn't re-derive it.

### F7 [#6]: `eval_problem2` full-split evaluation had two order-of-magnitude performance bugs
- When: [21:47:44–21:53:26] (turn ~60–90), the single largest cost item in either session
- What the agent was trying to do: run the new tier1 real-data test suite against the full PAN12 test split (per-issue instruction to "RUN it if real CSV+lexicon exist").
- What it assumed / where it looked: wrote `eval_problem2`'s gold-lookup using a Python `set` of `(conv_id, line)` tuples built and probed row-by-row — fine at fixture scale (dozens of rows), untested at real scale.
- What was actually true: at real scale (millions of message rows / 6,478 flagged lines) the set-of-tuples approach was the bottleneck; needed two successive rewrites — first replacing the naive scan, then vectorizing with a pandas `MultiIndex` — before the tier1 run finished in reasonable time.
- Cost: ~6 minutes of iterate/kill/rerun cycles (`pkill`, rewrite, rerun ×3) — roughly 25–30 tool calls total in this window.
- Category: SCALE/RUNTIME
- Evidence: `"Waiting on the tier1 real-data run (one assertion already failed... one already failed"`; `"The tier1 run exposed a real performance bug in my own code — let me fix it."`; `"The full-split set-of-tuples in eval_problem2 is the bottleneck. Replacing it with a vectorized MultiIndex."`; commit `"lines: real-data tier1 gate, and two order-of-magnitude scan fixes it exposed"`
- What would have prevented it: the dispatch prompt never stated the real corpus's actual scale (2,058,781 messages / 218,702 authors / 6,478 flagged lines — numbers the #5 worker *did* discover and could have been forwarded). A one-line note — "the real test split is ~2M message rows; any per-row Python loop or `set`-membership scan over gold labels will be the bottleneck — vectorize (merge/MultiIndex) from the start" — would have avoided writing the naive version at all.

### F8 [#5 and #6, shared]: file-ownership rule broke down on one shared stub-inventory file
- When: [21:44:29] area (#5) / commit at [21:55:47] (#6)
- What the agent was trying to do: follow the preamble's "FILE OWNERSHIP: touch ONLY the files your issue lists as owned... no shared-file edits."
- What it assumed / where it looked: both workers correctly scoped their edits to `csekit/score.py`/`csekit/lines.py` and their own tests.
- What was actually true: `tests/tier0/test_schema.py`'s stub-inventory list (`test_stub_raises_not_implemented`) enumerates every module's stub entries in one shared file — implementing a module makes its own 4–5 lines there fail, forcing every wave-1 worker to edit the same shared file, guaranteed-conflicting with siblings.
- Cost: low (both workers self-diagnosed and just deleted their own lines, flagging the expected merge conflict in their final report) — not a wrong-path detour, but it directly contradicts the stated ownership rule and both workers had to notice and route around it independently.
- Category: PROCESS
- Evidence: `"I deleted the five csekit.lines entries from tests/tier0/test_schema.py's test_stub_raises_not_implemented list... expect a trivial conflict there; resolve by taking both deletions."` (#6); `"I had to edit tests/tier0/test_schema.py — its stub inventory lists csekit.score's four S4 entries..."` (#5)
- What would have prevented it: preamble should carve out `tests/tier0/test_schema.py`'s stub list as an explicit, named exception to "no shared-file edits" ("every module deletes its own N lines from the shared stub inventory when implementing — this is expected, not a violation") so workers don't have to discover and self-justify it.

## What went smoothly because the prompt/issue supplied it
- Exact reuse function names + source files per issue ("read `src/lexicon.py` (`lexicon_spans`, `score_text`...), `src/uncertainty.py` (`block_bootstrap`...), `app/engine.py` `slant_readout`") → both workers went straight to the right files instead of grepping the whole `parot-bias` repo blind.
- The eSPD penalty formula was handed over pre-derived with paper citations ("`penalty(l) = -1+2/(1+exp(-p(l-1)))`, p = ln(3)/89... §3.2.2/§4.2/§5.1") → #6 implemented and cited the formula with zero re-derivation from the paper; the only paper-reading it did was for corroborating window/skepticism semantics.
- Explicit staged-execution instruction ("develop fully against fixtures... if real data exists when you're done, RUN the real sweep... if not, say so and stop") → both workers cleanly reported "stopped at fixtures, lexicon not landed" instead of guessing whether to block on missing upstream data.
- Exact worktree bootstrap commands in the preamble (`git worktree add ... -b issue-<N>-<slug>`, `ln -s .../data data`, `uv sync`) → zero fumbling in either session's first 20 seconds of setup.
- Threshold-selection protocol stated up front ("Choose threshold on train, report test ONCE") → no risk of test-set leakage bugs needing a later fix.
- Fixture files pre-built with documented expected behavior ("the 2 synthetic predator authors must rank top-2; prefilter drops the <6-msg author") → gave both workers a concrete, checkable correctness oracle for tier0 tests with no ambiguity about what "correct" output looks like.
- `justfile`'s explicit "CI contract is only the two aggregates at the bottom" comment → workers immediately knew which gate commands mattered vs. which were free to edit.

## Generalizable lessons (≤8 bullets, each a rule for writing the NEXT issue/prompt)
1. State the real corpus's scale up front (row/author/message counts) so workers vectorize gold-lookup/join code from the start instead of writing a naive per-row scan that only breaks at real scale.
2. Explicitly say "prefix any full-suite command (`just ci-fast`, `just ci-deep`) with `queue`" in the preamble — every worker hits the heavy-command block cold otherwise.
3. Pre-authorize the ci-fast-aggregate workaround: "if the queued aggregate gate is blocked >2 min behind another job, run its components individually and report those as green."
4. When telling a worker to reuse a function, name its exact return shape (tuple vs. dataclass vs. dict) — `ty check` is currently the only thing that catches a wrong assumption here, costing a full edit-test round trip.
5. Carve out the shared stub-inventory file (`tests/tier0/test_schema.py`) as a named, expected exception to "no shared-file edits" instead of leaving each worker to discover and self-authorize the conflict.
6. When one worker's real-data run surfaces a durable corpus fact (annotation quirk, scale, non-obvious invariant), route it into a place downstream issues will actually read (PLAN.md or the parent tracking issue) rather than only a peer-to-peer final report — #5's "scale is population-dependent" and #6's "recall ceiling ≠ 1.0" were both flagged forward manually and could easily be missed by a future issue's worker who never reads these two PR threads.
7. Instruct background timing/measurement scripts to always use `run_in_background: true` rather than `sleep N; cmd` chains — the latter got silently reaped mid-run in #5.
8. A staged "fixtures first, then real data if present, else stop and say so" instruction works well — keep using it; it fully eliminated ambiguity about whether to block on upstream issues (#3/#4) landing mid-task.

## Stats
- Friction events by category: SCALE/RUNTIME 3 (F4, F5, F7), ENV/TOOLING 2 (F1, F2 — F2 double-counted across sessions, root cause is one issue), FALSE-ASSUMPTION-ABOUT-CODE 1 (F3), DATA-SHAPE/SCHEMA 1 (F6), PROCESS 1 (F8). No LEAD-CORRECTION or USER-CORRECTION events in either session (single dispatch message, zero mid-session interventions from team-lead or user in both transcripts).
- Rough share of session spent on friction vs. productive work: #5 ~20% (mostly F4/F5 queue-wait/duplicate-process overhead, F1/F3 small); #6 ~30% (F7's perf-bug hunt alone was roughly a quarter of the session's wall clock).
