---
name: file-issue
description: File a GitHub issue that a fresh agent can implement in one shot — the filer scouts the repo ONCE and writes everything the implementer would otherwise have to discover (exact files/functions, seam contracts, acceptance numbers with tolerance, protocol with unit of derivation, scale/OOM classes, ownership + hot seams, blocked-on gates). Use whenever the user says /file-issue, "file an issue", "write this up as an issue", "turn this into an issue/epic", or before any `gh issue create` for work that will be implemented by another session. Also use to REWRITE a thin issue before /start-task dispatches it.
---

# /file-issue — issues an agent can implement without exploring

**The contract:** an implementing agent reads the issue body, `cd`s into its
worktree, and starts editing the right file within two minutes — no `rg`/`fd`
orientation, no "which function produces this number", no "is this file mine",
no "what does done look like", no mid-flight message from the lead. Every minute
of scouting the filer skips is paid back 5–50× by the implementer (and by the
lead who has to relay the missing fact to every sibling worker).

**Why these rules (evidence):** a post-mortem over 22 issue-implementing
sessions + 4 lead sessions (76 friction events; `references/post-mortem.md`)
found "looked in the wrong place" was the *rarest* failure (4/76) — because
dispatches already named absolute paths and file:line pointers. The real cost
was (a) under-specified protocol/acceptance in the issue body (~25 events,
30–70 min each — e.g. a CV leakage rule stated nowhere cost one worker 68 min
and was then hand-relayed to four siblings; one ambiguous noun, "training
authors" vs "messages", cost 51 min) and (b) environment papercuts that hit
every session identically (~40 events) and belong in ONE standing preamble
(`references/standing-preamble.md`), never in issues.

Arguments: a one-line goal, a bug report, a finding, or an existing issue
number to rewrite. Optional `--epic` to file an epic + phase issues.

---

## Phase 0 — Don't file a duplicate, don't file a symptom

1. `gh auth status`. Then search: `gh issue list --state open --limit 200
   --json number,title,labels,body` and the last ~30 days of closed issues.
   **One issue per INVARIANT, not per instance.** If the invariant is already
   tracked, add your instance as a comment there and stop.
2. If what you tripped over is one violation of a rule the codebase should
   enforce everywhere, sweep for siblings now (`rg -n -m 30`) and file the RULE
   with the inventory. Findings from one review become ONE hardening issue with
   a checklist.
3. Right-size: one worker, one worktree, one PR, ≤ ~half a day. An N-phase
   plan is an epic + N phase issues (see Phase 4), never one issue.

## Phase 1 — Scout (the filer pays this cost exactly once)

Delegate to a read-only scout (Explore / sonnet) with a self-contained prompt
when the repo is non-trivial; do it inline for a small, known target. The scout
returns a **file:line map**, not prose. Collect, for THIS change:

| What | Why the implementer needs it verbatim |
|---|---|
| Entry points + functions to change/reuse, as `path:line` + symbol | "port the logic from repo X" → blind search; `port whole_word_hit from src/discourse.py:41` → one grep |
| Exact return shapes / literal vocabularies / units of every seam touched (tuple vs dataclass; the exact label strings; raw vs logistic, [0,1] vs unbounded) | two workers coding against the same stub WILL invent different strings; a wrong shape only surfaces at `ty check` |
| The test path the CI gate actually collects (e.g. `tests/tier0/`), the gate command, current baseline count ("base = 276 passed") | a dispatch once pointed at an ungated test file; baselines let the worker self-verify |
| Every invariant a prior issue established that this one could violate ("exactly ONE recipe reads the test split", "grid must include the baseline row or Δ is nan") | workers do not archaeology-check old issues |
| Files that OTHER in-flight issues own; shared "hot seams" everyone edits (stub inventory test, `.gitignore`, `justfile`, README sections) | a worker shipped red because the failing shared test wasn't in its owned list; every sibling PR then conflicted on it |
| Real-data scale (rows / authors / messages), which operation classes OOM or are slow (per-message pmap over the full split; `LogisticRegression(solver='saga')` at 76k features), wall-clock of any regeneration step | naive per-row code that only breaks at 2M rows; two SIGTERMs before anyone said "queue it" |
| Any number the worker must reproduce: the **function** that produces it, the split, the value, the tolerance | "1533 admitted terms" was from a different function than the prompt named; "±10% of published counts" arrived after the PR was open |
| Known gotchas of helpers being reused (hidden invariants, argument order, unsafe generic sources) | `min_monotone_prior` assumes NL≈NR and is argument-order-asymmetric — rediscovered by two workers in the same hour |
| External data / access dependencies, and the fallback | an issue assumed a dataset obtainable by email; the user said "assume unavailable" → full rewrite + re-dispatch |
| End-state constraints (must build from a clean clone; no sibling-repo edits; regenerate exactly once, last) | each arrived as a late correction and cost an extra worker pass |

Verify every asserted fact against the code the scout pointed at — run the
function that produces the headline number; open the file at the line. A
wrong pointer costs more than no pointer.

## Phase 2 — Write the body (template)

Use every section; write "none" rather than deleting a heading — the absence
is information. Literal checklists and commands beat prose everywhere.

```markdown
## Goal
One sentence. Then the user-visible outcome.

## Definition of done (literal checklist)
- [ ] <observable result 1 — a command and its expected output/line>
- [ ] <tests: path under the gate's collection dir; names; expected count delta>
- [ ] <artifact regenerated ONCE at the final sha; report names its producer sha>
- [ ] PR into dev, `--merge`, issue closed explicitly (`Closes #N` does not fire on dev)

## Blocked on / unblocks
Blocked on: #N merged AND <specific invariant, e.g. scoring unit> unchanged. Unblocks: #M.
(So the worker self-gates instead of idling for a GO message.)

## Ground rules (COPIED from epic #E, binding)
<paste verbatim — never "see epic">

## Invariants from prior work you must preserve
- <"exactly ONE recipe reads the test split (#26)">
- <"every grid includes the all_predator_lines baseline row">

## Protocol (any stats / CV / eval / measurement)
- Unit of derivation: <message | author | conversation> — say it, every time.
- Any label-derived weight/gate/prior/vocab is refit PER FOLD from training-fold rows only;
  report optimistic (all-train) AND honest (per-fold); pick on honest.
- Cross-split direction: score split B by counting split A's FIXED vocabulary in B's text.
- Decision / tie-break: ship the better of two candidates unless within ~1 sd of noise; record both.
- Test-split touches: budget, the single door, the ledger.

## Acceptance numbers
`<module.function>` on `<split>` → <N> ± <tol>. Report-only vs gate: <which>.
If off: <stop and report | bounded sweep over these named variants: …>.

## Scale + resources
train ≈ <rows>/<authors>/<msgs>; <op class> WILL OOM — chunk it; <op class> is fine.
<step X> takes ~<N> min → queue it; regenerate exactly once, as the last step.
Shared single-slot queue with <sibling>; <who has priority>.

## Files
Own (create/edit ONLY): …
Do NOT touch: <path> (owned by #K, in flight) …
Shared hot seams + rule: `tests/tier0/test_schema.py` stub inventory — remove your module's rows in the same PR; …
Gate rule is absolute: a red test outside your files is STOP-and-report, never ship.

## Seam contracts
<function>(…) -> <exact shape>; labels ∈ {"a","b"}; score scale: raw log-odds, unbounded; column names: …

## Reuse map (file:line)
- `path/file.py:123 fn_name` — use for …; returns <shape>; gotcha: <…>
- Reference implementation to mirror: `../repo/path.py` (bounded: sections …)

## External deps + fallback
<dataset/API/host>; if unavailable: <exact fallback>. Known-dead URL → <archive path>.

## Hard constraints (restate next to the step they bite)
- Never <X> — including when <the tempting situation>.
- Git: <rebase vs merge>, checked against repo conventions (producer-sha reports ⇒ merge).

## Known gaps / expected negatives
<"known ~10% off — record the table, this is done not blocked">

## Out of scope
<explicit fences; what to file instead of fixing>
```

## Phase 3 — The cold-read test (before `gh issue create`)

Read the body as a fresh agent that has never seen the repo. Fail the issue if
any answer is "I'd have to look":

- Which file do I open first, at what line? What exactly do I change?
- Which test file do I add to, and is it under the gated path? What count do I expect?
- Is every "reuse X" a `path:line` + symbol with its return shape?
- Does every number name the function + split + tolerance + what-if-off?
- Does every protocol sentence name the UNIT (message/author/conversation/fold)?
- Which files are mine, which are a sibling's, which are shared — and what happens if a shared test goes red?
- What will OOM / take >5 min, and is the regeneration "exactly once, last"?
- What am I blocked on, and can I tell from `gh` alone when it clears?
- Are the "never"s placed where I'd be tempted? Do git instructions agree with repo conventions?
- Could "done" be mistaken for "PR merged"? (No — issue close is explicit.)

Also check the environment doctrine is NOT in the body: queue quoting,
wrapper-exit≠inner-exit, ruff format as a separate gate, BSD pgrep, `gh
--body-file`, `uv sync` first, ping cadence … belong in the repo's standing
preamble (`.agent-workflow/`, CLAUDE.md, or the dispatch preamble). If the
project has none, create it from `references/standing-preamble.md` ONCE and
reference it. Per-issue repetition of env facts is how they rot.

## Phase 4 — File it

- `gh issue create --title "<area>: <imperative goal>" --body-file <tmpfile> [--label …]`
  — always `--body-file`; inline `--body` with backticks breaks the shell.
- Titles: `<component>: <what changes>`; phase issues `<epic>/phase N: <scope>`.
- **Epic + phases:** the epic carries the ground rules, dependency graph, decision
  rules, and shared-resource budget; EACH phase issue re-pastes the ground
  rules, states its `Blocked on`, and names its ownership vs every sibling
  phase. When a ground-rule gap is found mid-epic, back-port it into the epic
  body AND comment it on every open sibling the same hour.
- **Close-out / finalization / report issues** state the task as a before→after
  diff ("shipped `score.py` uses unit=concat-mean, min_df=3; tuned winner is
  unit=message-logodds, min_df=5; switch it and regenerate once"), never
  "regenerate the report".
- Link back: `Part of #E` in the body; `Closes #N` lines in the PR, and the
  implementer closes the issue explicitly because the PR targets `dev`.
- Filed ≥3 issues you did not start with → run `/triage` before starting any.

## Anti-patterns (each one has a receipt in `references/post-mortem.md`)

- "See the epic for ground rules." → four workers each missed the same rule.
- "Derive weights from the fold's training rows." → which unit? 51 minutes.
- "Report the VTPAN counts vs the published numbers." → is that a gate? Reshipped.
- "Reuse #29's helper." → it operates at author level; this issue needed message level.
- "Port the logic from parot-bias." → name the file and function.
- "Assert 1533 terms." → from which function, on which split?
- "Watch memory." → name the operation class that OOMs.
- "Add tests to `tests/test_calibrate.py`." → not under the gated path.
- "Never parse markdown" once at the top → violated at the caching step; say it there too.
- "Rebase, never merge" → contradicted the repo's producer-sha convention.
- A split issue with two workers and one single-slot queue, no sequencing rule → 25 min of kills.
- An external dataset assumed obtainable → rewritten after a user correction.
