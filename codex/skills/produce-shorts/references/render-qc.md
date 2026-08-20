# Stages 1, 8, 9 — ingest, render, and quality control

These stages are deterministic: scripts do the work, the orchestrator sequences them and reads their exit codes. No creative subagents here; a failure is fixed by re-running with corrected inputs, never by an agent "adjusting" media by eye.

## Stage 1 — Ingest (`scripts/ingest.py`, `transcribe.py`, `sync_cameras.py`)

1. `ingest.py init EPISODE_ROOT --url URL --title T` — refuses to run unless the user has attested authorization (`--authorized` flag, recorded in episode.yaml). Downloads best video+audio via yt-dlp, probes every file in `source/` with ffprobe, writes `episode.yaml` (media + probes blocks).
2. User-supplied camera files: copy into `source/`, register speakers + camera files in `episode.yaml` (orchestrator edits YAML directly).
3. `transcribe.py EPISODE_ROOT --engine assemblyai|mlx-whisper` — word-level timestamps; speaker labels via engine diarization (assemblyai) or per-speaker camera audio activity (mlx-whisper + isolated tracks). Maps diarization labels to `speakers[].id` (asks orchestrator to confirm mapping via sample lines). Writes transcript.json + transcript.md.
4. `sync_cameras.py EPISODE_ROOT` — audio cross-correlation offset per camera file; writes the `sync` block with offset, confidence, gaps. Low confidence (< threshold in config) exits nonzero.
5. **Sync verification is mandatory before creative work when camera files exist:** extract a 5s side-by-side comparison at the computed offset (`sync_cameras.py verify`), eyeball/user-check it, then set `verified: true`. If sources cannot be reliably synchronized, STOP the pipeline and tell the user — do not proceed with unusable isolated footage silently.

## Stage 8 — Render

Tools: FFmpeg/FFprobe for extraction, audio assembly, encoding; **Remotion** (template in `remotion/`) for deterministic timeline composition — subtitles, split screens, crops, overlays, graphics. The Remotion composition takes a single `props.json` generated from `clip.yaml`; it renders what the manifest says, nothing more.

Per approved clip (status must be `approved_render` — gate 2 passed):

1. **Assemble audio:** `scripts/assemble_audio.py CLIP_DIR` — concatenates source audio per the timeline's source/output mapping (sample-accurate cuts, configurable micro-crossfade at internal cuts to kill clicks). Output: `renders/v<N>-audio.wav`.
2. **Lock the timeline.** After this point any timeline edit means going back to gate 2.
3. **Align subtitles:** `scripts/align_subtitles.py CLIP_DIR --audio renders/v<N>-audio.wav` → `subtitles/v<N>.ass`; then `scripts/validate_subtitles.py CLIP_DIR --ass subtitles/v<N>.ass` must pass.
4. **Extract visual segments:** `scripts/extract_segments.py CLIP_DIR` — cuts every A-roll source range (from episode or synced camera file, applying sync offsets), applies crops, normalizes to the target fps/resolution; stages files under `assets/aroll/`. **Naming contract with the Remotion template:** `assets/aroll/<SEGMENT-ID>.mp4` for single-source treatments; splitscreen segments emit two half-height crops `<SEGMENT-ID>-top.mp4` and `<SEGMENT-ID>-bottom.mp4` (each target-width × half-target-height).
5. **Compose:** copy `remotion/` into the episode workspace (one template copy serves one clip at a time — `gen-props.mjs` symlinks the clip dir into `public/clip`), generate `props.json` from clip.yaml, `npx remotion render` the composition over the assembled audio, A-roll, B-roll, text, graphics, and `.ass` subtitles. The Remotion output is the **visual master**, not a deliverable — don't QC codec/pix_fmt details on it (it may report `yuvj420p`).

   **Render with an explicit OffthreadVideo cache cap — this is not optional on a long clip:**

   ```
   queue npx remotion render Short <out> --props=props.json --timeout=1800000 \
       --offthreadvideo-cache-size-in-bytes=209715200 \
       --concurrency=3
   ```

   **ONE RENDER AT A TIME, MACHINE-WIDE, AND EVERY RENDER GOES THROUGH `queue`.** Both halves
   are load-bearing and neither substitutes for the other:

   - **`queue` serializes renders across agents.** With `QUEUE_SLOTS=1` exactly one render runs
     at a time no matter how many clips are in flight. A render started outside the queue makes
     `queue -l`'s slot count a lie, and every queued agent silently pays for it.
   - **`--concurrency=3` bounds ONE render's appetite.** Remotion's default is roughly half the
     logical cores, and each worker is a `chrome-headless-shell` process that forks helpers.
     Measured on a 10-core / 4-performance-core Mac: **four concurrent renders produced 102
     headless Chrome processes at 196% aggregate CPU and required a hard reboot.** Serializing
     alone would not have prevented this — an unbounded single render still oversubscribes the
     4 performance cores. Cap it.

   **`--props=props.json` is mandatory and its omission is not obvious.** Without it Remotion
   renders the composition's *default* props, `parseProps` rejects them, and the failure prints
   a code frame from `src/schema.ts` with an EMPTY issues list — it looks like a schema bug in
   the template, not a missing flag. `gen-props.mjs` writing `props.json` does not connect it to
   the render; nothing reads that file unless you point at it.

   **Preflight — run this before every render and read it, don't just run it:**

   ```
   n=$(pgrep -f chrome-headless-shell | wc -l | tr -d ' ')
   echo "headless chromes: $n"; [ "$n" -eq 0 ] || echo "REFUSING: a render is already live"
   uptime   # 1-min load average must be well under the performance-core count
   ```

   `pgrep` on macOS has **no `-c` flag** (that is procps/Linux) — it exits with a usage error, and
   inside `$(...)` with stderr redirected that error becomes an *empty string*, which then reads
   as a clean machine. Use `| wc -l`. Note also that `pgrep` exits 1 when nothing matches, so
   guard with `|| true` under `set -e`; the clean case is the one that would abort the script.

   Check the load average too, not just the process count. Zero renders does not mean an idle
   box: a post-reboot Spotlight reindex plus unrelated user processes were measured at load 9.51
   on a 10-core machine with zero Chromes alive. Starting a render into that reproduces the
   original saturation with none of the original causes present.

   Note the tension with the "not a fix" list below: `--concurrency=1` does **not** fix the
   OOM/font crash, and that is still true. It is listed here for a different reason — bounding
   CPU, not bounding memory. Two separate resources, two separate flags; don't collapse them.

   Without the cap, Remotion's frame cache grows unbounded, the Chrome tab is OOM-killed, the
   replacement page re-runs `src/fonts.ts`, and the render dies reporting
   `delayRender("loading the bundled Inter font") not cleared`. **That message names the wrong
   thing.** The font is fine; the browser died. Measured: the cap took one workspace from 12
   consecutive failures to 4-for-4 successes, including two 2300-frame clips.

   Things that look like fixes and are not — do not repeat them:
   - Raising `--timeout` alone. 180000→300000 only moved the number in the error message.
   - `--concurrency=1`, `--gl=swangle`, staging media or the template on the internal disk.
   - Waiting for the machine to go quiet. One failure landed at frame 1377/2317 with only four
     Chromes running, so **contention sets the rate, not the mechanism.** Failure frames are
     random run to run (416, 478, 572, 960, 1034, 1072, 1377, 1499) — the signature of a memory
     ceiling, not of bad media.

   Run the render in the **foreground** with a long tool timeout. Backgrounded renders were
   observed being reaped at ~10 minutes (exit 144), including one killed while merely sleeping.

   **If you must chunk (`--frames=A-B`), rejoin with the ffmpeg concat FILTER, never the concat
   demuxer with `-c copy`.** The demuxer silently dropped 14 frames across 7 boundaries — 3141
   instead of 3155 — while reporting success. Verify the join with
   `ffprobe -count_frames` against the expected total before trusting it.
6. **Encode profiles:** ffmpeg pass per platform profile over the master — loudness normalization to the profile's LUFS/true-peak (two-pass `loudnorm`), codec/container per profile. Profile encodes are what stage 9 QC judges.
7. **Version, never overwrite:** every render is `renders/v<N>-…`; `render.versions` in clip.yaml is append-only. A previously approved version is never deleted or replaced.

## Stage 9 — QC (`scripts/qc_render.py`)

`qc_render.py CLIP_DIR --version N --profile youtube-shorts` writes `qc-v<N>.json` (schema in `references/schemas.md`) and exits nonzero on any failed check:

- Stream integrity: video+audio streams present, no missing/duplicated frames at cut points, container/codec/resolution/fps/aspect match the profile.
- Duration: rendered duration == manifest `output.duration_s` (±ε); audio and video stream durations agree.
- `blackdetect` / `freezedetect`: black or frozen intervals are failures unless the storyboard explicitly specifies them.
- Audio: `ebur128` integrated loudness within profile target ±1 LU, true peak under ceiling, `astats` clipping check, `silencedetect` for accidental silence — especially in windows around every internal cut (jump-cut audio dropouts).
- Subtitles: every manifest line present in the .ass, no overflow beyond safe zones, timing within readability limits (re-run validate_subtitles against the muxed result).
- Manifest agreement: rendered timeline (cut points detected via scene/audio analysis at expected boundaries) consistent with clip.yaml; every asset in `assets[]` has a file+checksum; no compositing input outside the manifest.
- Contact sheet: tiled representative frames (one per timeline segment boundary ± midpoints) → `renders/v<N>-contact-sheet.png` for human visual review.

## Delivery

A clip is done when: QC passes, the human approves the final render (show the contact sheet + the render path), and the packaging step has written `provenance.json`. Then set `clip.status: delivered`. The episode is complete only when every approved clip reaches `delivered`.
