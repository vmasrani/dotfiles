# Issue #3 — session fb116429-426f-4229-8009-486e7837be84

Session overview: dispatch prompt asked the worker to implement `csekit.ingest` (PAN12 XML → S1 message
CSV, VTPAN flags, dual parot word/byte indexes) for issue #3, run it on the real 91MB PAN12 corpus, and
open a PR. Session ran 21:28:51 → 22:07:18 (~38 min, and the transcript cuts off mid-task at 22:07 —
final variant-sweep table for the lead's follow-up was in progress, not confirmed captured). ~230 tool
calls. PR #18 opened at 21:58 and later **merged** (confirmed via `gh pr view 18`: state MERGED). Two
lead interventions: one informational (VTPAN counts run high vs. published, "spend a bounded pass"), one
immediately following ("bounded follow-up ≤20 min before integrator measures"), both after the PR was
already open — the worker had to redo the VTPAN filter, re-run ingest+build-index on 2M+ rows, and update
docs/tests post-PR rather than before.

## Friction events (one block each, chronological)

### F1: `contains="predator"` substring matched 3 real zip entries, not 1
- When: [21:45] (turn ~55, first real-data ingest attempt)
- What the agent was trying to do: run `csekit.ingest.pan12_to_csv` on the real 91MB `pan12.zip` for the first time (unit tests against the small synthetic fixture had already passed).
- What it assumed / where it looked: wrote `_read_ids(train_zip, contains="predator")` — reasonable given the preamble's example filename `training-corpus-predators-2012-05-01.txt`.
- What was actually true: the real training inner-zip also contains `readme.txt` and `...-diff.txt`, and `"predator"` (singular) matches all three of `readme.txt`'s... no — it specifically matched `pan12-...-diff.txt` and the predators file, both containing the substring "predator". `_find_one` requires exactly 1 match and raised `ValueError` listing 3 candidates.
- Cost: ~2 tool calls (grep for the literal string, one Edit to narrow the substring) + one wasted ~10s pipeline run before the fix.
- Category: DATA-SHAPE/SCHEMA
- Evidence: `ValueError: expected exactly one entry containing 'predator' ending '.txt' among [...4 entries...], found ['readme.txt', '...-diff.txt', '...-predators-2012-05-01.txt']`
- What in the issue/prompt would have prevented it: the preamble already named the exact predator-file name (`training-corpus-predators-2012-05-01.txt`) — it just wasn't phrased as "match on the *plural* substring `predators`, not `predator` (the training zip also ships a `-diff.txt` file containing that substring)." A one-line warning about the diff.txt sibling file would have prevented the wrong first guess. Minor — fixed in under a minute.

### F2: git ignore-negation pattern didn't work for `data/README.md`
- When: [21:55] (turn ~150, staging the final commit)
- What the agent was trying to do: track `data/README.md` while keeping the rest of the shared, gitignored `data/` directory (real corpus + multi-GB indexes) untracked.
- What it assumed / where it looked: used the pattern already present in the repo's `.gitignore` (`data/` + `!data/README.md`) — a pattern it inherited from the existing repo, not one it invented.
- What was actually true: git's negation rule doesn't un-ignore a file inside a directory that is itself excluded with a trailing-slash pattern (`data/`) — `git add` refused with "paths are ignored ... use -f". Had to switch to `data/*` + `!data/README.md` (exclude contents, not the directory) to make the negation take effect, and also restructure the worktree's `data` symlink (it had been one single symlink to the whole shared `data/` dir, which itself doesn't work with a real tracked file inside it) into per-subdir symlinks (`data/raw`, `data/pan12`, `data/index`, `data/logs` symlinked individually, `data/README.md` a real file).
- Cost: ~6 tool calls (check-ignore, read .gitignore, edit, re-check, restructure symlinks, re-verify) over ~5 minutes.
- Category: ENV/TOOLING
- Evidence: `git check-ignore -v data/README.md` → `.gitignore:1:data/  data/README.md`; `hint: Use -f if you really want to add them`; agent comment "NOTE: `data/*` + negation, not `data/`..."
- What in the issue/prompt would have prevented it: the preamble said "data/ is gitignored and shared... ln -s .../data data" as a single symlink — it didn't flag that a *tracked* file needs to live inside `data/` too (`data/README.md` per the issue), which requires both a different `.gitignore` pattern and a different (per-subdir) symlink layout. Worth stating explicitly since this is a repo-wide gotcha every future issue that writes into `data/` will re-hit.

### F3: real ingest run needed to be re-run twice, and VTPAN thresholds only matched published numbers via a bounded lead-directed sweep — after the PR was already open
- When: [21:59]–[22:07] (turn ~205 to end of transcript)
- What the agent was trying to do: after building the real data, verify VTPAN-filtered counts against Villatoro-Tello's published numbers (this was explicitly listed as one of the issue's "ACTUALLY RUN" deliverables).
- What it assumed / where it looked: implemented the VTPAN filter directly from PLAN.md's frozen S1 spec (2 participants, ≥6 msgs/participant, no ≥20-byte non-ASCII run) and, on finding a 20–32% overshoot vs. published counts, concluded (correctly, per its own report) that the frozen rule "applied correctly" just produces a gap — flagged it in the PR/report rather than silently deviating, and moved on to opening the PR.
- What was actually true: the team lead (informed by issue #6's worker cross-checking the same CSVs) wanted a bounded empirical search over rule variants (msgs-per-user vs. per-predator-only, "intervention" = message vs. turn, non-ASCII run length 10 vs 20 vs 30, etc.) against the two source papers (`villatoro2012.txt`, `w13_1607.txt`) to land within ±10% of published, and said so explicitly only *after* the worker had already reported "done" and opened PR #18.
- Cost: full re-implementation of the junk-run rule, re-run of `pan12_to_csv` (~60s) + `build-index --fresh` (~57s, rebuilding ~3GB of parot indexes) on both splits, re-running tier0/tier1 tests, and rewriting `data/README.md`'s "known gap" section — roughly 30+ tool calls, ~8 minutes of wall clock, much of it after the PR was already open (later amended via a PR comment: "Pushed the VTPAN junk-rule reconstruction... chosen rule = any non-ASCII byte OR ≥9 identical chars").
- Category: SPEC-AMBIGUITY / ACCEPTANCE-UNCLEAR, LEAD-CORRECTION
- Evidence: lead: *"vtpan_keep is looser than Villatoro-Tello... spend a bounded pass on the two suspects... Don't block on exact parity; ±10% is acceptable."*; agent's earlier own report: *"Real finding: VTPAN-filtered ... run ~20-32% over ... Diagnosed and documented (not a bug — the frozen S1 rule itself, applied correctly, produces this gap) — flagged to the team lead for a decision rather than silently deviating."*
- What in the issue/prompt would have prevented it: the issue/preamble treated "VTPAN filtered counts vs Villatoro-Tello's" as a report-only metric ("report the published-count assertions passing, VTPAN filtered counts vs Villatoro-Tello's"). It should instead have stated the acceptance bar up front — e.g. "vtpan_keep counts must land within ±10% of Villatoro-Tello's published 15,330/25,120/222 (test) and 6,588/11,038/136 (train); if the literal PLAN.md S1 rule doesn't land there, do a bounded (≤20 min) empirical sweep over the ambiguous knobs — msgs-per-user vs per-predator, non-ASCII run threshold — against `villatoro2012.txt`/`w13_1607.txt` *before* opening the PR, and document the chosen variant + residual gap in data/README.md." Giving the ±10% bar and the two source-paper paths in the *first* dispatch (not a follow-up correction) would have let the worker do this once, before the PR, instead of twice.

## What went smoothly because the prompt/issue supplied it
- Exact real-data paths and structure ("data/raw/pan12.zip (91 MB; two inner zips; training XML 170 MB... use lxml iterparse with element clearing") → the agent wrote a streaming parser correctly on the first attempt with no memory/perf surprises; no time spent discovering the file layout.
- Exact XML/schema shape (`<conversation id>`, `<message line>`, `<author>`, `<time>`, `<text>`) and predator-file names/formats (`problem1.txt` 254 ids, `problem2.txt` 6,478 `conv_id<TAB>line` rows) given up front → the agent spent zero time reverse-engineering the corpus format; one bounded `unzip -l`/`zipfile` probe just to sanity check names against the description.
- "Look at `../parot-bias/corpus_build/` (bounded: build script and paths.json writer) and its justfile `build` recipe for exact `parot build` flags" → the agent reused the reference implementation directly instead of guessing `parot build` flags/container shapes; `build_indexes` worked against the real daemon (`statskit.Corpus`) on the first successful attempt.
- Explicit file-ownership list + "owned recipe bodies only" → no cross-worktree file conflicts; `git status --porcelain` diffs stayed exactly within the owned set (plus the two flagged collateral edits, both called out).
- Preamble's exact worktree-setup commands (fetch/worktree add/symlink data/uv sync/import smoke test) → setup took ~2 minutes with zero missteps.
- Text-normalization rules stated explicitly (CRLF→LF, empty `<text/>` kept as empty string, RFC-4180 quoting, row order) → tier0 tests against the fixture passed on the first write of `ingest.py`, no schema back-and-forth.
- "Any skip must be VISIBLE" / fail-loud culture already baked into the harness (queue-blocking, pipe-blocking guards) caught two potentially-silent failure modes automatically (piped test output masking exit code; unqueued heavy job thrashing the shared box) — cost a couple of retries but no wrong-but-plausible result got through.

## Generalizable lessons (≤8 bullets)
1. When an issue asks the worker to reproduce a published/reference number, state the acceptance tolerance (e.g. "±10%") and the reconciliation method ("bounded sweep over these N named variants, against these source files") in the *original* dispatch — don't leave it as a "report the delta" ask that turns into a second, PR-reopening round trip once someone else's worker cross-checks the number.
2. If any owned file must be a *tracked* file living inside an otherwise-gitignored shared directory (e.g. `data/README.md` inside `data/`), say so explicitly and give the working `.gitignore` pattern (`data/*` + `!data/README.md`, not `data/` + negation) — this is a generic git gotcha every future issue writing into a blanket-ignored dir will re-hit.
3. When multiple real filenames could share a substring your code will grep for (e.g. "predator" matching both the ids file and a `-diff.txt` sibling), name the exact distinguishing substring/plural to match on, not just an example filename.
4. Keep report-only "run it on real data and tell us the numbers" asks separate from pass/fail gates — if the numbers matter enough to gate the PR, say so up front so the worker doesn't ship, get told to redo it, and reship.
5. Precise low-level format facts (byte-for-byte parse rules, exact schema, reference build script location) up front eliminate almost all exploratory friction — this dispatch is a strong template to reuse.
6. Environment-level guardrails (queue-required heavy jobs, no-pipe-a-test-run) will cost 1–2 retries per session even when the worker does nothing wrong; that's expected overhead, not a prompt defect — no action needed there.
7. When a frozen spec (PLAN.md S1) is applied literally and produces an out-of-tolerance real-world result, a worker correctly stops and reports rather than silently deviating — reward/preserve that behavior in future prompts rather than treating the report as the end of the task; explicitly say whether "flag and stop" or "flag and try bounded alternatives" is wanted.
8. If a later worker (e.g. issue #6) will cross-check this worker's real-data output, sequence that cross-check *before* the first PR is opened, or tell this worker to expect a possible follow-up correction — reduces perceived rework/backtrack even though the total work was the same.

## Stats
- Friction events by category: DATA-SHAPE/SCHEMA: 1, ENV/TOOLING: 1, SPEC-AMBIGUITY/ACCEPTANCE-UNCLEAR: 1 (also LEAD-CORRECTION), LEAD-CORRECTION: 1 (same event as above, double-tagged)
- Rough share of session spent on friction vs productive work: ~25% friction (mostly F3's post-PR VTPAN rework), ~75% productive (first-pass implementation, real-data runs, tests, PR mechanics went smoothly)
