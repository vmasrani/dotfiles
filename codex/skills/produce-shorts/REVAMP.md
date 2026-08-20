# produce-shorts — revamp proposal

Audit of the first end-to-end field test, answering: *should we add particular scripts/tools
to the skill that we will always need in the future?*

**Short answer: yes, but the important ones are not new checks — they are one new
entrypoint and one new writer.** Roughly half the field-test defects were operator errors, and
every one of those was an operator error the skill *invited*: it stated a rule in prose and
provided no mechanism. A rule without a mechanism is a hope (FINDINGS 17o says this about
itself, and then the same run produced 102 concurrent Chromes).

Everything below is either **[V] verified** on this machine against the live workspace
`/Volumes/external/dev/podcast_shorts/episode-deutsch-raw/`, or **[I] inferred** from reading
the code. Timings are wall-clock measured today on the same box.

---

## 1. Taxonomy — six root causes

The ~20 findings cluster into six mechanisms. Each cluster is closable by **one** intervention;
today each is being closed one instance at a time, which is why the same shape keeps recurring
in the log (finding 4 → finding 7; finding 3 → finding 8 → finding 8a; finding 15 → 17f).

### Cluster A — Existence treated as validity  *(confirmed — the operator's hypothesis is right, and larger than stated)*

**Findings:** 17q, 17n, 22, 16, 17m, 17d, 17j, 17p, 17h, plus the `pgrep -c` preflight bug
recorded at `references/render-qc.md:60`.

**Shared mechanism.** A producer writes to the final path directly; a consumer then checks that
the path *exists* (or that a header *claims* something) and proceeds. Between those two facts
sits every way a write can go wrong — killed mid-stream, half-applied, syntactically accepted
but semantically dropped, or never executed at all.

The cluster is broader than files. The same mechanism produces:

| instance | what existed | what was never checked |
|---|---|---|
| 17q | `assets/aroll/S10.mp4`, 5 MB | a `moov` atom — died 8 min into a render |
| 17n | `format.duration` in the container | the decoded/muxed frame count |
| 22 | `candidates.yaml` | that the write completed |
| 16 | a YAML file PyYAML accepts | that the *consumer* (`js-yaml`) accepts it |
| 17j | a config field `outline_fraction: 0.10` | that the code path had ever run once |
| 17p | `BorderStyle: 3` in a well-formed `.ass` | that anything reads `BorderStyle` |
| 17h | 12 `provenance.json` files | that any two share a schema |
| 17m | a detached render's `.mp4` on disk | the process's exit status |
| render-qc.md:60 | `$(pgrep -c ...)` → `""` | that `-c` is not a macOS flag |

`run_ffmpeg` (`scripts/psmedia.py:210`) and `_write_yaml` (`scripts/pslib.py:390`) both write
straight to the destination path — **[V]** `extract_segments.py:399-400` passes `out_path`
directly to `extract()`, which hands it to ffmpeg as the output argument. There is no temp file
anywhere in the pipeline.

**Single intervention:** *nothing in this pipeline writes to its final path.* One helper in
`pslib`/`psmedia` — write to `<path>.tmp-<pid>`, validate it (ffprobe for media, re-parse for
YAML/JSON), `os.replace` into position. A killed write then leaves **no file**, which every
existing existence check already handles correctly. That single change closes 17q and 22
outright and is strictly better than the retry loop 17k proposes, because it makes the failure
*absent* rather than *plausible*.

The residue (17n, 16, 17j, 17h, 17p) is the same mechanism applied to non-file artifacts and is
closed by §2's decode check, strict loader, smoke test, and provenance writer.

### Cluster B — One truth, two lists, silent drift

**Findings:** 17a, 12, 17p, 17c, 14, 9a (lesson 1), 17i.

**Shared mechanism.** A fact about what the renderer will do is written down *a second time* —
in a Python validator, in a reference doc, in a style guide, in a storyboard's prose
justification — and the copy is not derived from the original. The copy then drifts, and because
the validator is green, the drift is invisible until render time or, worse, until a human looks
at the picture.

**[V]** The treatment vocabulary exists in **three** places that must agree by hand:
`remotion/src/Short.tsx:60,63,76,88,103` (the real list), `scripts/validate_clip.py:300`
(`_AROLL_TREATMENTS = ("splitscreen", "source-frame")` plus prefix tests at :316-319), and
`references/schemas.md:163-165` (prose). Finding 17a is the exact failure: storyboards asserted
a `blur-fill` treatment that did not exist, and `source-frame` — a *legitimate* name — absorbed
the intent and rendered 65% black.

**A correction to FINDINGS:** 17a is now partly stale. `blur-fill-<speaker>` **is** implemented
(**[V]** `Short.tsx:88-95`, with the dimmed-blur backdrop) and `validate_clip.py:316` knows it.
The second half of 17a is what remains open, and it is the dangerous half: `Short.tsx:60` maps
*any* unrecognised B-roll treatment to `contain`/`cover` before the A-roll throw at :108 — a
typo in a B-roll treatment still resolves to something plausible.

17i belongs here too and is easy to miss: the storyboard stage asserts `"verbatim runs 21
chars/sec here"` computed from spoken duration, while `clamp_windows()` gives the card the
following silence as well. Seven of nine condensations evaporated on contact with the real
windows. That is a *second implementation of the reading-speed model*, living in prose, drifting.

**Single intervention:** the renderer emits its own capability manifest and the Python side reads
it. One `remotion/capabilities.json` (or a `gen-props.mjs --print-capabilities`) listing valid
treatments, motion grammar, and consumed style fields; `validate_clip.py` imports it instead of
hard-coding. Symmetrically, the storyboard stage must call the *aligner's own* feasibility
function rather than restating a cps figure in prose.

### Cluster C — QC measures the container, never the picture

**Findings:** the headline, 9, 9a, 10, 11, 17a's consequence, gap E.

**Shared mechanism.** Every one of the 11 checks (**[V]** `qc_render.py:585-924`) is a container
property, a timing property, an audio property, or a manifest cross-reference. None opens a frame
and asks what it looks like. FINDINGS' observation that the letterbox defect *improved* two
checks is the sharpest evidence in the document: `cut_points` passed harder because a letterbox
cut is a large scene change, and subtitles on a black bar are maximally legible.

**Single intervention:** one intra-frame check (§2.4) plus promoting the contact sheet from
artifact to **required gate** (gap E). The second half matters as much as the first: green QC
means "eleven container properties held", and the skill currently lets that read as "the render
was looked at".

### Cluster D — A constant calibrated on one sample, promoted to a global

**Findings:** 3, 8, 8a, 4, 7, 6, 17l, gaps C and D.

**Shared mechanism.** A threshold measured on one clip becomes a pipeline constant; the next
clip's content sits on the other side of it. Finding 8 is the clean case — `0.08` was calibrated
on one clip and missed a real cut at `0.0789`, and the fix (per-render calibration at
`max(0.05, 2.5 × p95)`) is the *general* remedy this whole cluster needs.

The cluster's unpatched core is 17l: **`validate_subtitles.py` reports a boolean where the
useful signal is a margin.** Whisper's timings shift run to run, so re-aligning identical text
re-breaks the cards and a *different* card lands marginal. A card at 20.4 cps and a card at 12.0
cps produce byte-identical output today. Three clip-hours went into cards sitting within 0.5 cps
of the limit, and every agent rediscovered the cliff by falling off it.

**Single intervention:** **every threshold check reports distance-to-threshold, not pass/fail.**
This is one change applied uniformly — cps, loudness LU, duration ε, cut-point peak-vs-floor
(finding 8 already does this and FINDINGS explicitly credits the improvement: *"the next person
to hit this can see immediately whether the cut is absent or merely weak"*). Generalise it.

### Cluster E — The scripts model an exclusive local machine

**Findings:** 15, 15a, 17f, 17k, 17m, 17o, 27, and the `/private/tmp` staging folklore in 15.2.

**Shared mechanism.** Every script is written as if it owns the box and the disk. Reality: five
agents, one 10-logical/4-performance-core Mac, one external volume carrying `HOME`,
`node_modules`, source media and outputs. The pipeline has no representation of machine-wide
state, so it cannot refuse to start, cannot stage locally, cannot tell whose render a process is,
and cannot distinguish a killed render from a finished one.

Note the trail of *rules* issued to close this cluster: "every render goes through `queue`",
"invoke it by full path", "one render at a time machine-wide", "`--concurrency=3`",
"`--offthreadvideo-cache-size-in-bytes=...`", "run in the foreground", "stage to `/private/tmp`",
"pass absolute paths", "grep the log before claiming success". Nine rules, all correct, all in
prose, none mechanised — and the run that followed them produced 102 Chromes and a hard reboot.
FINDINGS 17o names this precisely and blames the orchestrator; I'd put it on the skill.

**Single intervention:** §3.

### Cluster F — A validator defect becomes an irreversible editorial decision

**Findings:** 17, 17e, 17l, 17i, gap C. *This one is not in the operator's list and is the most
expensive.*

**Shared mechanism.** When a checker is wrong, the only lever available to an agent is
**changing the content** — merge a card, delete a word, condense a line. So a checker bug
converts itself into an edit, and the edit is then burned into the master. 17e records it
exactly: four independent agents each hit `manifest_coverage`'s substring bug, each merged cards
to work around it, and *"fixing the checker does not undo the edits it forced."* On audit, one of
three changes on one clip turned out to be purely a validator artifact — recoverable only
because that agent happened to record which of its own changes were forced.

17i is the same shape with a stale constraint instead of a bug: seven of nine condensations were
made against a cps model the render stage does not use.

**Single intervention, two halves.**
1. **A validator that cannot match must SKIP loudly, never fail.** Finding 8a already
   established this principle for `cut_points` (`SKIPPED (unverifiable)` with the measured peak,
   never folded into the pass count) and it is the right precedent — *"a check that cannot
   succeed is worse than one that is absent: it blames a correct render."* Apply it to every
   checker whose failure mode is "I couldn't locate this", as distinct from "this is wrong".
2. **`known_deviations` in the provenance schema** (§2.2). A workaround-forced edit must be
   recorded *as a workaround*, permanently, not just while the agent that made it is still in
   the conversation.

---

## 2. The tooling proposal

Ordered by value-per-line. Costs are measured wall-clock on this box today.

### 2.0 `pslib.write_atomic` / `psmedia.ffmpeg_atomic` — **the single highest-value change**

*Purpose:* no artifact ever appears at its final path until it has been validated.

*Closes:* 17q, 22, and the whole file half of cluster A.
*Hooks:* `extract_segments.py:399`, `assemble_audio.py`, `align_subtitles.py`,
`_write_yaml` (`pslib.py:390`), the Remotion output, every encode profile.
*Cost:* **[V]** one `os.replace` plus one header-only `ffprobe` per media artifact — measured at
**45 ms/file** (5.37s for 118 A-roll assets). Effectively free.
*Why in the skill:* the failure that motivated it (17q) was caused by a machine reboot, not by an
operator. No habit protects against that; only the write pattern does. And the recovery cost —
one whole render, ~8.5 min — is 10,000× the check.

*Implementation note:* the ffprobe must run against the temp file **before** the rename, so the
rename is the commit. `ffprobe -v error -show_entries stream=codec_type` is sufficient; a file
with no `moov` fails it (**[V]** header-only probe errors on a truncated mp4).

### 2.1 `scripts/render_clip.py` — the single render entrypoint

*Purpose:* make queueing, capping, staging, verifying and provenance-writing **the only way to
render**, rather than nine prose rules.

*Closes:* 15, 15a, 17f, 17k, 17m, 17o, 20, 27, plus the `pgrep -c` preflight bug.
*Hooks:* replaces stage 8 steps 5-7 in `references/render-qc.md`.
*Cost:* preflight ~6s (asset sweep + machine probe); the render itself is unchanged.
*Why in the skill:* see cluster E. **[V]** The current documented preflight is itself defective —
`references/render-qc.md:55-63` documents `pgrep -c`'s macOS failure as a comment *below* a
snippet the operator is asked to type by hand each time. Documenting a footgun is not removing it.

Responsibilities, in order:
1. **Machine gate.** `pgrep -f chrome-headless-shell | wc -l`; 1-min load average vs performance
   cores; refuse with an actionable message, not a warning.
2. **Ownership map** (closes 27, in both directions). For every live render process, resolve
   pid → `--props` path → clip slug. FINDINGS' own conclusion is right and I'd go further: the
   reason 27 recurred twice *after being written down* is that the answer required an inference
   (`pgrep -fl | wc -l` returns a **count**, which carries no ownership information). Make it a
   lookup. Print a table; never let a count stand in for a name.
3. **Asset decode sweep** — every path `props.json` references, header-probed (2.0's helper).
   **[V] 5.37s for 118 files.** This is FINDINGS 17q's "cheap decode check at gate 2" and I
   endorse it, with one amendment: run it at *render start*, not only at gate 2. Gate 2 can be
   hours before the render, and 17q's corrupt file was created by a reboot *between* them.
4. **Local staging.** `clip.yaml`, `assets/`, `subtitles/`, `renders/v<N>-audio.wav` →
   `/private/tmp/<clip>`; output written back to the real `renders/`. ~100 MB/clip; FINDINGS 15.2
   measured ETA 20 min → 6 min. This is currently folklore passed agent to agent (17k names it as
   such). Folklore is exactly what a script is for.
5. **Invoke through `queue` by absolute path**, with `--concurrency`, `--timeout`, and
   `--offthreadvideo-cache-size-in-bytes` from `config/defaults.yaml` — one place, not a
   command-line the operator retypes.
6. **Foreground, with its own status line.** If detached is ever needed:
   `( cmd > log 2>&1; echo "exit=$?" >> log )`, grepped before any claim (17m).
7. **Verify the output** (2.3) and **write provenance** (2.2) before exiting 0.

### 2.2 `scripts/write_provenance.py` + a pydantic model

*Purpose:* derive the rights record from machine input instead of accepting typed input.

*Closes:* 17h entirely.
*Hooks:* end of `render_clip.py`; validated as a new `qc_render.py` check.
*Cost:* milliseconds.
*Why in the skill:* **[V] I reproduced FINDINGS' measurement and it is if anything understated.**
Twelve delivered clips carry **11 distinct top-level key sets**, ranging from 4 keys
(`hamlets-socks-excluded-middle`) to 13 (`probability-of-truth-is-zero`). Source is spelled
`source` in some, `sources` in others, **both** in four. FINDINGS' framing is exactly right:
*"divergence is not a diligence problem"* — one careful agent produced two shapes across its own
three clips in one hour. This is what hand-authoring is.

The constraint that matters (`generated_media == "none"`) held 12/12 — and it held on luck plus
five agents' diligence, with **[V]** no script anywhere reading, writing, or checking the file.
`rg 'provenance|generated_media' scripts/ remotion/` returns exactly one hit: a *docstring* at
`ingest.py:71`. The skill's single hardest constraint is enforced by prose.

Endorsed without amendment, including FINDINGS' three sequencing points, which are correct and
non-obvious:
- **writer before validator** — a validator dropped on 11 shapes produces 11 failures on
  substantively-correct files, and the rational response to that is to loosen the check;
- **`generated_media` must be DERIVED** from the asset provenance the pipeline already tracks —
  the agent whose typed `"none"` cannot be trusted is precisely the agent the field exists for;
- **regenerate, don't patch** the existing twelve.

Add `known_deviations` (cluster F) to the schema, as FINDINGS proposes.

### 2.3 `decoded_frame_count` — QC check 12  *(with a correction to FINDINGS)*

*Purpose:* verify what is in the file, not what the header claims.
*Closes:* 17n, the ffmpeg-concat frame-drop hazard in 17f, the partial-master half of 17m.

**FINDINGS prescribes `ffprobe -count_frames` and accepts its cost as the price of
trustworthiness. Measured, that trade is unnecessary.** On a delivered 42.1s / 1263-frame short:

| method | result | wall clock |
|---|---|---|
| `-count_frames` (full decode) | `nb_read_frames=1263` | **5.13s** |
| `-count_packets` (index only) | `nb_read_packets=1263` | **0.049s** |

**[V]** Identical answer, **105× cheaper**. For the failure this check exists for — a render
killed mid-write, a truncated file, a plausible header — the packet index is exactly the thing a
truncated file lacks, so packet counting is sufficient. At 0.05s it can run on every version and
every profile encode instead of being reserved as a one-shot gate.

Keep `-count_frames` for one job only: verifying a **chunked concat join** (17f), where the
concern is genuine decode-level drops that a correct packet index would still report. FINDINGS'
other two implementation notes stand: derive the expected count from `clip.yaml`
(`round(output.duration_s * fps)`), never a carried constant; and never poll it against a live
render.

### 2.4 `letterbox_dead_space` — QC check 13  *(endorsed; simpler implementation)*

*Purpose:* the first check that looks at the picture.
*Closes:* the headline, half of 9a, the consequence of 17a and 10.

FINDINGS' design is right in principle — inward row scan, luma **and** flatness, threshold 0.25,
with the stddev term correctly identified as the part a naive version gets wrong. My amendment is
implementation only: **ffmpeg's `cropdetect` already performs the inward scan at native decode
speed**, so the hand-rolled row loop is unnecessary.

**[V]** On the same 42.1s clip, `fps=0.3,cropdetect=limit=16:round=2:reset=1` over 11 sampled
frames ran in **0.95s wall** and reported `crop=…:1920:…` on every frame — i.e. zero vertical
dead space, correctly. (Side crop registered at 1076-1080 of 1080, ~0.4% — consistent with
FINDINGS' claim that nothing lands between 5% and 55% in practice.)

Proposed: `cropdetect` as the detector; apply FINDINGS' **stddev ≤ 4 flatness test only to the
band cropdetect reports**, which is where the night-sky-B-roll false positive would occur. Same
correctness, ~20 lines instead of a frame-scanning loop, ~1s per clip.

Also adopt the **cheaper pre-render form** FINDINGS proposes: in `extract_segments.py`, fail when
a staged A-roll job's height < 0.75 × profile height. That costs nothing and catches it before a
render rather than after one.

*Deferred:* `subject_scale` (face-share) needs a detector and a dependency. Worth it eventually —
9a is a clip a human rejected on sight at 11/11 — but it is the only proposal here that adds a
model to the toolchain, so it should follow the cheap checks, not lead them.

### 2.5 `just smoke` — execute the artifact-producing path once

*Purpose:* prove a changed code path *runs* before it is broadcast to N agents.

*Closes:* 17j, 12, 16, and the general class of 17d.
*Hooks:* a gate on editing any script in `scripts/` or `remotion/` during a batch.
*Cost:* one alignment on a ~5s fixture + `gen-props.mjs` + `npx remotion render --frames=0-0`.
Estimated 30-60s **[I]** (not measured — I did not run a render, per the read-only constraint).
*Why in the skill:* 17j is unanswerable any other way. Five new fields were put on the wrong
class; the crash is on the **first line of the new path**; it blocked five agents simultaneously;
the feature had never once taken effect while being described to those agents as a fact. FINDINGS
states the conclusion correctly: *"No review would have caught it and no type checker was in
play; only running it would."*

The fixture must **assert on the artifact's content, not on exit 0** — 17j's second rule:
*"Verify a style property by READING IT, never by observing that the run completed."* And parse
the `.ass` `Style:` line by **zipping against the `Format:` line by name**, never by positional
index; FINDINGS records its own verification harness being wrong twice this way.

### 2.6 Reading-speed **margin** report

*Purpose:* make the cliff visible before an agent falls off it.
*Closes:* 17l, most of 17i, gaps C and D.
*Hooks:* `validate_subtitles.py --json`.
*Cost:* free — the number is already computed and thrown away.

Emit per card: `cps`, `margin_cps`, `chars`, `window_s`, `hold_used_s / hold_available_s`, and
`owns_longest_rendered_line` (gap D — trimming that card pays twice). Ship gap C's ordered remedy
as machine output rather than doctrine: drop terminal punctuation → re-break lines → merge →
delete a **trailing** word, never a leading one (measured: dropping `"Yes,"` moved a card from
20.1 to **22.0** cps, because alignment re-anchors the window).

Same script should implement 17i's real fix: compute card feasibility at **storyboard** time
using the same `clamp_windows()` hold rule the aligner applies, so the design stage stops
condensing against a constraint the render stage does not have.

### 2.7 Small, free, unambiguous

| # | change | closes | cost |
|---|---|---|---|
| a | Duplicate-key-rejecting YAML loader in `pslib._read_yaml` | 16 | free |
| b | QC builds its check list **incrementally** and short-circuits on `duration_matches_manifest` — **[V]** `qc_render.py:1093` constructs `checks = [...]` eagerly, so `check_silence` at index 5 raises before *any* result is printed | 13 | free |
| c | `validate_clip.py` rejects a **dead seam** (contiguous source ranges + equal scale both sides): a 6-line scan at gate 2 instead of a render cycle | 17g | ms |
| d | `validate_clip.py` reads the renderer's capability manifest instead of `_AROLL_TREATMENTS` at line 300 | 17a (2nd half), 12 | ms |
| e | Merge `episode.yaml` config blocks in `load_config`, or delete the header comment claiming it | 14 | free |
| f | `scripts/encode_profile.py` — stage 8 step 6 is prose only; two documented traps (`true_peak_dbtp` targeted exactly always fails; omitting `-shortest` fails duration on AAC padding) each cost a full render round | 19 | ms |
| g | `sample_frame.py grid --at T1,T2,…`; unify `--out-dir`/`--out` | 24 | free |
| h | INFO listing other-speaker words inside a segment's source range | 25 | ms |

### 2.8 A test suite — the thing whose absence is invisible

The skill has none. **[V]** No `tests/` directory, no test recipe. FINDINGS says *"verified both
ways"* about a dozen times — natural-pause passes / injected hole fails; the 0.0789 cut confirms
/ freezing it fails; Lloyd's 18-of-20 with 2 skips / five clips at 11/11 with zero skips. That is
genuinely excellent verification work, and **none of it is captured**. The next edit to
`check_silence` or `check_cut_points` re-does it by hand or skips it.

Propose a `tests/fixtures/` micro-clip (5s, 2 segments, one hard cut) plus deliberately-broken
variants — truncated mp4, injected 1.0s digital hole, frozen cut, letterboxed segment, duplicate
YAML key, `motion: static 103%`. Each existing check gets one green and one red. This is the only
proposal that makes 17d's rule ("skill scripts are shared mutable state during a batch") into
something better than a warning.

---

## 3. If I could make only one structural change

> **SUPERSEDED — see §5.7.** This section was written inside the defect audit's frame: *the
> pipeline must produce correct clips*. The user has since watched both delivered clips and
> reported that the content is boring and irrelevant — i.e. the pipeline produced correct clips
> that should not have been made. Under that frame the single highest-value change moves to
> **gate 1** (§5.3). What follows remains the highest-value change *within the machinery*, and I
> would still make it second.

**Turn stage 8 from a documented procedure into `scripts/render_clip.py`, and make it the only
way to render.**

The argument is an asymmetry the field test made visible. Stages 1-7 and 9 are *scripts* — the
orchestrator sequences them and reads exit codes, exactly as `references/render-qc.md:3` promises.
Stage 8 is **prose plus a command line the operator retypes**, and it is where the run's most
expensive failures live: 15, 15a, 17f, 17k, 17m, 17o, 17q, 20, 27 — nine findings, one boundary.

Every remedy proposed for that boundary during the run was a *rule*: queue it, cap concurrency,
cap the cache, use the full path, run in the foreground, stage to tmp, pass absolute paths, grep
the log, don't reap what you didn't start. Every rule was correct. Compliance was taken on
report, and the outcome was 102 headless Chromes, a hard reboot, a 4× throughput tax paid by the
one agent who *did* queue, and real finished work destroyed by a watchdog. FINDINGS 17o draws the
conclusion itself — *"a rule without a measurement is a hope"* — and then the very next finding
(27) records the same class recurring twice more **after being written down**.

Writing it down is the intervention that has already been tried and has already failed, twice.

Two properties make this the right single change rather than one of the checks:

1. **It is where the compounding happens.** A corrupt asset (17q) is cheap on its own and costs a
   whole render because it is discovered at minute eight. A missing `--props` flag produces an
   error naming the wrong file. A detached render's partial mp4 is indistinguishable from a
   finished one. Every one of these is a *sequencing* defect, and sequencing is what a script is.
2. **It converts the other proposals from optional to automatic.** The asset sweep, the frame
   count, the local staging, the provenance write — all of them are things an operator must
   remember today. Behind one entrypoint they are the only path, and cluster A's mechanism
   (presence read as validity) loses its last foothold at the boundary where it was most
   expensive.

The alternative I considered and rejected is *"ship the 12th and 13th QC checks first."* They are
worth building (§2.3, §2.4) and the headline defect is real. But they are reactive: they catch a
bad render after 8.5 minutes of rendering, whereas the entrypoint prevents most of the ways a
render goes bad at all — and QC checks are the thing this pipeline is already good at adding.

---

## 4. What to remove or simplify

*A revamp that only adds is a worse skill.* Four removals, in increasing order of contentiousness.

### 4.1 Remove `source-frame` (finding 10)

It always succeeds, always validates, and for a 16:9 source in a 9:16 profile always produces
letterboxed junk. It is a textbook silent degraded fallback and violates the skill's own stated
doctrine. It was also the *vehicle* for the headline defect: 17a records a storyboard encoding
blur-fill intent as `treatment: source-frame` and rendering 65% black at 10/11 QC, precisely
because `source-frame` is a legitimate name that absorbs a wrong intent without complaint.

`blur-fill-<speaker>` now exists (**[V]** `Short.tsx:88`) and dominates it on every axis — nobody's
head is cropped, no dead space. Delete `source-frame`; the deletion is also the fix for
`Short.tsx:60`'s silent B-roll fallback, since removing the plausible sink forces the throw.

### 4.2 Remove the `.ass` round-trip — **the ASS format is doing no work here**

FINDINGS 17p is correct and its structural point is the more important half. **[V]** verified in
full:

- `align_subtitles.py` writes a completely styled `.ass`;
- `remotion/lib/ass.mjs:166-168` parses back exactly three style fields —
  `outlineColour`, `outline`, `shadow`;
- `gen-props.mjs:432-434` maps those three into props; `:308`'s `styleSignature` covers the same
  three plus font name and size;
- `Subtitles.tsx:31-33` redraws everything in CSS (`WebkitTextStroke`, `paintOrder`,
  `textShadow`);
- `BorderStyle` and `BackColour` are read by **nothing**.

So the pipeline writes libass's native format, validates it, and then declines to use libass —
keeping the file as a timing interchange and reimplementing its rendering half in CSS. The plate
option approved at the caption decision is a no-op that would have surfaced as *"the plate looks
wrong"* — a styling argument, not a bug report. And every future style knob inherits this failure
mode by default.

**Position: stop pretending the `.ass` carries style.** Make the interchange
`subtitles/v<N>.json` — timings, verbatim text, per-word emphasis, position — and let
`config/defaults.yaml` own drawing (17b's outline weight/colour, and the plate). Emit `.ass` only
as an optional sidecar export for platforms that want soft subs, generated *from* the JSON and
never read back.

I considered the opposite resolution — switch to libass via ffmpeg's `ass` filter and delete
`Subtitles.tsx` — and reject it for the caption layer specifically. Per-word emphasis colours,
auto-fit sizing measured against the real rendered line (gap D), and safe-zone positioning are
native in CSS and are fragile inline-override-tag work in ASS. The current design has the right
*renderer* and the wrong *interchange format*.

### 4.3 Is Remotion/Chrome earning its cost? — **Not today. Build the ffmpeg parity path and measure.**

Honest ledger. What Chrome genuinely buys that ffmpeg cannot:

1. **Type measured against real rendered text.** Gap D's coupling — the auto-fit divides the safe
   box by the widest *rendered* line — is only expressible in a layout engine. ffmpeg's `drawtext`
   cannot measure a string.
2. **Per-word emphasis, kerning, ligatures, real font shaping.**
3. **A typed manifest→render contract.** `parseProps`/`schema.ts` rejects a malformed props file
   at the boundary; an ffmpeg filtergraph fails somewhere in the middle of a string.
4. **Declarative motion/interpolation** (`motion.mjs`).

What it costs, all of it charged during this run: cluster E in its entirety — the unbounded
OffthreadVideo cache OOM-killing tabs (17f), the stranded font handle (15a), 102 concurrent
Chromes and a hard reboot (17o), ~8.5 min/clip and ~2 hours serialized for twelve clips (15a),
and the chunking + skip-if-present machinery that exists purely to make an 80-minute failure cost
10 minutes instead.

Now the decisive fact: **every treatment actually shipped is a two-filter ffmpeg graph.**
`blur-fill` = `gblur` + `scale` + `overlay`; `splitscreen` = `vstack`; `closeup`/`reaction` =
`crop` + `scale`; motion = `zoompan`; `crossfade-<N>f` = `xfade`; captions = the `ass` filter.
The visual vocabulary the pipeline can express today is 100% covered by ffmpeg, at plausibly
10-50× the throughput **[I]** and with no memory ceiling to hit.

**Position: keep Remotion for now, but build `scripts/render_ffmpeg.py` as a parity renderer for
the closed treatment set and shadow-render one delivered clip against it.** If frames match
within tolerance on the 12-clip corpus, ffmpeg becomes the default and Remotion becomes the
escape hatch for genuinely-DOM features. Objection (1) is answerable and answering it is an
improvement regardless: measure text once at **design** time (a one-shot headless pass, or
harfbuzz), bake the resulting px size into `clip.yaml`, and let ffmpeg draw it — which also fixes
gap D by making the coupling *visible in the manifest* instead of emergent at render.

I am not proposing the migration now, because the parity measurement has not been made and this
proposal's own rule is evidence over assertion. I am proposing that the measurement be made
before another twelve-clip batch pays cluster E's tax again. If ffmpeg holds parity, roughly half
the findings in this document stop being possible.

### 4.4 Simplify FINDINGS.md itself

918 lines, chronological, mixing patched / open / design-gap, with two superseded root causes
still narrated inline (15's contention theory, corrected by 17f; 17a's "blur-fill isn't
implemented", now shipped). It is an outstanding incident record and an unusable stage-time
reference — the skill's own doctrine is *"read the detail doc when you reach the stage."*

Split it: `references/hazards.md`, ~60 lines, indexed **by stage**, carrying only live hazards
and their one-line remedies; archive the narrative as `FINDINGS-run1.md`. Then prune what the
tooling makes redundant — every rule that becomes a script's behaviour should leave the prose
when the script lands, or the next operator gets nine rules again.

---

## Summary of disagreements with FINDINGS.md

| # | FINDINGS says | I found |
|---|---|---|
| 17n | use `ffprobe -count_frames`; its cost is the price of trust | **[V]** `-count_packets` returns the identical count **105× faster** (0.049s vs 5.13s) and is sufficient for the truncation failure it exists for. Reserve full decode for concat-join verification only |
| headline | hand-rolled inward row scan for `letterbox_dead_space` | **[V]** `cropdetect` does the scan natively in ~0.95s/clip; apply the (correct, essential) stddev flatness test only to the band it reports |
| 17a | blur-fill is not implemented | **[V]** it is now (`Short.tsx:88`, `validate_clip.py:316`). The open half is `Short.tsx:60` silently absorbing unknown B-roll treatments |
| 17h | 8 distinct provenance shapes across 12 files | **[V]** **11** distinct top-level key sets; four files carry both `source` and `sources` |
| 17q | atomic write **and** a decode sweep at gate 2 | Endorsed, but the sweep must also run at **render start** — 17q's corrupt file was created by a reboot *between* gate 2 and the render |
| 15 / 17f | both root causes still documented in `references/render-qc.md` | Consolidate to one. Two live explanations for one symptom is how two agents burned 6-8 attempts each chasing the font |
| 27 | rule: "never unilaterally kill a tree you did not start" | Correct, and it recurred twice after being written down. Make it a lookup (`render_clip.py ps`: pid → `--props` → clip), because the question requires ownership data that `pgrep \| wc -l` structurally cannot supply |

---

# 5. The content failure — this outranks everything above

*Added after the user watched both delivered clips.* Verdict: **the content is boring and
irrelevant.** That is a stage 2–3 failure. Everything §1–§4 audits — blur-fill, outline weight,
frame counts, provenance schemas — is polish on material that failed the only test that matters.
The audit is still correct; it is no longer the top of the list.

The measurements below are all **[V]** against the 12 delivered clips.

## 5.1 What gate 1 actually showed — the structural irony

Gate 1 exists precisely to prevent this, and it did not, because of what it presented.

**[V]** `selection-memo.md` is **200 lines** covering 12 selected clips. It contains 71 quoted
fragments; the longest is 50 words. The clips themselves carry **69–272 dialogue words each,
1,840 words in total**. So the human at gate 1 read a *curated selection of highlights, chosen by
the party proposing the clip*, amounting to a minority of the text, and never read any clip whole.

This is not an operator lapse. It is the specification. **[V]** `references/editorial.md:49`:

> Present to the user: the selection memo, per-clip duration, and the rejected-candidate list
> with reasons.

Memo, duration, rejects. The verbatim text is not in the gate contract at all. And the memo's
author is the senior editor — **the same agent whose selections are under review**. Gate 1 is a
defence counsel summarising its own case, and its summary is genuinely excellent advocacy: every
entry leads with *Central idea / Audience response / Hook / Payoff*, i.e. four claims about why
the clip is good, before any of its words.

The compounding detail: **the missing artifact was free.** **[V]** Every `clip.yaml` already
carries the full verbatim `dialogue` per segment (that is invariant 11's whole point). The
gate-1 transcript is a pure derivation of data that already existed, and the entire 12-clip set
is a **7-minute read**. The pipeline spent ~40 agent-hours and ~2 hours of serialized render on
material that could have been rejected in seven minutes of reading, using a file it could have
generated in milliseconds.

## 5.2 Why the content was boring — the mining and selection rubric

Three causes, all in the rubric rather than in any agent's judgement.

### (a) All nine miner scores measure well-formedness, not watchability

**[V]** `editorial.md:13-20` / `schemas.md:126-135`. The bar is: under three minutes; ONE
self-contained idea; strong hook; ends on insight/payoff; little outside context; clean edit
boundaries. The nine scores are `hook`, `standalone`, `central_idea`, `payoff`,
`edit_boundaries`, `visual_potential`, `missing_context`, `redundancy`, `risk`.

Read them as a set: **seven of nine are editor's hygiene** — is this thing well-shaped, complete,
non-repetitive, safe, cuttable. `hook` and `payoff` gesture at the viewer but are scored against
the *material's* structure, not against a viewer's state. **Not one criterion asks whether
somebody who has never heard of this person would keep watching.**

A clean-boundaried, self-contained, non-redundant, low-risk exposition of the excluded middle
scores 9s across the board and is boring. That is exactly what shipped.

Missing entirely, and each is scoreable from the transcript alone:

| proposed score | question | why it is the one that matters |
|---|---|---|
| `counterintuitive` | does this contradict what the target viewer currently believes? | the mechanism of a share |
| `stakes` | what does it cost the viewer to be wrong about this? | converts an argument into a reason to care |
| `concreteness` | is there a story, a number, an image — or only an argument? | the two clips that *do* have one (Lloyd's, hospital staffing) are the two the memo describes most vividly |
| `tension` | does somebody push back, in the clip, out loud? | see (c) |
| `quotable` | is there one line a viewer could repeat to somebody else? | the unit of spread |

And one **disqualifying binary** before any score: *would a viewer who does not know this person
watch fifteen seconds?* A candidate that fails it is not a low-scoring candidate, it is not a
candidate.

### (b) Selection was a filter dressed as a choice

**[V]** 12 selected from 35 — a 34% acceptance rate — against `editorial.md:37`'s instruction
*"three great clips beat eight passable ones."* Twelve survived. The instruction is right and
nothing enforced it, because "quality alone" is unfalsifiable at the point of use.

**Fix:** make the editor **rank all N candidates 1..N and defend only the top 3–5**, with the
rest presented as ranked-but-unselected. A ranking is falsifiable in a way a verdict is not, and
it changes what the gate asks the human: not *"approve these twelve"* but *"here are thirty-five
in order — where do you want the line?"*

Pair it with an explicit **kill quota** stated to the user at the gate, so a small number reads
as success rather than as the pipeline underperforming.

### (c) The clips are one man talking — measured

**[V]** Speaker distribution across all 122 timeline segments:

| speaker | segments | share |
|---|---|---|
| `guest1` | 104 | **85%** |
| `host1` | 15 | 12% |
| `host2` | 3 | 2% |

**Six of the twelve clips are single-speaker monologue end to end** (`no-games-of-chance`,
`no-observations-imply-the-future`, `pandemic-toilet-paper`, `pulsars-flashing-star`,
`the-future-is-never-like-the-past`, `trivial-but-bloody-hard`). The episode's title is
*"**Disagreeing** about Belief, Probability, and Truth"* and half the clips contain no
disagreement whatsoever.

This is a direct consequence of (a): a two-party exchange scores *worse* on `standalone` and
`edit_boundaries` than a clean monologue, so the rubric actively selects against the most
watchable material in the room. That is the single most fixable thing in this document.

### (d) The pipeline only ever subtracts — FINDINGS gaps A and B, confirmed

**[V]** Every selection-memo entry reads *"Internal cuts: none"* or, where cuts exist,
*"No word is removed and no word is reordered."* All twelve clips are a contiguous source region
minus some silence. FINDINGS gap A already established that **all four published human shorts
from this same episode are composites of non-adjacent regions**, and gap B that the published cut
**cold-opens on the punchline and then rewinds**.

So the human benchmark for this exact episode was available, was recorded in FINDINGS, and the
editorial stage still cannot express either structure.

**Fixes:**
- **Composite mandate.** For each selected clip the editor must either produce a non-contiguous
  structure — a cold open on the payoff then rewind, or a definition/example spliced in from
  elsewhere in the episode — or state in one line why contiguous is better here. Note this is
  cheap for the machinery: a non-adjacent splice is just another timeline segment with its own
  source range, which invariants 1–3 already handle and `assemble_audio.py` already builds.
- **Rival-cut benchmark, before gate 1.** One subagent receives the published human shorts of the
  same episode (or of the genre) and ranks our candidates against them, in writing. One agent,
  one pass, and it is the only mechanism proposed here that puts an *external* standard in front
  of the gate rather than an internal one. Every quality signal in the pipeline today is
  self-generated.

## 5.3 The gate-1 artifact — `transcript.md` per clip

*This is the change §5.7 argues is the single most important one.*

**What it is.** One file per candidate clip, at the clip's visible top level:
`clips/<slug>/transcript.md`. Contents, all derived — nothing typed:

1. Title, slug, duration, and the one-line logline. Nothing else evaluative.
2. **The complete verbatim text**, as continuous readable prose with speaker labels — assembled
   from the timeline's per-segment `dialogue`, in output order.
3. **Internal cuts marked inline**, e.g. `[— 1.60s trimmed —]` or `[— 11.65s removed: "Now, is
   this metaphysical probability?…" —]`, so the reader sees what was taken out *and its words*,
   not a claim that the removal was meaning-preserving.
4. **~20s of context before and after**, visually de-emphasised, so the reader can judge whether
   the clip stands alone rather than being told that it does.
5. For a composite (§5.2d), the source timestamp of each region, so a splice is visible as a
   splice.

**Cost:** milliseconds — every input already exists in `clip.yaml` and `transcript.json`.
**[V]** 1,840 words across all twelve.

**What the orchestrator presents at gate 1.** The transcripts, not the memo. Concretely, replace
`editorial.md:49` with: emit `gate1.md` concatenating every candidate's `transcript.md` in the
editor's ranked order; present that; then AskUserQuestion over the slugs. The selection memo
survives as an appendix the user may read *after* forming a view, and the rejected list stays —
it did real work (FINDINGS: gate 1 stopped B-roll spend on 20 rejected candidates).

**What makes it impossible to approve a clip whose text nobody read.** Two mechanisms, and the
distinction between them matters:

- *Enforceable:* `validate_clip.py` refuses to accept `status: approved_edit` unless
  `transcript.md` exists **and** its verbatim word count equals the timeline's total `dialogue`
  word count exactly. A stale or partial transcript is then a red, not a green — this is
  cluster A's lesson applied to the gate artifact itself. Every downstream stage already refuses
  to run on a clip that is not `approved_edit`, so this gates the whole pipeline for free.
- *Not enforceable, and should not be faked:* nothing can prove a human read prose. What the
  check buys is that **"there was nothing to read" becomes impossible**, and that the thing
  presented is the clip rather than an argument for it. Do not add a fake attestation checkbox;
  it would be a presence check standing in for a validity check, which is the mistake this whole
  document is about.

**The general principle worth stating in SKILL.md:** *the human gate presents the artifact, never
a summary of it.* Text is the cheapest available proxy for a finished short — 7 minutes against
40 agent-hours — and it was the one thing the gate omitted.

## 5.4 Storyboard — cut the prose

**[V]** 2,061 lines across 12 storyboards, mean 172. The largest,
`the-false-theory-that-bankrupted-lloyds/storyboard.md` at 231 lines, is **93 table lines and 109
non-blank prose lines — 54% prose.**

**[V]** `validate_clip.py:335` (`check_9_storyboard`) and `schemas.md:227-241` require exactly
one Timeline table and one Subtitle plan table with fixed headers, and state outright: *"Prose
sections around the tables are free-form and unvalidated."* So **100% of that prose is unread by
any machine** — and it is where the false claims live. That same file asserts:

> *"the renderer resolves each to the treatment the style guide defines for that speaker"*

The renderer does no such thing (**[V]** `Short.tsx:103` maps `closeup-*` to `fit: cover` and
nothing more). This is FINDINGS 17a's exact and most expensive class — a storyboard asserting
renderer behaviour that does not exist — still sitting unremarked in a delivered artifact.
**Cutting the prose is therefore not just ergonomics: it removes the habitat of cluster B.**

Proposed structure, target **≤40 lines plus the two tables**:

```markdown
# <slug>
**Idea:** one line.   **Hook:** one line.   **Payoff:** one line.

## Timeline
| Segment | Output | Source | Visual | Audio/Dialogue | Speaker | Shot/Transition |
...

## Subtitle plan
| Output | Verbatim text | Emphasis | Position | Notes |
...

## Decisions
- S04–S07: two-up stacked — Vaden's objection and Deutsch's reply overlap by 0.4s.
- S12: held wide, not cut — the pause is the joke.

## Open questions for gate 2
- ...
```

Rules: every Decisions bullet names a segment or asset ID; no bullet may assert what the renderer
does (that is the capability manifest's job, §2.7d); the visual-concept essay goes away entirely.
Add a soft check — `validate_clip.py` warns above ~40 non-table lines. A warning, not a failure:
a hard cap would be a threshold calibrated on one sample (cluster D).

## 5.5 Folder structure

**[V]** Today a clip directory holds twelve top-level entries, of which the human wants three:

```
.codex  .DS_Store  assets  clip.yaml  provenance.json
qc-v1.json  qc-v2.json  qc-v3.json  remotion  renders  storyboard.md  subtitles
```

Target:

```
clips/<slug>/
  transcript.md          # §5.3 — the gate-1 artifact
  storyboard.md          # §5.4 — terse
  <slug>.mp4             # the approved profile encode (hardlink/copy of .assets/renders/v<N>-<profile>.mp4)
  .assets/
    clip.yaml  props.json  provenance.json  qc-v<N>.json
    assets/  subtitles/  renders/  remotion/
```

### The migration is one substitution

Nearly every script already takes `CLIP_DIR` as an argument and resolves everything relative to
it. **Pass `<slug>/.assets` instead of `<slug>` and they all keep working unchanged** —
`extract_segments.py` (**[V]** `:399`, `clip_dir / out_dir / f"{name}.mp4"`), `assemble_audio.py`,
`align_subtitles.py`, `validate_subtitles.py`, `qc_render.py`. None of them needs to learn
anything about dotfolders.

**What actually breaks — three things, all small:**

1. **`gen-props.mjs`.** **[V]** `:88` resolves `<clip-dir>`; `:93-96` *requires* `--audio` and
   `--ass` to live inside it (`must live inside the clip dir`); `:413` symlinks that directory to
   `public/clip`. Point it at `.assets/` and all three constraints hold as-is.
2. **`validate_clip.py check_9`** reads `storyboard.md` from the clip dir — and `storyboard.md`
   is the one artifact moving *up*. This needs an explicit `--storyboard` path or a
   `../storyboard.md` default. **This is the single genuine code change in the migration.**
   Same for `transcript.md` under §5.3's new check.
3. **The delivered `<slug>.mp4`.** New concept — today the deliverable is
   `renders/v<N>-<profile>.mp4` and there is no stable "the final" path. A hardlink written by
   the delivery step (cheap, same filesystem) plus a `provenance.json` field naming which version
   it points at. Note this must be re-pointed on a v<N+1>, which makes it a cluster-A candidate:
   write it atomically (§2.0) and have QC verify it resolves to the version it claims.

### Does a dotfolder break Remotion or ffmpeg?

- **Remotion: no.** **[I]** The symlink is named `clip`, not `.assets` — `gen-props.mjs:413`
  creates `public/clip -> <dir>`, so the dot never appears in a served URL or in a `staticFile()`
  path. `public/` is served statically, not bundled, so no bundler dotfile rule applies. **[V]**
  `remotion/.gitignore` already ignores `public/clip`, confirming it is treated as generated.
  I did not run the bundler to confirm — this is the one claim here I could not measure.
- **ffmpeg: no.** Paths are passed explicitly; there is no globbing anywhere in the scripts.
- **`rg` and `fd`: YES, and this is the real cost.** **[V]** I reproduced it: `rg -l findme .`
  against `./.assets/clip.yaml` returns **nothing**; `rg -l --hidden findme .` finds it. Both
  tools skip hidden paths by default. Every agent's habitual `rg` inside a clip directory will
  silently return zero results — *an empty search reading as "nothing there" is precisely cluster
  A*, and it is the failure mode this document is otherwise trying to eliminate.

  Two honest options: keep `.assets/` as requested and **state the `--hidden` requirement in
  SKILL.md and in every documented command**, or name it `_assets/` — visible to `ls` only as a
  single underscore-prefixed entry, sorts to one side, and costs nothing in tooling. I lean
  `.assets/` per the request with the `--hidden` note, but the tradeoff should be a decision
  rather than a surprise.

- **While migrating:** delete `.DS_Store` and the stray `.codex/logs/` trees (FINDINGS 26) —
  they are currently inside the manifest-tracked asset tree.
- **Note:** `remotion/` is copied **per clip** today (**[V]** all 12 clip dirs hold their own).
  Hiding it does not reduce the 12 copies. Consolidating to one episode-level template would,
  but it collides with `render-qc.md:23`'s "one template copy serves one clip at a time"
  constraint — and under §2.1's serialized single render that constraint may no longer bind.
  Worth revisiting after `render_clip.py` lands; out of scope here.

## 5.6 Visual grammar — the capability exists and was used zero times

**The measurement is the whole argument.** **[V]** Treatments across all 122 segments of the 12
delivered clips:

| treatment | segments | share |
|---|---|---|
| `blur-fill-guest` | 100 | **82%** |
| `closeup-host` | 18 | 15% |
| `cover` (B-roll) | 4 | 3% |
| **`splitscreen`** | **0** | **0%** |

Four fifths of every delivered second is the same treatment on the same face.

And **split screen is fully implemented, stacked, end to end, exactly as requested**:

- **[V]** `extract_segments.py:29-31` — *"`splitscreen` → `<segment-id>-top.mp4` +
  `<segment-id>-bottom.mp4` … at target width × half target height (1080x960); the composition
  stacks them."*
- **[V]** `Short.tsx:63-73` — two `MediaLayer`s at `{top: 0, height: '50%'}` and
  `{top: '50%', height: '50%'}`.
- **[V]** `Short.tsx:64` already **throws unless exactly 2 sources** — "never three" is enforced
  in the renderer today.

So the two-up stacked look the user is asking for needed no code. It needed a decision, and
nothing in the skill makes one. **[V]** `storyboard.md:17` gives the only guidance —

> a static talking head longer than ~8–10s usually wants a reframe, zoom nudge, reaction cut, or
> B-roll overlay — but only where it serves the dialogue. **Variation for its own sake is the
> disease, not the cure.**

— which a per-clip director reasonably reads as licence to hold. Twelve directors read it
independently and eleven-plus held. FINDINGS' complementary observation (host full-bleed against
guest banded, in one clip) is the same root: **unguided per-clip taste produces both monotony and
inconsistency, and neither is visible from any artifact the pipeline produces.**

### Make alternation a computed plan, not a director's taste

**`scripts/plan_visuals.py`** — reads the locked timeline plus the word-level transcript and
emits a *proposed* treatment per segment. The director may override any of them, but must record
the reason as a Decisions bullet naming the segment (§5.4). Every rule below is computable from
data already in `clip.yaml`:

1. **Speaker change → cut to that speaker's solo.** This is the requested faster face-cutting,
   and it closes FINDINGS 11 as a side effect: `speaker` is in the manifest today and **drives
   nothing** — a clip shipped with 13 segments declaring `host1` while three people were visibly
   talking, validator green. Wiring `speaker → treatment` makes the field load-bearing, which is
   what makes it checkable.
2. **Two-up stacked when both parties are live** — a question and its answer within ~2s, an
   interruption, an overlap, an audible agreement. Detected from word timings, not taste.
   **[V]** Six of twelve clips have exactly two speakers in their timeline and are immediate
   candidates; the other six are monologues and §5.2c is the fix for those.
3. **Never three** — already enforced at render (`Short.tsx:64`). Move it to gate 2:
   `validate_clip.py` rejects a `splitscreen` segment that does not resolve to exactly 2
   speakers, so it costs seconds instead of a render (same reasoning as FINDINGS 17g).
4. **Dwell ceiling** — no single treatment held continuously beyond `N` seconds, `N` from
   `config/defaults.yaml`. This is the mechanised form of the "~8–10s" prose that produced 82%.
5. **Target a distribution, not a rule** — per clip: at least one splitscreen where a two-party
   exchange exists, solo-face in the majority, **no single treatment above ~60%**. Deliberate
   variation is a property of a *distribution*; uniform application is what produced the current
   82%, and a rule applied uniformly would just produce a different 82%.

**`visual_variety` — QC check 14.** Reports the achieved histogram and the longest
single-treatment dwell, **margin-style rather than pass/fail** (cluster D): a clip at 61% and a
clip at 95% must not print identically. Cost: reads `clip.yaml` only — milliseconds, no decode.
This is the one check that would have shown `100 / 18 / 4 / 0` *at the time*, on every clip,
instead of in an audit after delivery.

**Prerequisite:** fix `panel_crops`' hard-coded halves (FINDINGS 9) *before* splitscreen goes
into volume. **[V]** `extract_segments.py:191,200` forces top = left half, bottom = right half,
and `:209` errors when two preferred crops land in the same half. A composite whose large panel
straddles the midline cannot be centred — and every splitscreen segment will meet this.

**Caption interaction** (captions are being specified separately — flagging, not designing):
the two-up stacked layout puts a face in the **lower** half of the frame. A caption moving *off*
the bottom is compatible; a caption in the vertical middle would land on the panel seam, which is
the worst position in that layout. So the caption spec should carry a **per-treatment position**,
not one global position — `bottom-center` for solo, something else for splitscreen. Worth handing
to the caption researcher now, before their spec assumes a single value.

## 5.7 Revised: the one structural change

**Move gate 1 from reading *about* the clips to reading *the clips*.** Concretely §5.3: every
candidate gets a derived `transcript.md` carrying its complete verbatim text with cuts marked;
the orchestrator presents those instead of the selection memo; and no clip can reach
`approved_edit` without one that matches its timeline word-for-word.

The argument is a cost ratio, and it is not close.

Every defect in §1 costs a render, an hour, or in the worst case a reboot. **This one cost the
entire run.** Twelve clips were carried through storyboarding, B-roll research, critique, forced
alignment, ~2 hours of serialized rendering, and in several cases three QC versions —
**[V]** `a-good-way-of-killing-people` alone holds `qc-v1`, `qc-v2`, `qc-v3` and six render
outputs — on material the user rejected on sight. Roughly 40 agent-hours produced two delivered
clips that should not have been made.

Three properties make it the right single change:

1. **It is the cheapest fix in this document, by a wide margin.** The artifact is a pure
   derivation of data that already exists in every `clip.yaml`. **[V]** 1,840 words across all
   twelve clips — a seven-minute read against forty agent-hours. Nothing else in this proposal
   has that ratio.
2. **It is the only change that can reject work before it is done.** Every other proposal here —
   the atomic writes, the decode sweep, the frame count, the letterbox check, `render_clip.py` —
   makes the *doing* more reliable. None of them can tell you the thing was not worth doing.
   Gate 1 is the only place in the pipeline where that question is asked, and it was asked with
   the wrong evidence in front of it.
3. **It generalises to a rule the skill can state and check:** *a human gate presents the
   artifact, never a summary of it.* Gate 2 has the same latent defect — it presents a storyboard
   (a plan) rather than anything watchable — and FINDINGS gap E already reached the same
   conclusion from the far end of the pipeline: *"a green QC does not mean the render was looked
   at; make the contact-sheet review a required gate rather than an artifact."* Three gates, one
   principle.

**Revised order of work.** §5.3 (gate-1 transcripts) and §5.2's rubric changes first — they are
days of work and they determine whether anything downstream is worth building. Then §2.0 (atomic
writes) and §2.1 (`render_clip.py`), which remain the highest-value changes within the machinery.
Then §5.6's `plan_visuals.py`, §5.4/§5.5's document and layout cleanup, and the QC checks in §2.

The reordering is the finding. The defect audit was measuring how well the pipeline hits what it
aims at; the user's verdict is about where it was aiming.
