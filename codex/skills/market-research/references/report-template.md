# Report template — two pages, then the appendix

The reader is a founder or team lead deciding whether to fund the next phase. Pages 1–2 must stand alone; the appendix exists so that anyone who doubts a line on page 1 can find the evidence. Write the appendix first, the two pages last.

Numbers on the two pages are copied from generated artefacts (the JSON-rendered report, the TAM table); say where each comes from in a footnote or a "sources" line. Never place a hypothesised number next to a measured one without a label.

---

## Page 1

### Title + one-line verdict
"<Idea> — <GO / NO-GO / GO with narrow scope / inconclusive>: <one clause on why>."

### What we can do
One paragraph: the capability in plain language, then the three headline numbers with their comparators —
- vs the incumbent the buyer runs (R): "N× fewer <metric> than <incumbent> on <workload>"
- vs the best-in-class alternative on the gating axis (s): "M× faster / slower than <tool> after <one-time setup>"
- the correctness/safety number that makes it deployable (byte-identical restore, error rate, etc.)

### Which market to target, and why
- The wedge: buyer archetype, the bill that shrinks, the incumbent displaced, deal size range, why they buy (visible bill; drop-in; boring critical path).
- The second market (if any): the capability buyer — what they pay for that isn't the headline metric.
- One line naming the markets *not* to target (details in appendix).

## Page 2

### How big it is
- The SAM(R, s) number at the *measured* (R, s), with the GO-line and NO-GO-line SAMs for scale; SOM at 2–5 % share expressed as customer count × deal size ("20–60 customers at $0.2–1M/yr").
- One sentence on which axis moves the market more from here (speed vs ratio) — this is the instruction to engineering.

### How much better we are than the competitors
One table, rows = workload classes, columns = incumbent (bytes/cost), best delta/specialist tool (bytes/cost and speed), closest algorithmic competitor; cells show our multiple with direction (× better / × worse). Below the table, two sentences: where we win outright, where we are at parity, where we lose.

### Recommendation
Three to five bullets: what to build/not build, what to lead with in the pitch (and what *not* to lead with — usually "faster/smaller than the specialist" when you're at parity), the named-customer pilot to run next, the one measurement that would change the recommendation.

---

## Appendix

A. **Verdict against the criteria** — criteria verbatim; how they were operationalised; per-criterion table with numbers and pass/fail; sensitivity to conventions (verdict on both bases); "what would resolve it" if inconclusive.

B. **Full comparisons** — per workload class: per-pair tables (bytes, ratio vs incumbent, encode/apply time, throughput, RSS, correctness, run count), parameter sweeps, amortisation (many-vs-one) curves with plot; link to the generated report and the JSON.

C. **Limitations** — the structural ones (memory floors, algorithmic floors on the unfriendly workload class, what the design cannot do without changing the algorithm), the practical ones (index size, append/epoch, platform), and the workloads that defeat the technique (compressed/encrypted at rest, etc.).

D. **Markets to avoid, and why** — each with the number that rules it out (e.g. images/binaries: s = 0.09–0.15; media/parquet: compressed at rest; broad enterprise direct sale: no visible bill, trust barrier).

E. **The category question** — what is not new (steelman of existing tools including library-level features), the empty 2×2 cell, the capabilities that fall out of it with buyers, technical preconditions flagged, wedge → corpus → expansion, the category-creation trap.

F. **Named-customer pilot** — the company, what they ship/store, their incumbent, the offering, the bill and saving, why engineering cares, the public-data pilot and the one table it would produce.

G. **Methodology and provenance** — machine, quiet-machine evidence, tool versions and exact argv, corpora provenance (URLs, sha256, what changed between snapshots, realism flags), evidence discipline, how to regenerate.

H. **Business assumptions and sources** — the TAM inputs, sensitivities, and the dated source list.
