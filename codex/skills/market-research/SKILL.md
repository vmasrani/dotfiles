---
name: market-research
description: Decide, with numbers, whether a technical capability or product idea is worth building — and for whom. Runs the full make-or-break analysis: name the incumbent the buyer already runs vs the best-in-class alternative, fix kill/go criteria before any data, size the market as SAM(R, s) (how-much-better × adoption gate on the weakest axis), work out who owns the bill that shrinks and what they would pay, decide whether the idea is "a bit better" or its own category, stress it against a named prospective customer, and write a 2-page report with everything else in an appendix. Use this whenever the user asks "is this worth building", "who would pay for this and how much", "how big is the market", "should we go/no-go", "TAM/SAM/SOM", "what's our wedge", "are we better than X", "is this a new category", wants a decision memo or investor-style analysis for a repo/prototype/algorithm, or says "market research" — even when they only mention one piece (e.g. just "how much would a customer pay?" or just "size this market"), because the pieces only make sense together.
---

# Market research for a technical bet

You are turning a technical idea — an engine, an algorithm, a prototype, a repo — into a decision: build it or not, for whom, and what to lead with. The output is a short report a founder or team lead can act on, backed by an appendix that survives scrutiny.

The method comes from a real make-or-break run (a byte-granular snapshot/delta engine vs chunk-dedup incumbents; see `references/worked-example.md`) and generalises to any "we can do X better/faster/cheaper" claim. Its spine is a small number of ideas that most first drafts get wrong:

- **The buyer's incumbent is not your closest competitor.** You must be *order-of-magnitude* better than what the buyer *runs today* to make them move, and only *at parity* with the best specialist tool on your axis. Confusing the two produces both false optimism ("we beat the incumbent 100×") and false despair ("we're only 1.2× zstd").
- **There is always a gating axis** — usually speed, cost, memory, latency, or integration effort — on which being worse than the buyer's pipeline makes every other advantage irrelevant. Find it, and measure it with the same care as the headline metric.
- **Fix the kill/go criteria before the data exists**, then don't move them. Move the *operationalisation* only for fairness reasons, before results, and say so in the report.
- **A market is a bill that shrinks, owned by someone.** If you cannot name the line item and the person who sees it, there is no market yet.
- **"Own category" claims need a steelman first.** List what existing tools already do (including obscure library APIs) before claiming a capability is new.

## Inputs to collect first

Extract from the conversation and repo before asking; ask only for gaps. You need:

1. **The capability**, in one sentence, and the artefact that embodies it (repo, prototype, benchmark, paper).
2. **The claimed edge** (what is better) and **the claimed risk** (what is probably worse — the gating axis). If the user only states the edge, propose the risk; there always is one.
3. **The candidate incumbents** — what target buyers run today — and the **best-in-class alternatives** on the edge axis. Research these; don't take the user's list as complete.
4. **What numbers already exist** (benchmarks, measurements) and how trustworthy they are (real data or synthetic; quiet machine or not; provenance).
5. **The user's decision** — go/no-go on building, choosing a wedge, an investor memo, a pricing question. Shape depth to it.

If no numbers exist yet, the deliverable is the *experiment design* (Phase 2) plus a provisional analysis; say plainly which parts are hypotheses.

## The workflow

Run the phases in order; each produces a section of the appendix, and the front two pages are distilled from them last. Delegate research fan-out (market sizes, competitor capabilities, pricing pages) to parallel subagents where available — the main thread keeps the conclusions, not the page dumps.

### Phase 1 — Frame the bet as a 2×2 and two axes

Draw the incumbent-vs-specialist grid for this idea. Rows: the granularity/quality dimension the idea improves; columns: the operating-model dimension (e.g. "no reference state / global" vs "reference-aware / pairwise", "batch" vs "streaming", "self-hosted" vs "managed"). Place the incumbents, the specialist tools, and the idea. The idea is interesting only if it sits in a cell nobody occupies *and* buyers in an adjacent cell have a reason to move.

Then define the two numbers the whole analysis runs on:

- **R** — how much better than the *incumbent the buyer runs*, on the headline metric, per unit of work (bytes stored per snapshot, cost per query, latency per request…). Measured against the incumbent, never against the specialist.
- **s** — the speed/cost multiple vs the *best-in-class alternative* on the gating axis (throughput vs the fastest tool, cost vs the cheapest, latency vs the lowest). s = 1 is parity.

Write both definitions down before measuring anything. `references/experiment-design.md` has the template and the evidence-discipline rules.

### Phase 2 — Kill/go criteria, then the experiment (or the audit of existing numbers)

Write NO-GO / GO / inconclusive criteria in terms of R and s, with numbers, up front:

- NO-GO when R is below the switching threshold (typically 2–3× over the incumbent — below that nobody migrates) **or** s is below the adoption floor (typically 0.1 — ten times slower than the pipeline it joins is never adopted regardless of R).
- GO when R clears a comfortable bar on ≥ 2 real workloads *and* s is within a small multiple of parity (typically ≥ 0.33) or an amortisation curve crosses parity within a small N.
- Everything else is "inconclusive, with the numbers and what would resolve it".

Then either design the experiment (real corpora only, all baselines installed and versioned, missing baselines reported as MISSING, byte-identity/correctness checks per cell, quiet-machine timing, JSON → generated report with no hand-typed numbers) or audit the numbers that already exist against those standards. Compute the verdict programmatically on any convention that could plausibly change it (e.g. raw vs compressed output) and show the sensitivity — that turns "we chose a fair convention" into something the artefact demonstrates.

### Phase 3 — Size the market as SAM(R, s)

Do not quote a TAM headline; build the model in `references/tam-model-template.md`:

- Enumerate spend pools the idea touches (each with a source), the addressable share f, and the fraction of that price that is driven by your headline metric k (raw storage bills: 1; software/appliances whose price is mostly features/support: ~0.4).
- Ratio-driven savings per pool: `S · f · k · (1 − 1/R)`. Adoption gate `a(s)`: 0 at the floor, 1 at parity, log-linear between. Capture `c` (0.2–0.5). Speed-driven pools (where the *capability* is generation speed or any-to-any, not ratio) get their own gate `a_gen(s)`.
- Produce the SAM(R, s) table (rows s, columns R) and read off which axis moves the market more in the band you're actually in — usually speed dominates between s = 0.1 and 1, and ratio adds little above the switching threshold. That finding tells the engineering team what to optimise.
- SOM = SAM × realistic share for a niche engine (2–5 % over 3–5 years). Say what deal sizes and customer counts that implies; if it implies "20 customers at $200k–1M", say so — that is a different business from a broad product.
- List sensitivities: capture, addressable share, k, the shape of a(s). Note the "unmodelled upside" honestly but do not add it to the number.

### Phase 4 — Who pays, how much, and why

Answer "who owns the bill that shrinks?" with three archetypes, and do the arithmetic for each:

1. **The operator with the bill** (pays a fraction of savings — 20–30 % is normal; check whether the bill is big enough for a deal to exist at all: a $60k/yr bill cannot fund a sale, a $600k/yr one can).
2. **The vendor as OEM** (pays for a feature that wins deals or defends margin: flat license or royalty; discount for "ratio is table stakes"; note the trust barrier when your engine sits in their critical path).
3. **The capability buyer** (pays for something they cannot get elsewhere — speed of generation, any-to-any, search — where your headline ratio is irrelevant; the buyer is engineering, not procurement).

For each: why they pay (the bill is visible; it drops in behind what they run; the risky path — restore, correctness — is provably boring) and why they don't (metric is table stakes; their data defeats the technique; you're slower than their pipeline; migration cost). Name the data types or workloads that structurally defeat the idea (for compression: anything compressed/encrypted at rest) — these shrink every pool.

### Phase 5 — The category question

Before claiming a new category, steelman the field: list what existing tools already do, *including library-level features the CLI hides* (a "we amortise the index" pitch dies to "so does zstd's CDict"). Then name the genuinely empty cell and the two or three capabilities that fall out of it, each with its buyer. Flag the technical preconditions those capabilities need (usually the ones the current prototype does *not* have) as explicit "requires X" notes so the TAM never silently assumes them.

State the sequencing: wedge inside an existing budget → accumulate the corpus/footprint → expansion into the new capabilities. Name the category-creation trap (buyer education, no budget line, read-products that must be more than demos) so the recommendation does not lean on it by accident.

### Phase 6 — A named prospective customer and a public-data pilot

Pick one concrete company the user names (or the most legible one in the target segment) and work it through: what they ship or store that has the shape of the problem; what their incumbent is; the concrete offering in one sentence; the rough bill and saving; why their engineers would care beyond cost; and — most useful — a pilot you could run **without talking to them**, on public artefacts (public builds, public datasets, public images), that produces the one table you would put in front of them. If a candidate is a poor fit, say so and name a better one; a wrong customer picked to please the user wastes the whole exercise.

### Phase 7 — Write the report

Use `references/report-template.md`. Two pages first — what we can do, which market to target, how big it is, how much better than the competitors — written last, from the appendix, with numbers copied from generated artefacts (state where each number comes from). Everything else goes in the appendix: full comparisons, limitations, markets to avoid and why, the category question, the pilot, methodology and provenance. The verdict cites the criteria verbatim and states any operationalisation choices. If a run is still in progress, mark preview numbers as such and never let a hypothesised number sit next to a measured one without a label.

## Style and honesty rules

- Lead with the number, then the reason. "8× fewer bytes than block dedup on the DB corpus, 6× faster than zstd after the index is built; 7–11× slower than zstd on rebuilt images" beats a paragraph of adjectives.
- Never let "we win" stand without "against whom": every claim names the incumbent or the specialist it is measured against.
- Say which parts are measured, which are modelled, which are hypotheses. Ranges over point estimates for spend; point estimates only for measurements.
- When the user's excitement outruns the data ("we compress far better than existing solutions!"), correct the framing in one sentence and keep going — that correction is often the most valuable line in the whole engagement.
- When the user turns pessimistic ("this is a dead end"), separate the technical answer from the market-shape answer; often the tech is fine and the business is narrow. Say that plainly, and still finish the run — a written result is reusable either way.
- Preview verdicts are fine (users ask for them); label them "preview, subject to the full matrix" and replace them.

## Bundled references (read as needed)

- `references/experiment-design.md` — the make-or-break protocol: axes, criteria template, corpora rules, baselines, evidence discipline, verdict computation, what to record.
- `references/tam-model-template.md` — SAM(R, s) equations, adoption-gate shape, sensitivity table skeleton, how to source spend inputs.
- `references/report-template.md` — the two-page + appendix structure with the exact section list and per-section prompts.
- `references/worked-example.md` — the fast-delta case in one page: the 2×2, the criteria, the surprises, the business read. Use it for calibration, not as a template to copy numbers from.
