---
name: walkthrough
description: Build a self-contained single-file HTML walkthrough/explainer for a project — either a click-through DECK (one claim per screen, verbatim tool output, running scoreboard) or a scrolling PAGE (showcase → how it works → at scale → honest caveats) — backed by a generator script that computes every rendered number live. Use whenever the user wants to explain or demo functionality visually rather than in the terminal: "make a walkthrough", "html walkthrough", "explainer", "explain all the new functionality", "demo page", "guided tour", "write up how this works", a page to hand a customer/reviewer/collaborator, or when they point at an existing walkthrough.html / gen_*.py explainer and want one like it.
---

# walkthrough — self-contained HTML explainers

The deliverable is **one HTML file** that can be emailed, opened from `file://`, and
read offline: inline CSS and JS, data inlined into the page, no server, no network, no
build step. Behind it sits **one generator script** that computes every rendered number
live against the real system and inlines the result.

Two flavors. Both share the same spine and the same honesty rules; they differ in shape.

| | **DECK** | **PAGE** |
|---|---|---|
| shape | click-through steps, one claim per screen | long scroll, four fixed movements |
| best for | a narrative *loop* or workflow; live presentation | one capability explained in depth |
| content | commands + verbatim output + measured ms | mechanism, formulas, real citations |
| chrome | progress dots, keyboard nav, scoreboard footer | section rail, chips, provenance footer |
| look | dark terminal | light paper, dark panels for cost/mechanism |
| asset | `assets/deck.html.template` | `assets/page.html.template` |

Pick DECK when the point is *the sequence* ("watch each turn of this loop cost
milliseconds"). Pick PAGE when the point is *the mechanism* ("here is why this number
is trustworthy"). **Explaining several features → several PAGEs, one per feature**, not
one mega-page; they cross-link and stay separately readable. If the ask is broad ("walk
me through everything new"), a DECK that tours the surface plus a PAGE for each
substantial capability is the usual answer — say so and confirm before writing eight
files.

## The spine (identical for both flavors)

```
<name>.html          the source AND the deliverable — design + prose live here
gen_<name>.py        computes the ground truth, validates it, inlines it
<name>_data.json     the committed, diffable ground truth
```

The generator **never templates the HTML**. It rewrites, in place, only the
`<script id="wt-data" type="application/json">` block. So design edits survive every
regeneration and data refreshes never clobber layout work. Both directions fail loud:
missing block → error; unmeasured data → error.

## Bundled assets

- `assets/deck.html.template` — DECK page. Ships with a stub payload so it opens
  immediately, an honest empty state, and generic renderers (`chart`, `bars`, `cards`)
  that cover ranked comparisons, conditionals, gates, and the closing scoreboard.
- `assets/page.html.template` — PAGE skeleton with the four movements, the design
  system, and the table/bar/number-injection helpers.
- `assets/gen.py.template` — the generator: the `run()` capture helper (verbatim output
  + `perf_counter` ms), the ORACLE assertion block, `build_payload`, `check_payload`,
  and the in-place `inline()`.

Read the template you're using before writing — the conventions and the earned gotchas
are inline comments in it.

## How to build one

**1. Find the spine.** For a DECK, write the step list first, as sentences — each step
makes exactly ONE point, and the sequence should read like an argument. The proven
shape: *ask → harvest → gate → direction → iterate → control → receipts → close*. The
**control** step is not optional: a method that can only say "yes" is worthless, so one
step must run the same machinery on something that legitimately comes back flat/empty.
For a PAGE, write the claim sentence someone could disagree with, then the caveats —
if the caveats are embarrassing, the claim is too strong.

**2. Copy the template into the project** as `<name>.html` and adapt the marked
`▸ EDIT` points: title, brand/claim, section headings, prose. Prose is hand-written;
numbers are not (step 4).

**3. Write `gen_<name>.py`** from `assets/gen.py.template`. It runs the real tool or
calls the real library, parses its own output, and builds the payload. Add the ORACLE
block: known-true facts as *assertions only*, so a silently-broken pipeline crashes
instead of rendering a plausible page.

**4. Inject every number.** Any digit that could change when the input changes goes
through the payload and is written by JS into a `<span id=…>`. A number typed into the
markup is a number nothing measured, and it rots the first time the input grows.

**5. Regenerate and verify** (see below). Commit the `.html` and the `_data.json`
together — they are one artifact.

**6. Tell the user how to open and re-run it**: `open <name>.html`, regenerate with
`./gen_<name>.py`.

## DECK anatomy

Each step object carries: `tag` (2-word phase label), `title` (a question), `narration`
(why this move), `commands[]` (`display` / verbatim `output` / measured `ms`), an
optional viz (`chart` sparkline, `bars` with pass/fail badges, `cards` for the close),
`kicker` (the one sentence to remember), and `contrast` (what the alternative would
have had to do). The footer scoreboard accumulates real cost across steps and lands the
comparison on the last screen — but only if the baseline was **measured on this
machine**; otherwise leave `meta.baseline: null` and the half hides itself.

## PAGE anatomy — the four movements

1. **The showcase.** What it produces, on real data, before any explanation. Lead with
   the reader's question, not the builder's curation.
2. **How it works.** The real mechanism: named methods with citations (author, year,
   title), notation in a `.math` block, and a `.where` line defining every symbol. Say
   which naive approach fails and exactly how — that failure mode is the reason the page
   exists. Derivations of any parameter go here, with the derived value injected live.
3. **At scale.** Why the cost holds up: the operation, its complexity in the quantity
   that actually grows, the API that delivers it, and the **cost trap** — the
   plausible-looking call pattern that is accidentally O(everything). Best close: the
   property gets *stronger* with size, not merely faster.
4. **Honest caveats.** What this does NOT establish, in the reviewer's own words, before
   they ask. Never fewer than three. A page with no caveats reads as a sales page.

## The honesty architecture (the load-bearing part)

This is what separates these pages from a slide deck, and it is enforced in code:

1. **No oracle hardcoding.** Every input-specific *output* — which terms win, where the
   change-point is, which run is fastest — is produced by the technique at generation
   time. Known-true facts appear only as fail-loud assertions, never as a source of
   rendered content. The test: *would the deployed system hardcode this?* Generic config
   (window sizes, seeds, stoplists) passes; anything you learned by eyeballing this
   input fails.
2. **Fail loud, no fixtures.** One path. No mock mode, no `try/except` around a missing
   input, no "if the daemon is down use last week's numbers". A figure that cannot be
   computed renders an **honest empty state** that names the command to fix it — and a
   build/transport failure must look *visibly different* from a legitimate empty result.
3. **Derive, never restate.** Constants that depend on the input are computed from live
   input shape and read back. A tuned constant is a bug that breaks silently off the
   input it was tuned on.
4. **Verbatim output, measured clocks.** Tool output is trimmed, never paraphrased.
   Timings are `perf_counter` around the real call including process spawn — no
   warm-up subtraction, no best-of-N. Comparisons cite numbers measured on this machine;
   an unmeasured rival number is the fastest way to lose a technical audience.

## Design rules

- **No jargon on the page.** Internal vocabulary never renders — translate at the
  generator, so the HTML never needs to know the internal name. Sweep the rendered
  strings before shipping.
- **Escape everything from the payload** (`esc()`), except HTML you deliberately
  pre-built in the generator — and say so in a comment where you do.
- **Simple by default, complexity optional.** Methodology and tuning notes live behind
  `<details class="why">`; the reader who ignores them pays nothing.
- **Responsive and self-contained.** Wide tables scroll inside their own container; the
  body never scrolls sideways. No CDN fonts, no external scripts — a page that needs
  the network is not a deliverable.
- **Respect `prefers-reduced-motion`** (the DECK template already does).

## Verify before handing it over

```sh
./gen_<name>.py                            # must exit 0 and print what it wrote
rg -c 'wt-data' <name>.html                # exactly 1
rg -n '__DATA__|TODO|lorem|▸ EDIT' <name>.html   # must be empty — no unfilled placeholders
open <name>.html                           # click every step / scroll every section
```

Then actually **look at it**: open it, step through it, and check the browser console is
clean. A page that throws mid-render still shows its header, so "it opened" is not
evidence. Spot-check two or three rendered numbers against the tool's own output.

## Exemplars on this machine

- DECK — `/Volumes/external/dev/fsa/parot-radar/walkthrough.html` with
  `walkthrough_capture.py` and `WALKTHROUGH.md`.
- PAGE — `/Volumes/external/dev/fsa/parot-core/bias_examples/html/0*.html` with
  `gen/gen_0*.py`; the doctrine those pages were built under is in that directory's
  `EXPLAINER.md` ("The honesty architecture") and `CONTRACT.md`.
