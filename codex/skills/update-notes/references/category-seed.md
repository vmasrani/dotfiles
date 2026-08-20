# Category seed — definitions and examples

The seed set is 8 categories. Reuse them aggressively. Only introduce a new category when a finding genuinely fits nowhere below — and when you do, name it in the same kebab-case style and add a one-line definition here (via a subsequent run, not silently).

## api-surface

The shape, naming, overlap, or asymmetry of public-ish APIs in the repo. Builders, helpers, query primitives, adapter layers.

Examples:
- `builder-redundancy` — Two builders that produce overlapping shapes
- `query-primitives` — Three query builders share one primitive; surface asymmetry
- `async-client-defaults` — Client's default timeout is 5s, not the documented 30s

## architecture

How the pieces fit together at a level above any single module. Flow diagrams, sidecars, routing, layering.

Examples:
- `sidecar-flow` — Sidecar bypasses main router when flag is set
- `event-loop-ownership` — Only the main thread may own the event loop
- `two-phase-commit` — Writes go through stage buffer before final table

## footguns

Things that silently fail, silently corrupt, or behave surprisingly. The single most valuable category for future velocity.

Examples:
- `build-ram-env-var` — Unset `BUILD_RAM` silently OOMs at the reduce step
- `default-timezone` — Default timezone is UTC on CI, local on dev; breaks tests
- `polars-lazy-eval` — `.collect()` required; otherwise silent no-op

## conventions

Non-obvious conventions the project follows that a newcomer would violate. Format choices, naming, directory layout rules.

Examples:
- `columnar-arrow-format` — All intermediate data is columnar Arrow, not row-wise
- `module-suffix-means-side-effects` — Modules ending `_io.py` may perform disk I/O
- `test-fixture-naming` — Fixtures prefixed `fx_` are session-scoped

## integrations

Pitfalls and quirks of third-party libraries or services as integrated in *this* repo.

Examples:
- `libx-socket-leak` — Library X's async client leaks sockets under concurrency > 8
- `api-rate-limit-per-key` — Service Y rate-limits per API key, not per IP
- `auth-token-renewal` — Must renew 5min before expiry or mid-request failures

## decisions

Choices made with rationale, preserved so nobody re-litigates them. Only include when the rationale is non-obvious or the alternative was seriously considered.

Examples:
- `polars-over-pandas` — Chose Polars for streaming group-by memory profile
- `no-orm` — Chose raw SQL because ORM obscured query plans we needed to tune
- `monorepo-not-microservices` — Chose monorepo for shared build caching

## benchmarks

Measured performance facts about the system. Include the workload, date, and config so they can be reproduced or invalidated.

Examples:
- `arrow-vs-parquet-load` — Arrow load 3.2x faster than Parquet on workload W (2026-04-02)
- `async-concurrency-sweet-spot` — Throughput plateaus at concurrency=12

## gotchas

Catch-all for non-obvious behavior that doesn't fit the above. Use sparingly — prefer a more specific category.

Examples:
- `iso-date-truncation` — ISO date parser silently drops sub-second precision
- `cli-exit-zero-on-warning` — CLI exits 0 even when warnings were printed

## When to make a new category

Introduce a new category only when at least two notes would fit it. One-off findings go in `gotchas/`. When you introduce a new category, record its definition and one example here on the same run.
