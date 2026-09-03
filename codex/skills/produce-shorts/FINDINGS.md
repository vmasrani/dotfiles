# produce-shorts — findings from the first end-to-end run

Two episodes, ~40 agent-hours, 13 clips taken to render. Everything below was reproduced
against real media; nothing here is speculative. Patched items were verified by experiment
in both directions (the fix works AND the check still catches the defect it exists for).

---

## The headline: QC measures everything except what the video looks like

A control clip passed **11/11 QC checks** while **40.9% of its runtime** was a letterboxed
band on black with faces at 6.5% of frame height — roughly 8mm tall on a phone.

Every check is a container property, a timing property, an audio property, or a manifest
cross-reference. Not one inspects intra-frame composition. Worse, the defect *improved*
two checks: a letterbox cut is a large scene change, so `cut_points` passed harder, and
subtitles drawn on a black bar are maximally legible.

| check | why it was blind |
|---|---|
| `black_frames` | `blackdetect` uses a whole-picture ratio; 31.7% bright content never trips it |
| `frozen_frames` | bars are static but tiles move, so frame delta is non-zero |
| `container_matches_profile` | the container was correct; the content inside it was not |
| `duration`/`loudness`/`clipping`/`silence` | time and audio only |
| `cut_points` | actively passed *because* of the defect |
| `subtitles_present` | defect made subtitles more legible |
| `assets_tracked` | presence + sha256 only |
| `manifest_agreement` | agreed precisely because the manifest asked for this |

**A render can be geometrically perfect, correctly timed, correctly loud, and visually
worthless, and score 11/11.**

### Recommended: `letterbox_dead_space` (12th check)

Per timeline segment, sample `K = max(3, ceil(duration_s * 2))` frames. Scan inward from
top and bottom; count consecutive full-width rows with **both** mean luma ≤ 16/255 **and**
per-row luma stddev ≤ 4. Fail when `(median_top + median_bottom) / height > 0.25` for any
`aroll` segment, or `broll` with treatment `cover`. Exempt `contain`/`letterbox` — declared
intent, and the manifest already says so.

- **Why 0.25:** a bright line, not a tuned knob. 16:9-in-9:16 = 68.3%, 4:3 = 58%, 3:2 = 63%;
  full-bleed sits at ~0%. Nothing lands between 5% and 55% in practice.
- **Why the stddev term:** without it, genuinely dark footage (a night-sky B-roll plate)
  trips the test. Requiring *flatness* distinguishes a synthetic bar from dark image content.
  This is the part a naive luma-only version gets wrong.

Cheaper pre-render form: in `extract_segments.py`, fail when a staged A-roll job's height
< 0.75 × profile height. Catches it before a render instead of after.

Follow-on (needs a face detector): `subject_scale` — median face bbox height as a fraction
of frame height; warn < 8%, fail < 5%. Catches the grid-tile case even when *not*
letterboxed, e.g. a cover-crop of a composite that fills the frame with tiny faces.

---

## PATCHED (13) — all verified by measurement

### 1. `extract_segments.py` — `-ss` after `-i` (95× slowdown)
Output seeking decoded the full 99-minute episode from frame 0 for every cut: **107s to cut
a 3s segment**. Moved `-ss` before `-i`; used `-t` not `-to`, because after an input `-ss`
the `-to` value is relative to the post-seek timeline and silently produces the wrong length.

**Measured: 45.81s → 0.48s, identical duration, byte-identical first frame (same SHA-256).**

### 2. `validate_clip.py` — invariant 11: dialogue must cover audible audio
Invariant 8 checked subtitles ⊆ `dialogue` — **circular**, because both derive from the same
possibly-truncated word set. A `source_in` of 5694.26 against a word starting at 5694.258
dropped "to" from `dialogue` while leaving 76ms audible at full speech level. Forced
alignment matched the shorter text; every layer agreed; the first syllable of the delivered
short shipped uncaptioned.

New invariant: per segment, transcript words ≥50% audible within `[source_in, source_out)`
must equal `dialogue.split()`. Missing transcript → **visible skip**, never a silent pass.

**This defect occurred twice independently in 13 clips** (`"to"`, and `"I'm"` clipped off the
sentence a clip's own title quoted). Both were caught by humans reading transcripts.

### 3. `qc_render.py` — `cut_points` rejected every same-camera jump cut
Threshold was a flat 0.30. Scene scores are cleanly bimodal: cross-camera ~0.94, same-camera
jump cuts 0.109–0.205, noise floor ~0.07. A locked-off camera 1.1s apart *cannot* produce a
0.30 delta — physics, not a bad edit.

Split into two sensitivities rather than lowering one number: a gentle floor confirms expected
cuts; `SCENE_THRESHOLD = 0.30` still governs what counts as an *unexpected* visual change.
The confirm floor was first set to a constant 0.08 — see finding 8 for why that was wrong.

### 4. `qc_render.py` — `silence` flagged natural pauses
Flagged a 0.47s pause that exists in the uncut source at **0.854s** — the edit *shortened* a
natural pause and QC failed it. Now maps each flagged interval back through the timeline into
the untouched source and excuses it if the source already had that much silence.

Two subtleties: a pause spanning a cut is the silent **tail** of one segment plus the silent
**head** of the next, so the natural durations must be **summed**, not maxed. And an exact
comparison fails on re-encode measurement noise, so `NATURAL_PAUSE_TOLERANCE_S = 0.10`.

**Verified both ways:** natural pause now passes; an injected 1.0s digital hole at a cut
still fails.

### 5. `align_subtitles.py` — cards never held into following silence
Event windows ran first-matched-word → last-matched-word, ignoring the silence after. When a
speaker paused, the card was forced faster than necessary, and the only way to satisfy the
cps limit was **deleting words from the caption** — so the subtitle stopped matching the
audio. One clip had to drop "clarifying" from "Actually, one clarifying question." while the
speaker paused 1.60s immediately after it.

`clamp_windows()` now holds a card into the gap before the next card for exactly as long as
its reading speed requires. Never overlaps the next card, never extends a comfortable card.

**Verified:** verbatim restored, peak cps 19.8 → 19.4, and on the reference clip held cards
consumed 0.08s / 0.02s / 0.27s of 1.60s / 1.40s / 1.04s available — **at most 26% of margin,
no card ceiling-limited.**

### 6. `config/defaults.yaml` — `max_chars_per_line` 42 → 32
The renderer auto-fits type to the longest line, so one 42-char card shrinks captions for the
whole clip. **Measured: 45px → 57px (+27%).**

### 7. `qc_render.py` — the whole-clip silence sweep had no source comparison
Finding 4 fixed the per-cut probe and missed that the **whole-clip** sweep is a separate code
path with the same flaw. It failed a clip on four silences that the speaker had simply taken —
and several storyboards deliberately keep those beats ("those are the comic beats"), so this
would have reported a red on every clip that holds a pause.

Diagnosing it exposed a second problem: probing the source at the render's own `-50dB` floor
found nothing, which looked like a genuine audio hole. `volumedetect` settled it — source mean
**-54.0 dB** vs render **-57.0 dB**, both plainly quiet, sitting either side of the line. So
source probing now uses `SOURCE_SILENCE_NOISE_DB = "-45dB"`: the question is *"had the speaker
paused?"*, not *"was the source digitally silent?"*. Speech sits far above -45 dB, so a real
hole still fails.

**Verified three ways:** the red clip passes ("4 pause(s) present in the source"), the
reference clip stays 11/11, and an injected 1.0s digital hole still fails.

### 8. `qc_render.py` — the confirm threshold cannot be a constant
The 0.08 from finding 3 was calibrated on one clip and **missed a real cut on the next** at
0.0789. That cut was not marginal: it was the clear local maximum of its window, 3.5× the
clip's own noise. How large a same-camera jump cut registers depends on the shot — crop
tightness, how much the speaker moved, sensor noise — so no constant can serve every clip.

Now calibrated per render: take every frame ≥0.5s from **any** declared boundary (so neither
the cut under test nor an adjacent one inflates the floor it is judged by), and confirm at
`max(0.05, 2.5 × p95)`.

**Measured over 15 declared hard cuts across two clips: every real cut lands at 3.5–68.6× p95;
a cut that failed to render sits near 1.0×.** The 2.5× line splits that gap with the weakest
real cut clearing by 38% and the p99 noise level (1.7×) staying below. **Verified both ways:**
the 0.0789 cut now confirms at a computed floor of 0.0570, and freezing the video across that
cut fails with `S06->S07 @29.62s (peak 0.0000)`.

The `missing` message now reports the measured peak, so the next person to hit this can see
immediately whether the cut is absent or merely weak.

### 8a. `qc_render.py` — `cut_points` demanded a scene change that cannot exist
Reported by a producing agent against Lloyd's clip 1, and correct. `S15->S16 @85.12s` has
`source_out == source_in` on one file: the source runs straight through, and the split exists
only to change camera motion. There is no visual discontinuity by construction, so no
threshold — noise-calibrated or otherwise — can ever pass it. **A check that cannot succeed
is worse than one that is absent**: it blames a correct render.

Fixing that exposed the general case. `S11->S12 @63.75s` removes 0.5s from a static talking
head; the speaker barely moved, so it scores **0.0271** against real camera changes measured
at **>=0.0789**. Whether a same-shot jump registers depends on how much the subject happened
to move — which the pipeline neither controls nor promises.

The first patch was wrong and the measurement caught it: skipping every same-file /
same-treatment boundary structurally skipped **16 of 20** on Lloyd's, including ones peaking
at 0.1922 that were plainly detected. That trades away real coverage to fix two boundaries.

The shipped fix is **confirm first, categorise second**. Every hard cut is checked; one that
registers is verified regardless of category. Only an *unregistered* one is categorised: a
guaranteed-visible boundary (different camera or different treatment) still **fails**, while
a same-shot boundary is reported as `SKIPPED (unverifiable)` with its reason and measured
peak. A skip is never folded into the pass count — "verified" and "not verifiable" read
differently on a green check as much as on a red one.

Verified: Lloyd's 18/20 confirmed + 2 skipped (0.0271, 0.0108), 11/11 green. All five
previously-green clips re-ran 11/11 with **zero skips** — the relaxation engages only where a
boundary genuinely did not register, so no coverage was silently lost.

---

## OPEN — correctness

### 9. `preferred_crop` is episode-global; `panel_crops()` hard-codes halves
**Now has a confirmed shipping instance — see 9a.**
A speaker who is full-frame in one region and a grid tile in another cannot have two
treatments — the root cause of the 40.9% letterbox. And `panel_crops()` forces top = left
half, bottom = right half, so a composite whose large panel straddles the midline cannot be
centred. **Fix:** optional per-segment `visual.crop`, preferred over `preferred_crop`; allow
arbitrary per-panel rectangles with the half-rule as fallback.

### 9a. The episode-global crop clips a speaker who moves — and QC cannot see it
A producing agent held Lloyd's clip 1 on the contact sheet: Deutsch's head tight to the top
edge across 18 segments, face ~65-70% of frame height. It attributed this to an extra ~1.3x
zoom in `extract_segments.py`. That attribution is wrong, and measuring it is what found the
real defect:

- `center_crop(1280, 720, 9, 16)` returns `(405, 720, 437, 0)` — **all 720 source rows kept**,
  width cropped only. The path cannot clip vertically.
- Rendering the crop by hand (`crop=405:720:437:0,scale=1080:1920`) reproduces the produced
  asset essentially exactly. `extract_segments.py` is faithful.
- The difference is in the **source**. At one timestamp Deutsch sits back (head top ~15% down,
  bookshelf visible); at 3530s he leans forward and sits higher (~10%, headroom nearly gone).
  Same correct crop, different subject position.

So finding #9 is not theoretical: one fixed crop per speaker cannot track someone over a
99-minute recording, and where he leans in, the framing leaves the style guide's range.

Two compounding lessons:

1. **The style guide carried a wrong number that hid this.** It claimed faces fill "~40-45%
   of frame height"; measured, it is ~69% and ~72%. That number was written off contact-sheet
   tiles too small to judge from. Corrected in the episode's `style-guide.md`.
2. **This is exactly the class the missing `letterbox_dead_space` check does not cover.** QC
   went 11/11 on a clip whose framing a human rejected on sight. Composition — headroom, face
   share of frame — is measurable and currently measured by nobody.

**Fix:** per-segment `visual.crop` (as #9 proposes), plus a headroom/face-share check so
"green" stops meaning "nobody looked".

### 10. `source-frame` is a silent degraded fallback
It always succeeds, always validates, and for a 16:9 source in a 9:16 profile always produces
letterboxed junk. **Fix:** reject it for mismatched aspect profiles with an actionable error
naming the crop to use instead — or remove it.

### 11. No cross-check between `speaker` and `treatment`
A clip shipped with all 13 segments declaring `speaker: host1` while three different people
were visibly talking, and treatments (`reaction-guest1`) contradicting the label. Validator
green. Cosmetic on a single-source episode; on any episode where speaker drives track
selection it puts the wrong face on screen.

### 12. `motion.mjs` and `validate_clip.py` disagree on grammar
`motion: static 100%` passes the Python validator and crashes the JS renderer
(`unsupported motion string`). A manifest can be fully green and unrenderable. **Fix:** accept
`static|none|hold|locked` with optional trailing `<n>%`, or reject it in both.

### 13. A short render crashes QC in an unrelated check
QC'ing a 62s render against a 93s manifest does not report the duration mismatch. `check_silence`
runs first, builds its probe window from the manifest's `eof`, and hands ffmpeg `-t -7.425` — so
the run dies on an opaque `atrim ... out of range` instead of on `duration_matches_manifest`,
which was sitting right there with the actual diagnosis. Hit accidentally while building a
negative test; a truncated or interrupted encode is the realistic way in.

**Fix:** clamp probe windows to the measured render duration, and reject a negative window
length with a message naming the mismatch. Cheaper still: let the duration check short-circuit,
since every later check is measuring a file already known to be the wrong length.

### 14. Config override is documented but not implemented
`defaults.yaml`'s header says episode values win; `load_config` reads only the config file and
never merges `episode.yaml`'s blocks. Workaround was a full copy threaded through five scripts
via `--config`. **Fix:** merge the blocks, or delete the comment.

---

### 15. Long renders die on a stranded font handle — contention only sets the rate
Five agents rendering concurrently on a 16 GB box drove load average to 25/48/52 and one
agent's throughput from 41 to 7.6 frames/min. Every render then died the same way — and the
error named the wrong subsystem:

1. Chrome is OOM-killed mid-render → `Could not extract frame from compositor Error: Request
   closed` (or `The browser crashed while rendering frame N ... target-closed`)
2. Remotion recycles the page, which re-runs `src/fonts.ts`
3. that page's `delayRender("loading the bundled Inter font")` never resolves
4. the render dies reporting a **font timeout**

So finding 15 below ("fonts.ts loses a race") is real but is *not* what these agents were
hitting, and `--timeout` is useless against it: 180000 → 300000 moved the message from "not
cleared after 178000ms" to "after 298000ms" and changed nothing. Two agents each burned 6-8
attempts before root-causing it, one of them chasing the font red herring.

**The rate data settles the mechanism.** One agent measured **209 frames in 300s = 42 f/min,
healthy, right up to frame 570 — then instant death.** That is not gradual starvation.

**And an exclusive box does not fix it.** The same agent lost a render at frame 883 while the
machine was actively clearing. Failure frames across nine attempts — 244, 244, 268, 505, 570,
847, 883, 1369, 1980 — span three-way, two-way and effectively exclusive machine use. So
contention raises the *rate* of compositor drops but is not the cause, and serializing renders
is necessary-but-not-sufficient. **This was patched — see finding 15a.** Any framing of the
form "N concurrent renders is fatal, fewer is safe" is wrong.

**Three fixes, in order of value:**
1. **Serialize the browser stage machine-wide.** Every other stage parallelises fine. This box
   already has a 1-slot job queue (`queue <cmd>`); the skill should simply tell agents to
   prefix the Remotion render with it. Nothing else needs queueing.
   **Caveat learned the hard way: a queue only serializes what is submitted to it.** With one
   agent queueing and three rendering outside it, the 1-slot queue bought its user nothing —
   its job ran "serialized" alongside three unqueued renders and died anyway. Orchestration
   must make queueing the *only* way to render (or verify the box is clear before starting),
   not merely recommend it. Related: invoke it by **full path** (`/Users/vmasrani/tools/queue`);
   a bare `queue` is not necessarily on a subagent's PATH, which produces the especially
   confusing symptom of one agent reading an empty queue while another's jobs are running.
2. **Stage the clip's media on the internal disk.** `HOME` resolves under `/Volumes/external`,
   so A-roll, fonts, `node_modules` and media all contend on one external drive. Copying
   `clip.yaml assets/ subtitles/ renders/v<N>-audio.wav` to `/private/tmp/<clip>` and pointing
   `gen-props.mjs` there (output still written to the real `renders/`) took **ETA ~20 min →
   ~6 min and stopped the compositor errors outright.** ~100 MB per clip.
3. **A page recycle must not strand `continueRender`.** Now fixed — finding 15a.

### 15a. PATCHED — `fonts.ts` stranded its `delayRender` handle on a recycled page
The mechanism, from the code rather than from the error message: the module *does* re-run on a
recycled page, so a fresh handle is created. But the `staticFile` fetch against the recycled
static server can then hang forever, settling **neither `.then` nor `.catch`** — so nothing ever
clears the new handle, and ~178s later the render dies blaming the font. There was no timeout
and no retry anywhere in that path, and a single stranded fetch killed an 80-minute render.

Three changes, all in `remotion/src/fonts.ts`:
- every font fetch is bounded by `withTimeout(..., 20s)`, so a hang rejects instead of waiting;
- each subset/weight retries **4×** before giving up;
- `delayRender(..., { timeoutInMilliseconds: 90_000, retries: 3 })` — verified against the
  installed Remotion 4.0.506 `DelayRenderOptions`, so a still-timed-out handle retries the
  *frame* rather than failing the render.

`npx tsc --noEmit` passes. **Not yet verified against a long render** — the proof is a
multi-thousand-frame render surviving, which was still running when this was written. The
failure it targets is stochastic, so a single green render is weak evidence; the honest test is
several long renders with zero stranded-handle deaths.

**The render budget, and how to measure it honestly.** Two completed chunks, each verified with
`ffprobe -count_frames` against the queue's own start/finish stamps:

| chunk | frames (ffprobe) | wall clock | rate |
|---|---|---|---|
| `part-0-417` | 418 | 85s | 295 f/min |
| `part-418-835` | 418 | 42s | 597 f/min |
| combined | **836** | **127s** | **395 f/min** (0.15 s/frame) |

So a 110s clip (3346 frames) renders in **~8.5 minutes**, and twelve clips are **~2 hours
serialized** — affordable enough that serializing everything is clearly the right default.

**Do not measure this from Remotion's `time remaining:` line, and do not measure it by sampling
frame numbers over an interval.** The ETA extrapolates from early frames and is wildly
optimistic; a two-point sample silently includes any stall inside the window. Estimates taken
that way during this run ranged from **7 to 42 to 350 f/min** on the same clip, and one produced
an 80-minute ETA for a clip whose own chunks prove ~8.5 minutes. **Measure completed work:
`ffprobe -count_frames` on the output, divided by the job runner's start/finish stamps.** The
artifact cannot straddle a stall.

The stake is not academic: a 10× overestimate makes serialization look unaffordable, which
argues for exactly the parallelism that causes the failures in this finding.

**Keep chunked rendering regardless.** 418-frame chunks with skip-if-present converge whatever
the per-frame failure probability: a death costs ~10 min instead of ~80, and completed chunks
are never re-rendered. It also yields clean per-chunk wall-time for a real render budget.
Chunked output is video-only chunks concatenated and muxed against the same assembled audio —
a different assembly path from the documented one even when the content is identical, so it
**must** be recorded in `provenance.json` rather than passing silently.

### 16. `validate_clip.py` accepts duplicate YAML mapping keys
PyYAML silently last-wins, so a clip.yaml with a duplicated key passes the gate and then kills
`gen-props.mjs` with `YAMLException: duplicated mapping key (273:5)`. **Fix:** load with a
duplicate-key-rejecting loader. Same class as finding 13: the gate accepting a superset of what
the consumer will take.

### 17. `validate_subtitles.py` matches cards to events by substring
`manifest_coverage` reports a false failure whenever one card's text contains another's —
`"I believe that"` was found `present in 2 events: [20, 33]` against `"And I believe that it
probably won't"`. **Fix:** match card→event by index/time, not by substring search.

**This is not cosmetic: it changed a delivered edit.** The only workaround is merging cards, so
on one clip the agent merged `"I believe that"` into its neighbour specifically to protect
`"And I believe that it probably won't"` — the clip's final emphasised line — from being
touched. A second merge on the same clip (`"doesn't—"`, which also matched inside `"then the
success mark doesn't have to be"`) was forced the same way. A checker bug silently became an
editorial decision, and it would have shipped unremarked had the agent not flagged both as
workarounds rather than choices.

### 11a. PATCHED — `mlx_whisper` silently dropped 7 seconds of speech
`condition_on_previous_text` defaults to **True**, which lets the decoder skip a passage it
judges redundant. On one clip it dropped 88.4-94.4s entirely ("because they had a theory in
which stars flashing regularly doesn't happen"). The audio was fine — transcribing that window
alone returned the sentence perfectly.

This is the worst class of bug this skill can have: **the transcript is ground truth for every
downstream stage**, and a silent omission propagates into candidates, dialogue, and subtitles
with nothing red anywhere. It surfaces late and misleadingly as `these subtitle lines matched
no words at all`, which reads like a manifest error and sends you to debug the wrong file.

Patched at both call sites (`align_subtitles.py` MLX driver and `transcribe.py`) with
`condition_on_previous_text=False`.

### 17e. PATCHED — `manifest_coverage` now tries exact token equality first
Finding 17's fix, implemented after it forced editorial changes on **four independent agents**:
`"and I thought"` inside `"And I thought, right."`, `"it's a trivial theorem,"` inside `"As it
is, it's a trivial theorem."`, and two more. Because the only workaround available to an editor
is merging cards or deleting words, a checker bug kept converting itself into an editorial
decision — and would have shipped unremarked had the agents not each flagged it as a workaround.

Now: exact token equality first, containment only as a fallback for unmatched lines. Verified —
all 12 clips pass `validate_subtitles.py`.

**Only partly recoverable, and that is the lasting cost.** Fixing the checker does not undo the
edits it forced: the affected clips ship with those captions **burned into the master**, so
restoring a word means a full re-render cycle, not a text edit. On audit, one of three changes
on one clip turned out to be purely a validator artifact (a deleted leading "And"); the other
two were independently required by reading speed. That audit was only possible because the
agent had recorded which of its own changes were forced by the checker versus by real
constraints — most would not have kept the distinction, and the deletion would be indistinguishable
from an editorial choice forever.

Do not over-attribute to this bug. On the clip above, the card merge looks like a coverage
workaround and was not: card 25 measured **22.1 cps (23 chars in a 1.04s aligned window)** and
no legal deletion rescued it — every candidate either broke grammar or removed the leading word
and shrank the window further (see the leading-word rule in gap C). Merged with card 26 it reads
57 chars / 3.39s = 16.8 cps. The coverage clash was real but secondary; the merge was forced by
reading speed and would have happened anyway. Crediting it to the checker would tell the next
agent that a 22.1 cps card is survivable. It is not.

**Rule this suggests:** when a validator forces a content change, the workaround must be
recorded as a workaround in the storyboard and provenance, never as a decision. A checker bug is
recoverable; an unlabelled edit made because of one is not.

### 17k. A transient I/O error kills an otherwise-fine extraction, with no retry
`extract_segments.py` died with ffmpeg exit 252 — `Interrupted system call` — while writing one
segment's trailer, under five agents' concurrent I/O on the external volume. The media was fine;
re-running succeeded.

The correct fix is **not** a bare retry loop, which would silently paper over genuinely corrupt
media and violate the doctrine the rest of the script follows. A retry has to distinguish
*transient I/O* from *the input is wrong*: retry a bounded number of times on the syscall-level
errors only (EINTR/EAGAIN, ffmpeg 252), log every attempt, and let anything else fail
immediately with the ffmpeg stderr as it does today.

Adjacent smell worth naming: the whole pipeline treats a multi-agent shared external volume as
if it were exclusive local disk. This surfaced as an I/O error here, and as ~6x slower renders
earlier (which agents worked around by staging to `/private/tmp`). Local staging is currently
folklore passed between agents rather than something the scripts know about.

### 17l. Reading-speed greens do not survive a re-align
`validate_subtitles.py` reports pass/fail, not *margin*. Whisper's word timings shift slightly
run to run, so re-aligning the same verbatim text re-breaks the cards and a **different** card
lands marginal. Measured on `no-observations-imply-the-future`: at v1 card 28 failed and card 27
passed; at v3 card 28 passed and card 27 ("You don't talk about yourself.") failed at 20.5 cps
(30 chars / 1.46s). Fixed by dropping the terminal period — 29 chars / 1.46s = 19.9 cps, no word
lost. rn-induction spent three clip-hours across three clips on cards sitting within 0.5 cps of
the limit.

Two consequences:
- **Operational:** a previously-green clip is not green after a re-align. Re-run the validator
  every time; never carry a green forward across an alignment.
- **The fix:** report margin, not a boolean. A card at 20.4 cps is one word from red and should
  be visibly distinct from one at 12.0. Today they are the same output, so every agent
  rediscovers the cliff by falling off it.

### 17m. Renders run outside the queue, and the queue's slot count is therefore a lie
`queue -l` showed `run=0/1` while three Remotion instances were live on the box, because
renders were started directly rather than through `queue`. Measured cost: rn-broll's throughput
fell from ~395 f/min to ~90 under three-way contention — a ~4x tax paid by the agent who *did*
queue, in favour of the ones who didn't.

Related, from the same incident: an agent whose background tasks were swept externally
relaunched with `nohup ... & disown` to escape the harness task table. That protects the job
from a sweep but removes the completion notification and the exit code, converting a visible
death into an invisible one — a partially-written mp4 is indistinguishable on disk from a
finished one. Detached renders must end by writing their own status to a log
(`( <cmd> > log 2>&1; echo "exit=$?" >> log ) &`) which is then grepped before any claim about
the output. Standing rule issued to all five agents: every render goes through `queue`.

### 17n. QC verifies declared duration, never the decoded frame count
`qc_render.py`'s `duration_matches_manifest` and `manifest_agreement` both read
`format.duration` and the per-stream `duration` tags — i.e. **what the container claims**. No
check decodes the file and counts what is actually there. A render that dies mid-write, or one
that drops frames while still muxing a plausible header, can present a correct duration and pass.

The test that closes it (rn-broll's, adopted batch-wide):

    ffprobe -count_frames -show_entries stream=nb_read_frames <master.mp4>

compared against `round(clip.output.duration_s * fps)`. Same reasoning as reconciling a test
count against a baseline instead of reading the summary line: the status is a *claim about* the
count; the count is the count.

Two implementation notes for when this becomes the 13th check:
- **Derive the expected number** from `clip.yaml` — a hand-carried constant goes stale the moment
  a timeline shifts and then agrees with a wrong render.
- `-count_frames` decodes the whole file. That is why it is trustworthy and also why it must be a
  one-shot gate, never a poll loop competing with a live render.

### 17o. Parallel clips saturated every core and forced a hard reboot
Four clips rendering concurrently produced **102 `chrome-headless-shell` processes at 196%
aggregate CPU** on a 10-logical / 4-performance-core Mac. The user had to reboot. Two
independent defects, and fixing either alone would not have prevented it:

1. **The queue was bypassed, not broken.** `QUEUE_SLOTS=1` was correct and `queue -l` read
   `run=0/1` while three renders were live — because those renders were started directly rather
   than through `queue`. The slot count was accurate about the queue and silent about the box.
2. **One render is already oversubscribed.** Remotion's default concurrency is ~half the logical
   cores, so a single unbounded render spawns ~5 Chrome workers plus helpers against 4
   performance cores. Serializing four of these would have been slower-but-survivable; it does
   not address a single render eating the machine.

Fix shipped in `references/render-qc.md`: the documented render command now leads with `queue`
and carries `--concurrency=3`, with the rule stated as ONE RENDER AT A TIME, MACHINE-WIDE.

Worth recording because it nearly went unnoticed: `--concurrency=1` is on the "things that look
like fixes and are not" list for the OOM/font crash, and that remains true. It bounds **CPU**,
not **memory**. Reading the earlier finding as "concurrency doesn't matter" is what let four
unbounded renders run at once. Two resources, two flags — never collapse them.

The orchestration lesson is mine: I issued "every render goes through `queue`" as a rule to five
agents and then took compliance on report. Nothing measured actual machine-wide concurrency, so
a rule that four agents believed they were following coexisted with 102 live Chromes. A rule
without a measurement is a hope.

### 17p. The `.ass` round-trip is lossy — `border_style: plate` renders nothing
`align_subtitles.py` writes a fully-styled `.ass`; `gen-props.mjs` then parses that file back
apart and reads **exactly three** style fields — `outline`, `outlineColour`, `shadow` — and
`Subtitles.tsx` redraws the caption in CSS (`WebkitTextStroke`, `paintOrder: stroke fill`,
`textShadow`). `BorderStyle` and `BackColour` are read by nothing, and there is no
background-box code in the template.

So the plate option approved at the caption decision **is a no-op**: it writes `BorderStyle: 3`
plus a `BackColour` alpha, `validate_subtitles.py` sees a well-formed file, and the render shows
no plate. It would have surfaced as "the plate looks wrong" — a styling argument — rather than
as a bug. The outline half of the same decision *is* wired (`outlineWidthPx: firstStyle.outline
* scaleY`) and is in the renders.

Patched: `build_ass` now raises on `border_style: plate` naming the template as the thing that
must change first. Implementing it is ~10 lines in `Subtitles.tsx` plus one field in
`gen-props.mjs`; deferred rather than done mid-batch.

The structural point is bigger than the bug. **The pipeline generates `.ass` — the native format
of libass — and then declines to use libass**, keeping the file as a timing interchange format
and reimplementing its rendering half in CSS. Every style field is therefore silently optional:
it is written, validated, and ignored. Any future style knob added to the `.ass` inherits this
same failure mode by default. Either the template must consume the fields it is handed, or the
`.ass` should stop pretending to carry style.

### 17q. A truncated asset survives every existence check and dies inside the render
`assets/aroll/S10.mp4` was 5 MB with **no moov atom** — an extraction killed mid-write (by the
reboot) that left a file present, non-empty, and unreadable. Nothing upstream noticed:
`extract_segments.py` had already exited, `validate_clip.py` checks the manifest not the media,
and `gen-props.mjs` resolves paths without decoding them. The failure surfaced eight minutes into
a render as `Compositor error: Invalid data found when processing input` plus a wall of HTTP 500s
from Remotion's proxy — a message that names neither the file nor the cause.

Batch sweep after the fact: **118 A-roll assets checked, 1 corrupt.** So the rate is low and the
cost per instance is a whole render.

Two fixes, neither implemented yet:
- **`extract_segments.py` must write atomically** — encode to a temp name, `ffprobe` it, then
  rename into place. A killed extraction then leaves no file at all, which every existing check
  already handles correctly. This is strictly better than a retry: it makes the failure *absent*
  rather than *plausible*.
- **A cheap decode check belongs at gate 2**, before any render: `ffprobe` every asset the props
  reference. 118 files took seconds.

Generalises: the pipeline repeatedly treats presence as validity — the asset exists, the mp4
exists, the `.ass` exists. Every one of those has now produced a false green today (stale
`props.json`, partially-written master, truncated extract). **Existence is not integrity, and
the check that distinguishes them is almost always cheap.**

### 17r. Two of three speakers vanish from the transcript for the last 26 minutes
On the Deutsch episode the guest channel's last transcribed line is at **1:21:07** and host2's at
**1:20:53**; the episode runs to **1:47:45**. For the final ~26 minutes only host1 appears. By
mining chunk:

| chunk | guest1 | host1 | host2 |
|---|---|---|---|
| 05 | 188 | 60 | 39 |
| 06 | 165 | 90 | 13 |
| 07 | **0** | 78 | **0** |
| 08 | **0** | 45 | **0** |

Nothing flagged it. `chunk_transcript.py` proves *time* coverage — no source range is skipped —
and that proof was green, because host1's words cover the window. Coverage of the timeline is not
coverage of the room. Two miners worked chunks 07–08 and dutifully proposed three candidates built
entirely from one side of a conversation; the user's review of all three asked for "the guest's
response as well", which does not exist in the artifact the miner could see. The rubric rewrite
(§ point-counterpoint) makes this *worse*, not better: a region where only one speaker is
transcribed can never produce the shape the rubric now wants, and the miner cannot tell the
difference between "nobody disagreed here" and "the disagreement was not transcribed."

Fix, not yet implemented: **`transcribe.py` must emit per-speaker coverage and fail loud on a
sustained dropout.** For each labelled speaker, report first line, last line, and the longest gap;
error when any speaker present in the first half of the episode has a silent stretch beyond a
threshold (a few minutes). Diarization losing a channel is a normal failure mode; the pipeline
silently building on the remainder is not.

Same shape as 17q: presence was treated as completeness. The transcript existed, parsed, chunked
and covered the whole episode — and was missing half the conversation.

### 17s. A miner's rights declarations go stale the moment the mask is re-run
The Deutsch candidates were mined against a 37-span mask; the mask was then tightened (≥8-word
verbatim-run gate, 15s floor) to 33 spans. Re-checking mechanically, **3 of 13 candidates crossed
a cut they had not declared** in `rights_cut_spans` — E07 and E08 both over `[3078.7, 3086.8]`,
E10 over two more. Every one of them was marked `rights_checked: true` by the miner, truthfully:
it was true against the mask that existed when it ran.

The lesson is not that the miner erred. It is that **`rights_checked: true` is a timestamped
claim about a mutable artifact, and nothing in the pipeline re-evaluates it.** A candidate
carrying that flag would have gone through gate 1, storyboarding and render with unpublished audio
in it, and no stage would have looked again.

Fix, not yet implemented: `validate_clip.py` must re-derive the crossed cuts from the *current*
`rights-mask.yaml` and fail when a timeline segment overlaps any cut span. Derived from the mask
at validation time, the check cannot go stale; recorded in the manifest at mining time, it always
can. Same class as 17q/17r — the artifact was present and plausible, and its truth had expired.

### 17j. A field rename shipped to five agents without being executed once
Adding configurable caption outline (17b's fix) put five new fields on `SubtitleConfig` —
the **config** object — while `build_ass` read them off `clip.subtitles`, a **different class**
(`SubtitleSpec`, the manifest object). `AttributeError` on the very first field.

Three things make this worth recording beyond the typo:

1. **It blocked five agents simultaneously.** Every clip needs a re-align to pick up the new
   outline, so one broken line stopped a twelve-clip batch at the same step.
2. **The feature had never once taken effect.** The crash precedes the write, so no `.ass` was
   produced and `outline_fraction: 0.10` existed only in a config file — while I had already
   described the heavier outline to five agents as a fact.
3. **One execution would have caught it.** The failure is on the first line of the new path.
   No review would have caught it and no type checker was in play; only *running it* would.

The design error underneath: two objects with overlapping names and non-overlapping
responsibilities. `clip.subtitles` owns WHAT the captions say and where; `config.subtitles`
owns HOW they are drawn. Both are called "subtitles" and the local was called `subs`, so
reading a drawing field off the manifest looked completely natural. Fixed by passing the config
in as an explicitly-named `style` parameter, with the split written into the code as a comment.

**Two rules:**
- **A smoke test that produces the artifact belongs in the gate** — "align one clip, assert the
  `.ass` is written, assert `Outline` is what the config says". A half-migrated rename passes
  review and fails on first execution; nothing else catches that class.
- **Verify a style property by READING IT, never by observing that the run completed.** A render
  finishing proves nothing about an outline width — no QC check inspects one.

**And the verification harness was wrong twice before the code was right.** I parsed the ASS
`Style:` line by hard-coded index, was off by one, read `BorderStyle 6 | Outline 2`, and nearly
reported a second bug that did not exist. Fixed by zipping values against the `Format:` line by
name. A checker that indexes into a positional format is guessing; the format line is right
there and says what each field is.

### 17i. The storyboard stage systematically over-condenses against a stale constraint
After finding 5 gave cards a hold into following silence, one agent re-measured all nine
condensations it had made across two clips. **Seven of nine were unnecessary** and were restored
to full verbatim, with no timeline change and no caption shrink (longest line stayed 32 chars,
peak cps 20.0 and 19.5).

Restored: `"say"`, `"kind of"`, `"some approximation"`, `"employees and nurses"`, `"the
probability calculus or no?"`, `"here,"`, and a speaker's own self-correction (`"look at the,
uh, analyze"`). Every one is a hedge, qualifier, or the tail of an invitation to disagree —
exactly the words whose loss changes what a speaker is claiming.

The manifests carried explicit justifications like *"verbatim runs 21 chars/sec here"* that were
simply **wrong once the hold exists**. The storyboard stage estimates reading speed from spoken
duration, but the aligner's real window is spoken duration *plus* the silence after — so the
design stage condenses against a constraint the render stage does not have. It is a stale
assumption baked into prose that later agents reasonably trust.

**Fix:** compute card feasibility at storyboard time using the same hold rule `clamp_windows()`
applies, or stop asserting a cps figure in the storyboard at all and let alignment discover it.
Until then: **always re-align before condensing, and re-measure any inherited condensation** —
7 of 9 evaporated on contact with the real windows.

Two adjacent rules confirmed by the same pass:
- On a genuine over-ceiling card (68 chars > 64), **split rather than delete** — the split
  recovered four words *and* a trailing hedge that deletion would have lost.
- Disfluency repetition (`"you, you, you, you,"`, `um,`, `but, but`) is **not** what verbatim
  protects. A stutter set in type reads as a typo, not as fidelity. Every agent this run
  independently left these out; consistency across an episode matters more than literalism.

### 17h. `provenance.json` is hand-written and validated by NOTHING
Grep result: no script writes, reads, or checks it. `generated_media` appears exactly twice in
the codebase — once in SKILL.md prose, once in `references/schemas.md` as an illustrative
example — and nowhere in executable code.

So the skill's single hardest constraint, **"never AI-generated video or imagery"**, is enforced
entirely by each agent choosing to type `"generated_media": "none"` into a file nobody reads.
A clip with the field wrong, missing, or the whole file absent reaches `delivered` with 11/11
QC and a green `validate_clip`. The same holds for the rights attestation trail: `ingest.py`
demands `--authorized` at the front of the pipeline, and nothing carries that forward to the
artifact that actually gets published.

This is the rights-and-attribution record. It is the one artifact whose failure mode is legal
rather than aesthetic, and it is the least defended thing in the pipeline.

**Measured across the 12 delivered clips — the divergence is worse than the missing values.**

| | |
|---|---|
| `generated_media == "none"` | **12 / 12 correct** |
| distinct top-level key sets | **8, across 12 files** |
| key count range | 4 to 13 |

So the constraint held — every agent typed the right value — but the artifact is not a schema,
it is twelve improvisations. Five agents produced eight different shapes: some spell the source
`source`, some `sources`, some both; some carry `qc_status`, `profile`, `master_assembly`,
`tools`, `notes`; one carries the `known_deviations` block another agent invented. Nothing is
wrong in any of them and no two agree.

That combination is the real hazard. A downstream consumer — a publisher, a rights audit, a
takedown response — cannot read this directory programmatically at all, and the 12/12 on the one
field that matters is **luck plus five agents' diligence**, not enforcement. It is exactly the
state that looks fine until the first clip where someone is careless, and there is no check
anywhere that would distinguish that clip from these.

An audit written against an assumed schema (this one) misfires on the spelling differences
before it reaches the values — which is itself evidence: the fields cannot be verified because
they cannot be located. Six false failures on twelve substantively-correct files is a better
argument for the fix than any assertion: the shape is load-bearing, not cosmetic.

**Divergence is not a diligence problem.** The cross-agent spread understates it. *One* agent,
same hour, same template, produced two shapes across its own three clips (10 keys, 10, and 11 —
the third carrying `known_deviations` because it needed it). Five careful agents produced eight
schemas; one careful agent produced two. This is simply what hand-authoring is, and no amount of
care removes it.

**Sequencing constraint — the writer must land BEFORE or WITH the validator, never after.**
A validator dropped onto twelve files in eight shapes produces eight different failures on
clips that are all substantively correct, and the rational response to that is to loosen the
check until it passes — which is how a check ends up asserting less than the prose it replaced.
So:

1. **First, one writer.** A single function called from the render stage that *derives*
   provenance from `clip.yaml` + `episode.yaml` rather than accepting typed input: `clip_id`,
   `version` and `ranges_s` from the manifest, `authorized_by_user` from `episode.yaml`,
   `assets[]` from the resolved asset list, `tools` from what actually ran. Nothing an agent can
   spell two ways, and nothing an agent has to remember — the real defect, evidenced by an agent
   hand-updating `version` across a v1→v2 re-render and catching it only by accident.
2. **Then the validator**, as `qc_render.py`'s 12th check. At that point it checks machine
   output against machine input, and a failure means something is genuinely wrong.
3. **Regenerate the existing files with the writer**, don't patch them — one pass resolves all
   eight shapes and backfills the nine missing attestations.

**`generated_media` must be DERIVED, not copied.** As a hand-typed string it defends against
carelessness but not against the case it exists for: an agent that used a generated asset is
precisely the agent whose typed `"none"` cannot be trusted. The value has to come from the asset
provenance the pipeline already tracks — provider IDs and licences on every asset — with
*nothing* able to produce `"none"` except an empty or fully-attributed asset list.

**Fix:** a pydantic model for `provenance.json`, written by a script rather than by hand,
with `qc_render.py` refusing to mark a clip delivered unless it validates and
`generated_media == "none"`. Cheap, and it closes the gap between a documented prohibition and
an enforced one.

**Adopt `known_deviations` while doing it.** One agent invented the field to record a caption
that differs from the authored text and why (`authored_text`, `rendered_text`, reason,
`restore_at`). That is exactly the structure finding 17e argues for — it makes a
workaround-forced edit distinguishable from an editorial choice permanently, instead of only
while the agent that made it is still in the conversation. It belongs in the schema, not in
one clip's file.

### 17f. Chrome OOM, not contention, and not the font — the render fix
**This corrects the root cause recorded in finding 15.** The unbounded OffthreadVideo frame
cache OOM-kills the Chrome tab; the replacement page re-runs `fonts.ts`; the render dies naming
the font. `--offthreadvideo-cache-size-in-bytes=209715200` took one workspace from **12
consecutive failures to 4-for-4**, including two 2300-frame clips.

The decisive datum against the contention theory (mine): a failure at frame 1377/2317 with only
four Chromes running. Random failure frames across runs (416, 478, 572, 960, 1034, 1072, 1377,
1499) are the signature of a memory ceiling, not of load or bad media. **Contention sets the
rate, not the mechanism** — so "serialize the renders" was a real but incomplete remedy, and the
`fonts.ts` retry patch (15a) makes the symptom survivable rather than removing the cause. Both
are worth keeping; only the cache cap addresses it.

Documented in `references/render-qc.md`, along with two adjacent hazards found the same way:
backgrounded renders reaped at ~10 minutes (exit 144), and the ffmpeg **concat demuxer with
`-c copy` silently dropping 14 frames across 7 boundaries while reporting success** — use the
concat filter and verify with `ffprobe -count_frames`.

### 17g. The dead-seam class — detectable at gate 2, discovered after an 8-minute render
A seam whose source ranges are contiguous **and** whose scale is equal on both sides renders
literally identical frames: the declared cut does not exist. Found across three clips (four
seams, three, and one). One agent located them all with a 6-line scan of `source_in/source_out`
against motion endpoints, before rendering.

This interacts with the 8a patch: `cut_points` now reports such boundaries as `SKIPPED
(unverifiable)` rather than failing, which is honest but is *not* a fix — the seam is still a
cut that does nothing. **`validate_clip.py` should reject it at gate 2**, where it costs
seconds instead of a render cycle plus QC.

Aggravated by open #12: `static <N>%` is accepted by the Python validator and silently
normalized to 100% by the renderer, which *manufactures* dead seams. One clip's `cut_points`
failure was caused exactly this way — the storyboard said `static 103%`, the render made it
100%, matching the previous segment's end scale.

### 17a. There is no blur-fill treatment — but storyboards were written believing there is
**The most expensive finding of the second run, and it produced the headline defect twice.**

`Short.tsx` resolves exactly four treatments: `splitscreen`, `source-frame` (→ `fit: contain`),
`closeup-*`/`reaction-*` (→ `fit: cover`), else throw. **Nothing composites over a blurred
backdrop.** Yet the episode's own style guide asked for blur-fill, and two storyboards asserted
the pipeline provides it — one stating outright *"the renderer resolves that to the blur-fill
treatment."* It does not.

Consequences, both real: one clip encoded the intent as `treatment: source-frame` and rendered
with **~65% of every frame pure black**, face ~25% of frame height — and **passed QC 10/11**.
That is the letterbox defect from the headline, arrived at independently by a second agent on a
second episode. The other storyboard's false claim went unnoticed because `closeup-*` happens to
look acceptable.

Two distinct bugs here, and the second is the dangerous one:
1. Blur-fill isn't implemented. It is also the only treatment that yields head-complete framing
   from a 720p 16:9 source — the direct remedy for #9a's tight crops.
2. **A treatment name that does not exist should fail at gate 2, not resolve to something
   plausible.** `source-frame` is a legitimate name, so nothing caught the substitution.

**Fix:** implement `blur-fill` (extract at `fit: width`, composite over a blurred scaled copy),
and have `validate_clip.py` cross-check treatment names against the renderer's actual list.

### 17b. Subtitle outline is hard-coded and too light for a light-clothed speaker
Deutsch wears a cream shirt that fills the lower third, where the cards sit. Measured on
shipped `.ass` files: font 57, **outline 3px (5.3% of font)**, colour `#101010`, shadow 2px.
At full resolution `"but I don't know"` renders effectively white-on-white.

The weight is derived (`max(2, font_size * 0.05)`), not configurable: `clip.yaml`'s `subtitles`
block exposes only font / base_color / emphasis_palette / position. So an agent that *notices*
the problem cannot fix it — it can only report it, which is what happened.

**Fix:** expose outline weight/colour, and an optional opaque plate (`BorderStyle: 3`), in
`config/defaults.yaml` with a per-clip override. Raising the default is a series-look decision,
not a bug fix — it re-renders every delivered clip.

### 17c. `clip.yaml` `render.versions` schema is undiscoverable
Two agents independently wrote the obvious fields (`audio`/`master`/`profiles`/`loudnorm`) and
got 7 pydantic errors; the real schema is `version`/`preview`/`finals`/`rendered_at`/`qc`.
**Fix:** a worked example in `references/schemas.md`.

### 17d. Editing a skill script during a render batch crashes in-flight QC
Self-inflicted, and worth recording as a process rule rather than a code bug. My `cut_points`
edit was observed mid-write by a concurrent run: `AttributeError: 'Timeline' object has no
attribute 'skipped_cuts'`. It passed a minute later. The same agent also caught that my edit
left `expected_cuts` as a misleading alias for *all* hard cuts with its only consumer dead —
both now removed, `qc_render.py` re-verified 11/11.

**The crash was the lucky outcome.** An `AttributeError` is loud and unmistakable. A mid-edit
read that happens to *pass* — a check reading a half-written threshold, a list not yet
repopulated — is **indistinguishable from a real green**, and would be recorded in `qc-v<N>.json`
as one. The observable failure mode was the benign one; the dangerous one leaves no trace.

**Rule:** skill scripts are shared mutable state during a batch. Edit them between clips, or
accept that a green/red from that minute is untrustworthy.

## OPEN — usability / cost

18. **`remotion/src/fonts.ts`** — real, but see finding 15 first: under machine contention this
    same error is a *symptom* of Chrome being OOM-killed, and chasing it as a font bug cost two
    agents several render attempts each. Four `loadFont` calls share one `delayRender()` handle and
    lose a race at default concurrency. Workaround `--timeout=180000 --concurrency=2`.
    **Fix:** one handle per subset, and/or raise the timeout in `remotion.config.ts`.
19. **No `encode_profile.py`.** Stage 8 step 6 is prose only, and two traps cost a full render
    round each: targeting `true_peak_dbtp` exactly always fails (loudnorm's limiter lands *at*
    the target, so -1.0 measures -0.9 against a -1.0 ceiling — target `-0.5` below), and
    omitting `-shortest` fails duration on AAC padding.
20. **`--ass` and `--clip-dir` resolve relative to CWD**, not the clip dir. Confusing doubled
    paths in errors. Always pass absolute.
21. **`ingest.py` writes `speakers: []`** but `transcribe.py` requires non-empty, and
    `register-camera` needs a camera file — unrunnable for any single-stream source without
    hand-editing `episode.yaml`.
22. **`_write_yaml` is non-atomic.** An interrupt mid-write corrupted `candidates.yaml`.
    **Fix:** write to a temp file and `os.replace`.
23. **`stock_search.py --json`** omits `source_url`, which the table view renders.
24. **`sample_frame.py grid`** spreads frames evenly across a whole file with no `--at`, so it
    cannot do the job it exists for (checking a crop at *specific* moments). Flags are also
    inconsistent: `sample` takes `--out-dir`, `grid` takes `--out`.
25. **Cross-speaker interjections vanish silently.** A single-track clip drops every other
    speaker's words with no notice — it discards a sympathetic "Right." and a sharp "Wait,
    no—" with equal indifference. **Fix:** emit an INFO listing other-speaker words whose
    timestamps fall inside a segment's source range but not on its `source_file`.
26. **Stray `.codex/logs/` directories** appear inside manifest-tracked `assets/`.
27. **Stopping an agent does not stop its renders — but do NOT reap what you find.** `TaskStop`
    on four duplicate agents left their background shells alive and their renders running. The
    orchestrator (me) read "a render on a clip no named agent owns, which comes back after I
    kill it" as a runaway loop, and armed a watchdog to reap such trees every 45s.
    **That was wrong and it destroyed real work.** The trees were live agents:
    - the tree killed twice on `not-an-expert-on-popper` had **already finished the clip** —
      master, encode, contact sheet; it later passed QC 11/11. Discovered only because the
      orchestrator's own queued render failed with "file already exists";
    - `probability-of-truth-is-zero` had audio and subtitles ready and **no master precisely
      because its render was killed every 45s**;
    - `a-good-way-of-killing-people` was producing a deliberate **v2** (`v2-audio.wav`,
      `v2.ass`); "v1 is already green" says nothing about whether a v2 was wanted.

    Both resumed within seconds of the watchdog being stopped — which is what a working agent
    does and a zombie does not. **The faulty inference was treating "unowned by my roster" as
    "nobody's work".**

    **It recurred twice more after being written down, in both directions.** Later the same day
    an agent offered its own trees for reaping on the strength of `pgrep -fl 'remotion render' |
    wc -l` returning 2 — a *count*, carrying no ownership information at all — and filled the
    gap with a prior about orphans it had had earlier. Checking first showed the two live trees
    were a `probability-of-truth-is-zero` chunk belonging to a different agent, and a
    deliberately-started `a-good-way-of-killing-people` **v3**, two minutes old, begun *after*
    v2 went green. Neither was reapable.

    **The evidence that answers the question is what a process is WRITING, not how many there
    are.** `pgrep`/`ps` give the command line; ownership comes from the render's `--props` path,
    its output path, or `lsof -a -p <pid> -d cwd` — the clip name is the ownership signal. Every
    instance of this error came from reading a count or a name and inferring a fact the command
    could not supply. A session can contain more actors than the orchestrator's list knows
    about, and absence from that list is not evidence of abandonment. "It came back after I
    killed it" is at least as consistent with *someone is trying to work* as with *runaway
    loop*. Arbitrate contention by asking; never unilaterally kill a tree you did not start.

---

## Design gaps — not bugs, highest value remaining

### A. The editorial stage only produces CONTIGUOUS clips
All four published shorts from one episode are **composites of non-adjacent regions**. The
published Vivaldi short splices in a definition of solipsism from 4974s — a different part of
the episode — so a viewer who doesn't know the word can follow it. Ours, cut from one
contiguous region, never defines it. That is a structural limit of the senior-editor stage,
not a one-clip miss, and it is the single biggest quality gap against the human cut.

### B. Nothing does a COLD OPEN
The published short opens on the punchline, then rewinds. Ours opens on the premise and needs
~4s before it turns. Cold-open-then-rewind is the right structure for a vertical short and the
pipeline cannot currently express it.

### C. The two subtitle caps genuinely conflict
A card of `L` visible chars over `D` seconds is feasible iff **`L ≤ 20·D`**, **`L ≤ 64`**, and
**a word boundary exists in `[L−32, 32]`**. Reading speed forces you to *merge* cards (span
grows faster than characters); the 2×32 ceiling forces you to *split* them. The third
condition did not exist at 42 chars. Worth stating in the docs.

**A worked infeasible case, for calibration.** `"the right source of data."` — 25 chars in 1.18s
= 21.2 cps. The hold (finding 5) cannot help: the next card's speech begins at exactly the frame
this one ends, so there is **0.00s** of silence to extend into, against the reference clip's
1.60s/1.40s/1.04s. Dropping the terminal period gives 20.3 cps — **misses by one character**.
Merging upward to preserve the following beat gives 65 chars; even trimmed to exactly 64, the
line-break rule needs a word boundary at 32 and the available boundaries are 28 and 39. Deleting
a trailing word would delete the sentence's content. The only legal move was merging away a
comic beat ("And he is wrong.") that read better alone.

**At a 66-char ceiling the upward merge becomes legal and the beat survives.** That makes this a
concrete test case for whether the 2×32 cap should be profile-tunable, rather than an abstract
argument for loosening it.

**And the obvious fix for an over-speed card is backwards.** Invariant 8 permits dropping words,
so the instinct is to delete one — but deleting a card's **leading** word makes reading speed
*worse*. Alignment re-anchors the card's start to the first surviving word, so the window shrinks
by exactly that word's duration while the text shrinks by less. Measured: "Yes, I believe it's
coming." at 20.1 cps went to **22.0 cps** when "Yes," was dropped. Dropping only the terminal
period fixed it — 26 chars / 1.34s = **19.4 cps, no word lost**.

The ordered remedy, cheapest and least lossy first: **(1)** drop terminal punctuation;
**(2)** re-break lines (finding D — trim the card owning the longest *rendered* line, which pays
twice); **(3)** merge with a neighbour to buy span; **(4)** delete a **trailing** word. Never a
leading one.

### D. Font size is globally coupled to one line
The auto-fit divides the safe box by the single widest **rendered** line, so one extra
character on one card shrinks every caption in the clip. **Measured: restoring one terminal
period moved a break from 25/32 to 31/27 and took the clip from 57px to 53px.** Invisible from
the manifest. Corollary: when trimming, trim the card that owns the longest rendered line —
that trim pays twice.

### E. Green QC is not a gate
State plainly in `references/render-qc.md` that a green QC does **not** mean the render was
looked at, and make the contact-sheet review a required gate rather than an artifact.

---

## What worked well

- **Fail-loud discipline held.** Scripts refused unverified sync, missing speaker maps, and
  unauthorised sources. Every red was a genuine fault in the input.
- **`--episode-root` everywhere** let a non-standard `control/clips/<slug>/` layout run end to
  end with no moved files and no patched internals.
- **The two human gates did real work.** Gate 1 stopped B-roll spend on 20 rejected candidates;
  the design stage then caught three separate edits where one party's position was audible and
  the other's setup was not.
- **Style-guide adherence was consistent across twelve independent agents** — emphasis landed
  at 1.4–3.7% against a 15% ceiling, and nine of twelve clips independently concluded that
  stock footage would *argue against the dialogue* rather than support it.
