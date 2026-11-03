# Stage 0 (ingest), stage 3 (render, QC) and stage 4 (delivery)

These stages are deterministic: scripts do the work, the orchestrator sequences them and reads their exit codes. No creative subagents here; a failure is fixed by re-running with corrected inputs, never by an agent "adjusting" media by eye. (The creative loop is stage 2: `references/refinement.md`.)

**ffmpeg-full.** Everything that shells out to ffmpeg/ffprobe resolves `/opt/homebrew/opt/ffmpeg-full/bin` itself (`psmedia.ffmpeg_tool`) and raises with the install command when it is absent — PATH's default ffmpeg has no drawtext and is never used. Do not `export PATH` tricks; do not add a second resolver.

## Stage 0 — Ingest (`scripts/ingest.py`, `transcribe.py`; multitrack: `ingest_multitrack.py`, `sync_cameras.py`)

1. `ingest.py init EPISODE_ROOT --url URL --title T` — refuses to run unless the owner has attested authorization (`--authorized` flag, recorded in episode.yaml). Works on the owner's own episodes and on guest appearances on other shows (any YouTube URL). Downloads best video+audio via yt-dlp, probes every file in `source/` with ffprobe, writes `episode.yaml` (media + probes blocks).
2. Multitrack only — user-supplied camera files: copy into `source/`, register speakers + camera files in `episode.yaml` (orchestrator edits YAML directly).
3. `transcribe.py EPISODE_ROOT --engine assemblyai|mlx-whisper` — word-level timestamps; speaker labels via engine diarization (assemblyai) or per-speaker camera audio activity (mlx-whisper + isolated tracks). Maps diarization labels to `speakers[].id` (asks orchestrator to confirm mapping via sample lines). Writes transcript.json + transcript.md.
4. **Confirm speaker names, then fix name mis-transcriptions up front.** Show 2-3 sample lines per speaker and let the owner confirm who is who. Then take every proper noun the owner names (guests, hosts, people and works discussed) and `rg` the transcript for each AND for near-misses (phonetic neighbours, initials, `.`-split forms). The Bayesian Conspiracy transcript had Eneasz -> "Iñárritu"/"Faidner", Eliezer -> "Eliyahu", Jaynes -> "James", Vaden -> "Vadim". Keep `transcript.json.pre-fix` / `transcript.md.pre-fix`, replace across **both** `transcript.json` (words and segments) and `transcript.md`, and re-`rg` to prove no near-miss survives. Clips already frozen must have their `dialogue` re-synced (validate_clip invariant 11 reports the stale words).
5. **Episode metadata for intros.** Fill in `episode.yaml`:
   - `show:` — `name`, `hosts` (full names), `guest`, `own_show` (true for the owner's Increments episodes; guest appearances false). The intro card reads `<SHOW> / <hosts> / with <guest>` from it (`intro_overlays.py`).
   - `speakers[].full_name` and `.role` (name-tag text and subline, e.g. "co-host, Bayesian Conspiracy").
   - `layout_timeline:` — which gallery tile each speaker occupies over source time. Zoom-style layouts can reorder mid-episode (the Bayesian Conspiracy tiles reordered at ~2800 s). Detect from face tracks, then **confirm with source frames** on both sides of each change (`sample_frame.py`), and record every span (`schemas.md` § episode.yaml). Name tags and pips use it. Per-clip vertical framing infers identity per segment on its own; never pin one global mapping there (a global pin was tried and reverted).
6. `sync_cameras.py EPISODE_ROOT` — audio cross-correlation offset per camera file; writes the `sync` block with offset, confidence, gaps. Low confidence (< threshold in config) exits nonzero.
7. **Sync verification is mandatory before creative work when camera files exist:** extract a 5s side-by-side comparison at the computed offset (`sync_cameras.py verify`), eyeball/user-check it, then set `verified: true`. If sources cannot be reliably synchronized, STOP the pipeline and tell the user — do not proceed with unusable isolated footage silently.

## Stage 3 — Render

A refined, frozen pick renders directly (`clip.status: frozen`; legacy statuses read as frozen). There is no approval gate between refinement and render: render, QC, look at frames, deliver; the owner reviews the finished video.

### Clips (`format: clip`, horizontal)

`scripts/render_horizontal.py CLIP_DIR` — cuts every timeline segment from the 16:9 source, joins them with the configured micro-crossfade, normalizes loudness to the `youtube` profile, writes `renders/v<N>-youtube.mp4` plus `subtitles/v<N>.srt` (from forced alignment — uploaded as YouTube captions, not burned in). It runs validate_clip.py first and stops on red. Clips with `inserts` / `overlays:` (schemas.md § Inserts, § Overlays) add: per-insert loudness matching in assemble_audio.py, `dip-<N>f` fades, picture layers built by ffmpeg (`overlay_picture.py`: crop, cover-fit, push-in, dissolves, grids, pip border and move) and text layers rendered once by the Remotion `Card` composition (`overlay_text.py` → `remotion/render-cards.mjs`, transparent ProRes 4444, style from config `broll:`), all overlaid on the joined cut in one final pass. Captions are never burned into a horizontal clip. Then `qc_render.py --profile youtube` — its contact sheet samples every overlay window (entry + midpoint), and its asset check requires every `broll/` file on disk with a provenance entry.

### Shorts (`format: short`, vertical)

Tools: FFmpeg/FFprobe for audio assembly and encoding; **Remotion** (template in `remotion/`) for deterministic timeline composition — subtitles, split screens, crops and blur-fill (drawn from the source video, never pre-cut), overlays, graphics. The Remotion composition takes a single `props.json` generated from `clip.yaml`; it renders what the manifest says, nothing more.

A short with `overlays:` (blog-post quote screenshots) renders them as the quote layout — screenshot on the top half, current speaker on the bottom half (schemas.md § Overlays (shorts)); `frame_segments.py` frames the bottom panel, `validate_subtitles.py` keeps captions off the screenshot and the mouth. Check the `quote-layout` stills before the full render: screenshot legible at phone size, no neighbour in the speaker crop, captions clear.

Conventions the owner approved for shorts: speaker panels zoom **out** to head-and-shoulders (never tight on the face); where the tile is too small the **sharp** tile-bounded rect is **centred** over its blurred copy; **captions break at every speaker change** (a card never spans two speakers); a final caption too short to read (under `min_display_seconds`) is fixed by a **muted tail** segment from refinement (`audio: mute`, video-only closeup hold), not by stretching audio.

Per refined short, the whole path is two commands:

```
scripts/plan_framing.py CLIP_DIR          # computed framing (respects locked segments)
scripts/prep_short.py   CLIP_DIR          # steps 1, 3, 4 below + Remotion workspace + props.json for v<N>
scripts/render_short.py CLIP_DIR          # steps 5-6 + version bookkeeping + QC
```

`prep_short.py` exits 2 if subtitle validation fails: fix that before rendering. Run `render_short.py` with `run_in_background: true` (it blocks on `queue` and the render; poll `renders/v<N>-render.log`, never sleep in the foreground). It refuses to start unless prep is complete for the target version and **fails loud while any `chrome-headless-shell` from an earlier render is alive**. The steps below are what prep does, for reference and for re-running one of them alone:

1. **Assemble audio:** `scripts/assemble_audio.py CLIP_DIR` — concatenates source audio per the timeline's source/output mapping (sample-accurate cuts, configurable micro-crossfade at internal cuts to kill clicks). Output: `renders/v<N>-audio.wav`.
2. **Lock the timeline.** After this point any timeline edit means re-running `prep_short.py` for a new version.
3. **Frame the A-roll:** `scripts/frame_segments.py CLIP_DIR` — cuts NO video. For every A-roll segment it resolves the source (the episode, or a synced camera file with the sync offset applied), finds the speaker's face (cached under `assets/faces/`) and decides the framing; the result is `assets/framing.json`. **Contract with the Remotion template:** per segment, one `full` panel (closeup, 1080x1920) or a `top` + `bottom` panel pair (splitscreen, 1080x960 each); per panel the source file (a path under the episode root), the source start time and the shots — crop window keys in source pixels, the rectangle it is drawn into, the blur-fill backdrop, the speaker's tile. `gen-props.mjs` copies this into `props.json` (`segments[].panels`), validates it again, and the composition plays the ONE source video per panel with `<OffthreadVideo trimBefore>` inside an `overflow:hidden` box under a CSS transform (audio stays the assembled wav). **Tile invariant:** on a gallery source (Zoom-style tiles) a speaker's crop never crosses their own tile — the tile is measured from the colour seams around the face on every sampled frame (`facelib.tile_bounds`), a tile that still holds another person's face fails the run, and every shot is checked to lie inside it (`facelib._finish`, `geometry.mjs`). A split-screen panel (and the quote layout's speaker panel) frames head and shoulders — face box ~30% of the panel, eye line ~0.36 (`facelib.PANEL_FACE_HEIGHT`/`PANEL_EYE_LINE`) — and where a crop of the panel's aspect at that size would be wider than the tile, the crop is tile-wide and taller, fit to the panel by height with blur-fill side gaps (640px tile, 1080px tall -> 640x1080 source px at 0.89x, never magnified or cropped past the tile); closeups are head-and-shoulders (face box ~30% of the frame, eye line ~0.33). Nothing is magnified beyond `framing.max_upscale` (default 2.0): where the tile is too small the sharp tile-bounded crop is drawn smaller over a blurred, darkened copy of itself (blur-fill). `framing.json` also holds each mouth's nose-to-chin band (computed from the same shots Remotion draws) — so it must run BEFORE step 4.
4. **Align subtitles:** `scripts/align_subtitles.py CLIP_DIR --audio renders/v<N>-audio.wav` → `subtitles/v<N>.ass`; then `scripts/validate_subtitles.py CLIP_DIR --ass subtitles/v<N>.ass` must pass. Solo captions sit bottom-centre; a caption on screen during a split screen is placed on the panel seam (or the top of the bottom panel) so neither mouth is covered, using `assets/framing.json` (missing or stale framing fails loud). `validate_subtitles.py` re-checks that clearance.
5. **Compose:** copy `remotion/` into the episode workspace (one template copy serves one clip at a time — `gen-props.mjs` symlinks the clip dir into `public/clip`), generate `props.json` from clip.yaml, `npx remotion render` the composition over the assembled audio, A-roll segments and `.ass` subtitles. The Remotion output is the **visual master**, not a deliverable — don't QC codec/pix_fmt details on it (it may report `yuvj420p`).

   **Render with an explicit OffthreadVideo cache cap — this is not optional on a long clip.** `render_short.py` runs exactly this, as ONE quoted string handed to `queue`, from the clip's Remotion workspace:

   ```
   queue 'cd CLIP_DIR/remotion && npx remotion render Short ../renders/v<N>-master.mp4 --props=props.json \
       --timeout=1800000 --offthreadvideo-cache-size-in-bytes=209715200 --concurrency=3'
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

   **Preflight — `render_short.py` does the headless-chrome check for you (and warns on load average ≥ the performance-core count); this is what it runs, for manual renders:**

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

   Run `render_short.py` (or a manual render) as a tracked **background** task (`run_in_background: true`) and read its log; renders have been reaped at ~10 minutes (exit 144) when the *shell* was killed, in which case just re-run — the render step is idempotent.

   **If you must chunk (`--frames=A-B`), rejoin with the ffmpeg concat FILTER, never the concat
   demuxer with `-c copy`.** The demuxer silently dropped 14 frames across 7 boundaries — 3141
   instead of 3155 — while reporting success. Verify the join with
   `ffprobe -count_frames` against the expected total before trusting it.
6. **Encode the profile final** (`render_short.py`; ported from the owner's `encode_short.sh`): master video + the assembled `v<N>-audio.wav` (the master's own audio is ignored), two-pass **linear loudnorm** measured on the wav (I = profile LUFS, **TP = profile ceiling − 1.5 dB = −2.5**, LRA 11 — the AAC re-encode overshoots the wav's true peak), `scale=out_range=tv:out_color_matrix=bt709,format=yuv420p -color_range tv -colorspace bt709 -r <fps>`, `libx264 -preset slow -crf 18 -movflags +faststart`, `aac -b:a 192k -ar 48000`, `-t <manifest output.duration_s>`. Output `renders/v<N>-<profile>.mp4`. QC judges this file, never the master.
7. **Version, never overwrite:** every render is `renders/v<N>-…`; `render.versions` in clip.yaml is append-only and recorded by `render_short.py` (`{version, preview: master, finals: {profile: path}, rendered_at: real UTC time, qc}`; `qc_render.py` fills `qc` and promotes `clip.status` to `qc_passed` on green). A previously delivered version is never deleted or replaced.

## QC (`scripts/qc_render.py`)

`qc_render.py CLIP_DIR --version N --profile youtube-shorts` (`--profile youtube` for clips; `render_short.py` runs it for shorts) writes `qc-v<N>.json` (schema in `references/schemas.md`), records it in `render.versions[N].qc`, and exits nonzero on any failed check. A green QC of the newest version sets `clip.status: qc_passed`. Checks:

- Stream integrity: video+audio streams present, no missing/duplicated frames at cut points, container/codec/resolution/fps/aspect match the profile.
- Duration: rendered duration == manifest `output.duration_s` (±ε); audio and video stream durations agree.
- `blackdetect` / `freezedetect`: black or frozen intervals are failures.
- Audio: `ebur128` integrated loudness within profile target ±1 LU, true peak under ceiling, `astats` clipping check, `silencedetect` for accidental silence — especially in windows around every internal cut (jump-cut audio dropouts).
- Subtitles: every manifest line present in the .ass, no overflow beyond safe zones, timing within readability limits (re-run validate_subtitles against the muxed result).
- Manifest agreement: rendered timeline (cut points detected via scene/audio analysis at expected boundaries) consistent with clip.yaml; no compositing input outside the manifest.
- Contact sheet: tiled representative frames (one per timeline segment boundary ± midpoints) → `renders/v<N>-contact-sheet.png` for human visual review.

## Stage 4 — Delivery

QC green is necessary, not sufficient. **First look at the frames yourself** (`sample_frame.py` / the contact sheet, plus frames at every overlay and at each speaker change): right person per speaker, name tags on the right faces, quote highlights legible, captions clear of mouths. Then:

1. **Drive finals.** Upload the profile encode to the episode's `finals/` subfolder of `review.folder_id` (create it with `gog drive mkdir finals --parent <folder_id>` once and record `review.finals_folder_id` in episode.yaml). Name it `<PICK> <short slug> v<N>.mp4` (e.g. `S13 reagan-office v2.mp4`):
   `gog -a incrementspodcast@gmail.com drive upload renders/v<N>-<profile>.mp4 --parent <finals_folder_id> --name "…"`.
   **Verify the parent**: `gog -a incrementspodcast@gmail.com drive get <fileId> --json` must list the finals folder in `file.parents`. Then `doc_ops.py final CLIP_DIR --url <webViewLink>` (writes `review.final_url`) and give the owner the link.
2. **YouTube, private.** `yt upload renders/v<N>-<profile>.mp4 --title … --description … --tags a,b,c` (`--privacy` defaults to **private**; only ever private or unlisted — publishing is the owner's job in Studio). Conventions:
   - **Title**: a hook, ≤ 60 chars, a question or a bold claim.
   - **Description**: 1-2 lines on the exchange naming the people; `From <guest>'s debate/conversation with <hosts> on <show>.`; `Full debate/episode: <source URL>`; 2-3 hashtags. Clips also get the credits from `broll/ATTRIBUTION.txt`.
   - **Tags**: a comma-separated list (topic, people, show).
   - **Thumbnail**: shorts get none through the API (the owner can pick a frame in the mobile app); horizontal clips may pass `--thumbnail FILE`.
   - **Quota**: ~1600 units per upload, 10,000/day -> about 6 uploads a day; plan batches accordingly and stop at a quota error.
   - Record it: `doc_ops.py youtube CLIP_DIR --url <youtube url>` (writes `review.youtube_url`, `clip.status: delivered`).
   - `invalid_grant` from `yt`: the OAuth project must be **"In production"** (a Testing-mode token expires in 7 days). Re-auth: move `~/.cache/yt-cli/token.json` aside, run `PYTHONUNBUFFERED=1 yt auth` as a background task, give the owner the printed URL, and `curl` the localhost callback URL he pastes back.
3. Give the owner both links (Drive final, Studio). Anything he wants changed -> fix upstream, re-render as v<N+1>, upload again.

The episode is complete when every surviving pick is `delivered` (`status.stage: delivered`).
