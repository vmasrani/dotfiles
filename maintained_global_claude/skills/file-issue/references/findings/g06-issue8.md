# Issue #8 — session 8b55d045-da6e-415c-9f49-afa79485514e

Session overview: Issue #8 "app: port Bias Radar UI to flagged authors / conversation reader / receipts"
— port `../parot-bias/app` (FastAPI server/engine/translate/static) to the predatory-chat domain: tier-1
flagged-authors rail, tier-2 conversation reader, tier-3 term receipts, 4 endpoints, jargon boundary,
mock-engine dev mode, safety banner. 21:29:56 → 21:54:52 (~25 min wall clock), 127 tool calls. Finished
clean: PR #15 opened (issue-8-app → dev), commit aaec759, 77 tests passed / 1 honestly skipped, ruff +
ty all green, live-curled every endpoint including 404 and self-match-exclusion paths before shipping.
Zero team-lead interventions after the single dispatch message; zero user corrections. This was close to
a textbook one-shot.

## Friction events (one block each, chronological)

### F1: `app/` package name collides with sibling `../parot-bias/app/`, silently shadowed by namespace-package resolution
- When: [21:39–21:40] (turn ~35, tool calls ~95–108)
- What the agent was trying to do: smoke-test its newly-written `app/engine_mock.py` with
  `from app import engine_mock as em` before building the rest of the app on top of it.
- What it assumed / where it looked: assumed the local `app/` directory it had just started writing files
  into would resolve as the `app` package. When the import failed, it first suspected a `sys.path` /
  pyproject packaging issue (checked `pyproject.toml`, `packages`/`target`/`module` config in
  `../parot-bias/pyproject.toml`, tried `sys.path.insert(0, '.')`) — two dead-end probes before finding
  the real cause.
- What was actually true: `../parot-bias` is editable-installed into the same venv and ships its own
  regular package at `app/__init__.py`. The new worktree's `app/` had no `__init__.py` yet (only
  `translate.py` and `engine_mock.py` existed at that point), so Python treated it as an implicit
  namespace-package portion and import resolution picked `parot-bias`'s real `app` package instead —
  silently, no error until a name (`engine_mock`) that only exists locally was requested.
- Cost: ~6 tool calls / ~90 seconds before recovery (fast because the agent reasoned it out rather than
  guessing further).
- Category: FALSE-ASSUMPTION-ABOUT-CODE (env/packaging edge case)
- Evidence:
  - `ImportError: cannot import name 'engine_mock' from 'app' (/Volumes/external/dev/fsa/parot-bias/app/__init__.py)`
  - "Found it — our `app/` lacks `__init__.py`, so Python skips it as a namespace portion and finds
    parot-bias's regular `app` package instead."
  - Agent's own final report to lead: "Found+fixed one gotcha not in the brief: ../parot-bias is
    editable-installed and ships its own app/ dir at repo root — without app/__init__.py ours is a
    namespace portion and import resolution silently picks parot-bias's app.server instead."
- What in the issue/prompt would have prevented it: one sentence in the shared preamble or issue #8 body:
  "Create `app/__init__.py` FIRST, before any other file under `app/` — `../parot-bias` is
  editable-installed and also ships a top-level `app/` package; without `__init__.py` your `app/` is an
  implicit namespace package and imports silently resolve to parot-bias's `app` instead." This is a
  structural landmine for *any* wave-1 issue that creates a directory sharing a name with a sibling repo's
  package (the brief's REUSE section names `biaskit`/`statskit`/`parot` as importable siblings but doesn't
  flag that `parot-bias` also owns the bare name `app`).

## What went smoothly because the prompt/issue supplied it
- Shared preamble gave the exact worktree-creation command (`git worktree add ... -b issue-8-app origin/dev`)
  and noted sibling symlinks already exist → zero time spent figuring out the multi-repo dependency layout.
- Preamble named `data/` as gitignored+shared and gave the exact symlink command → no confusion about
  why fixture/data paths were missing, no accidental attempt to commit `data/`.
- Preamble explicitly said "PLAN.md ... S1–S6 are FROZEN seams, do not change them" and "REUSE, don't
  rewrite: `biaskit`... `statskit`..." → agent never touched those modules, went straight to reading only
  the functions it needed.
- `csekit/*.py` docstrings carry `"""... Owning issue: #N."""` (score.py→#5, lines.py→#6, receipts.py→#7,
  lexicon.py→#4) → the agent instantly knew which stubs belonged to sibling in-flight issues and coded
  against their S4 signatures + fixture data instead of trying to implement or debug them itself.
- Pre-existing `*-context.md` files in the reference app (`app/app-context.md`, `tests/tests-context.md`,
  `static/static-context.md`) gave a one-screen map of the source app before any full-file reads →
  the agent read exactly the right 6 source files once each, no exploratory `ls`/`fd` thrashing.
- Issue #8 body itself was unusually concrete: exact tier breakdown (rail/reader/receipts), exact 4
  endpoint names, exact jargon-boundary rule with example banned terms, explicit mock-engine-until-#3/#5/#6
  instruction, explicit "Parallel-safe: owns `app/`, `app/tests/`" — the agent never had to guess scope,
  ask "what does done look like", or worry about touching another issue's files.
- Preamble's GATES section gave the exact command line (`ruff format/check`, `ty check`, `pytest tests/tier0`)
  and explicitly said NOT to run `just ci-deep` → no wasted time running or debugging the slow gate.
- Preamble's SHIP section gave the exact `gh pr create` invocation and forbade `Co-Authored-By` / merging →
  PR mechanics were one shot, no back-and-forth.

## Generalizable lessons
1. When a ported subdirectory will share a name with a package already on `sys.path` from a sibling
   editable-installed repo (here: two repos each with `app/`), say so explicitly and tell the worker to
   create `__init__.py` before any other file in that directory — namespace-package shadowing fails
   silently and doesn't surface until the *first* locally-unique name is imported.
2. Tag stub modules with `"""... Owning issue: #N."""` docstrings when multiple issues in a wave touch
   related modules — it lets a consuming issue's agent instantly distinguish "stub I code against" from
   "thing I'm responsible for," with zero extra prompting.
3. Maintain `*-context.md` sidecar files in code being ported/referenced — they cut exploratory reads to
   near zero for an agent that needs to understand an unfamiliar reference implementation fast.
4. A dispatch preamble shared across a whole wave of issues (worktree command, symlink command, gate
   command, PR command, all verbatim and copy-pasteable) eliminates almost all process/mechanics friction;
   write it once per wave, not per issue.
5. State the tier/endpoint/jargon-boundary contract in the issue body as a literal checklist (tier names,
   exact endpoint paths, exact banned-term category, mock-vs-live engine switch) rather than a prose
   description — it removed every scope/acceptance ambiguity for this session.
6. Explicitly forbid the slow gate (`just ci-deep`) and name the fast one — prevents a worker from either
   guessing which gate to run or wastefully running the exhaustive one.
7. When ported code carries over patterns a stricter local type-checker will flag (e.g. `.itertuples()`
   yields untyped `NamedTuple`s that `ty` can't attribute-check), a one-line heads-up ("expect ~dozens of
   `ty` unresolved-attribute errors from itertuples; give rows a typed NamedTuple/dataclass instead") would
   save the routine but non-trivial cleanup pass this session had to do unprompted.

## Stats
- Friction events by category: FALSE-ASSUMPTION-ABOUT-CODE: 1
- (ty-check cleanup, ~10 edits over ~3 min, was routine gate-satisfying work with no wrong belief or
  backtrack, so it is not counted as a friction event per the brief's threshold — noted only as lesson 7.)
- Rough share of session spent on friction vs productive work: ~10–15% (one ~90s detour + a few dead-end
  packaging probes, inside a ~25 min session); the remaining ~85–90% was linear context-reading,
  writing, and gate-verification with no backtracking.
