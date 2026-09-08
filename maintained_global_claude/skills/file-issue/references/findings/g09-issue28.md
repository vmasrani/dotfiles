# #28 (PR #36) — session 0c69c452-3492-4e36-88a2-c791b54d95bf

Session overview: Issue #28 = "tune/phase 2: scoring unit + two-stage detection" — implement
conversation-aggregation ablation, a stage-A suspicious-conversation gate, and a stage-B
predator-vs-victim lexicon on top of the phase-0 offline tuning harness (epic #25), purely as
offline matrix products over cached count matrices (no live re-scoring, no classifier fit).
Ran 23:36:28 → 00:35:50 (~59 min), 162 tool calls, 109 assistant text turns. Finished and merged:
PR #36 merged into `dev` (merge `2a3f857`), issue #28 closed, epic #25 commented with headline
result. 4 team-lead messages total (1 initial brief + 3 mid-flight: an unconditional GO, a
GO-with-correction, and a SIGTERM diagnose-and-fix directive) — i.e. **3 lead interventions**
after the initial dispatch.

## Friction events (chronological)

### F1: Built a second test-touch recipe the project invariant forbade
- When: [00:03:42]–[00:08:14] (turn ~key commits 209→254)
- What the agent was trying to do: honor the brief's "spend test touch #1 ONCE via `just
  tune-test-touch`" instruction for a **two-stage** grid, which the existing `tune-test-touch`
  recipe (built for phase-0 grids only) couldn't run.
- What it assumed / where it looked: added a parallel recipe `tune-twostage-test-touch` in the
  justfile pointing at its own script — a reasonable, locally-scoped extension.
- What was actually true: issue #26 established `tune-test-touch` as the **ONLY** recipe allowed
  to read the test split, project-wide — an invariant "worth more than the convenience" per the
  lead, requiring a single dispatcher that branches on grid kind instead of a second recipe.
- Cost: ~8 tool calls / ~5 min — had to `pkill` the in-flight touch, write a new
  `scripts/tune_test_touch.py` dispatcher, rewire the justfile, add a dispatch tier0 test, re-run
  `ci-fast`, and amend the commit before re-running the touch.
- Category: SPEC-AMBIGUITY/ACCEPTANCE-UNCLEAR / LEAD-CORRECTION
- Evidence: `"NOT a second recipe: #26 established `tune-test-touch` as the ONLY recipe that reads the test split... Delete/don't add `tune-twostage-test-touch`."` / agent's own recognition: `"Clear redirection from the team lead: do not add a second recipe"`
- What in the issue/prompt would have prevented it: the #28 brief referenced `just tune-test-touch <name>`
  but never restated the single-entry-point invariant from #26. One added sentence — "`tune-test-touch`
  must remain the ONLY test-reading recipe project-wide; if two-stage needs different logic, make it
  a shared dispatcher `scripts/tune_test_touch.py` that branches on grid kind, not a new recipe" —
  would have produced the final design on the first attempt.

### F2: Un-queued heavy test-matrix build hit the box's memory cliff (SIGTERM), twice
- When: [00:08:14]–[00:24:02] (turn ~254→351), lead intervened [00:21:25] after a ~13 min quiet
  stretch
- What the agent was trying to do: run `just tune-test-touch phase2-demo` in the background —
  which internally builds 4 test count matrices (author/conv/conv_author over up to 355,567
  units) plus rebuilds the train bundle — to spend the epic's test touch #1.
- What it assumed / where it looked: treated the run as adequately isolated by Claude Code's own
  `run_in_background`; didn't invoke the repo's single-slot `queue` wrapper for it.
- What was actually true: the test split is huge (2,058,781 rows / 218,702 authors / 355,567
  conv-author units); building all 4 matrices concurrently with a **sibling worker's** own heavy
  job (a phase-3 tuning worker, discovered only via `queue --list` after the crash) exhausted the
  box's memory and got SIGTERMed — twice. The repo's convention (mentioned only generically in the
  brief as "heavy runs go through `queue`") was specifically required here.
- Cost: ~15 tool calls / ~16 min of diagnosis + rework: `queue --help`, README/justfile greps,
  test-split-size probe, a genuine code refactor to lazy-build only the matrices a config needs
  (`StageBundle` fields → `Optional`, added a `require()` helper), pre-building the two needed test
  matrices individually (~5 min each), then finally re-running through `queue` (which then queued
  behind 3 other jobs).
- Category: SCALE/RUNTIME + ENV/TOOLING (queue)
- Evidence: `"Killed again at the same heavy step... this is a resource problem"` / lead: `"CAUSE... memory pressure on this box... check `queue` docs in README/justfile and whether the live scorer spawned parallel workers"` / lead: `"you went idle without telling me"`
- What in the issue/prompt would have prevented it: name the exact scale up front ("test split ≈
  2M rows / 355k conv-author units; building test matrices is multi-minute and memory-heavy") and
  say explicitly which commands are mandatory-`queue`, not just "heavy runs" generically — e.g.
  "run `just tune-test-touch` (and any command that builds a TEST-split count matrix) through
  `/Users/vmasrani/tools/queue`, never bare `run_in_background`, because sibling workers on this
  box run concurrently and share memory." Also state that other workers' issues may be running
  concurrently on the same machine, so `queue --list` is worth checking before any first heavy
  real-data run.

### F3: Optional-field refactor left two stale `.units` accesses + broke a phase-0 invariant test (self-recovered)
- When: [00:30:46]–[00:32:48]
- What the agent was trying to do: final `ci-fast` before push/merge, after the F2 lazy-bundle
  refactor made `bundle.conv` / `bundle.conv_author` `Optional`.
- What it assumed / where it looked: assumed the earlier targeted `ruff`/`ty check` on the two
  touched files meant the refactor was fully clean.
- What was actually true: two `.units` accesses in the test file (different call sites, not
  re-checked) broke under the new `Optional` type, and a pre-existing phase-0 test asserting the
  ledger is header-only now correctly failed because touch #1 had legitimately been spent.
- Cost: ~6 tool calls / ~2 min; self-diagnosed and fixed with no lead involvement — this is the
  gate working as designed, included for completeness rather than as a real process gap.
- Category: WRONG-PATH (minor)
- Evidence: `"error[unresolved-attribute]: Attribute `units` is not defined on `None`..."` / `"FAILED tests/tier0/test_tune.py::TestShippedLedger::test_committed_ledger_is_header_only"`
- What in the issue/prompt would have prevented it: nothing issue-level — this is exactly what
  "run full `just ci-fast`, never trust a partial/targeted check, before any commit you call final"
  is for, and the agent already had that rule from CLAUDE.md/the brief. Not a prompt gap.

## What went smoothly because the prompt/issue supplied it
- Exact worktree path + branch + base sha + what #26/#27 already provide → zero time spent
  locating or verifying the environment; first tool call was already a scoped `cd` + status check.
- Explicit file/module ownership split vs. the parallel #27 worker ("own `csekit/tune.py`
  aggregation code... Do NOT edit `ingest.py` or the cache-key logic") → zero merge conflicts or
  scope collisions with the sibling worker despite both running concurrently on shared cached data.
- Numbered steps 1–5 with an explicit "wait for my reply" gate at step 4 → the agent stopped
  cleanly at the test-touch gate instead of guessing whether #27 had merged, exactly as intended.
- Ground rules given up front (CV-only on cached matrices, no live re-score except for a NEW
  vocab, no classifier fit, report naming `reports/tune/<name>-<sha>.{md,parquet}`, ledger append
  convention, "capture to a log + check exit status, never piped tail") → no format or process
  back-and-forth on any of these; every convention was followed correctly the first time.
- "Read CLAUDE.md, AGENT_WORKFLOW.md, README, justfile, PLAN.md, tune.py, ... test_tune.py" as an
  explicit reading list → the agent's own architecture pass (23:36–23:44) surfaced the existing
  `csekit/stages.py` subsystem and its reusable Fightin'-Words primitives entirely on its own,
  avoiding a duplicate mining implementation, because it had budget/direction to actually read
  before writing.
- `vocab_sha` cache-key check before running anything → confirmed the grooming lexicon matrices
  were already cached, avoiding an accidental full-matrix rebuild.
- Checking fixture per-split predator counts before writing the smoke grid → avoided writing a
  CV grid the 3-conversation fixture couldn't actually support.

## Generalizable lessons
1. If the codebase has a "there must be exactly ONE X" invariant from a prior issue, restate it
   explicitly in every new issue that could plausibly add a second X — don't rely on the worker to
   archaeology-check old issues for design constraints.
2. Name the exact scale of any real-data operation in the issue (row/unit counts, per-matrix
   wall-clock) rather than saying "heavy" — and say precisely which commands are mandatory-`queue`
   vs. merely `run_in_background`.
3. If other worker sessions may run concurrently on the same box, say so explicitly and warn about
   shared-resource contention (memory cliffs, single-slot queues) — don't make the worker discover
   a sibling's job only after a crash.
4. Give an explicit ping cadence for any step with a long background wait (e.g. "ping every ~10
   min on a step that can run 15-20 min") so a legitimate wait doesn't read as going idle.
5. State per-issue file/module ownership boundaries against parallel sibling work — this alone
   prevented all merge/scope friction in this session; keep doing it for every parallel-worker issue.
6. Front-load exact conventions (report naming/sha, ledger format, CV/gate rules, log-and-check-exit
   discipline) — this removed nearly all process/format back-and-forth in this session.
7. Treat "targeted lint/typecheck on the files I just touched" as insufficient after any type-shape
   change (e.g. required → Optional) — require the full-repo gate before calling any commit final.
8. When a tool exists for resource arbitration (like `queue`), have the worker check its usage /
   `--help` and current load *before* the first heavy real-data command, not reactively after a crash.

## Stats
- Friction events by category: SPEC-AMBIGUITY/LEAD-CORRECTION — 1 (F1); SCALE/RUNTIME + ENV/TOOLING — 1 (F2); WRONG-PATH (minor, self-recovered) — 1 (F3)
- Lead interventions: 3 (unconditional GO; GO-with-correction on the test-touch recipe; SIGTERM diagnose-and-fix directive)
- Rough share of session spent on friction vs. productive work: ~30% (≈17–19 min of confusion/rework/diagnosis out of ~59 min total; excludes legitimate unavoidable background build wait time, which is compute cost, not confusion)
