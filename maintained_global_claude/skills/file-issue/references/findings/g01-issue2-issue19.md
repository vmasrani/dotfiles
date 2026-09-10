# Issue #2 (scaffold: freeze seams, PR #11) & Issue #19 (pin ty/ruff, PR #22)

## Issue #2 — session `7b60a847-9b21-4215-b042-7b09272bc5ef`

Session overview: build the `parot-cse` scaffold (csekit package w/ stubs, synthetic fixtures, tests, justfile,
pyproject with 3 editable sibling-repo path deps) and open a PR. Transcript spans 20:44:32–21:16:11 (32 min, then
cuts off mid-followup — the transcript file ends right after the team-lead sends a second round of instructions;
PR #11 shows as MERGED with the followups completed, so the work finished but not inside this transcript). ~257
turns / ~120 tool calls. 1 PR opened (not merged by the worker). 2 lead interventions (1 idle-nudge, 1 substantive
correction after "done").

## Friction events (chronological)

### F1: `uv sync` blocked repeatedly by the auto-mode permission classifier
- When: [20:50–20:59] (turn ~62–119)
- What the agent was trying to do: run `uv sync` in the worktree to resolve the 3 sibling path deps (parot, parot-stats, parot-bias) after wiring `[tool.uv.sources]`.
- What it assumed / where it looked: assumed the first resolution failure (`parot-stats` requiring `parot` via `git+rev` conflicting with the worktree's local editable `parot`) was the whole problem, so it started editing `parot-stats/pyproject.toml` to swap `parot`'s source to a local path — then every subsequent `uv sync`/`uv lock` attempt (5 in a row, ~9 min) was denied outright by "the Claude Code auto mode classifier" (writes touching sibling repo dirs outside the worktree got blocked).
- What was actually true: the classifier block was transient/unrelated to the dependency conflict; retrying later (after ~10 min doing other work) let it through.
- Cost: ~9 tool calls, ~9 minutes of wall clock stalled on the same command.
- Category: ENV/TOOLING
- Evidence: `"Permission for this action was denied by the Claude Code auto mode classifier. Reason: Blocked by classifier."` (repeated 4x, 20:50:20–20:52:39)
- What in the issue/prompt would have prevented it: note in the dispatch prompt that writes to sibling-repo directories outside the assigned worktree may trip the auto-mode classifier and need a retry after a pause, rather than looking like a real uv/dependency failure — so the agent doesn't waste retries assuming its own edit caused it.

### F2: Sibling repo's wheel silently shipped empty (`biaskit` unimportable) — root-caused correctly, but fix left dangling
- When: [21:00–21:09] (turn ~122–148)
- What the agent was trying to do: verify `import biaskit, statskit, csekit` after `uv sync` finally succeeded.
- What it assumed / where it looked: `ModuleNotFoundError: No module named 'biaskit'` even though sync reported success; agent inspected `.venv/site-packages` dist-info, then built the wheel directly (`uv build --wheel`) and unzipped it to confirm it was empty of `biaskit.py`.
- What was actually true: `../parot-bias/pyproject.toml`'s `[tool.hatch.build.targets.wheel]` used `bypass-selection` with no `include`/`only-include` list, so the built wheel had no code in it — `import biaskit` had only ever "worked" inside `parot-bias` itself because running a script from that directory puts cwd on `sys.path`.
- Cost: ~15 tool calls / ~9 minutes to diagnose + patch a **sibling repo's** packaging config (not owned by this issue), left as an uncommitted local edit at report time.
- Category: FALSE-ASSUMPTION-ABOUT-CODE / PROCESS
- Evidence: `"import biaskit ... ModuleNotFoundError"`; `"the wheel fix is correct and should be permanent... commit ONLY that file in .../parot-bias"` (lead's followup)
- What in the issue/prompt would have prevented it: the dispatch prompt already anticipated cross-repo trouble ("if resolution fails... temporarily symlink or run smoke from a copy") but gave no guidance for *this* failure mode (a broken sibling wheel) or for what to do once a real bug is found in a repo the worker doesn't own — state explicitly: "if you fix a bug in a sibling repo to unblock yourself, commit it there directly (not just verify-then-leave-uncommitted) and say so in the report" or "flag it and stop touching that repo." This alone (see F3) is the single biggest lesson from this session.

### F3: Cross-repo edits left uncommitted/unreverted at "done" — lead had to send a full followup round
- When: [21:16] (post-completion, turn ~260, and confirmed via PR #11 description after the transcript cuts off)
- What the agent was trying to do: report the scaffold as done.
- What it assumed / where it looked: reported both the `parot-bias` wheel fix and the `parot-stats` source-flip as "real fixes someone should land... not mine to land" — i.e., punted ownership without finishing either action (parot-stats edit was never reverted per its own file comment "don't commit it"; parot-bias fix was correct but left as an uncommitted local edit, not landed).
- What was actually true: the lead wanted a decision, not a punt — REVERT parot-stats (`git checkout pyproject.toml`, since parot-bias already resolves the same chain without the edit), and land parot-bias's fix as a real commit (with a full 3-line git-add/commit instruction, forbidding staging unrelated files).
- Cost: a full second round-trip with the lead (3-point followup message), plus a required fresh `uv lock`/`uv sync`/re-verify cycle in the worktree — all avoidable if the worker had finished the cross-repo cleanup itself before reporting "done."
- Category: LEAD-CORRECTION / SCOPE-CREEP
- Evidence: `"Thanks — good catch on the empty wheel. Two follow-ups... REVERT the parot source flip... its own comment says 'don't commit it'"`; `"the wheel fix is correct and should be permanent... commit ONLY that file"`
- What in the issue/prompt would have prevented it: the dispatch prompt's step 2 already said "temporarily flip... verify, then revert" for exactly this kind of edit — add: "before reporting done, `git status`/`git diff` EVERY sibling repo you touched during verification and either revert it or commit it; never leave an uncommitted change in a repo you don't own."

### F4: `just ci-fast` heavy-job guardrail + shared-queue congestion
- When: [21:10–21:14] (turn ~152–232)
- What the agent was trying to do: run `just ci-fast` as instructed (step 4).
- What it assumed / where it looked: ran it as a plain background Bash call; got redirected by a system guardrail to use `queue`, then the queued job sat behind 8 other machine-wide jobs (other sessions' Rust test/bench runs) for several minutes.
- What was actually true: the shared `queue` mechanism serializes heavy jobs across all concurrent sessions on the box; `ci-fast` isn't special-cased for priority.
- Cost: ~4 minutes waiting, several idle "yield turn" tool calls, one `queue --cancel`/`--priority` maneuver, and ultimately a deviation from spec (ran the ci-fast sub-recipes directly instead of the aggregate, reported transparently).
- Category: ENV/TOOLING / SCALE-RUNTIME
- Evidence: `"just ci-fast is heavy and was not sent to the queue... Run it as: queue just ci-fast..."`; `"queue: 8 job(s) ahead; blocked by job 43..."`
- What in the issue/prompt would have prevented it: not really preventable from the issue text (shared-machine contention is dynamic) — but the dispatch prompt could pre-authorize the exact fallback taken ("if `just ci-fast`'s aggregate is congested in the shared queue, running its constituent sub-recipes directly is an acceptable substitute — report which you did") so the agent doesn't have to decide alone whether that's a permitted deviation.

### F5: Lead had to nudge for a status report during a legitimate background wait
- When: [21:12:25]
- What the agent was trying to do: wait silently for the queued `ci-fast` job's completion notification (per harness convention: yield the turn, get re-invoked automatically).
- What it assumed / where it looked: assumed waiting silently was correct because harness re-invokes on task-notification.
- What was actually true: from the lead's side, ~1–2 minutes of silence with an uncommitted worktree looked indistinguishable from "stuck" — same pattern recurred in issue #19 (see F2 there).
- Cost: 1 extra round-trip message; no wasted work, just an unnecessary lead interrupt.
- Category: PROCESS
- Evidence: `"You went idle with the worktree uncommitted... If something is blocking you... tell me exactly what instead of going idle."`
- What in the issue/prompt would have prevented it: dispatch prompts should state an explicit reporting cadence for background waits, e.g. "if a background command you're waiting on takes longer than ~2 minutes, send a one-line interim status ping before going quiet."

## What went smoothly because the prompt/issue supplied it
- Naming the exact sibling repos, their shipped module names, and known gotchas (`import parot` needs psutil; pyarrow==23.0.1; numpy<2.5; `src` is a reserved top-level name) → the agent never had to discover these the hard way; zero friction on the parts explicitly enumerated.
- "Copy the dependency list and pin comments VERBATIM from parot-bias/pyproject.toml" + "check how parot-radar/parot-bias handle [relative paths]" → agent went straight to those two files as reference patterns (turns 8–22) and wrote a correct pyproject.toml in one pass, no backtracking.
- The exact NotImplementedError-stub convention (module → owning issue number mapping #3–#7) → csekit package built in one pass, no rework.
- Precise synthetic-fixture spec (conv counts, IRC-style/non-ASCII/short-participant edge cases, vtpan_keep marking rule) → `make_fixtures.py` written once and only needed a 1-line NameError fix (trivial, not counted as friction).
- Explicit "Do NOT commit data/ or .venv", "no Co-Authored-By", "do NOT merge" → zero mechanical PR mistakes.

## Issue #19 — session `9db94770-fe41-423b-b2af-0d3f340b7796`

Session overview: pin `ty`/`ruff`/`pytest` versions, fix every diagnostic they raise, update README, verify
`just ci-fast` green with matching pytest count vs. dev baseline, commit. Transcript spans 07:05:57–07:13:25 —
**7.5 minutes**, ~125 tool calls, extremely efficient. 1 commit, PR #22 opened later and merged. 1 lead
intervention (idle-nudge only, no substantive correction).

## Friction events (chronological)

### F1: `queue` invocation misuse (2 failed attempts before success)
- When: [21:11:04–21:11:09 UTC] i.e. [07:11:04–07:11:09] (turn ~177–183)
- What the agent was trying to do: run `just ci-fast` in the background per the heavy-job guardrail's instruction to use `queue`.
- What it assumed / where it looked: first ran `just ci-fast` directly (not queued at all); after the guardrail rejected that, tried `queue (just ci-fast > /tmp/cifast.log 2>&1; echo exit=$?)` — got rejected again because the shell splits on `;`/`)` before `queue` executes, so only the first token reached `queue` and the rest ran unqueued.
- What was actually true: the whole command must be passed as ONE quoted string: `queue "just ci-fast > /tmp/cifast.log 2>&1; echo exit=\$?"`.
- Cost: 2 tool calls of detour, <10 seconds — auto-corrected by the guardrail's own error message each time.
- Category: ENV/TOOLING
- Evidence: `"just ci-fast is heavy and was not sent to the queue..."`; `"just ci-fast runs OUTSIDE the queue here. The shell splits on the operator before queue is exec'd..."`
- What in the issue/prompt would have prevented it: the dispatch prompt already told the agent to background+log slow commands but didn't give the exact `queue "cmd"` quoting form — supplying the working invocation verbatim (as global tooling doctrine, not per-issue) would remove this entirely; this is the same class of friction across both sessions, so it belongs in a shared/standing instruction rather than every dispatch prompt.

### F2: Lead had to nudge for a status report during a legitimate background wait
- When: [07:11:58]
- What the agent was trying to do: wait for two queued/backgrounded jobs (`ci-fast` in the worktree, `just test` baseline in the primary checkout) to finish, per harness convention (yield turn, resume on notification).
- What it assumed / where it looked: silent waiting was correct; it had in fact already gotten `ci-fast` green a few seconds earlier and was purely waiting on the read-only baseline count.
- What was actually true: from the lead's side, ~1 minute of silence with ~25 modified files and no commit looked like it might be stuck.
- Cost: 1 extra round-trip message; the agent's one-line reply resolved it immediately, no rework.
- Category: LEAD-CORRECTION / PROCESS
- Evidence: `"You went idle without a report. The issue-19 worktree shows ~25 modified files and no commit. Status?"`
- What in the issue/prompt would have prevented it: same lesson as issue #2 F5 — an explicit "ping every ~1–2 min while waiting on a background job, even just 'still waiting on X'" instruction in the dispatch prompt or as standing team doctrine.

## What went smoothly because the prompt/issue supplied it
- Exact version pins (`ty==0.0.73`, `ruff==0.16.4`, `pytest==9.1.1`), the exact file:line of the one known diagnostic (`csekit/receipts.py:98`, `itertuples()` unresolved-attribute), and the exact pyproject edit (move `pytest` out of `[project]` into `[dependency-groups] dev`) → the agent needed zero discovery time for the core fix; went straight from issue text to the fix.
- "If `uv lock` rewrites unrelated parts of uv.lock..., report it — do not hand-edit the lock" → agent explicitly diffed `uv.lock` and confirmed it was clean before proceeding (no wasted investigation, no risk of a bad hand-edit).
- "Do not add blanket `# type: ignore`; use targeted `# ty: ignore[rule]` with reason" and "prefer `ruff format`/`ruff check --fix` for mechanical ones; inspect the diff" → agent auto-fixed 41/66 ruff errors mechanically, then correctly recognized the remaining 25 as needing manual fixes without ever reaching for a blanket suppression.
- "Get the baseline by running `just test` ONCE in the primary checkout" → agent didn't have to guess what counts as an acceptable pytest-count match; found dev's 275-passed-1-skipped vs. worktree's 276-passed and correctly reconciled it as "same 276 total collected, baseline has 1 environment-dependent skip" rather than treating it as a real mismatch.
- Told explicitly which repo/branch/worktree to work in and to anchor every command with `cd .../issue-19 &&` → zero path-confusion tool calls in the whole session (contrast with issue #2's multi-repo path saga).

## Generalizable lessons
1. When a dispatch prompt tells the worker to make a **temporary** edit to a sibling/unowned repo to verify something, also require an explicit end-state check before reporting done: revert it, or commit it — never leave it dangling uncommitted.
2. If a worker finds and fixes a real bug in a repo it doesn't own while unblocking itself, tell it up front to commit that fix directly in that repo (with a precise `git add <file> && git commit` scoped to just that file) rather than "flag it and leave it."
3. Standardize the exact `queue "cmd"` quoting form (single-quoted whole command) as shared tooling doctrine, not per-prompt text — both sessions independently rediscovered/were corrected on it.
4. Add an explicit reporting-cadence rule to dispatch prompts: ping the lead with a one-line status update every ~1–2 minutes while waiting on a backgrounded/queued command, even when nothing is wrong — both sessions got an "are you stuck?" nudge for legitimate waits.
5. When multiple sibling repos have path-dependency conflicts (git-rev vs. path sources), tell the worker up front that the fix belongs inside the repo being built (`[[tool.uv.dependency-metadata]]` override), never by editing a sibling's committed source — issue #2's prompt hinted at this but didn't rule out editing siblings, which is exactly what happened.
6. Naming exact file:line diagnostics, exact version pins, and exact reference files to mirror (as issue #19's prompt did) collapses an entire class of discovery-time friction to zero — keep doing this for any issue with a known concrete symptom.
7. Warn the worker that writes touching directories outside its assigned worktree (e.g., sibling repos during multi-repo dependency verification) may trip the auto-mode permission classifier and need a retry, so a transient permission block isn't mistaken for a real resolution failure.
8. For any step involving a shared, congestable resource (the machine-wide `queue`), pre-authorize an acceptable fallback (e.g., "run the sub-recipes directly if the aggregate is stuck in queue") so the worker doesn't have to unilaterally decide whether deviating from the literal instruction is allowed.

## Stats
- Issue #2 friction events by category: ENV/TOOLING: 2 (F1, F4), FALSE-ASSUMPTION-ABOUT-CODE/PROCESS: 1 (F2), LEAD-CORRECTION/SCOPE-CREEP: 1 (F3), PROCESS: 1 (F5)
- Issue #19 friction events by category: ENV/TOOLING: 1 (F1), LEAD-CORRECTION/PROCESS: 1 (F2)
- Combined: ENV/TOOLING: 3, FALSE-ASSUMPTION-ABOUT-CODE: 1, LEAD-CORRECTION: 2, PROCESS: 2, SCOPE-CREEP: 1 (overlaps counted once per event)
- Rough share of session spent on friction vs. productive work: issue #2 ~40% (roughly 13 of 32 min: F1 9min + F2/F3 diagnosis ~9min overlapping with productive fixture-writing done in parallel, F4 congestion ~4min); issue #19 ~10% (under 1 of 7.5 min — almost entirely productive, friction was two brief guardrail corrections).
