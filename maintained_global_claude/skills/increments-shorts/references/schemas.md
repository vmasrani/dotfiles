# Canonical schemas — the machine-readable source of truth

Before the freeze, `picks.json` (approved in chat; shape in `scripts/picklib.py`) is the record of what is picked.
From the freeze on, `clip.yaml` is the machine truth (stage-2 refinement edits it
directly); the user reviews the final video. `scripts/validate_clip.py` enforces the invariants
below after the freeze and before any render.

## Units and time systems

- All times in YAML are **seconds as floats** (e.g. `734.20`). Human surfaces render `mm:ss` / `MM:SS.mmm`.
- Two distinct time systems exist and must never be conflated:
  - **Source time** — position in the original media file.
  - **Output time** — position in the finished short or clip.
- Comparison epsilon everywhere: `0.01s`.
- IDs are stable once assigned: pick IDs `S1…`/`C1…` per episode; segment IDs `S01, S02, …` per clip. Never renumber on revision — retire IDs and append new ones.

## Project layout

```text
episode-<slug>/
  episode.yaml
  source/                 # downloaded episode 
  transcript/
    transcript.json
    transcript.md
  picks.json              # approved picks (chat) -> freeze_picks.py
  thumbnails.yaml         # thumbnail options -> thumbnails.py
  thumbnails/             # rendered options + contact-sheet.jpg
  deliverables/           # <slug>.mp4 (+ end tag), <slug>-thumbnail.jpg, <slug>.txt
  dropped-clips/          # picks the user dropped after the freeze (moved, never deleted)
  clips/
    <clip-slug>/
      clip.yaml           # canonical manifest (schema below)
      remotion/           # shorts only: template copy + props.json (prep_short.py)
      assets/framing.json # shorts: per-segment crop geometry + mouth bands (frame_segments.py); no pre-cut video
      assets/faces/       # per-segment face detections (cache for the computed crops)
      subtitles/          # aligned .ass (shorts) / .srt (clips), validation report
      renders/            # versioned, never overwritten: v<N>-audio.wav, -master.mp4, -<profile>.mp4, -render.log
      qc-v<N>.json, qc-v<N>.log
      provenance.json
```

## episode.yaml

```yaml
episode:
  id: my-episode-slug
  title: "Episode 42 — ..."
  source_url: "https://youtube.com/watch?v=..."
  youtube_id: "V-w7X-zTkCY"   # when the source is this channel's own upload
  authorized: true            # user attested ownership/authorization; ingest refuses to run when false/absent
  created: "2026-08-05"
platform_profiles:            # copied from config/defaults.yaml profiles at ingest
  - name: youtube-shorts
    format: short
    aspect: "9:16"
    resolution: "1080x1920"
    fps: 30
    max_duration_s: 180
    container: mp4
    video_codec: h264
    audio_codec: aac
    loudness_lufs: -14.0
    true_peak_dbtp: -1.0
  - name: youtube
    format: clip
    aspect: "16:9"
    resolution: "1920x1080"
    fps: 30
    max_duration_s: null      # no maximum
    container: mp4
    video_codec: h264
    audio_codec: aac
    loudness_lufs: -14.0
    true_peak_dbtp: -1.0
show:                         # intro card + name tags (intro_overlays.py); guest appearance or own show
  name: "The Bayesian Conspiracy"
  hosts: ["Eneasz Brodsky", "Steven Zuber"]   # full names, card order
  guest: "Vaden Masrani"      # omit for the show's own episodes
  own_show: false             # true = an Increments episode (Increments branding, no "with ..." line)
layout_timeline:              # gallery tile layout over SOURCE time (3-up Zoom-style sources)
  - from_s: 0                 # first span starts at 0; strictly ascending from_s; each span ends where the next begins
    tiles: {left: host1, mid: guest1, right: host2}    # tile -> speaker id
  - from_s: 2800              # the tiles reordered here (detected from face tracks, confirmed on source frames)
    tiles: {left: guest1, mid: host2, right: host1}
speakers:
  - id: host1                 # referenced by transcript + clip timelines
    name: "Eneasz"            # short label (speaker headers)
    full_name: "Eneasz Brodsky"                  # name tags / intro card (default: name)
    role: "co-host, Bayesian Conspiracy"         # name-tag subline
    camera_file: null         # optional isolated footage
    preferred_crop: null      # legacy, unused: shorts crops are computed per segment from face detection
media:
  episode_video: source/episode.mp4
  episode_audio: source/episode.m4a     # optional separate best-audio stream
  probes:                     # keyed by path relative to episode root
    source/episode.mp4:
      duration_s: 5432.10
      width: 1920
      height: 1080
      fps: 29.97
      video_codec: h264
      audio_codec: aac
      audio_channels: 2
      sample_rate: 48000
sync: []                      # unused: [{file, offset_s, confidence, method, gaps, verified}]
transcript:
  json: transcript/transcript.json
  md: transcript/transcript.md
  engine: assemblyai          # or faster-whisper
  language: en
  word_count: 48210
status:
  stage: ingested             # ingested → picking → frozen → rendering → delivered   (legacy `storyboarding` reads as `frozen`)
config_overrides: {}          # optional per-episode pipeline overrides, shaped like config/defaults.yaml (e.g. subtitles.max_chars_per_second)
```

`show:` and `layout_timeline:` are optional in the model (absent on old episodes) but `intro_overlays.py`
fails loud without them. `layout_timeline` spans are validated: first `from_s` is 0, strictly ascending,
every tile names a known speaker id. `Episode.tile_of(speaker_id, source_s)` answers "which tile".

## transcript.json

```json
{
  "engine": "assemblyai",
  "language": "en",
  "audio_file": "source/episode.m4a",
  "words": [
    {"w": "Today", "start": 0.12, "end": 0.31, "speaker": "host1", "conf": 0.98}
  ],
  "segments": [
    {"start": 0.12, "end": 8.40, "speaker": "host1", "text": "Today we're ..."}
  ]
}
```

`words` is the alignment truth (pick boundaries, subtitles, cut points). `segments` is the readable
truth (picks.json). Speaker IDs must match `episode.yaml speakers[].id`; the
transcription step maps diarization labels (e.g. `SPEAKER_00`) to speaker IDs and records the mapping.

## clip.yaml — the canonical per-clip manifest

Written by `freeze_picks.py`; refined by `plan_framing.py`.

```yaml
clip:
  id: why-incentives-fail     # slug, from the pick title
  pick: S1                    # pick id from picks.json
  format: short               # short (9:16, < 180 s) | clip (16:9, any length)
  title: "Why incentives backfire"
  status: frozen              # frozen → rendered (render_short/render_horizontal) → qc_passed (qc_render, green) → delivered (uploaded private)
                              #   (legacy `storyboarded`/`approved_render` read as `frozen`)
  why: "The pick's why line from the doc."
  ends_on: "verbatim last line"
timeline:                     # ordered by output_in; the edit decision list
  - id: S01
    source_file: source/episode.mp4
    source_in: 734.20
    source_out: 741.55
    output_in: 0.00
    output_out: 7.35
    dialogue: "exact verbatim words spoken in this range"
    speaker: host1
    audio: as-recorded        # as-recorded | duck | mute  (mute = video-only hold, e.g. the muted tail that lets a too-short last caption finish)
    visual:
      kind: aroll             # aroll = the episode; insert = a credited non-episode source (clips only, § Inserts).
                              #  B-roll is never a timeline segment — it lives in `overlays:` (§ Overlays)
      treatment: closeup-host1   # short: closeup-<speaker> | splitscreen ; clip: source-frame
      speakers: null          # splitscreen only: exactly two speaker ids [top, bottom]
      locked: false           # true = user override from the refinement chat (solo close-up to hide a reaction, restored pause split); plan_framing.py never changes it
      reason: null            # why: the framing rule, or the user's comment text
      crop: null              # optional hand override "x=..:y=..:w=..:h=.." for a closeup; normally absent —
                              # crops are computed per segment from face detection (frame_segments.py)
      asset_id: null
      motion: null
    transition: cut           # transition INTO next segment: cut | crossfade-<N>f
subtitles:
  font: "Inter Semibold"
  base_color: "#FFD400"        # every word's colour; the spoken word's colour/weight are config subtitles.active_*
  emphasis_palette: ["#FFFFFF"]   # seeded from config subtitles.emphasis_color
  position_default: bottom-center
  lines: []                   # optional design-time overrides; final timing comes from forced alignment
assets: []                    # always empty — kept so the asset invariants hold vacuously
review:
  # legacy `storyboard_docs` / `cover` keys in old manifests are ignored on read and dropped on write
  final_url: null             # unused (no Drive in this skill)
  youtube_url: null           # the PRIVATE/unlisted YouTube upload (upload_youtube.py; the user publishes)
output:                       # short: 9:16 1080x1920 ; clip: 16:9 1920x1080
  aspect: "9:16"
  resolution: "1080x1920"
  fps: 30
  duration_s: 41.70           # must equal last timeline output_out
render:
  versions: []                # append-only: {version, preview: renders/v1-master.mp4 (shorts), finals: {profile: path},
                              #  rendered_at: real UTC time of the render, qc: qc-v1.json (set by qc_render.py)}
```

## Timeline invariants (enforced by validate_clip.py)

1. Output timeline is contiguous from zero: `timeline[0].output_in == 0.0`; each `output_in == previous output_out` (±ε). No gaps, no overlaps.
2. Segment durations match across time systems: `output_out - output_in == source_out - source_in` (±ε). No speed changes.
3. Every `source_in/source_out` lies within the probed duration of `source_file` (from `episode.yaml media.probes`).
4. `clip.output.duration_s == timeline[-1].output_out` (±ε) and ≤ the `max_duration_s` of every profile for the clip's format (clips have no maximum).
5. Every `broll` segment names an `asset_id` present in `assets[]` (vacuous: B-roll is in `overlays:`).
6. Every asset's `used_in_segments` matches the timeline exactly (vacuous: `assets: []`).
7. Every asset file exists on disk and its `sha256` matches (vacuous).
8. Subtitle `output_range`s lie within `[0, duration_s]`, do not overlap, and each range's text words appear (in order) in the union of `dialogue` of the segments it spans.
9. `format: short` uses only `closeup-*` / `splitscreen`; a `splitscreen` names exactly two distinct speakers; `format: clip` uses only `source-frame`. `output.aspect` matches the format.
10. Speaker IDs and `treatment` speaker references exist in `episode.yaml speakers[]` (an insert's speaker is exempt — it is named by `insert.speaker_name`).
11. Every segment's `dialogue` accounts for every transcript word audible in its range (inserts are checked against their own words file by 12).
12. **Inserts** (§ Inserts): `visual.kind: insert` ⇔ an `insert:` block; `format: clip` only; a `broll:` block exists; `source_file` lies under `clips/<id>/broll/`; `treatment: letterbox`; the file exists, has an audio stream and a provenance entry; `source_in/out` lie inside its duration; the segment does not touch the protected tail; `dialogue` tokens equal the audible tokens of the insert's words file.
13. **Overlays** (§ Overlays): `format: clip`, or `format: short` with fullscreen still pictures only (§ Overlays (shorts); anything else is a finding "not implemented for shorts"); a `broll:` block exists; ids unique; window inside `[0, duration_s]`; fades fit the window; picture modes have `shots` and no `lines`, text modes the reverse; `pip` needs a `box` (inside the frame, even width and height), `fullscreen` has none; `from_box` ⇔ `move_frames`; shots start at 0 and ascend inside the window, each names exactly one of `asset`/`grid`; dissolves fit both shots; zoom within 1–2; crops parse and lie inside the asset; grid tiles are stills and fit `cols×rows`; a video range lies inside the asset's duration and plays at least its slot (or says `hold_last`); every asset exists and has a provenance entry; no picture overlay over an insert; no fullscreen overlay past the start of the protected tail; text-run times lie inside the window; overlays in the same layer (picture: fullscreen+pip; text: lowerthird+card) never overlap.

### Overlays (shorts): the quote layout

A short takes the SAME `broll:` / `overlays:` schema, restricted to what the vertical frame draws: `mode: fullscreen`,
shots that are stills (`asset` png/jpg/webp, `at`, `zoom`, `dissolve_frames`), `fade_in_frames`, `fade_out_frames`. Times are
OUTPUT seconds. pip, `lowerthird`/`card`, video ranges, grids, `crop`, `label` are refused ("not implemented for shorts").
Every file has a provenance entry; the screenshot is the RAW capture (`broll/orig/...`), the renderer does the compositing.

While an overlay is up the frame is two 1080x960 panels (geometry decided by `scripts/frame_segments.py` /
`scripts/quotelayout.py`, written to `assets/framing.json` `quotes` + each segment's `quote` panel, copied into props.json by
`gen-props.mjs`, drawn by `remotion/src/Short.tsx`):

* TOP — the screenshot fitted to the panel (40 px margin) on a blurred, darkened copy of itself, slow push-in per `zoom`,
  cross-dissolve per `dissolve_frames`, whole layout fades in/out per the overlay's fade frames over the normal picture.
* BOTTOM — the speaker of the timeline segment on screen (`segment.speaker`, even if the segment's treatment is a closeup
  of someone else), cropped like a split-screen panel: the crop never leaves that speaker's tile.
* Captions sit at the top of the bottom panel (or on the seam) and clear both the speaker's mouth and the screenshot as
  drawn; `validate_subtitles.py` checks both (`mouth_clearance`, `quote_clearance`).

### Inserts (horizontal clips)

An insert is a timeline segment whose picture AND sound come from a credited third-party file in
the clip's `broll/` (e.g. the guest saying the line in a talk the hosts are discussing):

```yaml
  - id: I01
    source_file: clips/<slug>/broll/talk_insert_ext.mp4   # relative to the episode root, inside broll/
    source_in: 0.80          # in the insert FILE's own time
    source_out: 23.65
    output_in: 37.125
    output_out: 59.975
    dialogue: "That's not a dog. …"     # = the audible words of insert.words, token for token
    speaker: guest
    audio: as-recorded
    transition: dip-6f        # cut | crossfade-<N>f | dip-<N>f (horizontal only: fade through black, N frames each side)
    visual: {kind: insert, treatment: letterbox}
    insert:
      speaker_name: David Deutsch
      words: broll/talk_insert_ext.words.json   # transcribe_insert.py; times in the file's own clock
      loudness: match-hosts   # assemble_audio.py gains it to the hosts' integrated LUFS (+ true-peak limiter)
```

Splice an insert with `broll.insert_segment(clip, at, segment, words)`: it splits the host segment
at a word gap (never inside a word), renumbers the tail, shifts every later segment, overlay and
subtitle line by the insert's length, and refuses overlays or lines that straddle the cut. The `.srt`
of a clip with inserts is aligned from the episode words outside inserts and each insert's own words.

### Overlays (horizontal clips)

Real, credited footage and stills composited over the finished cut (render_horizontal.py, after
the concat), plus lower-thirds and cards. Never AI-generated. Times are OUTPUT seconds.

```yaml
broll:
  provenance: broll/provenance.json     # the ledger; every overlay/insert file needs an entry
  protected_tail_s: 62.0                # final N s: no fullscreen cutaway, no insert
overlays:
  - id: B2
    mode: fullscreen          # fullscreen | pip (picture layer) ; lowerthird | card (text layer)
    start: 15.10
    end: 22.60
    fade_in_frames: 8
    fade_out_frames: 8
    shots:
      - asset: talk_canvas_build.mp4     # file in broll/ (video or .png/.jpg still)
        at: 0.0                          # seconds after the overlay starts
        src_in: 0.4                      # video: range in the file
        src_out: 8.4
        speed: 1.0                       # source s per output s
        hold_last: false                 # hold the last frame if the range ends before the slot
        crop: "x=0:y=238:w=896:h=504"    # in asset pixels; must match the box aspect
        zoom: [1.0, 1.05]                # slow push-in across the shot
      - grid:                            # a grid of stills (tiles pop in at `at` after the shot)
          cols: 3
          rows: 3
          tiles: [{asset: dog_01.jpg, at: 0.0, label: null}, …]
        at: 4.0
        dissolve_frames: 10              # cross-dissolve from the previous shot
  - id: B3
    mode: pip
    start: 22.60
    end: 30.00
    box: {x: 1184, y: 72, w: 672, h: 378}      # output px; pip gets the config border
    from_box: {x: 0, y: 0, w: 1920, h: 1080}   # optional animated scale/move into `box`
    move_frames: 18
    label: "David Deutsch, 'Knowledge Creation' talk"   # caption under the pip
    shots: [{asset: talk_hero.png, zoom: [1.0, 1.04]}]
  - id: B4
    mode: lowerthird          # card: kinetic type; placement presets in config broll.text.placements
    start: 48.0
    end: 53.0
    placement: lowerthird
    reveal: none              # none | words (type on over reveal_s)
    lines:
      - runs: [{text: Jake Orthwein}]
      - runs: [{text: "podcast host", color: muted, at: 0.4, underline_at: null, strike_at: null}]
```

Placement presets include `title-center` (intro card) and `tile-left|mid|right` (name tags under a face
in a 3-up gallery source). `scripts/intro_overlays.py` generates the intro card and the tags from
`episode.yaml show:` / `layout_timeline:`; `references/broll-horizontal.md` is the full recipe with
a trimmed real overlay track.

The look of every card, lower-third and label (font = `subtitles.font`, colours, plate, sizes,
placements, pip border, grid gutter) lives ONLY in config `broll:`; the Remotion `Card` composition
renders each text layer as transparent ProRes 4444. QC samples every overlay window into the contact
sheet and treats a fullscreen still / grid / held frame as a planned freeze, and a `dip-<N>f` as
planned black.

## qc.json (written by qc_render.py)

```json
{
  "clip_id": "why-incentives-fail",
  "render_version": 1,
  "profile": "youtube-shorts",
  "checked_at": "2026-08-05T14:00:00Z",
  "passed": false,
  "checks": [
    {"name": "container_matches_profile", "passed": true, "detail": "h264/aac 1080x1920@30"},
    {"name": "duration_matches_manifest", "passed": true, "detail": "41.70s vs 41.70s"},
    {"name": "black_frames", "passed": true, "detail": "none"},
    {"name": "frozen_frames", "passed": true, "detail": ""},
    {"name": "loudness", "passed": false, "detail": "-11.2 LUFS, target -14.0 ±1.0"},
    {"name": "clipping", "passed": true, "detail": ""},
    {"name": "silence", "passed": true, "detail": ""},
    {"name": "cut_points", "passed": true, "detail": "2 hard cut(s) matched; 1 crossfade exempt"},
    {"name": "subtitles_present", "passed": true, "detail": "subtitle rules re-validated against final timing"},
    {"name": "manifest_agreement", "passed": true, "detail": ""}
  ],
  "contact_sheet": "renders/v1-contact-sheet.png"
}
```

`passed` is the AND of all checks. A failed QC blocks delivery — fix and re-render as a new version.

## provenance.json

```json
{
  "clip_id": "why-incentives-fail",
  "source": {"url": "…", "downloaded": "2026-08-05", "authorized_by_user": true},
  "youtube_url": null,
  "generated_media": "none"
}
```

`generated_media` must always be `"none"` — AI-generated video/imagery is prohibited in this pipeline.

### broll/provenance.json (clips and shorts with overlays or inserts)

A top-level JSON list, one entry per file in `broll/` that the clip composites. Required keys:
`file`, `source_url`, `licence`, `permission`; also recorded: `source_in`, `source_out`, `author`,
`attribution`, `downloaded`, `notes`. `broll/ATTRIBUTION.txt` carries the human-readable credits for
the video description. Real, credited media only — an AI-generated file never gets an entry.
