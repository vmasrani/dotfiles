# #3–#9 (wave-1 integration) + #19/#20/#23/#10/#25 (team-lead) — g15-integrator-lead641a

Two sessions, two lenses (per brief twist): the wave-1 INTEGRATOR (`aa460a67…`, merging 7 issue branches into `wave1-integration`) reviewed with the standard friction-event rubric; the TEAM-LEAD session (`641a6f5b…`, orchestrating #19/#10/#23/#25 via dispatched subagents) reviewed for (a) mid-flight corrections to workers, (b) user corrections, (c) scouting the lead had to do that an issue body should have pre-contained.

---

# SECTION 1 — Wave-1 Integrator (`aa460a67-bcc2-45ec-8593-f883728c5d50`)

**Session overview:** Merge PR #17,#13,#12,#14,#16,#15 (issues #4–#9) then an addendum PR #18 (#3) into one integration branch `wave1-integration`, on top of the frozen-seam contract in `PLAN.md`. First→last timestamp 21:59:10→22:30:23 (~31 min). ~185 tool calls. Two lead addenda mid-flight (merge #18 first; reframe the problem-1 report to recall-at-budget). Finished: branch pushed, all gates green, PR-ready; 2 unsolicited status reports sent to team-lead. No user-typed messages in this transcript (pure teammate-to-teammate).

## Friction events

### F1: Same shared stub-inventory test collides across three branch merges
- When: 22:00, 22:00:24, 22:08:02 (turns ~8, ~14, ~50)
- What the agent was trying to do: merge #13 (score), then #12 (lines), then #18 (ingest) `--no-ff` in sequence.
- What it assumed / where it looked: each merge would auto-resolve; had to `rg` for conflict markers in `tests/tier0/test_schema.py` each time.
- What was actually true: three separate branches (#12, #13, #18) each independently edited the same shared stub-inventory parametrize block (`test_stub_raises_not_implemented`) that #20 later replaced — a single shared "bookkeeping" test file every issue branch touches with no designated owner.
- Cost: ~4 tool calls × 2 occurrences (~8 calls), a few minutes.
- Category: PROCESS (workflow kit / PR mechanics — shared-file ownership)
- Evidence: `"CONFLICT (content): Merge conflict in tests/tier0/test_schema.py"` (×2); `"<<<<<<< HEAD ... >>>>>>> origin/issue-6-lines"`
- Prevention: PLAN.md's Frozen Seams section should flag `tests/tier0/test_schema.py`'s stub-inventory block as a shared/hot file every wave-1 branch touches, with an explicit rule ("delete a module's stub-test row the moment its issue lands, whichever branch merges last") instead of leaving ad-hoc deletion to the integrator each time.

### F2: `.gitignore` `data/` pattern + worktree symlink destroyed by merging #3
- When: 22:08:04–22:12:11 (turns ~55–100), recurring twice (gitignore conflict, then broken symlink)
- Trying to do: merge #18 (issue-3-ingest), which itself edited `.gitignore` to make `data/README.md` trackable while keeping `data/` ignored and worktree-symlink-safe.
- Assumed / where it looked: guessed `/data` alone would satisfy both the canonical checkout (real dir, tracked README) and the worktree (symlink) — tested via `git check-ignore` after the fact.
- Actually true: git-ignore semantics needed **four order-sensitive lines** (`/data`, `!/data/`, `data/*`, `!data/README.md`), verified empirically in two disposable sandboxes; the first guess failed verification. Separately, merging #18 (which tracks `data/README.md`) silently replaced the worktree's `data` **symlink** with a real directory, breaking every downstream `just` recipe (`MISSING PREREQUISITE: data/pan12/train.csv …`).
- Cost: ~20 tool calls, ~5 minutes across both incidents.
- Category: ENV/TOOLING (git worktree + gitignore interaction)
- Evidence: `"My /data claim failed verification — data/README.md is still ignored in the canonical checkout."`; `"MISSING PREREQUISITE: data/pan12/train.csv … The tests that read these would SKIP and still report success. Refusing."`; `"The data symlink was destroyed — #18 tracks data/README.md, so git replaced the symlink with a real directory."`
- Prevention: PLAN.md / AGENT_WORKFLOW.md should state the exact validated 4-line `.gitignore` block up front (not leave it to be reverse-engineered via trial-and-error), plus an explicit warning: "a worktree's `data` symlink is replaced by a real directory the instant any branch adds a tracked file under `data/`; re-symlink data's **children**, never `data` itself, after merging a data-touching branch."

### F3: `stages.py` (#9) called `lines.changepoint` (#6) against a stale stub signature
- When: 22:02:56–22:04:04 (turns ~30–38)
- Trying to do: run the merged tier0+app suite.
- Assumed: #9 and #6, each individually green, would also compose cleanly.
- Actually true: #9 was written against `csekit.lines.changepoint`'s **stub** signature (frozen seam S4, pre-#6); #6's real implementation used a different call contract, so the mismatch was invisible until both branches merged together.
- Cost: ~6 tool calls, a few minutes.
- Category: FALSE-ASSUMPTION-ABOUT-CODE
- Evidence: `"csekit/stages.py:866: in changepoint_vs_boundary\n    cp = int(changepoint(cid, split, lexicon)[\"seq\"])"`; `"the #6 seam has landed; assert the real contract, not the stub"`
- Prevention: PLAN.md's S4 frozen-seam entry should pin `csekit.lines.changepoint`'s exact signature as an authoritative contract before #6 and #9 both start coding, so #9 never needs a post-hoc patch when #6 ships something different from the stub.

### F4: `mine_lexicon.py` (#4) and `receipts.py` (#7) disagree on side-label vocabulary
- When: 22:02:21–22:02:53 (turns ~26–35)
- Trying to do: run the merged tier0 suite.
- Assumed: #4's `receipts_for()` and #7's `_SIDES` dict would use the same label strings for the two PAN12 classes.
- Actually true: `_SIDES = {"predator": 1, "non_predator": 0}` in #7, but #4's script passed `"positive"`/`"negative"` — two branches, each written against a stub, independently invented their own vocabulary.
- Cost: ~5 tool calls.
- Category: DATA-SHAPE/SCHEMA
- Evidence: `"ValueError: side must be one of ['non_predator', 'predator'], got 'positive'"`
- Prevention: the frozen-seam contract for `csekit.receipts`'s side parameter should name the exact literal strings, so #4 doesn't invent a second vocabulary independently.

### F5: Calibration threshold scale ambiguity (author-logistic vs per-text-raw) — genuine defect
- When: 22:23:17–22:24:54 (turns ~140–160)
- Trying to do: wire the calibration report to a real operating point per the lead's addendum.
- Assumed: `generate_calibration_report.py --threshold` used the same [0,1] logistic scale as #5's author-level threshold (0.9718).
- Actually true: FPR came back `nan` — the calibration script's `threshold` gates a **per-text raw** score, a different scale from the per-author logistic score; nothing in either branch documented this, and it only surfaced when the integrator tried to connect the two for one coherent headline number.
- Cost: ~10 tool calls, a rename (`threshold`→`raw_threshold`) across 3 files.
- Category: DATA-SHAPE/SCHEMA
- Evidence: `"The calibration ran without a threshold, so FPR is nan — let me check what scale that threshold expects"`; `"Found a real defect."`
- Prevention: PLAN.md should record, next to every frozen-seam "score," which scale it is on, and name the parameter accordingly from the start (`raw_threshold` vs `author_threshold`) so two independently-built scripts can't collide on an ambiguous bare `threshold`.

### F6: Self-inflicted — deleted `data/logs` while a background job was still writing to it
- When: 22:29:18–22:29:46 (turns ~230–235)
- Trying to do: consolidate the worktree's local `data/logs` into the shared canonical `data/logs` (`rm -rf data/logs && ln -sfn … data/logs`).
- Assumed: `lines_report.py` (problem2+eSPD, a long real-data job) had already finished writing.
- Actually true: it was still running and actively appending to that log file; the `rm -rf` deleted the directory out from under the live process.
- Cost: ~3 tool calls to assess (no functional damage — the process itself survived; only its diagnostic log was truncated).
- Category: PROCESS (background-job hygiene)
- Evidence: `"I made a mistake there — I deleted data/logs while lines_report was writing into it."`
- Prevention: not a PLAN.md fix — an operational rule for AGENT_WORKFLOW.md: never `rm -rf` a directory a `run_in_background` job you're still waiting on may be writing into; check `ps`/job state first.

## What went smoothly because the prompt/issue supplied it
- PLAN.md's "Frozen seams" + "Dependency graph" sections, read in full up front → 4 of 7 merges (#6, #7, #9, #8) auto-merged with **zero** conflicts; none of the predicted PLAN.md/justfile/pyproject.toml conflicts materialized.
- The lead's addendum naming the exact branch, SHA, and required combination for #18 ("merge it FIRST … before #17 … combine with the bare `data` symlink line I asked for") → no ordering guesswork.
- Existing static-gate commands (`uv run ruff format --check .`, `uv run ty check .`) were already known conventions → zero time spent discovering the lint/type toolchain.
- The lead's Phase-B reframe ("we are a fast, high-recall PREFILTER … operating point is recall-at-budget, not F0.5") arrived as one clear, self-contained addendum → implemented (`recall_vs_pass`, `prefilter_alone`, `throughput_table`) with no back-and-forth.
- Harness guardrails (blocked `sleep`-then-check, blocked unconditional post-commit echo) fired exactly when needed and were corrected in the very next tool call each time — no real backtracking cost, a positive signal for the harness's own safety rails.

## Generalizable lessons
1. Name every file that multiple parallel branches will edit (shared stub-inventory tests, `.gitignore`, `justfile`) as a "hot seam" in the plan, with an explicit resolution rule — not just the data schemas.
2. Pin exact literal vocabularies (side labels, column names) in the frozen-seam contract, not just types — two branches built against the same stub will invent different strings otherwise.
3. When a signature is still a stub at the time a dependent branch is written, freeze the stub's exact signature as the contract — don't let the "real" implementation silently diverge from it.
4. State the exact validated `.gitignore`/worktree-symlink recipe in the workflow doc instead of leaving it to be re-derived per integration.
5. Name the scale/units of every "score" or "threshold" a frozen seam produces (raw vs logistic, [0,1] vs unbounded) so downstream integration code doesn't guess.
6. Treat a live background job's output directory as off-limits for destructive operations until its process is confirmed finished.

## Stats
- Friction events by category: PROCESS ×2, ENV/TOOLING ×1, FALSE-ASSUMPTION-ABOUT-CODE ×1, DATA-SHAPE/SCHEMA ×2
- Rough share of session on friction vs productive work: ~20% (≈40 of ~185 tool calls directly tied to the 6 friction events; the remainder was clean merges, running/reading gates, and the (also clean) headline-measurement pipeline).

---

# SECTION 2 — Team-lead session (`641a6f5b-e7ed-41f7-975f-7231f80cec98`)

**Session overview:** Kicked off from a single user message, `"continue working on the open issues"` (07:04). The lead surveyed issues/PRs, dispatched a read-only scout (`scout10`) and a worker (`w19`) in parallel, closed #19 via PR #22, then dispatched two parallel workers (`w10a`, `w10b`) for #10's two work packages, integrated their branches itself (history surgery + cherry-pick), merged PR #24, filed #23 (orphan daemons) along the way, and — much later in the same session (20:45–22:53) — answered user status questions, then dispatched a "knobs" scout and filed a new tuning epic #25 with `/triage` sub-issues. ~995 lines / several hundred tool calls across ~16 hours of wall-clock (mostly idle between the morning implementation burst and the evening summary/planning burst).

## (a) Mid-flight interventions the lead sent to a worker — what was missing from the original dispatch

1. **`w19` status ping** (07:11:52) — *"You went idle without a report. The issue-19 worktree shows ~25 modified files and no commit. Status? If you're blocked, say on what."* The dispatch prompt never told the lead (or the worker) how to distinguish "idle = done, about to report" from "idle = stalled mid-task" — the harness's `idle_notification` carries no such signal. The lead had to inspect `git status`/`git diff` itself before and after pinging; it turned out `w19` had, in fact, already committed (`4820d4c`) by the time of inspection — a race, not a real block.
2. **`w10a`: "why queue job 270 (second full report.py run)?"** (08:20:56) — the dispatch prompt described the four report tables to produce but never stated the sequencing rule "run the expensive (46-min) full regeneration exactly once, as the LAST step, after all code is final." Supplied mid-flight: *"Your report.py run finished (exit=0, ~46 min wall) and you have 2 commits + 14 uncommitted files. I see you queued a SECOND full run…"*
3. **`w10a`: "Table 4 must carry a real FPR at Table 1's θ"** (08:21:37) — neither the issue nor the brief pinned a cross-table consistency requirement (Table 4's calibration FPR must be evaluated at the exact threshold Table 1 picked). This only became visible once the lead read the rendered report output.
4. **`w10a`: "cancel 270; do Table-4 θ fix first, then ONE final run"** (08:22:29) — reinforcement of #2/#3's ordering, after the worker's own reasoning for rerunning didn't match the lead's intended sequencing.
5. **`w10a`: "drop markdown-parsing reuse; persist frames; ONE full run at final sha"** (08:35:18) — the dispatch prompt gave no caching/reuse strategy for avoiding repeated 46-minute regenerations; the worker's own solution (parse its own previously-generated markdown back into data) was a hack the lead had to redirect to a proper design (persist per-table DataFrames to sha-keyed parquet).
6. **`w10a`: "also add `walkthrough` justfile recipe in final commit"** (08:45:56) — the two workers' file-ownership split (A owns `justfile`/`README.md`; B owns `gen_walkthrough.py`/`walkthrough.html`) left the **glue** — the justfile recipe that invokes B's generator — unassigned to either worker until the lead noticed the gap after B had already finished.

## (b) User-typed corrections
**None of substance.** Across the entire session the user sent: the opening one-liner, two status check-ins (`"status so far?"`, `"give me a full summary…"`), one confirming question (`"okay so basically all the code works, except we're doing much worse than the baseline… is that correct"` — the lead confirmed rather than being corrected), a new-direction request (tune the algorithm + a theory question), and `"great, save the plan an an issue"`. Zero instances of the user telling the lead it had done something wrong. This is itself a notable positive data point (see lessons).

## (c) How the lead discovered information it put into dispatch prompts (→ what an issue body should pre-contain)
1. **Tool-version delta for #19.** The issue said only "dev is red under ty 0.0.34"; the lead had to run `uv run ty --version` (0.0.17 installed) *and* `uvx ty@latest --version` (0.0.73) itself to compute the exact pin values it then wrote into `w19`'s prompt. → An issue that says "pin tool X" should name the exact target version(s), not just the version that broke.
2. **Repo conventions.** `justfile`, `pyproject.toml`, `.ci/init.sh`, README's worktree section, `.agent-workflow/AGENT_WORKFLOW.md` rules 1–6, and the list of installed skills were all read cold via `ls`/`cat`/`rg` before any dispatch — none of this is issue-specific, all of it is re-derived every session.
3. **`dev` branch drift.** Local `dev` was 10 PRs behind `origin/dev`; discovered only via `git fetch && merge --ff-only`, not flagged anywhere.
4. **Issue #10's actual scope.** The issue body ("report: regenerated numbers, README tables, walkthrough, caveats") named no file:line mapping at all. The lead had to spawn a dedicated read-only **scout subagent** (`scout10`) to produce a full implementation brief — mapping every table to an existing function with file:line pointers — *before* it could write real dispatch prompts for `w10a`/`w10b`. This is the clearest single piece of evidence for the brief's whole thesis: a "wire up existing work" issue is not shovel-ready without a scouting pass.
5. **Structural template for the walkthrough worker.** The lead located `../parot-stats/gen_walkthrough.py` (a sibling repo) and `~/.claude/skills/walkthrough/assets/` via `ls`, then pasted the exact path into `w10b`'s prompt as "a structural model … copy its structure, not its domain." Not in the issue.
6. **Orphaned `parot __serve` daemons** (18 processes, up to 33h old) were found incidentally while checking `w19`'s environment (`pgrep -f 'parot __serve'`) — not flagged by any issue — and became new issue #23 rather than an inline fix (correct scoping discipline, but also evidence that nothing tracks this invariant anywhere).
7. **Tuning epic #25.** Same scout-first pattern repeated at the *issue-authoring* stage: a "knobs" subagent inventoried every tunable parameter with file:line pointers before the lead wrote the epic and its `/triage` sub-issues — scouting fed the issue body this time, not just a dispatch prompt.

## Generalizable lessons
1. For any "wire together existing work" issue (reporting, glue code, walkthroughs), run a read-only scout subagent first and paste its file:line map directly into the body/dispatch prompt — don't send an implementing worker in to rediscover the codebase.
2. When splitting one issue into file-ownership-partitioned work packages, explicitly assign every shared "glue" artifact (a justfile recipe invoking the other package's script, a README section referencing both) to exactly one owner up front — the seam between two ownership boundaries is invisible until late review otherwise.
3. An issue that says "pin tool X" must name the exact target version(s) (check `<tool> --version` vs `uvx <tool>@latest --version`), not just describe the symptom.
4. For any task with an expensive (tens-of-minutes) regeneration step, state explicitly: make all changes first, regenerate exactly once as the last step, and specify how to iterate cheaply on subsections (persisted per-stage frames) — don't leave the worker to invent, and the lead to reject, a markdown-parsing reuse hack.
5. Never treat an `idle_notification` as proof of either "stuck" or "done" — always cross-check `git log`/`git status` before intervening; the notification alone is not a status.
6. Review generated artifacts for cross-referential consistency across tables/branches (e.g., "this FPR must be evaluated at the OTHER table's chosen threshold") — that class of gap won't appear in either individual worker's own tests.
7. A single well-scoped kickoff sustained ~2.5 hours of fully autonomous multi-issue work with zero corrective user input; the dispatch-prompt discipline observed here (explicit file ownership, exact commands, context-hygiene line, ≤12-line report mandate) is what made that possible — keep authoring prompts at this level of specificity.
8. Route incidental discoveries (orphaned daemons, stale docs) into a newly filed issue immediately instead of fixing inline mid-task — preserves scope while still capturing the finding for triage.

## Stats
- Mid-flight `SendMessage` interventions requiring new information/correction: 6 (all to `w10a`, except the one status ping to `w19`).
- User-typed corrections: 0 (only informational/directional asks — a positive result).
- Scouting instances whose findings were folded into a dispatch prompt or issue body: 5 (tool-version delta, git/dev drift, `scout10` brief, walkthrough structural template, `knobs` inventory) + 1 incidental discovery filed as its own issue (#23).
