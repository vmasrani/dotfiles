# TAM model template — SAM(R, s)

The point of the model is not the headline number; it is the *table* that shows which axis moves the market in the band you are actually in, so engineering optimises the right thing and the pitch leads with the right claim.

## Variables

| symbol | meaning | how it is measured |
|---|---|---|
| **R** | improvement over the incumbent the buyer runs, on the headline metric, per unit of work | the experiment, against the incumbent (never the specialist) |
| **s** | speed/cost multiple vs the best-in-class alternative on the gating axis (1 = parity) | the experiment, after legitimate one-time setup |
| **S_i** | annual spend in pool i (USD/yr) | analyst ranges, vendor ARR, cloud list prices × estimated volumes — always ranges, always sourced |
| **f_i** | addressable share of pool i (fraction of that spend on workloads where the idea applies at all) | estimate; the least defensible input — say so |
| **k_i** | fraction of the vendor's price that is driven by the headline metric | 1 for raw resource bills; ~0.4 for software/appliances priced on features/support; ~0 if the metric is table stakes |
| **c** | capture: fraction of savings/uplift the vendor can charge | 0.2–0.5 |
| **a(s)** | adoption gate for ratio-driven pools | 0 at the floor (s ≈ 0.1), 1 at parity, log-linear between; nobody pays extra above parity |
| **a_gen(s)** | adoption gate for speed-driven pools (where speed *is* the product) | keeps rising past parity if the competitor is much slower (e.g. SA-based patchers ~50× slower than the hash tool) |
| **share** | realistic share for a niche engine/OEM vendor over 3–5 years | 2–5 % |

## Equations

```
Savings_i(R)   = S_i · f_i · k_i · (1 − 1/R)        # spend × addressable × metric-driven × saved fraction
SAM_ratio(R,s) = a(s) · c · Σ_i Savings_i(R)
SAM_gen(s)     = a_gen(s) · c · S_speed · f_speed    # pools where generation speed / a new capability is the product
SAM(R,s)       = SAM_ratio + SAM_gen
SOM            = SAM · share
```

`(1 − 1/R)` is why ratio saturates: R = 2 saves 50 %, R = 4 saves 75 %, R = 8 saves 87.5 % — doubling ratio past 4 adds ~12 points. `a(s)` is why speed dominates below parity.

## The table to produce

Rows s ∈ {0.05, 0.1, 0.2, 0.33, 0.5, 1}, columns R ∈ {2, 4, 8}. Fill SAM in USD M/yr. Then read it aloud in three sentences:

1. Below s ≈ floor the ratio doesn't matter (all remaining SAM is the speed-driven pool).
2. Between the floor and parity, how much a doubling of speed is worth vs a doubling of ratio (typically ~10× more).
3. Above parity, what speed adds (usually nothing in-model; name the unmodelled upside separately).

Then place the GO line and the NO-GO line from the criteria on the table and quote the SAM at each — that is the number that answers "how big is this if it works as specified".

## Pools — how to enumerate them

Ask "whose bill shrinks, and by what mechanism?" per buyer archetype:

- **Operators paying a resource bill** (cloud storage/egress lines, compute hours, API spend): S = list price × volume; k = 1; f = the workload share your technique applies to.
- **Vendors who would OEM** (backup/storage software, appliances, platforms): S = their revenue; k ≈ 0.4; discount hard if the metric is table stakes.
- **Capability buyers** (fleet/OTA delta generation, distribution, search/compliance): S = the delivery or tooling budget; goes in SAM_gen with its own gate.
- Explicitly list the pools you *exclude* and why (data compressed/encrypted at rest; already-solved by app-store deltas; markets where the incumbent isn't the thing you beat).

## Sensitivities to list every time

- c linear; f linear (and least defensible); k → 0 if table stakes (state what the base drops to); the a(s) ramp shape (softer/harder buyer ±40 %); one line on unmodelled upside (do not add it in).

## Sourcing

Collect on a stated date; label everything "analyst ranges, not audited". Prefer: vendor IR/press releases for ARR, cloud pricing pages for unit prices, two independent analyst ranges per pool, one anchor per delta claim (e.g. "Android file-by-file patches avg 65 % smaller"). Put the list at the end of the model doc.

## Output

`docs/tam-model.md` with: variables table, equations, inputs table with sources, SAM(R, s) table, the three-sentence read, GO/NO-GO SAM, "where we are on s today", sensitivities, and — kept separate — a "Beyond the wedge" section for capabilities that require preconditions the current prototype lacks (flag each with "requires X").
