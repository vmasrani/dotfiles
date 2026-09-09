# Worked example — fast-delta (byte-granular snapshot/delta engine), 2026-08

For calibration: what each phase produced on a real run, and the moments where the analysis changed direction. Do not copy its numbers; copy its moves.

## The bet
A persistent suffix-array/FM-index over a reference (later: over a whole corpus) that streams new snapshots of large binaries (SQLite/Postgres files, VM/container images, data exports) through it and emits `COPY/INSERT` recipes; byte-identical restore. Claimed edge: 2–10× fewer bytes per snapshot than chunk dedup. Claimed risk: an exact index is too slow / memory-hungry vs hash-based delta tools.

## Phase 1 — the 2×2 and the axes
Rows: chunk-granular vs byte-granular. Columns: no reference state (global hash set) vs reference-aware matching. Incumbents (EBS/ZFS block snapshots, restic/borg CDC) sit in chunk × global; specialist delta tools (zstd `--patch-from`, xdelta3, HDiffPatch, bsdiff) in byte × pairwise-reference. The empty cell: byte × everything-ever-seen.
- R = bytes_incumbent / bytes_ours per snapshot vs 8 KiB-block proxy and restic.
- s = throughput_ours / throughput_zstd-patch-from-3, per target, after the reference index is built (index build reported separately; many-vs-one curve as the fleet number).

## Phase 2 — criteria (fixed in the issue before any code) and the experiment
NO-GO: bytes not ≤ 1/3 of block proxy and ≤ 1/2 of restic on DB/image corpora, or s < 0.1 with no obvious fix, or consistently larger than xdelta3. GO: ≤ 1/5 of block proxy on ≥ 2 DB/image corpora, within 2× of HDiffPatch/bsdiff, s ≥ 1/3 or many-vs-one crossing zstd by N ≤ 10. Five real corpora (SQLite and Postgres built from a public wiki dump plus its real recent-changes replayed; consecutive Docker image tags; monthly Wikimedia SQL dumps; consecutive Firefox tarballs), all baselines installed and versioned, sha256 restore check per cell, everything under a serialising job spooler.

## What the data did
- First probe: DB pair 8× fewer bytes than the block proxy, parity with zstd on bytes, encode 6× slower than zstd. Second probe (rebuilt container image): **200× slower** than zstd — every literal byte paid a full SA search. This is the class of surprise the "unfriendly workload" rule exists for.
- Two exact, parse-preserving optimisations (LCP-bounded search; a min_match-gram membership filter so literal positions skip the search) took the DB pair to **6× faster than zstd** and the image pair to ~7× slower — 28–40× cumulative — without changing a byte of output (proved by a differential test against a search-everything oracle, which also caught a real false-negative bug in a parallel build). The "with no obvious fix" clause earned its place.
- Convention fix made before results: compare the *compressed* recipe to baselines because every baseline patch format is entropy-coded; verdict computed on both bases with a sensitivity line.
- The Postgres tar corpus turned out adversarial for fixed-block tools (an 80 KB heap-file growth shifted the whole tail → 76 % of blocks "changed" for ~300 row edits). Kept and documented: it is exactly the axis that separates fixed-block from shift-aware tools.

## Phase 3 — TAM as SAM(R, s)
Pools: cloud snapshot storage/egress, enterprise backup software + appliances (k = 0.4), BaaS/DPaaS, registries; speed-driven pool: OTA/fleet delta generation. Table showed: below s ≈ 0.1 ratio is irrelevant; between 0.1 and 1 doubling speed is worth ~10× doubling ratio; GO line (s = 0.33, R = 4) ≈ $0.55–0.6 B SAM; SOM at 2–5 % ≈ $10–30 M ARR → 20–60 customers at $0.2–1 M/yr. That is an infra-engine business, not a broad product.

## Phase 4 — who pays
An "average enterprise" doesn't buy this; it arrives inside Veeam/Rubrik/AWS. Operators with a PB-scale snapshot + replication bill ($600k+/yr → $100k–1M/yr deals); backup vendors as OEM ($0.5–2M/yr if ratio is still a paid differentiator; trust barrier for a startup engine in the restore path); OTA/distribution vendors who pay for any-version-to-latest generation at bsdiff quality 50× faster (a capability, not a ratio). Nobody pays where data is compressed/encrypted at rest.

## Phase 5 — the category question
Not new: many-vs-one (zstd's CDict amortises a reference in the library API), one-server-many-clients (rsync/zsync/casync), global dedup (the whole chunk column). New: any-to-any delta on demand across every version ever shipped; byte-content search across snapshots without restore (security/compliance buyer); containment/lineage. Preconditions flagged: FM-index path (SA is 5n RAM), append/epoch, an any-to-any measurement. Sequencing: wedge inside an existing budget → corpus → expansion; category creation named as the trap.

## Phase 6 — named customer
Discord desktop client: host + independently-updated modules, tens of millions of desktop users, many far behind the current version, Squirrel deltas only adjacent-version. Offer: any-installed-version → latest, on demand, at bsdiff ratio, all three OSes, reference = files on the user's disk (uncompressed, so the compressed-at-rest objection doesn't apply). CDN egress saving ~$0.3–1M/yr; UX and removed patch-matrix engineering as the real argument; deal $100–300k/yr — a design partner, not a whale. Pilot runnable on public builds from the update manifests: (older → latest) for the last ~10 versions vs full download vs adjacent-delta chain vs zstd vs ours.

## The user's arc, and the correction that mattered
"We compress far better than existing solutions" → corrected: far better than the *incumbent*, parity with the *specialists*, and the risk is on speed. "This seems like a dead end… we have to be OOM better for people to care" → separated: OOM better than the incumbent is real on the core workload; the sober part is market shape (few, slow, trust-heavy deals) not the tech. Decision: finish the run, write the report regardless, front two pages for the decision, appendix for everything else.
