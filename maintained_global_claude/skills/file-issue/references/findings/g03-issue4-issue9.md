# Issue #4 & Issue #9 — sessions 6eb6ceec-cb14-4a73-a049-09db1cde81e4 (PR #17) & 2d6abadd-69d4-4dd1-9461-d5602e14e3a2 (PR #16)

Both sessions were smooth, self-contained, one-shot implementations of related `csekit` features (a Fightin' Words lexicon
mined from PAN12, and a per-stage variant of the same technique). Neither needed a lead or user correction mid-session.
Friction was entirely self-diagnosed/self-resolved, and — notably — issue #9 hit almost the exact same shipped-helper
gotcha (`biaskit.min_monotone_prior` / `fw_z_monotone`'s non-obvious argument-order/balance assumption) that issue #4 hit
independently a few minutes earlier in wall-clock time, because the discovery from #4 was never pushed back into the
shared helper's docstring before #9's worker ran into its own variant of it. That's the single biggest cross-issue lesson.

---

## Issue #4 (session 6eb6ceec-cb14-4a73-a049-09db1cde81e4, PR #17)
Session overview: implement `csekit.lexicon` — mine a Fightin' Words grooming-vs-benign contrast lexicon from PAN12 (`mine_lexicon`), load it (`load_lexicon`), and build the intent-vs-register confound tripwire (`confound_report`), plus `scripts/mine_lexicon.py` and tier0/tier1 tests, per issue #4 / PLAN.md S3. Ran 21:29:06 → 21:58:33 (~29 min wall clock), ~84 tool calls. Finished cleanly: real PAN12 train mine ran, report committed, PR #17 opened against `dev`, all local gates green (`ruff format`/`ruff check`/`ty check`/tier0+tier1 pytest). Zero lead interventions mid-session (the team-lead's only message was the initial dispatch); zero user corrections. This was a smooth, self-contained one-shot session — the friction below is all self-diagnosed and self-resolved, not lead/user-corrected.

### Friction events (one block each, chronological)

#### F1: Reference-repo exploration commands run from the wrong cwd
- When: [21:29:55]–[21:30:11] (turn ~13–17)
- What the agent was trying to do: read `src/tokenization.py` and `assoc_stats.g2_cell` from the reference repo `parot-bias`/`parot-stats` while sitting in the `csekit` (parot-cse) worktree, then ran `uv sync` right after.
- What it assumed / where it looked: assumed the previous `cd` (into `parot-bias` for `fightin_words.py`) was still the cwd, or conversely ran `uv sync` while still cd'd into `parot-bias` instead of the `parot-cse` worktree.
- What was actually true: `tokenization.py` doesn't exist under `parot-cse`; `uv sync` in `parot-bias` hit a real dependency conflict (`parot` resolved both as a local editable path and a git+ssh ref) that had nothing to do with the actual task — it was just the wrong project's lockfile.
- Cost: ~2 tool calls before recovery (one failed `cat`, one failed `uv sync`, then correct re-run in the worktree).
- Category: WRONG-PATH
- Evidence: `"Exit code 1\ncat: src/tokenization.py: No such file or directory"`; `"Failed to resolve dependencies for parot-stats ... conflicting URLs for package parot"`
- What in the issue/prompt would have prevented it: nothing issue-level — this is normal multi-repo cwd bookkeeping. A one-line reminder in the dispatch preamble ("re-`cd` into your worktree before every `uv`/`git` command — reference repos are read-only side trips") would have caught it a step earlier, though the cost here was trivial.

#### F2: Shipped `biaskit.min_monotone_prior`/`fw_z_monotone` silently assumes a balanced 50/50 corpus and fails on PAN12's real imbalance
- When: [21:42:43]–[21:44:40] (turn ~74–84)
- What the agent was trying to do: satisfy the issue's explicit requirement — "the monotone-prior regression from parot-bias must hold: |z| largest for never-said terms" — by calling the shipped `biaskit.min_monotone_prior` at the live PAN12 slice shape.
- What it assumed / where it looked: assumed (per the issue's own wording, which treats this as a given inherited property) that the shipped `min_monotone_prior`/`fw_z_monotone` from `parot-bias` would just work at any NL/NR/N shape; wrote the tier0 kernel tests against that assumption first.
- What was actually true: `fw_z_monotone`'s gate walks `aL` from `tot // 2` down to `0`, i.e. it defines "no separation" as the 50/50 point — true only when `NL == NR`. PAN12 is ~1:8.5 predator:benign in this session's slice (and far worse, ~1:30, at full scale). On any meaningfully imbalanced shape (200/800/1000, 400/600/1000, 2000/8000/10000, and all PAN12-like shapes) `min_monotone_prior` raises `ValueError: no monotone prior ≤ hi` — not a bug in the corpus, a mis-parameterized gate. The agent had to write two throwaway probe scripts (`/tmp/probe_mono.py` etc.) sweeping shapes to isolate this, then implement a local `z_monotone_in_support`/`min_monotone_prior_for_shape` that reduces to the shipped answer on balanced data but actually works on imbalanced data.
- Cost: ~10 tool calls / ~2 minutes wall clock (test failure → single-test rerun → probe script #1 → probe script #2 with corrected parameterization → source patch → docstring fix → re-run).
- Category: FALSE-ASSUMPTION-ABOUT-CODE / DATA-SHAPE
- Evidence: `"ValueError: no monotone prior ≤ 100000000 at NL=200 NR=800 N=1000 — the Woolf variance cannot be stabilized at this corpus shape"`; probe output `"(200, 800, 1000) mine -> 177  shipped -> NONE"`; own code comment `"The failure is the GATE's parameterisation, not the corpus."`
- What in the issue/prompt would have prevented it: state PAN12's actual predator:benign imbalance ratio in the issue (e.g. "~1:8 in this session's train slice, ~1:30 at full scale") next to the monotone-prior requirement, and flag explicitly that `biaskit.fw_z_monotone`'s gate assumes `NL≈NR` and is known to fail on imbalanced slices — i.e. tell the implementer up front that they'll need an imbalance-aware substitute for `min_monotone_prior`, not just "the regression must hold."

#### F3: Generic sklearn `ENGLISH_STOP_WORDS` silently strips real grooming-signal terms
- When: [21:46:43]–[21:48:24] (turn ~98–104)
- What the agent was trying to do: get `mine_lexicon` to admit the planted grooming signal terms (`pic`, `meetup`, `alone`) in its own synthetic-mine test.
- What it assumed / where it looked: initially screened candidate terms the way `parot-bias` does it (via a generic English stopword list), matching the issue's instruction to "replace `ATTRIBUTION_VERBS` with a chat-scaffolding stoplist."
- What was actually true: `sklearn.feature_extraction.text.ENGLISH_STOP_WORDS` contains ordinary-looking words that are actually load-bearing grooming signal in this domain — `alone`, `call`, `front`, `interest`, `keep`, `never`, `please`, etc. — so a generic stopword screen silently deleted the exact terms the tripwire exists to catch. The agent had to probe sklearn's list, confirm the overlap, and replace the screen with a syntactic closed-class function-word filter (determiners/pronouns/prepositions/etc.) instead of a generic content-word list.
- Cost: ~6 tool calls / ~1.5 minutes (failing assertion → real-index repro script → sklearn overlap probe → screen_terms rewrite → verify).
- Category: MISSING-DOMAIN-CONTEXT
- Evidence: `"assert {'alone', 'meetup', 'pic'} <= admitted"` failing; `"IN sklearn: ['alone', ..., 'call', ..., 'front', ..., 'interest', 'keep', 'never', 'please', ...]"`
- What in the issue/prompt would have prevented it: the issue already correctly anticipated a custom stoplist was needed ("keep short, document why each is scaffolding not intent") but didn't warn that the *generic* stopword approach (what `parot-bias` uses) is actively dangerous here because ordinary English function/content words carry grooming signal. One sentence — "do not reuse a generic English stopword list (sklearn or otherwise): several such words (alone, call, please, never...) are grooming signal in this corpus" — would have let the agent design the closed-class screen on the first pass instead of discovering it via a failing assertion.

#### F4: `ty` (static type checker) can't resolve a `scripts/` entry-point script imported at runtime via `sys.path`
- When: [21:52:53]–[21:55:11] (turn ~129–135)
- What the agent was trying to do: write a tier0 test that imports `scripts/mine_lexicon.py` (a `uv run --script` entry point, not a package) to test its report-writing logic.
- What it assumed / where it looked: assumed a normal `sys.path.insert(...); import mine_lexicon` would satisfy both pytest at runtime and the repo's `ty check` gate.
- What was actually true: `ty` does static module resolution and doesn't see the runtime `sys.path` mutation, so it reported `unresolved-import` and failed the gate. Fix: load the script by file path via `importlib.util.spec_from_file_location`/`module_from_spec` instead of a `sys.path` import.
- Cost: ~3 tool calls / ~2 minutes (ty failure → diagnostic → rewrite to importlib-by-path → full re-run).
- Category: ENV/TOOLING
- Evidence: `"error[unresolved-import]: Cannot resolve imported module mine_lexicon"`
- What in the issue/prompt would have prevented it: a repo-level (not issue-specific) convention note — "files under `scripts/` are `uv run --script` entry points, not importable packages; tests that need to exercise one must load it via `importlib.util.spec_from_file_location`, not `sys.path` + `import`, or `ty check` will fail" — belongs in the shared preamble/CLAUDE.md rather than being rediscovered per-issue, since any future test against a `scripts/*.py` file will hit this again.

### What went smoothly because the prompt/issue supplied it
- Team-lead preamble named the exact read-first sequence (`gh issue view`, `PLAN.md` whole file, the stub signature, `tests/fixtures/pan12_mini/`) -> agent went straight to spec/fixtures with zero wasted search, no `fd`/`rg` hunting for "where is the spec."
- Preamble gave the exact worktree-creation command, the sibling-symlink convention for cross-repo deps, and the `ln -s .../data data` step -> `uv sync` + daemon-backed tests worked on the first real attempt inside the worktree.
- Preamble named which functions to reuse from which files (`biaskit.candidate_vocab`, `fightin_words.py`, `statskit.Corpus` tf/df/occ/kwic/where_) -> agent read exactly those files instead of surveying the whole reference repo.
- Issue enumerated the concrete API contract (`mine_lexicon(split=, filtered=, negatives=)`, sign convention, `confound_report` columns, output paths `data/lexicon/grooming_lexicon.parquet` + `reports/lexicon-<sha>.md`) -> zero ambiguity about function signatures or where artifacts should land.
- Issue named the exact differences from `parot-bias` to implement (no capitalisation filter, chat-scaffolding stoplist, `negatives="two_party"` semantics) -> agent didn't have to reverse-engineer what should differ from the ported code.
- Preamble's "FAIL LOUD" / narrow-gate instructions (`ruff format`/`ruff check`/`ty check` + `pytest tests/tier0` only, don't run `ci-deep`) -> agent never wasted time running or waiting on the slow full gate; it used `run_in_background` correctly for the one genuinely slow step (the real PAN12 mine).
- Preamble's exact commit/PR/report format (no Co-Authored-By, `gh pr create --body-file`, ≤12-line report) -> shipping mechanics were friction-free, one clean push+PR at the end.

### Generalizable lessons for issue #4
- When an issue requires a re-used statistical/algorithmic gate to "hold" (e.g. a monotone-prior invariant), state the actual data shape it will be evaluated against (imbalance ratio, size) next to the requirement — shipped helper functions ported from a different corpus often bake in an implicit balanced-data assumption that silently breaks.
- Never tell an implementer to build a "custom stoplist" without also naming which off-the-shelf stopword source is unsafe here and why — generic function-word lists can delete the exact signal words a detection task depends on.
- Repo-wide tooling gotchas (e.g. `ty check` can't see `sys.path` runtime imports of `scripts/*.py` entry points) belong in the shared preamble/CLAUDE.md once discovered, not re-derived by every future issue that touches `scripts/`.
- A team-lead preamble that front-loads read-order, worktree setup, reuse targets, gate scope, and ship format (as this one did) produces a near-zero-friction one-shot session — this dispatch prompt is a good template to reuse verbatim for future issues.

### Stats for issue #4
- Friction events by category: WRONG-PATH: 1, FALSE-ASSUMPTION-ABOUT-CODE/DATA-SHAPE: 1, MISSING-DOMAIN-CONTEXT: 1, ENV/TOOLING: 1
- Rough share of session spent on friction vs productive work: ~15% friction (≈21 of ~84 tool calls across the 4 events), ~85% productive (spec reading, implementation, test authoring, real-data mine, PR mechanics)

---

## Issue #9 (session 2d6abadd-69d4-4dd1-9461-d5602e14e3a2, PR #16)
Session overview: issue asked for `csekit.stages` — a stage lexicon for PAN12-only grooming-stage detection (flagged-line, position, and LCT-seed views), each mined via Fightin' Words each-vs-rest, plus a cross-view confound report, PLAN.md updates, and a real-data report if `data/pan12/` existed. Wall clock 21:32:40 -> 21:55:54 (~23 min). ~61 tool calls. Finished cleanly: committed, pushed, PR #16 opened and later merged into dev (issue #9 closed with "Landed in dev via PR #16, wave 1 merged 2026-08-21"). Zero mid-session lead interventions — the team-lead sent exactly one dispatch message at the start and received exactly one "done" report at the end; no corrections, no back-and-forth, no AskUserQuestion.

### Friction events (one block each, chronological)

#### F1: `biaskit.min_monotone_prior` / `fw_z_monotone` argument-order (orientation) quirk had to be reverse-engineered by probing
- When: [21:43:30]-[21:45:08] (turn ~40-45, mid-implementation)
- What the agent was trying to do: derive the informative Dirichlet prior for each-vs-rest Fightin' Words contrasts inside `csekit/stages.py`, using `biaskit.min_monotone_prior(NL, NR, N, hi=...)` exactly as issue #4's `fightin_words.py`/`lexicon.py` do.
- What it assumed / where it looked: assumed `min_monotone_prior(NL, NR, N)` would behave symmetrically regardless of which slice (positive/negative) was passed first, and that a single fixed `hi` bound would work across pool shapes. It probed with several `(NL, NR, N)` shapes and `hi` values (1,000,000 then 200,000 then a self-written `derive()` helper trying both orderings) before finding the pattern.
- What was actually true: `fw_z_monotone` sweeps the LEFT slice's df down to 0 and the RIGHT's up to the term total — i.e. it only probes "a term only the RIGHT slice says." Each-vs-rest always puts the smaller slice on the positive side, so the correct call is with the LARGER slice passed first (verified: `min_monotone_prior(43, 77, 120)` raises, `(77, 43, 120)` returns 48 — same pool, opposite argument order). This orientation requirement is NOT documented in `fightin_words.py`'s docstrings (confirmed by reading them — they explain the size-dependence of the prior at length but never mention argument order/orientation).
- Cost: ~4 tool calls of probing (21:43:30, 21:43:48, 21:44:38 exploratory shape sweeps, then 21:45:06 to patch `stages.py` with a `_derive_prior` helper + `MIN_POOL=60` guard) — roughly 2 minutes of wall clock, plus it produced a whole new helper function and a doctrine comment to encode the discovery.
- Category: MISSING-DOMAIN-CONTEXT / FALSE-ASSUMPTION-ABOUT-CODE
- Evidence: `"(43, 77, 120) RAISED"` vs `"(77, 43, 120) 48"` (from the probe output); PR body itself: *"`biaskit.min_monotone_prior` had to be probed with the **larger** slice first... Un-mirrored, every each-vs-rest contrast in this module would be rejected."*
- What in the issue/prompt would have prevented it: a one-line note in the dispatch prompt or in `fightin_words.py`'s own docstring: "`min_monotone_prior`/`fw_z_monotone` are NOT symmetric in `(NL, NR)` — always pass the larger slice first; each-vs-rest puts the smaller (positive) slice second." Since issue #4 (which the dispatch prompt pointed at as "reuse exactly as #4 does") presumably used a 2-class, not each-vs-rest, contrast and may never have hit this, the team lead could not have known — but once #9 discovered it, this belongs back in `fightin_words.py`'s docstring for future each-vs-rest consumers (issue #6, #8 etc. may hit the same wall).

#### F2: ChatCoder/Kontostathis source PDFs 404'd on first fetch, required a web.archive.org fallback
- When: [21:34:22]-[21:34:48] (turn ~18-20)
- What the agent was trying to do: fetch the earlier ChatCoder papers (`ICASubmissionLuringLanguage.pdf`, `TextMining2009BookChapter.pdf`) from `webpages.ursinus.edu/akontostathis/...` as the dispatch prompt suggested ("if reachable").
- What it assumed / where it looked: tried the direct ursinus.edu URLs first.
- What was actually true: the ursinus.edu host is dead (curl exit 6 "cannot open", then HTTP/2 404 on the fallback host guess); had to be fetched via `web.archive.org/web/2018/http://...` instead.
- Cost: 2 tool calls (one failed fetch attempt across 3 URLs, one archive.org retry that succeeded) — under a minute, low severity since the dispatch prompt already hedged with "if reachable."
- Category: ENV/TOOLING
- Evidence: `"ICASubmissionLuringLanguage.pdf rc=6 cannot open..."`, `"HTTP/2 404"`, then successful archive.org fetch.
- What in the issue/prompt would have prevented it: naming the archive.org fallback directly in the dispatch prompt (`webpages.ursinus.edu` is known dead; use `web.archive.org/web/2018/http://webpages.ursinus.edu/akontostathis/<name>.pdf`), since the team lead or a prior session presumably already knows this host is gone.

#### F3: `ty check` (type checker) errors from pandas `groupby`/`itertuples` idioms — routine but real detour
- When: [21:51:12]-[21:51:45] (turn ~55-57, gate-running phase)
- What the agent was trying to do: pass the `uv run ty check .` gate after finishing the module and tests.
- What it assumed / where it looked: wrote `for (stage, fold), part in lexicon.groupby([...])` and `for row in robust.itertuples(): row.views` — idiomatic pandas that `ty` (a static type checker) cannot narrow (`Hashable` not iterable / `tuple[Any,...]` has no attribute).
- What was actually true: `ty` needs `.groupby(...)` keys destructured differently and `.itertuples()` replaced with `.to_dict("records")` to keep static types resolvable.
- Cost: 3 tool calls (list errors, inspect one, patch both files) — a few minutes, essentially routine gate-passing, not a wrong belief so much as an unavoidable static-analysis friction with this codebase's stricter-than-usual type checker.
- Category: ENV/TOOLING
- Evidence: `"error[not-iterable]: Object of type 'Hashable' is not iterable"`, `"error[unresolved-attribute]: Object of type 'tuple[Any, ...]' has no attribute 'views'"`.
- What in the issue/prompt would have prevented it: a repo-level note (CLAUDE.md or PLAN.md) that `ty check` doesn't narrow `DataFrame.groupby()` tuple-unpacking or `.itertuples()` attribute access — prefer `.to_dict("records")` / explicit column access. This would save every future stages-like worker the same 3-call detour.

### What went smoothly because the prompt/issue supplied it
- Exact reuse targets named with full paths (`/Volumes/external/dev/fsa/parot-bias/src/fightin_words.py`, `src/lexicon.py`'s `vetted_lexicon`, `src/stats.py`) -> agent went straight to reading those 4 files instead of searching for "how did #4 do this."
- File ownership boundary stated explicitly ("do not edit csekit/lexicon.py, which issue #4 owns") -> no risk of a merge conflict or scope creep into another issue's files.
- Fallback data source given concretely (`tests/fixtures/pan12_mini/mini.csv` with exact column/label facts: "test split has line_is_predatory labels and two predator authors") -> agent didn't have to discover the fixture's shape by trial and error; it did confirm column names/row counts but that was verification, not discovery.
- Explicit go/no-go on scope ("Optional, needs explicit go-ahead... Not started") -> agent correctly did not attempt the LLM-synthetic-validation-set stretch goal, no wasted effort.
- Told upfront that ChatCoder2 is unavailable and why ("decision 2026-08-20") -> agent didn't waste any tool calls trying to locate/download ChatCoder2 itself; went straight to public ChatCoder *papers* as instructed.
- Precise column/semantics spec ("stage parquets carry `stage`, `view`, `fold`"; fold semantics: "fold=k mined on the other K-1 folds") -> no ambiguity in output schema, single pass implementation.
- PDF-extraction command pattern handed over verbatim (`uv run --with pypdf python -c ...`, bounded) -> zero time spent picking a PDF library or figuring out the invocation.
- Real-data conditional branch spelled out ("If real data exists ... RUN scripts/mine_stages.py ... Else stop at fixtures and say so") -> agent didn't have to guess whether to attempt real-data mining; it checked `data/pan12/` existence and proceeded correctly.

### Generalizable lessons for issue #9
- When a dispatch prompt says "reuse X exactly as issue #N does," and the new issue's usage pattern differs from #N's (here: each-vs-rest vs 2-class), call out that the shared helper's non-obvious invariants (argument order/orientation, symmetry assumptions) may not have been exercised by #N and should be verified empirically rather than assumed transitive.
- Push safety-critical / orientation-sensitive helper functions (like `min_monotone_prior`) to document their non-symmetric argument contract directly in the docstring the moment it's discovered — the fix belongs upstream (parot-bias) so every future consumer inherits it for free instead of re-discovering it.
- When a dispatch prompt points to an external URL as a data/paper source, if it's already known to be dead/moved, give the working replacement (e.g. the archive.org path) instead of "if reachable" — saves a guaranteed-fail probe.
- Document repo-wide static-analysis idiom gotchas (e.g. "`ty` can't narrow pandas groupby-tuple-unpack or `.itertuples()`; use `.to_dict('records')`") once, centrally, rather than letting every worker rediscover it.
- This issue is a model example of a well-scoped dispatch: exact owned files, exact reuse targets with paths, exact fixture facts, explicit optional-scope fencing, and an explicit conditional branch for the "real data present vs not" case — reproduce this level of specificity for future issues.

### Stats for issue #9
- Friction events by category: MISSING-DOMAIN-CONTEXT/FALSE-ASSUMPTION-ABOUT-CODE: 1 (F1); ENV/TOOLING: 2 (F2, F3). LEAD-CORRECTION: 0. USER-CORRECTION: 0. SPEC-AMBIGUITY: 0. SCOPE-CREEP/UNDER-SCOPE: 0.
- Rough share of session spent on friction vs productive work: ~15% friction (roughly 3-4 min of the ~23 min session across F1-F3), ~85% productive (research reading, writing stages.py/lct_seeds.py/mine_stages.py/tests, running gates, real-data report, PR).

---

## Generalizable lessons across both issues (≤8 bullets, imperative)
1. **Ported statistical helpers carry hidden invariants — state the invariant, not just "it must hold."** `biaskit.min_monotone_prior`/`fw_z_monotone` assumes `NL≈NR` (issue #4: fails outright on PAN12's real class imbalance) and is non-symmetric in argument order (issue #9: raises unless the larger slice is passed first). Neither is documented in the source. Name the actual data shape (imbalance ratio) and the argument-order contract in the dispatch prompt when telling a worker to reuse this function.
2. **The moment a worker discovers a shipped-helper gotcha, push the fix upstream into that helper's docstring before the next issue that reuses it runs** — issue #9 rediscovered a cousin of issue #4's `min_monotone_prior` problem independently, at nearly the same wall-clock time, because the discovery from #4 wasn't yet documented when #9 started. This is the single highest-leverage fix: a shared "gotchas learned" note (in `fightin_words.py`'s docstring or a repo CLAUDE.md) would have saved ~4-10 tool calls in the second session.
3. **Never ask for a "custom stoplist" or domain-specific filter without naming which generic/off-the-shelf source is unsafe and why** — sklearn's `ENGLISH_STOP_WORDS` silently deletes grooming-signal words (`alone`, `call`, `please`, `never`).
4. **Document repo-wide static-analysis tooling gotchas centrally, not per-issue**: `ty check` can't resolve `sys.path`-based imports of `scripts/*.py` entry points (use `importlib.util.spec_from_file_location`), and can't narrow `DataFrame.groupby()` tuple-unpacking or `.itertuples()` attribute access (use `.to_dict("records")`). Both were rediscovered from scratch in each session.
5. **When a dispatch prompt names an external URL as a data/paper source that's already known dead, give the working replacement (e.g. an archive.org path) instead of hedging with "if reachable"** — saves a guaranteed-fail probe.
6. **A team-lead preamble that front-loads exact read-order, worktree setup commands, exact reuse-target file paths, file-ownership boundaries between concurrent issues, exact API contracts/output paths, explicit optional-scope fencing, an explicit conditional branch for "data present vs not," and narrow gate scope produces near-zero-friction one-shot sessions** — both dispatch prompts here hit ~85% productive time and zero mid-session corrections; treat them as the standard template.
7. **State explicit file-ownership boundaries when two issues touch adjacent modules concurrently** (issue #9's prompt explicitly said "do not edit csekit/lexicon.py, which issue #4 owns") — this fully prevented any merge-conflict risk or scope creep, at zero cost.
8. **Reference-repo cwd bookkeeping (`cd` back into your own worktree before every uv/git command after a side-trip into a read-only reference repo) is a recurring trivial-cost trap** — worth one line in the standard preamble even though the cost per instance is low.

## Stats (combined)
- Friction events by category (both issues): WRONG-PATH: 1 · FALSE-ASSUMPTION-ABOUT-CODE/DATA-SHAPE: 2 (one balance-assumption, one argument-order) · MISSING-DOMAIN-CONTEXT: 2 (stoplist, argument-order overlap) · ENV/TOOLING: 3 (ty/scripts import, dead URL, ty/pandas idioms) · LEAD-CORRECTION: 0 · USER-CORRECTION: 0 · SPEC-AMBIGUITY: 0 · SCOPE-CREEP/UNDER-SCOPE: 0 · PROCESS: 0 · SCALE/RUNTIME: 0
  (7 total friction events across the two sessions; MISSING-DOMAIN-CONTEXT/FALSE-ASSUMPTION-ABOUT-CODE double-tagged where a finding genuinely spans both)
- Rough share of session spent on friction vs productive work: ~15% friction / ~85% productive in BOTH sessions independently — both finished cleanly with zero lead or user interventions and merged PRs.
