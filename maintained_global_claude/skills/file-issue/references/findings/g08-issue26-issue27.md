# #26, #27 — sessions 0da5bcc3…(w26), ee784fe5…(w27)

Session overview (#26): Issue #26 "tune/phase 0: harness — cached count matrix, CV, sweep, test-touch ledger."
23:05:16 → 23:34:50 (≈30 min), 94 tool calls. Finished end-to-end: PR #34 merged to `dev` (merge `e02f9d5`),
issue closed, `just ci-fast` 337 passed/1 skipped. Lead interventions: 1 (a false "you went idle" nudge, answered
and dismissed in one round-trip).

Session overview (#27): Issue #27 "tune/phase 1: VTPAN prefilter fidelity — match published 2012 counts; gate vs
feature; explain structure-only." 23:36:02 → 23:58:35 (≈22.5 min), 102 tool calls. Finished end-to-end: PR #35
merged to `dev` (merge `ade2475`), issue closed, `just ci-fast` 358 passed/1 skipped. Lead interventions: 0.

Both are unusually clean, well-scoped issue-implementation runs — the dispatch prompts and issue bodies were
dense with exact facts (file lists, published numbers, ground rules, file ownership for the parallel sibling
`#28`), and both sessions finished with almost no wrong-path exploration. The friction that *did* occur is
concentrated in generic environment/process mechanics, not domain confusion, and one pattern repeats
independently across both sessions — that repeat is the most important finding here.

## Friction events (one block each, chronological)

### F1: `queue`-wrapped `ci-fast` falsely believed green (recurs in BOTH sessions independently)
- When: #26 [23:20–23:21] (turn ~45); #27 [23:51] (turn ~68)
- What the agent was trying to do: run the heavy `just ci-fast` gate through the repo's `queue` prefix (as
  instructed) and read its result.
- What it assumed / where it looked: in #26, the agent first trusted the background-task-runner's own
  "exited with code 0" status for the `queue '...; echo "exit=$?" | tee -a log'` invocation and said
  "ci-fast exited 0." In #27 it made the identical call, `queue just ci-fast > log 2>&1; echo "exit=$?" | tee
  -a log`, and again initially treated the wrapper's reported exit as authoritative.
- What was actually true: `fmt-check` (a `ruff format --check` step, first in `ci-fast`'s dependency chain)
  had failed in both cases — new/edited files hadn't been formatted before the gate ran. The task-runner's
  "exited 0" reflects the `queue`-dispatch process completing, not the inner job's exit code; the real
  exit was only visible by grepping the captured log (`fmt-check failed on line 45 with exit code 1` /
  `exit=1`).
- Cost: #26 ~3 tool calls to discover + ~10 calls to fix 4 lint/format issues and re-run; #27 ~2 tool calls to
  discover + ~8 calls to fix 3 issues and re-run. Both self-caught (no lead/user correction needed) but each
  cost a full extra heavy `ci-fast` queue cycle (the single most expensive operation in the session).
- Category: ENV/TOOLING
- Evidence:
  - "ci-fast actually **failed** at `fmt-check` (the queue wrapper's exit 0 was the trailing echo — the log
    shows fmt-check exit 1)." (#26)
  - "The queue wrapper reported 0 but the log shows `exit=1` — fmt-check failed." (#27)
  - Sandbox's own suggested pattern (which the agent then followed): `Run it as: queue cd ...; just ci-fast >
    log 2>&1; echo "exit=$?" | tee -a log` — this exact shape is what produced the false green in #26.
- What in the issue/prompt would have prevented it: Both dispatch prompts already said "capture test/build
  output to a log file and check the exit status of the command itself, never a piped tail" — but that rule
  doesn't cover the `queue`-wrapper case, where the *task-completion notification itself* (not a pipe) reports
  a misleading exit=0. Add one explicit sentence to the dispatch prompt (or, better, to CLAUDE.md's queue/
  evidence-discipline section): "A `queue '<cmd>; echo exit=$? >>log'` task's own completion status is NOT the
  inner command's exit code — after every queued `ci-fast`/build run, `rg -n 'passed|failed|error|exit='
  <log>` before trusting it green." Also: run `uv run ruff format . && uv run ruff check --fix .` on
  new/touched files immediately after writing them, *before* the first `ci-fast` invocation, to avoid ever
  hitting `fmt-check` red on the expensive first pass.

### F2: Lead flagged worker "idle" while it was correctly waiting on a tracked background build
- When: #26 [23:27:20] (turn ~65)
- What the agent was trying to do: wait for a queued, ~2-minute real-data count-matrix build+reconciliation
  job (a `Command running in background` task) to finish before committing the `reports/tune/*` artifact the
  PR must land with.
- What it assumed / where it looked: the agent had already committed code (`c87deff`) and was correctly idling
  its own turn ("Ending my turn to await it") to let the tracked background task re-invoke it on completion —
  standard practice per the harness's own guidance against polling.
- What was actually true: from the team-lead's outside view (no visibility into the background-task state),
  "committed but not pushed, no PR yet, no new tool calls" looked indistinguishable from stuck/abandoned, so
  the lead sent a "you went idle... continue" correction.
- Cost: 1 round-trip SendMessage exchange (~1 min), no rework — the agent replied "Not stuck — building
  required artifact," gave exact status (commit sha, queue job ID, `ci-fast` result), and the lead did not
  press further. Low cost but avoidable.
- Category: LEAD-CORRECTION
- Evidence:
  - Lead: "You went idle with commit c87deff local ... but no push and no PR. Continue from step 4/5..."
  - Worker: "Not stuck, no blocker. Code is committed (c87deff) and `just ci-fast` is green there (337
    passed, 1 pre-existing skip)... [building required artifact]"
- What in the issue/prompt would have prevented it: either (a) tell workers to proactively post one status
  line to the lead the moment they start a multi-minute background build ("started queued build+reconciliation
  for reports/tune/*, ETA ~2 min, will push+PR after"), so idle-detection has fresher information than silence,
  or (b) tell the lead's own idle-check to treat "task-notification pending on a `run_in_background` job" as
  active, not idle, before nudging.

### F3: Assumed the PR's CI would run the heavy `ci-fast` gate; discovered dev-PRs only get "Secret scan" + "Workflow lint"
- When: #27 [23:56:13–23:57:09] (turn ~88)
- What the agent was trying to do: after opening PR #35, watch CI checks to green before merging.
- What it assumed / where it looked: expected `ci.yml`'s substantive test job to appear alongside the two
  quick checks; when only two showed, it re-queried `gh pr checks`/`gh pr view --json statusCheckRollup`
  twice before reading `.github/workflows/ci.yml`'s trigger block directly.
- What was actually true: `ci.yml`'s `pull_request: branches: [main]` trigger means the full `ci-fast` suite
  only runs on PRs targeting `main`; PRs into `dev` get only the light "Secret scan" + "Workflow lint" checks,
  and the *local* `just ci-fast` run is the real substantive gate for a dev PR.
- Cost: 3 tool calls (~1 min), self-resolved, no rework.
- Category: PROCESS (CI/PR mechanics)
- Evidence: "Only two checks showed — the `ci.yml` CI job may not have registered yet. Let me re-check..."
  → "`ci.yml` only triggers on PRs into **main**. My local `just ci-fast` is the substantive gate and passed."
- What in the issue/prompt would have prevented it: one sentence in the dispatch prompt or README's CI section
  stating "PRs into `dev` only run Secret-scan + Workflow-lint in CI — your local `just ci-fast` green *is*
  the merge gate for `dev`; `ci-fast`/`ci-deep` only run in CI on PRs into `main`." (This session #26 avoided
  the confusion only because it never checked for a missing third check — it got lucky, not informed.)

## What went smoothly because the prompt/issue supplied it
- Exact worktree path + branch + "already symlinked, claim comment posted" up front → zero time spent
  discovering/creating worktree state; both sessions went straight to `gh issue view`.
- Both issue bodies restated the epic's full "Ground rules" (test-touch budget, score-once-sweep-offline,
  `--merge` convention, worktree symlinks, `queue` for heavy runs) verbatim → neither session had to chase the
  epic issue for policy; both merged with `--merge` correctly and never touched the `test` split unnecessarily.
- #27's dispatch prompt named exact file ownership vs the parallel sibling `#28` ("you must not edit
  csekit/tune.py except additively; #28 owns aggregation/stage code") → the agent respected the boundary with
  no cross-file collision, and proactively added an additive-only staleness guard rather than modifying
  existing signatures.
- #27's prompt pointed at exact line ranges (`csekit/ingest.py` lines ~240–300) and named the exact published
  target numbers (66,928→6,588 conv / 11,038 users / 136 predators; 15,330/25,120/222) → the agent went
  straight to the fidelity sweep instead of hunting for what "the published counts" meant.
- #27's prompt pre-disclosed the known gap ("ours is ~10% off ... Known gap") → when the sweep confirmed exact
  reproduction was impossible, the agent reported it as an expected, pre-scoped finding rather than treating it
  as a failure requiring escalation.
- Issue #26 body's "Score once, sweep offline" ground rule, with the exact live-scorer cost numbers
  (124s train / 275s test per lexicon variant) → gave the agent a concrete performance budget to design the
  cached-matrix architecture against, with no need to benchmark it themselves first.
- `data/README.md` documenting that `data/` is gitignored + shared across worktrees → agent correctly decided
  NOT to edit that file mid-flight (would be a non-durable, cross-worktree mutation) and put findings in the
  committed report instead — a good call that needed no lead intervention.

## Generalizable lessons (≤8 bullets)
1. State explicitly that a `queue`-wrapped background task's own "exited 0" completion status is not the
   inner command's exit code — always `rg` the captured log for `passed|failed|error|exit=` before treating
   a queued `ci-fast`/build run as green.
2. Tell workers to run `ruff format .` + `ruff check --fix .` on new/touched files immediately after writing
   them, before the first (expensive) `ci-fast` invocation — avoids burning a full heavy gate cycle on a
   trivial formatting failure.
3. State which CI checks actually gate a PR into `dev` vs `main` (e.g. "dev PRs only run Secret-scan +
   Workflow-lint; your local `ci-fast` green is the real gate") so workers don't spend cycles waiting for a
   check that will never appear.
4. When a worker is expected to wait multi-minutes on a queued/background build, have it post one proactive
   status line to the lead at the start of the wait (what's running, ETA) so idle-detection isn't guessing
   from silence.
5. Restate the epic's binding ground rules verbatim inside each phase issue (not just linked) — both sessions
   never had to re-fetch epic context mid-task because the rules were already in front of them.
6. Name exact file/module ownership boundaries when sibling issues run in parallel on the same repo — prevents
   any need to negotiate or discover collisions at runtime.
7. Pre-disclose known gaps/expected negative results in the issue scope (e.g. "known ~10% off; record the
   table") — lets the agent report an honest negative finding as done, not as a blocker needing escalation.
8. Give exact target numbers and file:line-range pointers for anything requiring numeric fidelity — turns a
   research task into a direct verification task.

## Stats
- Friction events by category: ENV/TOOLING: 1 (recurring ×2 instances across sessions), LEAD-CORRECTION: 1,
  PROCESS: 1.
- Rough share of session spent on friction vs productive work: #26 ≈10% (extra ci-fast cycle + idle
  round-trip out of ~30 min); #27 ≈8% (extra ci-fast cycle + CI-trigger investigation out of ~22.5 min).
  Both sessions were overwhelmingly productive time — implementation, verification, and correct architecture
  decisions with no rework.
