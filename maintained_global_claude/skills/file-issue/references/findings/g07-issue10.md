# Issue #10 — sessions edcf775f (Work Package A: report.py/README) and d3859653 (Work Package B: walkthrough page)

Repo sophiaconsulting/parot-cse. Issue #10 was split into two sibling worktrees/branches (`issue-10-report`,
`issue-10-walkthrough`) worked by two parallel teammate sessions, later rebased together and merged as **one PR (#24,
merge 024a717)**. Both are genuine issue-implementing sessions — proceeding with full report.

## Session overview

**Package A (edcf775f)** — `scripts/report.py`, README `## Results` tables, justfile recipes, regenerated `reports/`.
07:16:27 → 09:37:25 (~2h21m wall, most of it queued/waiting on real-data runs). 159 tool calls. Finished, 3 commits
(`3519c61`, `19c975c`→amended, `06dcb3b`/`a90a27f`-lineage), `ci-fast` green (289 passed/1 skipped), not pushed (per
instructions) — later became part of PR #24. **4 lead interventions** (mid-session `<teammate-message>` corrections).

**Package B (d3859653)** — `gen_walkthrough.py`, `walkthrough.html`, `walkthrough_data.json`, `tests/tier0/test_walkthrough.py`.
07:16:59 → 08:45:54 (~1h29m wall). 125 tool calls. Finished, 1 commit (`2db0a02`), `ci-fast` green (291 passed/1
skipped), not pushed. **0 direct lead corrections** (one FYI status exchange only) — self-corrected everything via its
own fail-loud guards and re-runs.

## Friction events (one block each, chronological)

### F1 (A): ruff's project-specific rule set (ISC004, DTZ011, PLW1510…) discovered only by trial-and-error
- When: [07:25–07:27] (turn ~15)
- What the agent was trying to do: lint `scripts/report.py` after writing it.
- What it assumed / where it looked: ran a bare `uv run ruff check`, hit `ISC004` (implicit string concat in a
  collection needs parens), fixed, re-ran, hit more — iterated ~4 times before checking `pyproject.toml`'s
  `[tool.ruff.lint]` block for the actual enabled rule set.
- What was actually true: the project has an extended ruff rule set beyond stock defaults (extra `select`s: FURB,
  DTZ, RUF, PLW, etc.) documented in `pyproject.toml`.
- Cost: ~6 tool calls of iterate-lint-fix before landing on a clean pass.
- Category: ENV/TOOLING
- Evidence: `"ISC004 Unparenthesized implicit string concatenation in collection"`; `"Let me check what ruff rules the project actually enforces (my bare ruff check may use different defaults than just lint)."`
- What would have prevented it: one line in the dispatch prompt — "run `uv run ruff check .` / `ruff format --check .`
  as you go; the project's extra lint rules are in `pyproject.toml [tool.ruff.lint]`."

### F2 (A): forgot `ruff format` before the final commit → had to unwind and re-split commits
- When: [09:30–09:34] (turn ~135)
- What the agent was trying to do: run `just ci-fast` as the final gate after committing 3 "clean" commits.
- What it assumed / where it looked: assumed `ruff check` (lint) passing meant formatting was also fine.
- What was actually true: `ruff format --check` is a **separate** ci-fast recipe (`fmt-check`) and failed — 2 files
  needed reformatting (whitespace-only, but now the already-made commits were "dirty").
- Cost: ~8 tool calls — `git reset` to before the two commits, re-stage/re-commit cleanly with formatted files, re-run
  ci-fast.
- Category: ENV/TOOLING
- Evidence: `"ci-fast is red — fmt-check failed."`; `"I forgot to run ruff format before committing."`
- What would have prevented it: dispatch-prompt line: "before each commit, run `uv run ruff format . && uv run ruff
  check . && uv run ty check .` (fmt-check is a separate ci-fast recipe from lint, not implied by lint passing)."

### F3 (A): LEAD-CORRECTION — questioned a redundant second full report run
- When: [08:20:58] (turn ~103)
- What the agent was trying to do: after run 1 (`4820d4c`) succeeded, queued a second full `uv run scripts/report.py`
  run at the newly amended HEAD, reasoning the sha in filenames should match the committing code.
- What it assumed / where it looked: proceeded without flagging the ~46-min-run cost to the lead first.
- What was actually true: the lead's read was reasonable (cheap idempotency check would suffice) but the worker's
  actual reason (a real Table-4 content fix, not just a sha bump) was valid — resolved by explanation, not reversal.
- Cost: 1 lead message + 1 reply; no wasted compute (the run was legitimate) but it did cost a full 46-min real-data
  run that arguably could have been deferred until all fixes were known.
- Category: LEAD-CORRECTION
- Evidence: `"I see you queued a SECOND full uv run scripts/report.py run (queue job 270). If that's only to..."`
- What would have prevented it: the dispatch prompt could have said up front "batch all known content fixes before
  triggering the ~46-min full regeneration; don't run it speculatively / more than once per finalized code state."

### F4 (A): LEAD-CORRECTION — Table 4 FPR gap, then a genuine scale-mismatch discovery, then reversed design churn
- When: [08:21–08:44] (turns ~104–170), the session's single biggest time/complexity sink
- What the agent was trying to do: react to the lead's request that Table 4 carry a real FPR at Table 1's chosen
  threshold θ (previously "—" with prose deferring to issue #5).
- What it assumed / where it looked: initially had to verify whether `csekit.calibrate`'s per-text raw scores and
  `csekit.score.author_scores`'s per-author logistic-squashed scores were on the same scale (they are not — this
  itself was correctly caught, a good save). It then built a "sha-keyed section reuse" mechanism that **parsed the
  previous `report-<sha>.md` markdown** to avoid a full 46-min re-run — which directly violated the dispatch prompt's
  explicit "never parses markdown" constraint (agent didn't notice the conflict itself; the lead had to call it out:
  "the brief's one hard 'never'"). Lead then asked for a principled frame-parquet cache instead. Agent rewrote `main`
  accordingly, cancelled two premature queued full-runs along the way (job 270, then job 276).
- What was actually true: the fix needed was (a) an honest prose explanation of the scale mismatch, not a fabricated
  FPR, and (b) a proper DataFrame-parquet cache, not markdown re-parsing.
- Cost: ~35 tool calls, 2 cancelled/wasted queue jobs, 3 commit amends, 2 full report-generation attempts before the
  final "single full run at final sha" landed — roughly 25 minutes of session time on design churn (excluding the
  unavoidable real-data run time).
- Category: LEAD-CORRECTION / SPEC-AMBIGUITY (the dispatch prompt's own "never parse markdown" rule was violated by
  the agent's own later design, and nothing caught it until the lead did)
- Evidence: `"the section-reuse by parsing report-<old-sha>.md is out: it parses markdown (the brief's one hard 'never'"`; `"author_scores produces a per-author, baseline-centred, logistic-squashed score... while calibration uses per-text raw... not comparable"`
- What would have prevented it: (1) issue/brief should pre-empt the scale question directly — e.g. "Table 4's FPR
  must be computed at Table 1's chosen θ IF AND ONLY IF the two scores are on the same scale; verify that first and
  say so explicitly if not" — this was knowable from reading `csekit/calibrate.py` + `csekit/score.py` before writing
  any table code, not discovered under lead pressure. (2) A standing rule like "no report.py caching/reuse strategy
  may re-parse its own markdown output — cache the underlying DataFrames if speed matters" would have prevented the
  agent from building (and having to unbuild) the wrong mechanism.

### F5 (A): background-command exit code is the wrapper's, not the payload's — surfaced twice
- When: [08:28:05–08:28:29] (turn ~113) — also foreshadowed generically in CLAUDE.md's evidence-discipline rule.
- What the agent was trying to do: interpret job 270's outcome after a task-notification said the background run
  "finished."
- What it assumed / where it looked: initially trusted the notification/wrapper's reported success.
- What was actually true: the log showed `exit=255` — the run never actually executed `report.py` (queue dropped/
  cancelled the job); the on-disk reports were unchanged from run 1.
- Cost: 2 tool calls to catch, but it fed directly into the confusion of F4 (agent briefly believed a stale run had
  succeeded).
- Category: ENV/TOOLING
- Evidence: `"The notification's 'exit 0' was the wrapper's — the log shows exit=255. The run FAILED partway."`
- What would have prevented it: this is exactly the CLAUDE.md rule already in force ("a background task's reported
  exit code is the wrapper's — always grep the log") — the agent DID follow it correctly once it looked, so this is
  more a confirmation than a gap; worth calling out in the dispatch prompt for `queue`-based work specifically, since
  `queue`'s own exit codes (255 = dropped/cancelled) are a distinct failure mode from the wrapped command's.

### F6 (B): PYTHONPATH — ad hoc probe script imported the wrong `app` package
- When: [07:20:19–07:20:36] (turn ~26)
- What the agent was trying to do: run a throwaway `/tmp/wt_probe.py` to time `LiveEngine.startup()` before
  committing to the generator design.
- What it assumed / where it looked: ran `queue uv run python /tmp/wt_probe.py` from the worktree directory, expecting
  local imports to resolve.
- What was actually true: a script outside the repo root doesn't get the repo on `sys.path`; it silently imported a
  same-named `app` from elsewhere (parot-bias) instead of the local `app/engine.py`.
- Cost: 1 wasted background run + 1 fix (`PYTHONPATH="$PWD"`) + re-run.
- Category: ENV/TOOLING
- Evidence: `"The probe imported parot-bias's app, not the local one (script in /tmp → repo root not on path)."`
- What would have prevented it: minor — this was a self-inflicted throwaway-script issue, not something the dispatch
  prompt could reasonably pre-empt; noted for completeness only.

### F7 (B): self-inflicted regex bug in own jargon-sweep test (HTML comment ate the real body)
- When: [07:32:24–07:32:57] (turn ~59)
- What the agent was trying to do: verify its own `walkthrough.html` didn't leak banned jargon terms, using a
  strip-script-then-grep approach in a throwaway check.
- What it assumed / where it looked: assumed `<script>...</script>` was the only place `id="wt-data"` text could
  appear.
- What was actually true: an HTML **comment** in the file also mentioned `<script id="wt-data">`, so the naive
  strip regex ate everything from the comment to the first real `</script>` tag, silently swallowing ~23KB of real
  body text and making the jargon check pass vacuously.
- Cost: 2 tool calls to detect (diff between raw grep hits and "stripped" zero hits) + 1 fix (strip HTML comments
  first).
- Category: FALSE-ASSUMPTION-ABOUT-CODE
- Evidence: `"my _rendered_text strip is buggy: the HTML comment mentions <script id=\"wt-data\">, so the script-strip regex eats everything..."`
- What would have prevented it: nothing in the issue/prompt — a genuine self-caught, self-fixed bug in the agent's
  own throwaway verification tooling; listed because it shows the value of the agent's own paranoid re-verification
  (it re-ran the raw grep to sanity-check its "clean" result before trusting it).

### F8 (B): real-data selection failure — the top-scored flagged author had almost no KWIC evidence
- When: [08:22:06–08:25:34] (turn ~86)
- What the agent was trying to do: run the real generator for the first time; `pick_flagged_author` selected the
  single highest-scoring test account for the showcase.
- What it assumed / where it looked: assumed "highest score" implies "has a rich receipt/evidence trail" — the two
  are actually independent (a high score can come from a shrinkage-adjusted rate over few signal terms).
- What was actually true: the top-scoring account only yielded 1 KWIC receipt; the fail-loud guard (correctly)
  raised rather than shipping a thin showcase.
- Cost: a full ~23-minute real-data generator run consumed to discover this, then ~10 tool calls to restructure
  `pick_flagged_author`/`receipts_for` into a combined "highest-scoring account WITH a substantial evidence trail"
  selector, then a second full run (~5 min) to confirm.
- Category: DATA-SHAPE/SCHEMA (also FALSE-ASSUMPTION-ABOUT-CODE)
- Evidence: `"only 1 receipts for the flagged account —"`; `"pick the highest-scoring flagged account that actually has a substantial evidence trail"`
- What would have prevented it: the dispatch prompt already said "highest score from LiveEngine.authors_payload... with
  2–3 real KWIC receipts" as if these two properties always co-occur. A one-sentence caveat — "the top-scored account
  may have few KWIC hits; select for score AND receipt count together, and fail loud (not silently) if none qualify"
  — would have saved the first full run. This is a case where the fail-loud discipline (also mandated by CLAUDE.md)
  worked exactly as intended — it just cost one real-data cycle to trigger.

### F9 (cross-package): shared `queue` resource contention — worker A's 46-min report.py starved worker B's generator, background tasks got killed
- When: [07:33:03] queued behind A → [07:58:07] worker B's 3 background tasks (`btyxj2d8j`, `b0ebow7fi`, `bpsbhb5nl`)
  all reported **killed**, after sitting queued behind A's `report.py` for ~26 minutes without ever starting.
- What the agent was trying to do: run its own real-data generator, correctly serialized behind other heavy jobs via
  the mandatory `queue` prefix (as instructed).
- What it assumed / where it looked: no false assumption — it correctly diagnosed the kill as environmental
  (session/idle timeout on the blocked background wait), not a bug in its own code, and simply re-queued.
- What was actually true: the shared single-slot `queue` meant two parallel workers on the same issue effectively
  serialized their heaviest steps, and one worker's very long real-data run (A's initial 46-min `report.py`, later
  repeated 3× more due to F3/F4's churn) directly delayed and then killed B's background wait.
- Cost: ~25 minutes of dead time for B, plus 1 extra re-queue-and-explain cycle; no data was lost (B's code was
  already complete and green offline) but final verification/commit was pushed back by nearly half an hour.
- Category: SCALE/RUNTIME / PROCESS
- Evidence: `"My generator sat in the queue for 26 min behind worker A's very slow report.py and never started before the kill."`; `"queue: 1 job(s) ahead; blocked by job 264 (issue-10: uv run scripts/report.py, running 1568s)"`
- What would have prevented it: this is the clearest **package-interaction** lesson in the pair. Splitting one issue
  into two parallel workers that both need the single-slot heavy-command `queue` means one worker's slow/iterated
  real-data step (worsened here by A's own re-run churn from F3/F4) silently taxes the other. The team-lead dispatch
  should either (a) warn each worker explicitly that they share the queue and to budget/sequence heavy runs
  accordingly, or (b) sequence the two packages' heavy real-data steps explicitly (e.g. "B's generator run takes
  priority since it's faster; A, hold your regen until B confirms") rather than leaving both to queue-race.

## What went smoothly because the prompt/issue supplied it

- **Exact file-ownership boundaries per worker** ("you own and may create/edit ONLY: ...") → zero cross-worker file
  conflicts in either session; each worker never had to ask "is this mine to touch?"
- **The implementation brief (`issue10-brief.md`) with file:line pointers for every table/section** → both workers
  oriented in <2 minutes and went straight to the right functions instead of exploring; A explicitly noted "the
  brief is thorough" and "trust it but verify pointers."
- **Explicit `queue`-prefix + backgrounding + logging protocol given verbatim in the prompt** (`queue <cmd> > log
  2>&1; echo exit=$?`, "never `| tail` a gate") → both workers followed it exactly and it caught real issues (F5,
  F9) instead of silently swallowing them.
- **A structural model to copy (`../parot-stats/gen_walkthrough.py`) plus the `walkthrough` skill loaded first** →
  worker B never had to invent the ORACLE/build_payload/check_payload/inline() pattern from scratch; it read the
  model file once and matched its shape.
- **Base counts given up front ("base here = 276 passed")** → both workers could confirm their own test contribution
  precisely (A: 289 total = +13; B: 291 total = +15... i.e. each could sanity-check without re-deriving history) and
  immediately flag the pre-existing skip as not-mine, rather than investigating it as a regression.
- **Explicit "no push, no PR, no Co-Authored-By" instructions given identically to both workers** → no ambiguity, no
  wasted turns on git-remote actions; both correctly stopped at local commits.
- **The Table-4/PANC-row wording pre-supplied verbatim** ("PANC row = literal 'pending data (ChatCoder2 unavailable
  — decision 2026-08-20)'") → worker A pasted it in unmodified rather than re-deriving the decision date/rationale.
- **"data/ is gitignored, writes there are intended" stated explicitly** → neither worker wasted time wondering
  whether writing to `data/lexicon/...` was safe/appropriate.

## Generalizable lessons (≤8 bullets)

1. **State the project's non-default lint/format rule locations up front** (e.g. "extra ruff rules live in
   `pyproject.toml [tool.ruff.lint]`; run `ruff format` as a *separate* step from `ruff check` before every commit")
   — both workers independently rediscovered this by trial-and-error.
2. **When two properties are asserted to co-occur in a spec ("highest score... with 2–3 real KWIC receipts"),
   verify they actually correlate in the data before writing the selection code**, or flag in the prompt that they
   might not and the selector must guard for both.
3. **Repeat any "hard never" constraint (e.g. "never parse markdown") at the point in the prompt where a worker is
   most likely to reach for it** (e.g. right next to guidance about caching/reuse for a slow report step) — stating
   it once at the top wasn't enough to stop the agent from building and then having to tear down a markdown-parsing
   cache under its own design pressure.
4. **When splitting one issue across parallel workers who share a scarce serialized resource (a single-slot `queue`),
   say so explicitly and give a priority/sequencing rule** — otherwise one worker's slow or repeated real-data run
   silently starves the other's background wait until it's killed.
5. **Before requesting a design change to an already-running real-data step (e.g. "add the real FPR"), have the
   issue/brief pre-answer the obvious feasibility question** (are the two scores even on the same scale?) so the
   worker doesn't have to reverse-engineer it live under a "make this less handwavy" request.
6. **Discourage speculative re-runs of expensive (tens-of-minutes) real-data steps** — instruct workers to batch all
   known content fixes into code first, then trigger exactly one full regeneration at the final commit sha.
7. **Reiterate the "background exit code is the wrapper's, not the command's" gotcha specifically for `queue`-based
   heavy commands** — `queue`'s own exit codes (e.g. 255 = dropped/cancelled) are a distinct failure mode workers
   need to recognize, separate from the wrapped command failing.
8. **When a dispatch prompt gives near-verbatim strings to use** (exact PANC-row text, exact recipe names, exact
   base test counts) workers use them directly and correctly — keep doing this; it measurably prevented re-derivation
   detours in both sessions.

## Stats

Friction events by category:
- ENV/TOOLING: 4 (F1, F2, F5, F6)
- LEAD-CORRECTION: 2 (F3, F4 — F4 also SPEC-AMBIGUITY)
- FALSE-ASSUMPTION-ABOUT-CODE: 2 (F7, F8 — F8 also DATA-SHAPE/SCHEMA)
- SCALE/RUNTIME / PROCESS: 1 (F9, cross-package)

Rough share of session spent on friction vs productive work:
- Package A: ~35–40% of wall-clock was friction/design-churn (F3+F4 dominate — cancelled/re-triggered full report
  runs, commit-history surgery), but most of that time was background real-data compute the agent was correctly
  waiting on rather than actively wasting; active-turn friction (tool calls not toward the final artifact) is closer
  to ~20% of tool calls.
- Package B: ~15% friction (F6–F8 combined); the bulk of wall-clock was legitimate real-data generator runtime
  (3 full runs × ~5–24 min) plus queue wait from F9, not agent confusion.
