# #32 (PR #40, follow-up #44) — session 9e46e4e8-a472-40f3-bfca-d677f7782a11

Session overview: issue #32 = epic-#25 phase 6, "lines & early detection" — offline tuning harness for Problem-2
line-flagging rules (weight>t/smoothed>t/after_changepoint/CUSUM) and eSPD (skepticism × window × penalty), built
on the tuned lexicon from sibling issues #29/#30. Ran 00:40:59 → 04:48:09 (≈4h07m wall clock), 425 tool_use calls
(236 Bash, 103 Edit, ~20 Read-only-shown truncated). Finished: PR #40 merged into dev (`0e8edda`), issue #32 closed,
follow-up issue #44 filed for a `nan` baseline cell. 6 team-lead interventions (2 protocol/scope-changing mid-flight
corrections, 1 decision on worker's own empirical finding, 1 stale "are you idle" ping, 1 initial dispatch, 1 final
pivot-to-stop message after this transcript's captured window). No user-typed corrections — all steering came from
the team-lead.

## Friction events (one block each, chronological)

### F1: Late-arriving CV leakage protocol note forced an injection-point refactor
- When: [01:17] (turn ~40)
- What the agent was trying to do: finish the CV harness (espd_cv/rules) as originally scoped and queue the heavy sweep.
- What it assumed / where it looked: that all-train-derived weights, scored on held-out folds, were an acceptable "optimistic" default — this is standard practice elsewhere in the repo's existing `tune.py`/`tune_weights.py` units it had been told to mirror.
- What was actually true: this leaks the fold's own predators into the weights (label leakage). The team lead only flagged this after the worker had drafted the harness, via a mid-session `<teammate-message>`, citing a discovery made on sibling issue #29 — not something in the original issue/epic text.
- Cost: ~20 tool calls, ~7 minutes to build an injection point + protocol-note reply; the REAL cost surfaces later at F5 (50 min) because the note was ambiguous about the leak-free derivation's granularity ("fold's training rows").
- Category: LEAD-CORRECTION / SPEC-AMBIGUITY
- Evidence: "weights/gates/priors derived from ALL train labels and evaluated on held-out train folds leak the fold's predators" (team-lead, 01:17); "Protocol note note — leakage from all-train weights. Let me check what's already in `csekit/tune_weights.py` (w29's territory)" (agent, 01:18).
- What in the issue/prompt would have prevented it: state the leakage rule in epic #25's ground rules up front (it's a general CV-hygiene fact, not #29-specific), AND specify the exact unit of leak-free derivation ("per-fold weights are derived at the MESSAGE level, matching the lexicon's own construction — not author level") — this exact ambiguity is what caused F5.

### F2: `csekit/tune_weights.py` didn't exist yet — dependency not actually landed
- When: [01:18] (turn ~42)
- What the agent was trying to do: reuse #29's per-fold-weights helper per the protocol note.
- What it assumed / where it looked: `ls -la csekit/tune_weights.py` and `rg` for fold/weight symbols in it.
- What was actually true: file doesn't exist on the worker's base yet (#29 hadn't merged) — `ls: No such file or directory`.
- Cost: 2 tool calls, <2 min; cheap because the agent guessed right and moved on (injection point, defer to step 5).
- Category: MISSING-DOMAIN-CONTEXT
- Evidence: "ls: csekit/tune_weights.py: No such file or directory"
- What in the issue/prompt would have prevented it: the dispatch already said #29 "will merge soon and may change..." — could be tightened to "NOT YET MERGED as of dispatch; do not assume its files exist until step 5."

### F3: Sweep SIGTERM'd (OOM) — pmap held full corpus in memory at once
- When: [01:42]–[01:56] (turn ~95)
- What the agent was trying to do: run the real per-message count-matrix build + CV sweep over all ~304k train messages via the shared single-slot `queue`.
- What it assumed / where it looked: that `pmap`-based `value_counts` over each message (mirroring the existing `tune.py` pattern) would fit in memory like the author-unit build does.
- What was actually true: `pmap` materializes ~304k `value_counts` Series simultaneously (~1GB+ peak) — the message-count build is much higher cardinality than the author-unit builds it was modeled on; job 317 got SIGTERM (exit 143) at 125s, the same watchdog that had already OOM-killed one worker per the dispatch's memory warning.
- Cost: 14 tool calls, ~14 minutes (kill notification → root-cause → chunked rewrite → re-verify → re-queue → completion).
- Category: SCALE/RUNTIME
- Evidence: "Job 317 got SIGTERM (exit 143) at 125s during the matrix build — memory pressure... `pmap` over all ~304k messages holds all 304k `value_counts` Series in memory at once (~1GB+)."
- What in the issue/prompt would have prevented it: the dispatch's memory warning ("one was already OOM-killed") was present but generic; naming the specific danger — "message-level builds are 100x higher cardinality than author-level ones already in the codebase; chunk any per-message pmap" — would have caught this in the design phase instead of after a real OOM.

### F4: "admitted-only is the shipped path" assumption baked in, then falsified empirically — 3-way refactor
- When: [01:25]–[02:33] (turn ~100–150)
- What the agent was trying to do: after an early team-lead decision ("admitted-only is the primary/shipped path, full-vocab is reference-only"), thread a boolean `admitted_only` through the harness and ship on that basis.
- What it assumed / where it looked: that lines/eSPD should mirror the *author* scorer's admission gate (positive-logodds-only), since the epic's stated premise is "one lexicon, one weight column" reused end-to-end.
- What was actually true: running the real sweep showed the admitted-only path collapses eSPD (F_latency ~0.199) vs. full-vocab's 0.568 — negative-weight *benign* terms (dropped by the positive-only admission gate) are exactly what let a clean window's score fall, which eSPD's discrimination depends on. This required a design escalation to the team lead and then generalizing `admitted_only: bool` into a 3-way `side` param (`full`/`admitted`/`both`) across ~8 functions, the report, and tests.
- Cost: 53 tool calls, ~68 minutes total (includes the empirical discovery, the lead round-trip, and the full refactor+re-sweep+re-verify).
- Category: FALSE-ASSUMPTION-ABOUT-CODE / MISSING-DOMAIN-CONTEXT
- Evidence: "the admitted-only path *collapses* eSPD... the negative-weight benign terms the admission gate drops... are exactly what give the line/eSPD detector its discrimination"; team-lead: "Decision: NOT (b)... Do (c')... add that variant (`admitted_both`)".
- What in the issue/prompt would have prevented it: nothing here was really preventable by more up-front text — it's a genuine empirical result the epic's own premise didn't anticipate. But once found, the *decision protocol* ("ship the better of two candidates unless within noise of a third") could have been given as a standing rule in epic #25 rather than negotiated live per-issue, since #31 (decision/calibration) surely needed the same statistical-tie logic.

### F5: "Per-fold weights from the fold's training authors" — author-unit vs message-unit granularity mismatch
- When: [03:19]–[04:10] (turn ~330–420) — the single biggest cost in the session
- What the agent was trying to do: implement the "honest" (leak-free) per-fold weight column from F1's protocol note, reusing #29's cached author-unit superset matrix per the team lead's literal wording ("weights... from the fold's TRAINING AUTHORS").
- What it assumed / where it looked: that deriving per-fold weights at the *author* granularity (reusing #29's `build_full_counts(split, "author")`, excluding the fold's test-conversation authors) was correct, since the lead's instruction said "authors" and #29's kernel only offers that unit. Spent ~35 min building this (reading #29's `CountMatrix`, coordinating a non-blocking confirmation message to w29, reindexing the author-unit weight vector onto the message vocab, threading it through the harness, tests, docs).
- What was actually true: author-unit logodds are systematically skewed positive (88% positive, corr 0.75 with message-unit) because a predator's message history is mostly benign chit-chat averaged into one author-level number — so almost every message clears threshold and the eSPD signal collapses (~0.195 across all sides, a clear "something's wrong" red flag the agent caught). The correct unit was **message-level**, matching the lexicon's own construction (which #29's protocol note didn't specify, and which #29's author-unit-only kernel didn't offer).
- Cost: 92 tool calls, ~51 minutes (build author-unit path → run sweep → see collapse → diagnostic probe (2 tool calls, corr/skew stats) → root-cause it in <2 min once probed → rewrite to message-unit → re-verify tests → re-run sweep → confirm recovery).
- Category: SPEC-AMBIGUITY / FALSE-ASSUMPTION-ABOUT-CODE
- Evidence: "author-unit logodds: 88% positive, sd 0.31, corr 0.75... so per-message means almost always clear the threshold → everything fires → collapse."; "message-unit logodds: frac>0 0.525... corr 0.919 with the shipped lexicon — faithful, discriminative."
- What in the issue/prompt would have prevented it: the protocol note (F1) should have said "message-level" explicitly instead of "training rows"/"training authors" — an ambiguous noun that pointed the agent at the wrong existing kernel (#29's, which is author-only). One sentence in the team lead's leakage note ("derive at the SAME unit as the lexicon itself, i.e. message-level, not author-level") would have saved the entire 51-minute detour.

### F6: Rebase-vs-merge contradiction between the dispatch and a repo-wide "producer sha" invariant
- When: [04:41]–[04:45] (turn ~500)
- What the agent was trying to do: follow step 5 of the dispatch verbatim — `git fetch origin dev && git rebase origin/dev (never merge dev in)` — after dev advanced past the branch's base with #31 merged.
- What it assumed / where it looked: did the rebase as literally instructed; resolved the `justfile` conflict; only afterward noticed the rebase rewrote the sha `788c1eb` (the touch-#4 report's producer sha, referenced by the ledger and reports) out of reachable history.
- What was actually true: a project-wide MEMORY convention read earlier (from CLAUDE.md/AGENT_WORKFLOW.md) states "reports name their producer sha: regen last, merge with `--merge` never rebase" — which directly contradicts the dispatch's explicit "never merge dev in." The agent had to `git reset --hard` back to the pre-rebase commit and redo the sync as a merge, re-resolving the same `justfile` conflict a second time.
- Cost: ~10 tool calls, ~5 minutes; low absolute cost but a genuine two-source contradiction the agent had to notice and adjudicate itself, mid-merge, with an irreversible report-sha at stake.
- Category: PROCESS / SPEC-AMBIGUITY
- Evidence: dispatch: "`git fetch origin dev && git rebase origin/dev` (never merge dev in)"; agent later: "The MEMORY note is explicit: 'reports name their producer sha: regen last, merge with --merge never rebase.' ... dev is unprotected and allows merge commits — so I merge dev into the branch... rather than rebasing, per the MEMORY note."
- What in the issue/prompt would have prevented it: the dispatch's rebase instruction should have carried the caveat "...UNLESS a report/ledger sha from an earlier commit must stay reachable, in which case merge instead" — or simply not contradicted the standing repo convention at all (the dispatch author likely wrote "never merge dev in" as a generic rebase-not-merge preference without checking it against the report-sha invariant).

### F7: Test-touch report shows `nan` baseline — a grid-config gap discovered only at the very end
- When: [04:36]–[04:47] (turn ~530)
- What the agent was trying to do: finalize the touch-#4 report and confirm the numbers before closing out.
- What it assumed / where it looked: read `reports/tune/phase6-lines-test-788c1eb.md`.
- What was actually true: `grids/phase6-lines.yaml`'s `problem2_rules` lists only the 3 tuned rules (`weight>t`/`smoothed>t`/`after_changepoint`), never `all_predator_lines`, so `problem2_table_offline` never emits that baseline row and `base_f1` resolves to NaN. The real numbers (F1 0.2250) were correct; only the baseline-Δ display was broken.
- Cost: ~6 tool calls, ~10 minutes to diagnose, correctly decide NOT to re-spend the gated test touch to fix a report-only cosmetic bug, and file it as follow-up issue #44 instead.
- Category: DATA-SHAPE/SCHEMA
- Evidence: "baseline F1 nan (Δ +nan)... a NaN baseline is an ambiguous state I should diagnose"; issue #44: "A test-touch report must show a COMPUTED baseline comparison, never `nan`... Cause: `grids/phase6-lines.yaml` `problem2_rules` lists only [3 rules], so `problem2_table_offline` never emits the `all_predator_lines` row."
- What in the issue/prompt would have prevented it: grid-authoring guidance in the harness README/#26 invariant should say "every phase-N grid's `problem2_rules` MUST include the `all_predator_lines` baseline row, or the report's Δ will silently show nan" — this is exactly the kind of invariant the user's own CLAUDE.md flags ("a computed zero must look visibly different from a transport/build failure").

## What went smoothly because the prompt/issue supplied it
- Exact absolute worktree path + branch + base sha → the agent never had to discover where to work; first action was a single batched `cd && git status && gh auth status` command.
- Named ownership boundaries (files it owns vs. #29/#30/#31's files, "additive only, do not edit existing functions") → zero encroachment on sibling work observed in the transcript.
- Explicit numbered read list (issue #32, #25, CLAUDE.md, AGENT_WORKFLOW.md, README sections, justfile recipes, specific `csekit/*.py` modules, existing tests) → the entire research phase (steps 1-3) took ~15 minutes and ~15 tool calls, mostly batched `rg`/`sed -n`/`ls` calls, with no wrong-file detours.
- "single-slot `queue`, one job at a time... memory-cliff" warning → the agent correctly used `queue` for every heavy job and never tried to fan out beyond pmap, even though it still hit the OOM once (F3) — the warning meant it diagnosed the kill correctly and fast rather than being surprised by "why did my job die."
- "capture test output to a log and check exit status, never a piped tail" → the agent consistently used `rg -n 'exit='` patterns on log files instead of piping to `tail`, and a sandbox hook caught and blocked one deviation attempt before it could silently misreport a commit.
- "Final report ≤12 lines: PR URL, merge sha, ..." template → produced a genuinely concise, complete final report with no back-and-forth needed to extract status.
- Naming the exact test-touch door (`just tune-test-touch`, "ONLY ONCE, at the END, ONLY after my go") → the agent visibly gated all its work around this (e.g., re-ran ci-fast at the final sha before spending the touch, refused to spend it prematurely even when the team lead pinged asking if it was idle).

## Generalizable lessons (≤8 bullets, each a rule for writing the NEXT issue/prompt, phrased as an imperative)
1. State cross-cutting methodology rules (CV leakage, unit-of-derivation, statistical-tie decision rules) in the shared epic doc up front, not as a mid-flight message discovered on a sibling issue — by the time it reaches the worker it can already have caused an hour of wrong-unit work (F1→F5).
2. When telling a worker to "reuse sibling X's helper," name the exact granularity/unit the helper operates at (author vs. message vs. conversation) and confirm it matches what THIS issue needs — a one-word mismatch ("authors" vs. "messages") cost 51 minutes here.
3. Never give a git-workflow instruction ("rebase, never merge") without checking it against standing repo conventions that touch immutable artifacts (report/ledger producer-shas) — state the exception explicitly if one exists.
4. When warning about a shared resource limit (OOM, memory cliff), name the specific operation class at risk (e.g., "any per-message pmap over the full train split will OOM; per-author ones are fine") rather than a generic "watch memory" warning — the worker still had to discover the exact failure mode live.
5. If a config file (grid yaml) has an invariant like "must include row X or a report field silently becomes nan," say so in the harness/grid-authoring docs — silent nan in a baseline-Δ column is exactly the kind of ambiguous-empty-state failure that's expensive to catch only at the very end.
6. Keep giving exact absolute paths, ownership boundaries, and a numbered read-list — this measurably worked (near-zero wrong-file/wrong-directory time in this session) and should be the template for every future dispatch.
7. When a worker reports "idle" status to a lead based on background-job telemetry the lead's own view doesn't reflect (stale queue snapshot), that's a monitoring-freshness problem on the lead's side, not the worker's — consider having the lead re-check `queue -l`/task status before pinging.
8. Encode statistical decision rules ("ship the better variant unless within ~1 sd of noise") as a standing project rule once, rather than re-deriving/negotiating them per issue — this exact pattern (full vs. two-sided admission, then again for ship-side) recurred twice in one session.

## Stats
- Friction events by category: SPEC-AMBIGUITY 3 (F1, F5, F6), FALSE-ASSUMPTION-ABOUT-CODE 3 (F1's downstream in F5, F4, F5), MISSING-DOMAIN-CONTEXT 2 (F2, F4), SCALE/RUNTIME 1 (F3), LEAD-CORRECTION 1 (F1), DATA-SHAPE/SCHEMA 1 (F7), PROCESS 1 (F6)
  (F1 and F5 are counted once each as their primary category; several events straddle two categories by nature)
- Tool-call split: ~184 of 425 tool_use calls (≈43%) fall inside the 7 friction windows above (F1:20, F2:2, F3:14, F4:53, F5:92, F6:10, F7:6 ≈ 197 including overlap trimming); the remainder was first-pass harness construction, routine verification (lint/type/test loops), and orchestration (queue polling avoidance, status messages).
- Rough wall-clock share: friction events span roughly 145 of the session's ~247 minutes when counted end-to-end (F1 7m, F3 14m, F4 68m, F5 51m, F6 5m, F7 10m ≈ 155m, with some overlap/interleaving with waiting-on-queue time that would have elapsed regardless) — call it **~55-60% of wall clock**, though a large fraction of that is legitimate empirical-science iteration (F4, F5) rather than pure confusion: the agent was doing real work (running sweeps, diagnosing collapses) that happened to invalidate an earlier assumption, not wandering lost.
