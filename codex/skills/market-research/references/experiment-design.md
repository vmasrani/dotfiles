# Make-or-break experiment design

The experiment exists to falsify the bet cheaply — "spend days deciding whether to spend weeks." Everything below is in service of one property: when the numbers come back, nobody can argue about what they mean.

## 1. Define the two axes before anything else

| symbol | definition | measured against |
|---|---|---|
| **R** | improvement on the headline metric per unit of work: `metric_incumbent / metric_ours` (bytes stored per snapshot, $ per query, ms per request…) | the **incumbent the buyer runs today** — never the closest specialist tool |
| **s** | speed/cost multiple on the gating axis: `throughput_ours / throughput_best_alternative` (s = 1 parity, s = 0.1 ten times worse) | the **best-in-class alternative** on that axis, measured *after* any one-time setup you can legitimately amortise (say so, and report the setup separately) |

Also define any amortisation curve the product depends on (e.g. one-time index vs N targets, cumulative time vs N independent runs of the alternative) — for fleet/many-vs-one workloads that curve *is* the speed number.

Write the operationalisation down: which variant of yours is primary (decided a priori, not after seeing results), what statistic per workload (median over pairs), which units.

## 2. Kill / go criteria — fixed before data, quoted verbatim in the report

Template (fill the numbers for the domain; the shape is what matters):

- **NO-GO** if, on the core workload classes, R is below the switching threshold (typ. 2–3× over the incumbent — below that the migration isn't worth it) — **or** s is below the adoption floor (typ. 0.1) *with no obvious fix*.
- **NO-GO** if you lose to the specialist tool on your own axis (e.g. bigger patches than xdelta3).
- **GO** if R clears a comfortable bar (typ. 4–5×) on ≥ 2 real workloads, you are within a small multiple of the specialist tools' quality (typ. 2×), and s ≥ ~0.33 or the amortisation curve crosses parity within a small N (≤ 10).
- Otherwise **inconclusive**, with the specific numbers and what would resolve it.

Rules: don't move the criteria afterwards. You *may* change the operationalisation for a fairness reason **before results exist** (e.g. compare compressed output to entropy-coded baselines) — record the reason, and compute the verdict on both conventions with a sensitivity line ("both bases give X" / "⚠ the outcome depends on the convention").

Implement the criteria in code that reads the JSON, with a `NOT EVALUABLE` state distinct from "failed" (a run with no core-workload corpus must not read as "no corpus met the bar").

## 3. Corpora — real data only, provenance recorded

- ≥ 4 workload classes, ≥ 3 (prefer ≥ 5) consecutive snapshots/inputs each, sizes chosen for the machine (state RAM; e.g. an SA at 5n plus bsdiff at 17n caps inputs at ~500 MB on 16 GB).
- Real base + real change log replayed through a real engine counts as "real-replay"; workload generators (pgbench) are "synthetic" — flag and weight lower.
- Anything compressed/encrypted at rest is decompressed first and flagged; a "1×" on compressed input is not evidence about the engine.
- Every fetch is an idempotent script that writes `provenance.json`: URLs, sha256, sizes, exactly what changed between snapshots, notes on anything odd (a dump date that isn't the content date; a tar member shift that makes a corpus adversarial for fixed-block tools — keep it, and document why it discriminates).
- Keep large files outside the repo (a data dir); commit provenance and READMEs with the exact regenerate command.

## 4. Baselines — all of them, versioned, fail loud

- The incumbent(s): the thing buyers actually run (block/chunk dedup, the default cloud service, the standard library) — include a cheap proxy where the real system isn't scriptable (e.g. fixed-block diff as an EBS/ZFS proxy) *and* a real one where it is (restic/borg).
- The specialists: fastest hash-based tool, the closest algorithmic competitor, the quality floor. Record exact argv and version for each.
- Naive: full cost, and full cost with the standard compressor.
- A missing tool is reported as **MISSING** in the results, never silently skipped. A tool that self-verifies inside its timing (hdiffz) gets that disabled and verified externally like everyone else — otherwise its speed number is unfair *against* it. Check argument orders (bspatch's patch is the third argument) with a smoke test.
- Fairness notes go in the results, e.g. `-T1` when your side is single-threaded; whether baselines entropy-code their output; whether the incumbent compresses.

## 5. Measurement discipline

- Quiet machine: every timed command runs through a serialising job spooler (`queue`); record its state in the manifest as evidence. Nested-queue deadlock: launch one job per corpus with `--solo` and let inner calls run directly.
- `/usr/bin/time -l` (macOS) / `-v` (Linux) for wall + peak RSS; note timer resolution and render sub-resolution results as `< 10 ms`, never `0`.
- Median of 3 when a run is short (adaptive: run once, repeat if under a cap), `runs: 1` recorded when it isn't. Delete outputs before each repeat so a repeat redoes the same work.
- Correctness per cell: byte-identity (sha256 of restored/produced artefact vs original) or the run FAILS. Restore/apply time is measured too.
- Report a one-time setup separately (index build) and the amortised number the product depends on; also the whole-process wall so nobody can say you hid it.
- Idempotent runner: skip done cells, re-run MISSING ones, rewrite the manifest after every corpus segment (a run that dies at hour six leaves a manifest of what it finished).
- Never `cmd | tail` a run — capture to a log and finish with the run's own exit code; grep the log for failure patterns.

## 6. Watch for the surprises this design tends to surface

- The primitive you planned to reuse is private / has the wrong return type — depend on the underlying library directly rather than coupling to a repo you may archive.
- The naive algorithm is catastrophically slow on the *literal-heavy* case even when the *mostly-matching* case looks fine — measure a rebuilt-image/binary class, not just the friendly one, before concluding on s.
- Obvious, exact optimisations (bounded searches, membership prefilters) can move s by 10–40× — the "no obvious fix" clause exists so a NO-GO isn't declared on a naive implementation; keep the parse/result provably identical (differential test against a search-everything oracle) so speed work never silently changes quality.
- Convention choices (raw vs compressed, single- vs multi-thread) can flip criteria — that's why the verdict runs on both.

## 7. What the artefact set looks like at the end

`bench/results/**/*.json` (one file per cell + per-corpus curves + manifest + versions + machine), a generated report rendered from JSON only (deterministic; regenerates byte-identically), and provenance per corpus. The generated report is the appendix's evidence; the human-written report cites it.
