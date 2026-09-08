# Issue #7 (calibrate + receipts, PR #14) — session dca71ec2-9a3c-452c-8a31-4c1c0541ada2

Session overview: implement `csekit.calibrate` (Aegis/ToxicChat FPR calibration harness) and `csekit.receipts`
(byte-corpus KWIC citations), porting logic from `../parot-bias`. Span 21:29:44 → 21:47:31 (~18 min), 111 tool
calls, finished: PR #14 opened and later merged. Lead interventions: 1 (the initial dispatch message only — no
mid-flight correction). Net outcome quality: the PR shipped a red gate that required a follow-up bug (issue #20,
fixed 4 stub-inventory tests on `dev`).

## Friction events (one block each, chronological)

### F1: Cold `uv run` in a fresh worktree blew through the 120s tool timeout
- When: [21:30:22]–[21:32:29] (tool calls ~15–20)
- What the agent was trying to do: `uv run python -c "import biaskit"` to confirm the sibling packages resolve from the new worktree.
- What it assumed / where it looked: assumed the command would return quickly like a normal `uv run`.
- What was actually true: first `uv run` in a brand-new worktree triggers a full dependency resolve/build (venv creation, sibling editable installs), which took >120s and got auto-backgrounded.
- Cost: ~2 min wall clock, 1 extra explicit `uv sync` call to confirm it had finished; no real backtracking, just a stall.
- Category: ENV/TOOLING
- Evidence: `"Command did not complete within its 120s timeout and was moved to the background (ID: bescuulz1)"`
- What in the issue/prompt would have prevented it: preamble should tell workers to run `uv sync` explicitly as the very first command in a fresh worktree (before any `uv run`), since the initial sync is slow and predictable.

### F2: Shipped a red gate — stub-inventory test left failing because the file wasn't in "owned files"
- When: [21:43:32]–[21:46:16] (tool calls ~85–103)
- What the agent was trying to do: get the narrow gate green (`uv run pytest tests/tier0 -q` + its own new tests), per the preamble's GATES section ("... green").
- What it assumed / where it looked: ran `tests/tier0 tests/test_calibrate.py tests/test_receipts.py`, saw `4 failed, 65 passed`, recognized the 4 as `tests/tier0/test_schema.py::TestCsekitImportSmoke::test_stub_raises_not_implemented[csekit.calibrate-*]` and `[csekit.receipts-kwic_citations]` — tests asserting that its own just-implemented functions still raise `NotImplementedError`. It had pre-labeled this "the expected stub-test breakage" and, after a `--collect-only` check, moved straight to `git add`/commit/push/PR without editing `test_schema.py` or flagging the conflict.
- What was actually true: git history (PRs #3–#6) established the actual project invariant — "every PR that implements a module must remove its entries in the same PR" — but `tests/tier0/test_schema.py` was NOT in this issue's "Owned files" list (`csekit/calibrate.py, csekit/receipts.py, tests/test_calibrate*.py, tests/test_receipts*.py, tests/fixtures/external/`), and the FILE OWNERSHIP rule said "touch ONLY the files your issue lists as owned." The preamble never mentioned the stub-inventory file at all, so the worker had no instruction covering this shared file and no green path that respected both rules simultaneously. Result: `origin/dev` went red on 4 tests; a bug had to be filed (#20) and fixed in a separate PR.
- Cost: no extra tool calls in-session (it shipped anyway), but downstream cost = 1 filed issue + 1 follow-up PR to unbreak `dev`, plus every other wave-1 PR touching the same file conflicted on merge ("every wave-1 PR conflicted on it" — issue #20 comment).
- Category: PROCESS / SPEC-AMBIGUITY (file-ownership isolation model conflicts with a shared cross-cutting test file)
- Evidence: `"Now let's run the full tests/tier0 suite (as the narrow gate requires) and check for the expected stub-test breakage."`; issue #20: `"Every PR that implements a module must remove its entries in the same PR (as #3, #4, #5, #6 did). PR #14 ... did not, so origin/dev @ 7b6b9a9 is red on 4 tests."`
- What in the issue/prompt would have prevented it: one explicit sentence in the shared preamble: "`tests/tier0/test_schema.py`'s stub inventory is a shared exception to file ownership — if your module's stub graduates, remove its row(s) there in the same PR." Alternatively, state as a hard gate rule: "the narrow gate is not green until `tests/tier0` has zero failures, full stop — a failure outside your owned files is never OK to ship; stop and report instead."

## What went smoothly because the prompt/issue supplied it
- Exact expected row count with tolerance ("Aegis 'Sexual (minor)' ... expected 66 ±5 rows, assert and fail loud") → agent explored the multi-label HF schema confidently and stopped as soon as it hit 68 (within tolerance), instead of spinning on "which label combination is correct."
- Exact source files/functions to port ("port `_whole_word_excerpts`/`whole_word_hit` from .../app/engine.py and kwic_citations from src/discourse.py") → single grep+read pass found everything, zero wrong-path search for the reference implementation.
- Explicit fallback rule for the lexicon dependency ("load via csekit.lexicon.load_lexicon if #4 has landed by then; else read the parquet directly with the S3 columns") → when `data/lexicon` didn't exist, the agent didn't stop to wonder whether that was a bug; it used the documented fallback immediately.
- "REUSE, don't rewrite" + exact module paths for `biaskit`/`statskit` → no time spent hunting for whether existing math/corpus utilities existed.
- Auth-failure guidance for the gated HF dataset ("if `datasets` raises an auth error, fail loud with the huggingface-cli login instruction") meant the agent had a pre-agreed contract for that failure mode (never triggered here, but no exploration needed to decide what "fail loud" should say).

---

# Issue #23 (leaked `parot __serve` daemons in tests, PR #33) — session 1353db50-ffd9-40b8-ba9f-443c376e2911

Session overview: fix `parot __serve` daemon leaks from test fixtures (`mini_index` in `test_lexicon_mine.py`)
that don't shut down their daemons on teardown. Span 23:05:38 → 23:14:21 (~9 min), 46 tool calls, finished:
PR #33 merged to `dev`, issue closed, 10 tmpdir orphan daemons killed. Lead interventions: 1 (initial dispatch
only). This dispatch prompt was unusually detailed (explicit decision framework a/b, exact `pkill` pattern,
exact merge policy, red-green steps spelled out) and the session ran essentially friction-free — all four
events below are low-cost (1–2 tool calls, immediately self-corrected), not confusion or backtracking.

## Friction events (one block each, chronological)

### F1: `pgrep -c` doesn't exist on macOS (BSD pgrep, not GNU)
- When: [23:09:00]–[23:09:36] (tool calls ~15–17)
- What the agent was trying to do: get a daemon count with `pgrep -fc 'parot __serve'` before running the red-phase test.
- What it assumed / where it looked: assumed GNU-pgrep's `-c` (count) flag was available.
- What was actually true: this box's `pgrep` is BSD pgrep (macOS) — no `-c` flag; it printed a usage error and the count came back empty.
- Cost: 1 wasted call, fixed on the very next command with `pgrep -f ... | wc -l`.
- Category: ENV/TOOLING
- Evidence: `"usage: pgrep [-Lfilnoqvx] ..."`; `"macOS pgrep has no -c flag — I'll use pgrep -f ... | wc -l for counts."`
- What in the issue/prompt would have prevented it: name the exact count idiom in the prompt (it already did this correctly in step 6's `pkill`/`pgrep -fl` instructions — just needed to extend the same idiom to the earlier red-phase step) or note once "this box is macOS; use `pgrep -f ... | wc -l`, not GNU flags."

### F2: `just ci-fast` run directly instead of through `queue`
- When: [23:10:20]–[23:10:25] (tool calls ~24–25)
- What the agent was trying to do: run the full `ci-fast` gate in the background per the prompt's "Use `run_in_background: true` for slow commands (`just ci-fast` ...)".
- What it assumed / where it looked: assumed `run_in_background: true` was sufficient for a heavy command on this box.
- What was actually true: the box requires heavy commands to go through a `queue` wrapper (memory, not cores, is the constraint) — a hook intercepted the raw call and told it to re-run with `queue` prefixed.
- Cost: 1 blocked call, corrected on the next command.
- Category: ENV/TOOLING / PROCESS
- Evidence: `"just ci-fast is heavy and was not sent to the queue. Several of these at once on this box thrash rather than finish -- memory is the cliff, not cores."`
- What in the issue/prompt would have prevented it: the dispatch prompt should say "prefix `just ci-fast`/`just test` with `queue`" explicitly (mirrors the user's own standing `rust-gates` convention of a mandatory `queue` prefix for heavy local commands — this Python repo needs the identical sentence).

### F3: Backticks inside an inline `gh issue comment --body '...'` string broke the shell call
- When: [23:10:47]–[23:11:23] (tool calls ~29–33)
- What the agent was trying to do: post the a/b decision as an issue comment via `gh issue comment 23 --body '...markdown with `backtick`-quoted code...'`.
- What it assumed / where it looked: assumed the single-quoted `--body` string would pass the backtick-containing markdown through literally.
- What was actually true: the shell executing the Bash tool call expanded the backticks as command substitution (`(eval): command not found: mini_byte_corpora`, etc.), so the comment call failed outright (exit 127) before ever reaching `gh`.
- Cost: 1 failed call; recovered immediately by writing the body to a file and using `--body-file` (and used `--body-file` proactively for the PR body right after, avoiding a repeat).
- Category: ENV/TOOLING
- Evidence: `"(eval):1: command not found: mini_byte_corpora"`; `"the gh comment failed on shell quoting (backticks) — I'll use a body file to avoid the quoting mess."`
- What in the issue/prompt would have prevented it: a standing rule (this is generalizable across all issues, not #23-specific) — "any `gh issue/pr` body containing backticks or code fences MUST go through `--body-file`, never an inline `--body '...'` string."

### F4: Assumed merging into `dev` would auto-close the issue
- When: [23:13:21]–[23:13:55] (tool calls ~41–43)
- What the agent was trying to do: confirm issue #23 auto-closed after the PR (which said "Closes #23") merged.
- What it assumed / where it looked: assumed GitHub's "Closes #N" auto-close linkage fires on any merge.
- What was actually true: GitHub only auto-closes on merges to the repo's *default* branch; this repo merges feature work into `dev`, not the default branch, so the issue stayed OPEN after merge.
- Cost: 1 check + 1 manual `gh issue close` — trivial, but worth naming since it would silently under-deliver ("PR merged" ≠ "issue closed") if the report step didn't explicitly re-check state.
- Category: FALSE-ASSUMPTION-ABOUT-CODE / PROCESS
- Evidence: `"{"closed":false,"state":"OPEN"}"`; `"Merging into dev doesn't auto-close (GitHub only auto-closes on the default branch). Closing #23 manually..."`
- What in the issue/prompt would have prevented it: one line in the workflow-kit docs/preamble: "PRs target `dev`, not the default branch, so `Closes #N` never auto-fires — always `gh issue close -c '<summary>'` explicitly as the last step."

## What went smoothly because the prompt/issue supplied it
- The decision framework was handed to the agent verbatim ("Decide (a) vs (b)... do NOT modify `../parot`... if the class fix needs a parot-side change, describe precisely what is needed in a comment on #23") → zero time spent wondering how much scope this issue covered or whether to touch the sibling repo.
- The exact `pkill` pattern and safety caveat were pre-written ("`pkill -f 'parot __serve.*/T/'` ... confirm with `pgrep -fl` first that the pattern excludes `data/index/pan12_train_word`") → the cleanup step ran with a dry-run-then-execute check and zero risk of killing the by-design long-lived daemons.
- Exact merge policy given up front ("`--merge` (never squash); if behind dev, `gh pr update-branch --rebase`") → no hesitation or wrong choice at merge time.
- Red-green steps were spelled out as literal commands (before/after `pgrep` counts, `just test` diff) → the agent reproduced the leak, wrote a regression guard, and verified the fix in one pass with no re-litigating what "done" meant.
- "Never touch the primary checkout ... or other worktrees" + "Anchor every command with an absolute `cd`" → no path confusion across the whole session (0 wrong-worktree edits).

---

## Generalizable lessons (for writing the NEXT issue/prompt)
1. State the environment explicitly once, globally: "this box is macOS (BSD `pgrep`/`sed`/etc, not GNU) and heavy commands (`just ci-fast`, `just test`, builds) MUST go through `queue`, not just `run_in_background`." Don't rediscover this per worker.
2. Name shared/cross-cutting files that fall outside normal file-ownership up front (e.g. a stub-inventory test file every module-landing PR must edit) — otherwise a worker will either wrongly touch another issue's files or wrongly leave a required file untouched and ship red.
3. Make the gate rule absolute, not negotiable: "the narrow gate is zero-failures, full stop; a failure you believe is 'expected' or 'out of scope' is still a STOP-and-report, never a ship-anyway."
4. Ban inline `--body '...'` for any `gh issue/pr` call whose text contains backticks or code — mandate `--body-file` always, as a blanket rule, not something each worker rediscovers by breaking it once.
5. If PRs merge into a non-default branch (`dev`), say so and add "`Closes #N` will NOT auto-close the issue — always `gh issue close` explicitly" to the ship checklist.
6. Give exact expected numeric sanity checks (row counts ± tolerance) for any external/generated data the worker must validate — this was the single biggest smooth-execution win in issue #7 and should be the template for every data-loading task.
7. Name the exact reference file + function to port from, not just "port the logic from X" — a worker with `port whole_word_hit from src/discourse.py` finds it in one grep; a worker with just a repo name searches blind.
8. Tell workers to run `uv sync` (or the project's cold-start command) explicitly as step 0 in a fresh worktree, before any other command — the first invocation is slow and predictable, so front-load the wait instead of letting it silently eat a tool-call timeout mid-task.

## Stats

Friction events by category (both issues combined, 6 events total):
- ENV/TOOLING: 4 (issue7 F1; issue23 F1, F2, F3)
- PROCESS / SPEC-AMBIGUITY: 1 (issue7 F2 — also PROCESS-adjacent overlap with issue23 F2/F4)
- FALSE-ASSUMPTION-ABOUT-CODE: 1 (issue23 F4)
- (no WRONG-PATH, DATA-SHAPE/SCHEMA, MISSING-DOMAIN-CONTEXT, SCALE/RUNTIME, LEAD-CORRECTION, USER-CORRECTION, or SCOPE-CREEP events in either session)

Rough share of session spent on friction vs productive work:
- Issue #7: ~10% friction (the uv timeout stall + the tail-end gate-shipped-red episode cost time/attention but no in-session backtracking loop); the more consequential cost (issue #20 + its fix PR) landed *after* this session ended.
- Issue #23: <5% friction — every friction event was a single wasted tool call immediately self-corrected; this was the smoothest of the two sessions, directly attributable to how detailed and prescriptive the dispatch prompt was.
