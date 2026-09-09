# Issue #31 (tune/phase 5: decision & calibration) — session 9afb1246-b1ff-480b-b3bf-12d72b7ad26f

Session overview: Dispatch (00:00:31) told teammate "w31" to own issue #31 end-to-end (threshold grid/tie-break, pinned
logistic scale, F0.5 operating point + CV band, and author-scale calibration of Aegis/ToxicChat for a real Table 4),
working only in a dedicated worktree, in a 4-issue parallel batch (#28/#29/#30 as siblings owning other files/modules
of the same epic #25). Session ran 00:00:31 → 04:04:34 (~4h04m wall clock, most of it parked waiting on sibling
PRs #28/#29/#30 to merge). ~289 tool calls. PR #37 opened as draft at 00:40:00, sat parked at the gate from ~01:09
until the lead's GO at 03:41:41, finalized and merged into `dev` at 04:03:14 (merge `38a711b`). Issue #31 closed,
epic #25 commented with the headline. 6 mid-session `<teammate-message>` interventions from the lead (beyond the
initial dispatch); 2 were pure status pings (siblings merged, rebase now), 1 was a "GO" signal, and 3 carried
information the agent needed and didn't already have (see F1, F3, F5).

## Friction events (chronological)

### F1: Live-scorer calibration pass launched bare, not through the shared-box queue
- When: 00:19 → corrected 00:23 (turn ~40)
- What the agent was trying to do: kick off `scripts/generate_calibration_report.py --author-scale` (a ~34k-text
  live scoring pass over Aegis/ToxicChat) in the background while other work continued.
- What it assumed / where it looked: ran it directly (`uv run scripts/generate_calibration_report.py --author-scale
  > cal.log 2>&1`, `run_in_background: true`) without ever grepping/reading the README's queue section — despite
  step 1 of the dispatch explicitly listing "README.md (Worktrees, queue, ...)" as required reading. A `rg -i queue`
  over the whole timeline up to that point returns zero hits.
- What was actually true: the box is shared by 4 worker sessions; a bare live-scorer pass thrashes memory ("memory
  is the cliff, not cores") and a sibling (w28) had already been OOM-killed. Only `just ci-fast` run bare triggered
  an automated guard message (a hook that recognizes `just` recipes); the raw python invocation slipped past it
  because it isn't a `just` recipe, so nothing caught this until a human did.
- Cost: ~4.5 min of a heavy pass running unqueued on a shared box (00:19:13 → 00:23:51 `TaskStop`), 1 lead message,
  3 tool calls to stop/resubmit correctly.
- Category: LEAD-CORRECTION / ENV-TOOLING (queue)
- Evidence:
  - `just ci-fast` is heavy and was not sent to the queue... memory is the cliff, not cores.` (auto-guard, 00:21:23)
  - `Reminder (w28 just got OOM-killed mid-run): four workers share this box. Every live-scorer pass (incl. your
    generate_calibration_report.py --author-scale, which is running bare right now) MUST be...` (lead, 00:23:38)
  - `Critical memory warning — my --author-scale calibration is a live-scorer pass running bare and must go through
    the single-slot queue.` (agent, 00:23:51)
- What in the issue/prompt would have prevented it: the dispatch already said "Heavy runs go through the repo's
  `queue` prefix" — but it named no concrete commands. It should have said explicitly: "every live-scorer pass,
  INCLUDING `scripts/generate_calibration_report.py` and any bare `uv run python -c ...` scoring script, must be
  prefixed with `queue`, not only `just ci-fast`" — the automated guard only catches `just` recipes, so anything
  else is the agent's own responsibility.

### F2: CI-gated test file location — issue itself pointed at an ungated path
- When: 00:25 → 00:27 (turn ~55)
- What the agent was trying to do: add author-scale calibration tests per the dispatch's file list ("`tests/tier0/
  test_tune_decision.py` (+ `tests/test_calibrate.py` additions)").
- What it assumed / where it looked: added its calibration tests to `tests/test_calibrate.py` (root `tests/`) as
  literally named in the dispatch.
- What was actually true: `just ci-fast` / CI is path-gated on `tests/tier0` only (`pytest.ini_options` markers +
  the justfile recipe). `tests/test_calibrate.py` sits outside `tests/tier0` and is never collected by the gate —
  discovered only by deliberately diffing `pytest tests/tier0 --collect-only` against the file list.
- Cost: ~5 tool calls (rg pyproject.toml, inspect CI workflow, collect-only diff) + had to move the new tests into
  a brand-new `tests/tier0/test_calibrate_author_scale.py` and revert the `tests/test_calibrate.py` edit.
- Category: SPEC-AMBIGUITY / PROCESS
- Evidence:
  - `But just test runs only tests/tier0 — let me confirm whether tests/test_calibrate.py is actually in the gate`
  - `Confirmed: ... tests/test_calibrate.py (both #7's and my additions) is NOT under tests/tier0, so it's outside
    the CI gate. I'll move my author-scale calibration tests into a gated tier0 file.`
- What in the issue/prompt would have prevented it: the dispatch should not have named a specific test file for
  additive test coverage unless it had verified that file is inside the CI-gate path; either point at
  `tests/tier0/` directly, or add one line: "verify any test file you touch is under `tests/tier0` — that's the
  only path `ci-fast` collects."

### F3: CV band computed with all-train weights leaks held-out predators into every fold ("optimistic" vs "honest")
- When: self-flagged by lead at 01:08 after the agent had already declared phase 5 "complete through the gate" at
  00:41 (turn ~150)
- What the agent was trying to do: build the F0.5-optimal operating-point θ with a CV confidence band per the
  dispatch's box (i): "per-fold θ and F0.5 → mean±sd / percentile band."
- What it assumed / where it looked: computed the CV band by resampling folds over the cached count matrix whose
  weights (lexicon admission, gate) were mined once on ALL of train, then reused unchanged in every fold.
- What was actually true: that band is "optimistic" — each fold's evaluation includes predators whose signal
  leaked into the shared weight-mining pass. The methodologically-honest band requires per-fold weight
  re-derivation from that fold's TRAINING rows only — a fact that lived nowhere in #31's own issue or the #25
  binding-ground-rules issue; it surfaced only because sibling #29 built the per-fold-weights machinery for its own
  CV and the lead relayed the implication to #31.
- Cost: work built and validated against the wrong (optimistic-only) band from ~00:30 to 01:08 (>30 min), then
  had to park until #29 merged (03:12) to reuse its honest per-fold machinery, then rewire `tune_decision.py` to
  report both bands.
- Category: MISSING-DOMAIN-CONTEXT / LEAD-CORRECTION
- Evidence:
  - `Protocol note for your finalization (found on #29): CV bands computed with weights/gates derived from ALL
    train labels leak the held-out fold's predators.` (lead, 01:08:13)
  - `Critical protocol note for finalization: my current CV band is the optimistic one — the count matrix's weights
    are mined on all train, so they leak held-out predators into every fold.` (agent, 01:08:35)
- What in the issue/prompt would have prevented it: the CV methodology (repeated stratified grouped CV) is a
  binding ground rule shared by every tuning issue in the epic (#25) — the leakage pitfall (weights/gate/prior
  must be re-derived per-fold from that fold's training rows only, not mined once on all-train) is a property of
  the SAME shared harness every sibling issue touches, and should have been stated once in #25 (or the phase-0
  harness docstring) rather than discovered independently per-issue and relayed ad hoc.

### F4: `biaskit` reference lookup — assumed a package directory, it's a flat re-export shim
- When: 00:02:31 → 00:03:47 (turn ~8)
- What the agent was trying to do: understand the origin of `logistic_scale`/`MIN_EVIDENCE`/`bias_score`, which
  `csekit/calibrate.py` imports from the sibling repo's `biaskit` package, to reuse the same centring+scale+squash.
- What it assumed / where it looked: assumed `biaskit` was a package directory (`biaskit/*.py`) inside
  `/Volumes/external/dev/fsa/parot-bias`; `rg 'biaskit/'` returned "No such file or directory."
- What was actually true: `biaskit.py` is a flat single file that just re-exports the real implementation from
  `src/lexicon.py` (`logistic_scale`, `bias_score`) and `src/article_view.py` (`MIN_EVIDENCE`).
- Cost: ~7 tool calls (failed `rg biaskit/*.py`, failed `fd`/`rg biaskit/` IO error, `ls` to discover the flat
  file, two more greps before finding the re-export line, then locating `src/lexicon.py`).
- Category: WRONG-PATH
- Evidence: `rg: biaskit/: IO error for operation on biaskit/: No such file or directory (os error 2)`
- What in the issue/prompt would have prevented it: one line in the dispatch pointing straight at the source:
  "the author-scale squash logic your calibration must match lives in
  `/Volumes/external/dev/fsa/parot-bias/src/lexicon.py:logistic_scale`/`bias_score` — `biaskit.py` is only a
  re-export shim, not a package."

### F5: Sibling #28's winning unit forced an unplanned unit-agnostic refactor mid-flight
- When: 00:22 heads-up → refactor 00:28-00:31 (turn ~60)
- What the agent was trying to do: build decision/calibration code against the shipped author-concatenated-mean
  score matrix, per the dispatch's framing of the existing pipeline.
- What it assumed / where it looked: built the first pass of `tune_decision.py`/`calibrate.py` assuming that fixed
  matrix shape.
- What was actually true: sibling #28 (still in flight, same epic) landed a different scoring UNIT
  (per-conversation-summed weight → author MAX rollup, not the author-concatenated mean) — unknowable at dispatch
  time since #28 hadn't finished — requiring #31's cores to be rewritten unit-agnostic (`agg` parameter) before
  finalizing.
- Cost: a full refactor pass (~15 tool calls: rewrite `tune_decision.py`, thread `agg` through `calibrate.py` and
  `generate_calibration_report.py`, new tests) — necessary regardless, but would have been done once instead of
  twice if built unit-agnostic from the start.
- Category: SCOPE-CREEP/UNDER-SCOPE (inter-issue dependency, not really preventable at dispatch time)
- Evidence: `Key info: #28 merged (2a3f857); shipped unit is agg-sum-max ... My unit-agnostic cores + agg="sum"
  calibration are already built for this.` (00:36:52)
- What in the issue/prompt would have prevented it: when dispatching parallel siblings in the same epic that share
  a scoring pipeline and one (#28) is explicitly still choosing a design axis (aggregation unit), tell the
  downstream issue up front to build its core math parameterized/unit-agnostic from day one rather than against
  today's shipped default — the dispatch already flagged the PARALLEL SIBLINGS list but not this specific
  "expect the unit to change under you" risk.

### F6 (minor): Superset count-cache location found by trial and error at finalize
- When: 03:55:45 → 03:56:59 (turn ~330)
- What it assumed: tried `fd`/`ls data/**/full*` glob patterns to find the cached superset count matrices.
- What was actually true: cache root is `csekit/tune.py:COUNTS_ROOT = DATA_DIR / "tune" / "counts"`, keyed by
  `split/unit/sha`, not a `full*`-named directory.
- Cost: ~4 tool calls (empty glob results, then had to grep `csekit/tune_weights.py`'s `load_full_counts` docstring
  and `csekit/tune.py`'s `COUNTS_ROOT` constant to find the real layout).
- Category: WRONG-PATH
- What would have prevented it: dispatch could have stated the cache path constant/layout once (`COUNTS_ROOT`,
  `split/unit/sha`), since every phase in the epic needs to locate this cache.

## What went smoothly because the prompt/issue supplied it
- Explicit file/module ownership list ("YOUR ownership: `csekit/calibrate.py`, `csekit/tune_decision.py`, ...")
  → three clean rebases onto siblings' merges (#28, #29, #30) with zero conflicts across the whole session.
- "Binding ground rules (#25): TRAIN-only ... never refit [scale] on test... #31 has NO PAN12 test touch" → the
  agent never once queried or scored against PAN12 test; no wasted exploration of whether it was allowed to.
- "queue is single-slot and shared with siblings — submit, don't spin" + Monitor tool guidance → after F1's
  correction, all subsequent long-running jobs were submitted via `queue` and awaited via `Monitor`/task
  notifications rather than polling loops (verified: no further bare heavy runs, no `sleep`-based polling after
  00:24).
- "Final report ≤12 lines: PR URL, merge sha, chosen θ + CV band, ..." → the final SendMessage to the lead matched
  that exact structure with real numbers, no padding.
- "No new deps unless unavoidable" / "additive only" to `score.py`/`lexicon.py` → the agent never touched those
  files' existing functions; the one true blocker (parquet dtype crash) was in its own new script, fixed in 2 tool
  calls without touching shared code.
- "NO Co-Authored-By lines" (from user's global CLAUDE.md, reinforced by dispatch) → every commit followed this
  with no correction needed.
- Step-4 merge policy ("never squash", "gh pr update-branch --rebase if behind") → merge mechanics at 04:02-04:03
  were followed exactly with no missteps (checked mergeable/clean, `--merge` not squash).

## Generalizable lessons
1. Name the concrete commands that must go through `queue`, not just the policy — an automated guard may only
   catch `just` recipes; anything else (raw `uv run` scripts) is on the agent, and a shared box means one miss can
   OOM a sibling.
2. Before naming a specific test file path in a dispatch, verify it's actually under the CI-gate's collection path
   (e.g. `tests/tier0/`) — don't let the dispatch prompt itself point the agent at an ungated file.
3. State cross-cutting methodology pitfalls (like CV weight/gate leakage across folds) once in the shared
   ground-rules issue that every sibling tuning issue inherits, not per-issue after one sibling stumbles onto it.
4. When a downstream issue's output depends on a sibling issue's still-undecided design axis (e.g. scoring unit),
   say so explicitly and tell the downstream issue to build that axis as a parameter from day one.
5. When telling an agent to reuse constants/behavior from another module (a shared cache root, a squash function
   in a sibling repo), give the exact symbol/file path — don't make it rediscover the module layout by trial glob.
6. A "read README.md's queue section" instruction buried in a longer reading list is easy to skip in practice;
   consider a standalone one-line reminder right before the first heavy command is likely to run.
7. Explicit ownership boundaries (exact file list per parallel sibling) reliably prevented merge conflicts across
   three separate rebases — keep doing this for any multi-worker batch on a shared codebase.
8. A tight final-report template (exact fields, line cap) reliably produces a clean, complete handoff — keep
   specifying it verbatim in the dispatch.

## Stats
- Friction events by category: LEAD-CORRECTION 2 (F1, F3) · ENV-TOOLING 1 (F1, overlaps) · SPEC-AMBIGUITY/PROCESS 1
  (F2) · MISSING-DOMAIN-CONTEXT 1 (F3, overlaps) · WRONG-PATH 2 (F4, F6) · SCOPE-CREEP/UNDER-SCOPE 1 (F5)
- Rough share of session on friction vs productive work: ~15-20% (most of the 4h wall clock was legitimate parked
  waiting on sibling PRs/queue jobs, not confusion; friction proper — F1 through F6 — accounts for roughly 30-40
  min of the ~90 min of actual working time, concentrated at session start and at finalize).
