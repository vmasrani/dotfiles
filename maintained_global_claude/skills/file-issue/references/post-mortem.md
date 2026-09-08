# Where issue-implementing agents got confused — and what to put in the issue next time

Scope: every parot-cse session that implemented a filed issue (issues #2–#10, #19, #23, #26–#32, #25 close-out, #43 in-flight), plus the wave-1 integrator and the three team-lead/orchestrator sessions (parot-cse ×2, parot-bias wave-1 lead). 22 worker transcripts, 4 lead/integrator transcripts, ~50 MB of JSONL. 16 sonnet analysts, one per session group; per-session findings under `references/findings/g*.md` (this report cites them as g01…g16).

**76 friction events** cleared the bar (≥2 tool calls of detour or a visible wrong belief).

## 1. The headline

"Looked in the wrong place" is the *rarest* failure (4 WRONG-PATH events out of 76). Your dispatch prompts already name absolute worktree paths, base SHAs, file:line pointers and ownership boundaries, and every analyst independently flagged that as the single biggest reason sessions were clean. Don't change that.

The cost lives elsewhere, in two very different shapes:

| Shape | Count | Cost profile | Where it belongs |
|---|---|---|---|
| **Under-specified protocol / acceptance** (SPEC-AMBIGUITY, MISSING-DOMAIN-CONTEXT, half the LEAD-CORRECTIONs) | ~25 | Rare but huge: 30–70 min each, often after a PR is open | the ISSUE body |
| **Environment doctrine** (ENV/TOOLING, SCALE/RUNTIME, PROCESS) | ~40 | Small each (1–15 min) but hits *every* session, identically | a standing PREAMBLE / CLAUDE.md, not per-issue |

Roughly: the issue-body gaps cost ~4 hours of rework across the epic; the environment gaps cost ~2 hours spread as 1–3 papercuts per session plus a few OOM/queue cycles.

## 2. The expensive ones — issue-body lessons, ranked by minutes lost

### L1. State the statistical protocol as an invariant, including the UNIT of derivation (≈3 h total)
- #29 built a full sweep + draft PR on label-leaky CV (all-train weights scored on held-out folds; F0.5 0.88 vs honest 0.65) — 68 min reworked (g10 F1). Lead then had to relay the same fix to #30, #31, #32 individually (g16). #31 had >30 min of work against the optimistic band (g12 F3); #30 got a second 40-min work phase (g11 F5).
- #32 then received the corrected note saying "per-fold weights from the fold's training **authors**" — built the author-unit path, watched the eSPD signal collapse, root-caused the skew, rebuilt at **message** level: **51 min / 92 tool calls on one ambiguous noun** (g13 F5).
- Epic #25's ground rules said "train-only CV" — that didn't imply fold-safe weights to any of four workers.
- **Rule:** if any weight/gate/prior/vocabulary is label-derived, the issue says: "refit per fold from training-fold rows only; derive at the <message|author|conversation> unit; report optimistic AND honest; pick on honest." Same for cross-split scoring direction ("score split B by counting split A's fixed vocab") — #29 hit that as a runtime ValueError (g10 F4).

### L2. Copy the epic's binding rules *and* prior-phase invariants into every phase issue
- #28 built a second test-touch recipe because #26's "exactly ONE recipe reads the test split" lived only in #26 (g09 F1). #31 got pointed by its own dispatch at `tests/test_calibrate.py`, outside the `tests/tier0` CI-gate path (g12 F2). #32's grid omitted the baseline row → nan Δ (issue #44) because the grid invariant lived nowhere (g13 F7).
- Phases #26/#27, whose bodies restated ground rules verbatim, never re-fetched the epic (g08).
- **Rule:** every phase issue carries a "Ground rules (copied, binding)" block + a "Prior-phase invariants you must not break" list + "Blocked on: #N merged AND <invariant> unchanged" so the worker self-gates (the lead hand-sent 8+ GO messages; g16).

### L3. Acceptance numbers need a tolerance, a method, AND the exact function that produces them
- #3 shipped, then had to redo the VTPAN filter and rebuild ~3 GB of indexes because "±10% of the published counts" arrived as a follow-up (g02 F3).
- #25 close-out's prompt asserted "1533 admitted terms from `mine_lexicon`" — the number came from a different unit-level function; 10 min of diagnosis (g14 F1).
- **Rule:** "`<function>` on `<split>` must yield N ± tol; if not, <stop-and-report | bounded sweep over these named variants>". Separate report-only numbers from gate numbers explicitly.

### L4. Empirical-decision rules are standing rules, not live negotiations
- #32 falsified its own premise ("admitted-only is the shipped path") mid-sweep: 68 min including a lead round-trip to agree "ship the better of two unless within noise" (g13 F4). The same tie-break pattern recurred twice in one session and in #31.
- **Rule:** the epic states the decision protocol once ("ship better-of-candidates unless within ~1 sd; record both").

### L5. Name shared "hot seams" that break file ownership
- #7's worker saw 4 red tests in `tests/tier0/test_schema.py` (the stub inventory, not in its owned list), labeled them "expected", and shipped red → issue #20, PR #21, and every wave-1 PR conflicted on that file (g05 F2, g15 F1). #5/#6 each self-authorized editing it (g04 F8). #10's justfile glue recipe between work packages A and B had no owner (g15).
- **Rule:** list every file multiple branches will touch (stub inventory, `.gitignore`, `justfile`, README sections) with an explicit owner/resolution rule, and make the gate absolute: "a red test outside your files is STOP-and-report, never ship."

### L6. Freeze literal vocabularies and scales in seams, not just types
- Integrator found #4 and #7 disagreeing on side-label strings, #9 calling #6's stub with a stale signature, and a threshold whose scale (author-logistic vs raw) nobody had named (g15 F3–F5). #5 assumed `biaskit` helpers returned objects; they return tuples (g04 F3).
- **Rule:** seam contracts pin exact strings, column names, return shapes, and units/scales.

### L7. State corpus scale and the specific operation class that will OOM
- #6 wrote a naive per-row gold lookup that only broke at 2M rows (g04 F6/F7). #28's un-queued matrix build was SIGTERM'd twice (g09 F2). #32's per-message pmap held the whole corpus → OOM (g13 F3); the prompt's memory warning was generic. #29's LR `saga` never converged at 76k features (g10 F2).
- **Rule:** "train ≈ N rows / M authors / K msgs; any per-message pmap over the full split will OOM — chunk it; per-author is fine; use solver X at this scale."

### L8. Ported helpers: document the hidden invariant where the next worker will read it
- `biaskit.min_monotone_prior` / `fw_z_monotone` assume NL≈NR and are argument-order-asymmetric; #4 and #9 rediscovered this independently within the same hour (g03). sklearn's English stoplist deletes grooming-signal words (g03).
- **Rule:** the moment a worker finds a helper gotcha, push it into that helper's docstring / PLAN.md, not only its final report. Name which generic source is unsafe and why.

### L9. External dependencies and end-state constraints go in the issue up front
- #9 was written assuming a dataset obtained by emailing its owner; your correction ("assume this dataset is unavailable") forced a full rewrite and re-dispatch (g16). "Must build from a clean clone, no sibling-path deps" arrived at the end and cost an extra vendoring pass (g16). #2 left edits dangling in a sibling repo because the prompt said "temporarily flip… then revert" but no end-state check (g01 F2/F3).
- **Rule:** name the fallback in the body; state self-containment / "no sibling-repo edits — if you must, commit or revert before reporting done."

### L10. Hard "never" constraints get repeated where the temptation is
- #10A's prompt said "never parse markdown" at the top; under design pressure it built a markdown-parsing reuse cache anyway, torn down after lead review (g07 F4). Similarly a mid-flight "rebase, never merge" contradicted the repo's producer-sha convention; the worker caught it mid-rebase (g13 F6).
- **Rule:** restate the constraint next to the step where it bites; check dispatch git instructions against standing repo conventions.

### L11. Split-issue workers sharing one queue need a sequencing rule
- #10A's 46-min report run (then repeated) starved #10B until 3 of B's background tasks were killed: ~25 min dead (g07 F9). #5/#6 polled 10+ min behind an unrelated job (g04 F5).
- **Rule:** "you share a single-slot queue with worker X; make all content fixes first and regenerate exactly once; A has priority."

### L12. For "wire-together / close-out / report" issues, scout first and paste the file:line map into the body
- #10's two workers oriented in <2 min off a scout's brief (g07, g15). The #25 close-out needed a dedicated scout to discover the real task was "switch shipped `score.py` from config Y to winner Z", not "regenerate the report" (g16).

## 3. The ubiquitous papercuts — one standing preamble, stop paying per session

Each of these hit 2–10 sessions identically; none is issue-specific:

1. **`queue`**: prefix `just ci-fast`/`just test`/any count-matrix or live-scorer run; exact form `queue "cmd > log 2>&1; echo exit=\$?"` (single string); check `queue -l/--triage` before resubmitting (esp. after context compaction — #29 double-submitted); a queue-wrapper "exited 0" is NOT the inner exit — `rg 'passed|failed|exit=' log` (#26, #27, #10 all believed a red ci-fast was green). An OOM/SIGTERM is not the lead killing you — resubmit through queue (lead reassured workers twice).
2. **Format/lint**: `ruff format` is a separate gate from `ruff check`; run both on touched files BEFORE the first heavy ci-fast (#10 unwound commits; #26 burned a gate cycle). Non-default rules live in `pyproject.toml [tool.ruff.lint]`. `ty` gotchas: `.itertuples()` attrs, `groupby` tuple-unpacking, `scripts/*.py` are `uv run --script` entry points → `importlib.util.spec_from_file_location`, never `sys.path` import.
3. **Box facts**: macOS — BSD `pgrep`/`sed` (no `pgrep -c`); `pmap` process mode raises EOFError here — use threads; `uv sync` as step 0 in a fresh worktree (cold `uv run` blew the 120 s tool timeout); re-`cd` into your worktree after any side-trip into a reference repo.
4. **gh**: bodies with backticks → `--body-file`, never inline `--body`; PRs target `dev` so `Closes #N` never auto-fires — `gh issue close` explicitly; dev PRs only run Secret-scan + Workflow-lint, local `ci-fast` is the real gate.
5. **git**: `data/*` + `!data/README.md` (not `data/` + negation) when a tracked file lives in an ignored dir; worktree symlink layout accordingly; never pipe `git push` (masked a non-fast-forward).
6. **Packaging**: a new `app/` next to an editable-installed sibling `app/` is silently shadowed until `__init__.py` exists (#8).
7. **Reporting cadence**: workers got "are you stuck?" nudges during legitimate background waits in ≥5 sessions — tell them "post one line when starting a multi-minute queued job (what, ETA)"; and tell the lead to check `git status`/`queue -l` before nudging (two nudges were stale-monitoring artifacts).
8. **Pre-authorized fallbacks**: "if the ci-fast aggregate is stuck behind another job >2 min, run its sub-recipes directly and say so" — three workers made that call unilaterally.

## 4. What worked — keep doing exactly this (every analyst said so)

- Absolute worktree path + branch + base SHA + "data symlinked, claim posted" → zero orientation time.
- Exact file:line pointers / function names to reuse ("port `whole_word_hit` from `src/discourse.py`") → one grep, done. Vague "port the logic from repo X" → blind search.
- Per-worker file-ownership lists ("you may create/edit ONLY…", "do not edit `lexicon.py`, #4 owns it") → zero merge conflicts across three rebases.
- Verbatim copy-pasteable commands (worktree add, symlink, gate, PR, `queue` protocol, pkill pattern) → ran first time.
- Literal checklists instead of prose (tier/endpoint/jargon list in #8; decision framework a/b in #23; red-green steps as commands) → no "what does done look like".
- Staged execution: "build against fixtures; if real data exists when done, run it; else stop and say so" → no blocking on upstream.
- Exact expected numbers with tolerance ("66 ±5 rows, assert and fail loud"; "base = 276 passed") → self-checking workers.
- `"""Owning issue: #N"""` docstrings on stubs; `*-context.md` sidecars in reference code → instant "mine vs theirs".
- Pre-disclosed expected negatives ("known ~10% off; record the table") → honest negative reported as done, not escalated.
- A tight ≤12-line final report template → clean handoffs.
- Prompt tightness is measurable: #19 (exact pins, exact file:line diagnostic) ran 7.5 min at ~10% friction; #2 (multi-repo, hedged) ran 32+ min at ~40%.

## 5. Proposed issue-body template (for the next epic/phase/feature issue)

```
## Goal (one sentence) + Definition of done (checklist, literal)
## Blocked on / Unblocks: #N merged AND <invariant> unchanged
## Ground rules (COPIED from epic, binding)        ← not a link
## Prior-phase invariants you must preserve       ← "exactly ONE test-touch recipe" etc.
## Protocol (if any stats/CV/eval): unit of derivation, per-fold refit, optimistic+honest, cross-split direction, decision/tie-break rule
## Acceptance numbers: <function> on <split> → N ± tol; report-only vs gate; what to do if off (stop | bounded sweep over …)
## Scale + memory: rows/authors/msgs; which ops must be chunked/queued; known-slow solvers
## Files you own / files you must NOT touch / shared hot seams (owner + rule)
## Seam contracts: exact strings, column names, return shapes, units/scales
## Reuse map: file:line + function names; known helper gotchas
## External deps + fallback; end-state constraints (self-contained, no sibling edits)
## Hard constraints (repeated at the step they bite)
## Known gaps / expected negatives (so they're reported, not escalated)
```
Plus ONE standing preamble (section 3) referenced, not re-typed, by every dispatch.

## 6. Lead/orchestrator-side lessons (g15, g16)
- The lead did ~40 SendMessages in the tune epic; the majority were (a) relaying one protocol fix to 4 workers, (b) GO gates, (c) OOM reassurance, (d) idle nudges — all four vanish with L1/L2 + section-3 items 1 & 7.
- Scout before writing: the wave-1 lead fanned out 3 scouts and baked them into PLAN.md — those issues ran cleanest. Close-out/report issues need the same.
- When a ground-rule gap is found mid-epic, back-port it into the epic body (it was, on #25 — good) AND broadcast to every open sibling immediately, not just where found.
- Scope one-time operational instructions with an end condition ("kill what's queued now, not future jobs") — the over-generalized queue kill hit other projects' jobs.
- A user pivot that kills a session needs wind-down runway (commit/push/handoff) or a fresh short agent to do it — #25's transcript ends mid-pivot.
- Verify dispatch-prompt facts against code before asserting them (the 1533, the `tests/test_calibrate.py` path, "rebase never merge").

## Appendix — per-session index
g01 #2 scaffold + #19 pin-ty · g02 #3 ingest · g03 #4 lexicon + #9 stages · g04 #5 score + #6 lines · g05 #7 calibrate + #23 serve-leak · g06 #8 app · g07 #10 A/B report+walkthrough · g08 #26 harness + #27 VTPAN · g09 #28 two-stage · g10 #29 weights · g11 #30 mining · g12 #31 decision · g13 #32 lines/eSPD · g14 #25 close-out + #43 · g15 integrator + lead 641a · g16 leads (tune epic, wave-1).
Files: `references/findings/g01…g16.md` (this skill).
