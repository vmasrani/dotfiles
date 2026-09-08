# #29 — session 946ada50-0f19-428f-b8f6-a62fcee9e8c2

Session overview: Issue #29 (epic #25 phase 3: "tune/phase 3: weights & vocabulary — weight column,
aggregation, admission gate, prior/min_df, NB full-vocab cell, LR diagnostic upper bound") in
sophiaconsulting/parot-cse, worked by agent "w29" in worktree `parot-cse-wt/issue-29`. First→last
timestamp 23:59:36 → 03:11:57 (~3h12m wall clock, one mid-session context compaction at 01:27:49).
~404 tool calls. Finished and merged: PR #38 → dev (merge `f279434`), issue #29 closed, #25 commented.
9 team-lead interventions (`<teammate-message>`) landed mid-session (4 of them delivered in one batch
at 01:08:04 after the agent had been heads-down for ~68 min).

## Friction events (one block each, chronological)

### F1: Full sweep + draft PR built on label-leaky CV, invalidated after ~68 minutes
- When: [00:00–01:10] (turn ~1–~120)
- What the agent was trying to do: implement the phase-3 weight/vocab sweep per issue #25's ground
  rule "every experiment runs on TRAIN with repeated stratified k-fold CV... report mean±sd F0.5."
- What it assumed / where it looked: computed weight columns (logodds/z/g2), admission gate, prior,
  and min_df **once from all-train labels**, then evaluated via CV folds on top of that — a classic
  leak (the label-derived stats for a fold have already seen that fold's held-out predators). Reported
  a headline **NB-fullvocab-logcountratio CV F0.5 0.8824±0.041**, essentially matching the LR upper
  bound, opened draft PR #38 titled "NB full-vocab wins CV F0.5 0.88", messaged team-lead at the
  test-touch gate.
- What was actually true: issue #25's ground rules describe the CV *evaluation* protocol but never
  spell out that label-derived quantities (weights/gate/prior/min_df) must be **re-derived per fold
  from that fold's training rows only**. Team-lead caught it structurally ("counting beats LR by
  +0.20 is the leakage signature, not counting being better than discrimination") and issued a HOLD,
  requiring a full rewrite: per-fold honest derivation, dual optimistic/honest reporting, re-pick
  winner on honest column. Honest winner ended up **0.6489±0.080** — a different config family
  entirely, not the full-vocab NB cell.
- Cost: ~90+ tool calls / ~68 minutes of work (full module + grid + draft PR) substantially reworked;
  another ~40 min (01:10–01:49) spent implementing the dual protocol, re-sweeping, and re-presenting.
- Category: SPEC-AMBIGUITY / ACCEPTANCE-UNCLEAR (also MISSING-DOMAIN-CONTEXT — this is a standard
  ML pitfall the epic's ground rules didn't name)
- Evidence:
  - "LEAKAGE: you wrote the winner uses 'all-train weights'... that is the signature of label
    leakage, not of counting being better than discrimination." (team-lead, 01:08:04)
  - "phase-0/2 CV numbers share the milder version of the same leak through the shipped lexicon"
    (team-lead — confirms this is a systemic gap across the whole epic, not #29-specific)
  - "The team-lead's HOLD supersedes the GO. Two substantial changes before I can spend the touch:
    (1) fix CV label-leakage..." (agent, 01:10:34)
- What in the issue/prompt would have prevented it: the epic's ground rules ("Ground rules (all
  phases)" in #25) should state explicitly: *"Any quantity derived from labels (weight column,
  admission gate, prior, min_df) must be re-derived per CV fold from that fold's TRAINING rows only
  — never from all-train labels before splitting. Report optimistic (all-train) vs honest (per-fold)
  side by side; pick the winner on honest."* This single sentence, present from phase 0 onward, would
  have prevented the leak in #29 (and, per team-lead's own admission, in phases 0–2 as well).

### F2: LR diagnostic (saga) doesn't converge in reasonable time on 76k features
- When: [00:30–00:37] (turn ~35)
- What the agent was trying to do: fit the elastic-net LR diagnostic (sklearn `LogisticRegression`,
  `solver=saga`) on the full 97,689×76,254 count matrix as part of a smoke sweep, to size the full
  grid's wall-clock budget.
- What it assumed / where it looked: assumed saga would converge in a reasonable multi-minute window
  like the rest of the sweep (counting configs finished in seconds).
- What was actually true: saga on 76k sparse features at extreme class imbalance (142/97,689
  predators) didn't converge inside the 30-min target — it was still running past 13 minutes with
  buffered stdout giving no progress signal.
- Cost: ~13 minutes of wall-clock waiting + 1 kill + a diagnostic rewrite (switch to `SGDClassifier`,
  elastic-net/log-loss, which fits in seconds on sparse data).
- Category: SCALE/RUNTIME (job too slow)
- Evidence: "stdout is buffered so I can't see LR progress, but >13 min is unacceptable. Let me kill
  the run and make the LR tractable." / "SGD on sparse is seconds, not minutes."
- What in the issue/prompt would have prevented it: the dispatch prompt already named
  `LogisticRegression` generically ("elastic-net LR... scikit-learn already present"); naming the
  solver constraint up front — *"use SGDClassifier(loss='log_loss', penalty='elasticnet') for the LR
  diagnostic, not LogisticRegression(solver='saga') — saga does not converge in budget on the full
  ~76k-term vocabulary"* — would have saved the 13-minute dead-end entirely.

### F3: Duplicate queue job submitted across a context-compaction boundary
- When: [01:37:08] (turn ~130, shortly after the 01:27:49 compaction)
- What the agent was trying to do: build the `conversation_author` superset matrix needed for the
  honest re-sweep on #28's shipped unit.
- What it assumed / where it looked: after the mid-session compaction, the agent (working from the
  compaction summary, not the raw history) submitted a `queue` job for the build without checking
  whether a prior instance of itself had already queued the identical command.
- What was actually true: a pre-compaction invocation had already submitted the same build (job 315);
  the new submission (316) was a same-command, same-dir duplicate. Team-lead caught it via
  `queue --triage`.
- Cost: ~6 tool calls to diagnose which job (315 vs 316) the agent's *live* shell was actually
  attached to (PID-tag matching) before safely cancelling the true duplicate.
- Category: ENV/TOOLING (queue, compaction) / LEAD-CORRECTION
- Evidence: "`queue --triage` shows you submitted the conversation_author build twice: jobs 315
  ((file) output) and 316 (stdout), same command, same dir." (team-lead, 01:37:08)
- What in the issue/prompt would have prevented it: not really preventable via issue text — this is
  a compaction-hygiene gap. Worth a standing dispatch-prompt line: *"Before submitting any `queue`
  job, run `queue --triage`/`--list` and grep for your own command string first — especially right
  after a context compaction, since queued background jobs from before the compaction are not in
  your summarized history."*

### F4: Cross-split vocabulary mismatch in the test-touch scorer (self-caught bug)
- When: [02:43–02:57] (turn ~330, during final close-out)
- What the agent was trying to do: pre-build the test-split count matrices ahead of spending test
  touch #2, to make the actual touch a light foreground step.
- What it assumed / where it looked: built the test matrix over **test's own mined vocabulary**
  (145,723 terms) — a design that seemed natural for "test matrices."
- What was actually true: the weight vector chosen by the honest CV winner is indexed by the
  **train** superset vocabulary (76,254 terms); scoring test requires counting the **train**
  vocabulary's terms in test messages (the same fixed-lexicon design phase-0/2 already used via
  `build_counts(lex_train, split="test")`). The mismatch produced a matmul dimension error
  (`ValueError: Scalar operands are not allowed...`) only surfaced when the touch was actually run.
- Cost: ~15 tool calls / ~15 minutes: diagnose the traceback, add `over_vocab`/`--over-split` plumbing
  to `build_full_counts`/`_load_context`/`_test_touch`, rebuild the correct test-over-train-vocab
  matrices, add 2 regression tests, re-verify ci-fast, amend the commit.
- Category: FALSE-ASSUMPTION-ABOUT-CODE / DATA-SHAPE-SCHEMA
- Evidence: "the touch reached `_test_touch`... errored before the ledger append" / "`_test_touch`
  builds the test matrix over **test's own** vocabulary... but the weight vector is indexed by the
  **train** superset → matmul dimension mismatch. My pre-built test matrices... are the wrong
  artifact." / team-lead later: "good catch on the cross-split vocab — the test touch must score the
  FIXED train lexicon in test."
- What in the issue/prompt would have prevented it: an explicit invariant in the epic ground rules or
  #29's own text: *"Test-touch scoring always counts the TRAIN-fixed vocabulary/lexicon in test
  messages — never test's own mined vocabulary. This is the fixed-lexicon design already used by
  phase-0/2's `build_counts(lex_train, split='test')`."* One sentence would have prevented building
  the wrong artifact.

### F5: "Went idle" status check from team-lead during a legitimate wait
- When: [02:58:42] (turn ~360)
- What the agent was trying to do: wait on a background `queue` build (`byumgl2qz`) before running
  the final test touch, having already reported state at 02:58:12.
- What it assumed / where it looked: relied on the tool-notification mechanism to re-invoke it when
  the build finished, without an interim status ping.
- What was actually true: from the team-lead's view, ~30s of silence after a status message (with
  touch #2 still unspent and PR still draft, after several OOM/kill scares earlier in the session)
  looked indistinguishable from a stalled agent, prompting a "what's the blocker?" message.
- Cost: 1 extra round-trip (SendMessage exchange); no real work lost, but it interrupts the wait.
- Category: PROCESS (workflow kit / status cadence)
- Evidence: "You went idle at 02:58 with touch #2 still unspent... What is the current step..."
  (team-lead) / "Checking the build now and proceeding — not idle." (agent)
- What in the issue/prompt would have prevented it: minor — could note in the dispatch prompt that a
  one-line "waiting on <job-id>, ETA ~Nm" SendMessage right before a long background wait avoids a
  false idle read, especially late in a session that already had OOM/kill scares.

## What went smoothly because the prompt/issue supplied it
- Exact worktree path + branch + base sha ("origin/dev at ade2475") → agent verified state in one
  `git status`/`git log` call, zero wrong-directory risk.
- Named ownership boundaries ("new `csekit/tune_weights.py`... do NOT edit existing functions in
  `csekit/tune.py`/`score.py`/`lexicon.py`") → zero cross-file conflicts with siblings #28/#30/#31
  the entire session; rebases onto #28 stayed clean/no-conflict twice.
- Exact file+line pointers ("`csekit/score.py` `prepare_lexicon(weight_col=…)` ~line 149,
  `MIN_EVIDENCE`, `Z_GATE`, `FDR_Q`, `VOCAB_CAP`, `DF_PER_DOCS`") → orientation phase (00:00–00:04)
  hit every named symbol on the first `rg`/`Read`, no missed-context backtrack.
- Explicit read list for step 1 (CLAUDE.md, AGENT_WORKFLOW.md, README, justfile, PLAN.md, `tune.py`,
  `tune_sweep.py`, sample grid, sample report, `score.py`, `lexicon.py`, `test_tune.py`) → the agent
  never had to search for "where do I even start"; ~15 focused reads and it had full context.
- "No new dependencies unless unavoidable (scikit-learn already present... check pyproject.toml
  first)" → agent verified deps in one `rg` against pyproject.toml instead of guessing/adding one.
- Sibling ownership map with exact modules (#28 owns `tune_twostage.py`/`tune_twostage.py` "stage/agg
  code", #30 owns `lexicon.py` mining, #31 owns `calibrate.py`) → gave the agent the right place to
  look when #28's unit changed, even though the actual module name differed from the stated one
  (`csekit/tune_stage.py`, not `tune_twostage.py` — a small mismatch, ~3 tool calls of detour, not
  logged as its own F-event since it self-resolved in under 2 minutes).
- "Test touch #2 via `just tune-test-touch` ONLY ONCE, at the END, ONLY after my go" + explicit gate
  step (step 4/5 split) → the agent never risked spending the shared epic's scarce test-touch budget
  prematurely, even through two leakage rewrites, a unit change, and two kill scares; it correctly
  held at the gate every time and asked before spending.
- "queue --triage"/PID-tag mechanics were discoverable and the team-lead's OOM-vs-stop-gesture call
  ("Not me and not a stop gesture — assume OOM... your mitigation is right") let the agent proceed
  confidently instead of guessing.

## Generalizable lessons (≤8 bullets, each a rule for writing the NEXT issue/prompt, phrased as an imperative)
1. When a CV protocol has ANY label-derived preprocessing step (feature weights, gates, priors,
   thresholds, vocabulary selection), state explicitly that it must be refit per-fold from
   training-fold data only — never assume "CV" implies this; spell it out as its own ground rule.
2. When a scoring/evaluation path involves two different data splits, state the vocabulary/feature
   direction explicitly (e.g. "score split B by counting split A's fixed vocabulary in B's text,
   never split B's own vocabulary") — cross-split feature mismatches are a classic self-inflicted bug
   that only a runtime error catches.
3. When a diagnostic/comparator model must run at a specific scale (e.g. 76k sparse features), name
   the solver/estimator explicitly if a common default (LogisticRegression(solver='saga')) is known
   to be intractable at that scale — one sentence saves a multi-minute dead run.
4. Sibling-PR ownership maps prevent conflicts, but keep module names loosely stated ("the unit logic,
   check the module that implements it") rather than a specific filename when you're not 100% sure —
   a wrong filename costs a few detour calls even when the rest of the map is right.
5. After a context compaction, background jobs already in flight are not visible in the compacted
   summary — instruct the agent to check `queue --list`/`--triage` for its own already-running work
   before resubmitting anything heavy.
6. Exact file+line pointers for the core API surface (as this prompt did) reliably eliminate
   orientation-phase wrong turns — keep doing this; it is the single highest-leverage practice
   observed in this session.
7. A systemic protocol gap (like the CV leakage here) discovered mid-phase should immediately be
   back-ported into the epic issue's ground rules text, not just relayed as a one-off correction —
   this session did retroactively note it on #25, which is correct practice; make it explicit in the
   dispatch prompt template ("if you find a ground-rule gap, comment it on the epic issue, not just
   fix your own branch").
8. For long unattended waits late in a session with prior kill/OOM scares, have the agent proactively
   post a one-line "waiting on <job>, ETA ~Nm" before going quiet — avoids a false "is it stuck?"
   ping-pong with the lead.

## Stats
- Friction events by category:
  - SPEC-AMBIGUITY / ACCEPTANCE-UNCLEAR: 1 (F1 — also tagged MISSING-DOMAIN-CONTEXT)
  - SCALE/RUNTIME: 1 (F2)
  - ENV/TOOLING: 1 (F3)
  - FALSE-ASSUMPTION-ABOUT-CODE / DATA-SHAPE-SCHEMA: 1 (F4)
  - PROCESS: 1 (F5)
  - (LEAD-CORRECTION overlaps F1 and F3 — both were caught by the team-lead, not self-caught; F4 was
    self-caught via a runtime error)
- Rough share of session spent on friction vs productive work: ~45% friction (dominated by F1's
  ~110-minute leakage-fix cycle: build leaky sweep → present → HOLD → rebuild honest dual-protocol
  sweep → re-present) vs ~55% productive (initial harness build, tier0 tests, final honest sweep
  itself, close-out mechanics, PR/report writing). F1 alone accounts for the large majority of the
  friction share; F2–F5 combined are under 10% of total wall clock.
