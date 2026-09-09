# #30 (Phase 4: lexicon mining axes + confound tripwire) — session `b123debe-ce83-4f8b-ae97-6af6931b4cd1`

Session overview: Issue #30 (part of epic #25, "tune the counting method end-to-end") asked the worker to add
mining-axis parameters (negatives, filtered-at-mine, n-grams, `CHAT_SCAFFOLDING` stoplist) to the existing
lexicon-mining harness, re-run the intent-vs-register confound tripwire per variant, and spend "test touch #3"
under a shared epic-wide budget. First→last timestamp 00:00:05 → 03:41:14 (~3h41m wall clock, includes a
mid-session context-compaction/continuation). 292 tool calls. Finished: **yes** — PR #39 merged into `dev`
(merge `3c1a992`), issue #30 closed, epic #25 commented. 8 team-lead teammate-messages arrived mid-session
(3 informational heads-ups, 1 stale-observation correction the worker had to push back on, 1 hard protocol
correction, 1 pre-go planning guidance, 1 final GO). 3 of the worker's own background heavy jobs were OOM-killed
by shared-box memory pressure (not the worker's fault, but real recovery cost).

## Friction events (one block each, chronological)

### F1: YAML `scaffold: off` silently parses to boolean `False`
- When: [00:14] (turn ~35, right after writing new grids + tests)
- What the agent was trying to do: run its new tier-0 test suite for the new `scaffold` mining axis (`any`/`all`/`off`).
- What it assumed / where it looked: that the grid YAML strings `any`/`all`/`off` would load as strings.
- What was actually true: YAML 1.1 (PyYAML's default loader) parses the bareword `off` as boolean `False`, so `StageConfig.__init__` raised `ValueError: ... got False`.
- Cost: ~3 tool calls (run tests → read failure → sed-fix 2 grid files + defensive `str()` coerce in `from_dict`) / <2 min, self-recovered, no lead help needed.
- Category: DATA-SHAPE/SCHEMA
- Evidence: `"ValueError: variant 'scaffold-off': scaffold must be one of ('any', 'all', 'off'), got False"`; `"YAML footgun: scaffold: off parses as boolean False (YAML 1.1)."`
- What in the issue/prompt would have prevented it: a one-line note in the issue or in `csekit/tune.py`'s existing grid-authoring docs — "YAML bareword values `on/off/yes/no/true/false` are parsed as booleans; always quote them in grid YAML" — since this repo already had prior grids using enum-like string labels.

### F2: Wrong assumption about `scaffold-off` admitted-set size on the tiny fixture
- When: [00:14]–[00:17] (turn ~37–44)
- What the agent was trying to do: assert that disabling the scaffold stoplist (`scaffold-off`) causes greeting/filler tokens to leak into the *admitted* lexicon on the test fixture.
- What it assumed / where it looked: that `scaffold-off` would simply admit more terms (a superset of `scaffold-any`'s admitted set), so it wrote `assert int(t.loc["scaffold-off","scaffold_leak"]) > 0`.
- What was actually true: on the tiny fixture, admitting scaffolding tokens enlarges the candidate vocabulary enough to shift the Fightin'-Words smoothing constant (α₀) and zero out ALL admissions for that variant — a real Fightin'-Words property, not a bug. `run_mining` correctly records a per-variant error and continues. The agent had to write a throwaway debug script hitting the daemon directly to confirm this before trusting it.
- Cost: ~6 tool calls (2 wrong assertions written+failed, 1 debug script, re-read) / ~3 min.
- Category: FALSE-ASSUMPTION-ABOUT-CODE
- Evidence: `"assert 0 > 0"`; `"That's a real Fightin' Words property, not a bug: the scaffolding terms enlarge the candidate set... so scaffold-off admits nothing here"`.
- What in the issue/prompt would have prevented it: since this is a genuine numerical-methods surprise specific to the tiny fixture (not something the issue author could easily anticipate), the fix is process not spec — but a one-line note in the fixture's docstring/PLAN.md ("admission count is NOT monotonic in candidate-vocab size — smoothing can zero out a variant on a small fixture") would have saved the detour for this and any future issue touching mining axes on this fixture.

### F3: Stale team-lead observation — thought a bare (non-queued) heavy job was still running
- When: [00:26]–[00:27] (turn ~139)
- What the agent was trying to do: nothing wrong — it had already killed its own bare `queue`-violating job 15 minutes earlier when the queue-hook flagged it (see "what went smoothly" below).
- What it assumed / where it looked: N/A — the lead's message asserted `scripts/tune_mining.py grids/phase4-mining.yaml` was "running bare right now."
- What was actually true: that job (queue id 295) had already been killed by the agent at [00:23]; the lead's monitoring was stale.
- Cost: 2 tool calls (verify `queue -l` + `pgrep`) / ~1 min, resolved by SendMessage back to lead — no real course change needed.
- Category: LEAD-CORRECTION (reversed — agent corrects lead's stale info)
- Evidence: `"The team lead flags a memory cliff and thinks a bare tune_mining is running... let me verify the actual state"`; `"No course change needed — and no bare job of mine is running. The tune_mining ... you saw I already KILLED"`.
- What in the issue/prompt would have prevented it: not really preventable from the issue side — this is a monitoring-lag artifact of a shared box with 4 concurrent workers. Lesson is for the ORCHESTRATOR side: cross-check `queue -l`/`pgrep` before broadcasting a "your job is running bare" warning to a worker, to avoid a wasted round-trip.

### F4: Mid-session unit change (#28 merge) forced a rebase + CV-unit rework
- When: [00:36]–[00:46] (turn ~180)
- What the agent was trying to do: continue building phase-4 mining variants against the harness as understood at session start (author-unit scoring, mean aggregation).
- What it assumed / where it looked: the scoring unit/aggregation it read at [00:00] would remain the shipped baseline throughout the session.
- What was actually true: sibling issue #28 merged mid-session and changed the shipped scoring unit to `agg_sum_max` (conversation-summed weight, author-MAX rollup) — a substantial CV-methodology change the worker had to rebase onto and adapt to before its own results were comparable.
- Cost: rebase + re-read of `tune_weights.py`/`tune.py` scoring internals, ~15 tool calls / ~10 min. This was flagged in advance by the lead's "Heads-up" message (see smooth section) so it wasn't a surprise, but still real rework.
- Category: SPEC-AMBIGUITY / ACCEPTANCE-UNCLEAR (moving target — inherent to parallel-epic tuning work, not a prompt gap)
- Evidence: `"Major update: #28 merged... I must rebase now and adapt my CV to the shipped unit."`
- What in the issue/prompt would have prevented it: nothing on issue #30's side — this is unavoidable in a fan-out epic where sibling issues change shared scoring config. The mitigating factor (the advance heads-up) is exactly right; see smooth-section takeaway.

### F5: Mid-session CV-protocol correction (label leakage) applies retroactively to this issue too
- When: [01:07]–[01:11] (turn ~448)
- What the agent was trying to do: report a single CV winner from an all-train-derived weight/gate/vocab column, per the harness as built earlier in the session.
- What it assumed / where it looked: the CV protocol used by the phase-0/3 harness (deriving weights/admission gate from ALL train labels, then scoring held-out folds) was correct.
- What was actually true: that protocol leaks held-out-fold labels (discovered on sibling issue #29 — all-train weights "beat" per-fold by +0.20 F0.5). The lead's correction explicitly said "applies to you too," requiring the agent to report BOTH an optimistic and honest column and pick the winner on honest — but the honest per-fold helper lived in #29's not-yet-merged branch, so the agent had to defer the honest column to a later "step 5" re-run after #29 merged, rather than being able to fix it immediately.
- Cost: no wasted code (matrices being built were label-free/reusable), but added a second work phase (step 5, ~40 min of session time later at [03:12]–[03:38]) that reworked the entire scoring section of `tune_mining.py`.
- Category: SPEC-AMBIGUITY / ACCEPTANCE-UNCLEAR — the CV-honesty protocol was not specified in issue #30 or in the phase-0 harness docs the agent read at session start; it was a cross-cutting methodology bug discovered downstream on a sibling issue mid-session.
- Evidence: `"Protocol correction that applies to you too (found on #29... label leakage): any weight column/admission gate/prior/min_df derived from ALL train labels and then evaluated on a held-out fold has seen that fold's predators."`
- What in the issue/prompt would have prevented it: if this per-fold-honest-weights requirement was already known (even provisionally) at epic-planning time, stating it in issue #30's acceptance criteria up front ("report both optimistic and honest CV columns; pick winner on honest") would have let the agent build the harness once instead of twice. Since it wasn't known yet, the fallback (lead broadcasts the correction to all affected open issues immediately) is the right process and was followed correctly here.

### F6: `Monitor` tool called with the wrong schema (wasted call)
- When: [03:31] (turn ~724)
- What the agent was trying to do: block on a background heavy CV re-run finishing (`grep -q "^exit=" /tmp/tm_run.log`) instead of polling.
- What it assumed / where it looked: guessed a `{until, timeout}` parameter shape for the `Monitor` tool.
- What was actually true: `Monitor` requires a `description` parameter and does not accept `until`/`timeout` — the tool's actual schema was not loaded/known to the agent.
- Cost: 1 wasted tool call, immediately recovered by falling back to "wait for the completion notification" (the correct pattern per this environment's doctrine) — negligible cost.
- Category: ENV/TOOLING
- Evidence: `"InputValidationError: Monitor failed... The required parameter description is missing. An unexpected parameter until was provided..."`
- What in the issue/prompt would have prevented it: not an issue-content gap — a harness/tool-discovery gap. Could be mitigated by the dispatch prompt reminding workers that tool schemas may need `ToolSearch`/discovery before first use, or simply that background-task notifications are the intended wait mechanism (which the agent already knew and fell back to).

### F7: `git push` non-fast-forward rejection misread as success because of a piped `tail`
- When: [03:38] (turn ~782)
- What the agent was trying to do: push its rebased branch and mark PR #39 ready in one command: `git push ... | tail -3; echo "pushed rc=$?"`.
- What it assumed / where it looked: `rc=$?` would reflect `git push`'s exit code.
- What was actually true: piping through `tail` meant `$?` was `tail`'s exit status (0), masking the real non-fast-forward push failure — exactly the "never pipe a test/build run" footgun. The agent caught it on the next turn by reading the actual push hint text in the output, not from the exit code.
- Cost: ~3 tool calls (push attempt, diagnose, force-with-lease pinned to remote tip) / ~1 min, self-recovered, correctly used `--force-with-lease=<branch>:<remote-tip-sha>` rather than a blind force-push.
- Category: PROCESS
- Evidence: `"The push was rejected (non-fast-forward) — my local rebase diverged from the remote... The rc=0 was tail's exit, not git's."`
- What in the issue/prompt would have prevented it: nothing issue-specific — this is exactly the general "never pipe a test/build run" rule already in the user's global CLAUDE.md; the agent violated it once for a `git push` (not just test/build commands) and self-caught. Worth widening that rule's phrasing to explicitly cover `git push`/any command whose exit code matters, not just test/build runs.

### F8 (minor, sub-2-call, noted for completeness not scored): `gh pr view --json merged` — invalid field name
- When: [03:39]
- What: `--json state,merged,mergeCommit` isn't a valid `gh pr view` field set; failed once, corrected to `mergedAt` immediately. 1 tool call cost — below the ≥2-call threshold, listed only because it's adjacent to F7 in the same merge sequence.

## What went smoothly because the prompt/issue supplied it
- **Exact worktree path, branch, and base sha given up front** ("Work ONLY in `/Volumes/external/dev/fsa/parot-cse-wt/issue-30`... branch `issue-30-mining-axes`, created from origin/dev at ade2475 which includes the phase-0 harness (#26...)") → the agent never had to search for where to work or which commit its work assumed; recon (`git status`, `gh issue view 30`/`25`, file layout) was a single clean batch with zero wrong turns.
- **Issue pointed at the specific owning files/phase harness (#26's `csekit/tune.py`) instead of leaving discovery to the agent** → the agent went directly to `csekit/lexicon.py`, `csekit/tune.py`, `scripts/mine_lexicon.py` and correctly identified the exact gap ("`mine_lexicon` is already parametrised for negatives/filtered/ngrams/min_df — the gap is the `CHAT_SCAFFOLDING` stoplist mode") within the first ~12 tool calls.
- **The environment's own `queue`-usage hook fired automatically** when the agent ran `just ci-fast` bare, printing the exact corrected command to run → the agent adapted in one turn each of the two times it forgot (00:17, 03:28), rather than needing a lead correction. (Still cost 2 extra round-trips total — see Lessons.)
- **The lead's advance "heads-up" about #28's pending unit change, sent well before the merge landed** ("build the conversation-unit matrix too... make the CV unit a parameter so the re-run on my go is a config flip") → the agent had already made the scoring unit config-driven before the disruptive rebase hit, which measurably reduced F4's cost versus a cold rebase.
- **Explicit epic-wide test-touch budget rule stated by the lead pre-go** ("if the honest winner is still `shipped`... DO NOT spend touch #3... append a ledger NOTE line instead") → the agent executed this exactly, with no back-and-forth, saving what would otherwise have been an ambiguous judgment call at the very end of a 3.5-hour session.
- **`--merge` vs default-branch auto-close semantics already known to the agent** (merging into `dev`, not the repo default branch, doesn't auto-fire `Closes #30`) → the agent proactively closed #30 and commented on #25 manually without being told, avoiding a dangling-issue mistake.

## Generalizable lessons (≤8 bullets, each a rule for writing the NEXT issue/prompt, phrased as an imperative)
1. Always give the exact worktree path, branch name, and base sha in the dispatch prompt, plus a pointer to the specific prior-phase file(s) that define the owning harness — this alone eliminated nearly all wrong-path search in this session.
2. When a sibling issue in the same epic is expected to change shared scoring config (unit, aggregation, CV protocol) before this issue's gate, send that heads-up as early as possible and ask the worker to make the affected dimension a config parameter — do this proactively, don't wait for the merge to surprise the worker.
3. If a cross-cutting methodology bug (e.g. CV label leakage) is found on one issue, broadcast the exact required fix (both optimistic+honest columns, pick-on-honest) to every other open issue in the epic immediately, not just the issue where it was found.
4. State epic-wide shared-resource budget rules (e.g. "test touch budget ≤6, do not spend a touch that would duplicate a prior touch's config") explicitly in the issue or an early lead message — this is exactly the kind of judgment call that's expensive to get wrong at the very end of a long session.
5. Note any known non-monotonic/surprising numerical behavior on tiny test fixtures (e.g. "admission count is not monotonic in vocab size on the mini fixture") in the fixture's docstring or PLAN.md so future variant-adding issues don't re-derive it via a debug script.
6. Quote YAML enum-like bareword values (`on/off/yes/no`) in any new grid file, or add a defensive `str()` coercion in the config loader's `from_dict` — this is a recurring PyYAML footgun worth a repo-wide convention note, not a per-issue fix.
7. Before broadcasting a "your job is still running bare" warning to a worker on a shared box, cross-check `queue -l`/`pgrep` first — stale monitoring cost both sides a verification round-trip here.
8. Treat `git push`/any exit-code-sensitive command the same as test/build runs under the "never pipe, check the real exit code" rule — the agent piped `git push | tail` once and had to recover from a masked non-fast-forward failure.

## Stats
- Friction events by category:
  - DATA-SHAPE/SCHEMA: 1 (F1)
  - FALSE-ASSUMPTION-ABOUT-CODE: 1 (F2)
  - LEAD-CORRECTION (reversed): 1 (F3)
  - SPEC-AMBIGUITY / ACCEPTANCE-UNCLEAR: 2 (F4, F5)
  - ENV/TOOLING: 1 (F6)
  - PROCESS: 1 (F7)
  - SCALE/RUNTIME (OOM kills, not separately detailed above but real cost): 3 background heavy-job kills (00:52, 01:03, 01:42), each triggering a diagnose→re-launch cycle (~3-6 tool calls, ~5-10 min each) before the agent converged on `--n-jobs 1` serial builds. Root cause: shared 4-worker box memory contention, not an issue/prompt gap — already covered by this repo's `queue` doctrine; worth noting only that OOM recurred even after the first mitigation (`--n-jobs 6`), so "cap parallelism" guidance in the justfile/README could suggest starting at `--n-jobs 1` under known high box contention rather than iterating down from 6.
- Rough share of session spent on friction vs productive work: the 3 OOM-kill recovery cycles + F1-F7 total roughly 45-60 minutes of the 221-minute session (~20-25%); the largest single chunk was OOM recovery/waiting (queue congestion + re-runs), not information gaps in the issue itself. The issue/prompt-preventable friction (F1, F2, F6, F7) is small — well under 10% of total wall clock — indicating this was a well-specified dispatch; most cost came from shared-infrastructure contention and legitimate mid-epic methodology evolution (F4, F5), not missing information.
