# Canonical schemas — the machine-readable source of truth

Before the freeze, the **pick doc** (a Google Doc) is the only record of what is picked — there is
no YAML for picks. From the freeze on, `clip.yaml` is the machine truth; storyboard docs are
generated *from* it and never parsed back. `scripts/validate_clip.py` enforces the invariants
below after the freeze and before any render.

## Units and time systems

- All times in YAML are **seconds as floats** (e.g. `734.20`). Human surfaces render `mm:ss` / `MM:SS.mmm`.
- Two distinct time systems exist and must never be conflated:
  - **Source time** — position in the original media file.
  - **Output time** — position in the finished short or clip.
- Comparison epsilon everywhere: `0.01s`.
- IDs are stable once assigned: pick IDs `S1…`/`C1…` per episode; segment IDs `S01, S02, …` per clip. Never renumber on revision — retire IDs and append new ones (the one exception: `doc_ops.py format` renames a pick whose format changes).

## Project layout

```text
episode-<slug>/
  episode.yaml
  source/                 # downloaded episode (+ raw camera files, multitrack only)
  transcript/
    transcript.json
    transcript.md
  published-overlap.json  # published_shorts.py match output
  review/
    draft-picks.json      # editor's one-shot input to build_pick_doc.py; never read again
    pick-doc.html         # what was uploaded (debug only — the Google Doc is the truth)
  clips/
    <clip-slug>/
      clip.yaml           # canonical manifest (schema below)
      storyboard/rev<N>/  # beats.json, beat-<k>.png, cover-<k>.png, preview.mp4, storyboard.docx
      assets/aroll/       # extracted source segments
      assets/faces/       # per-segment face detections (cache for the computed crops)
      subtitles/          # aligned .ass (shorts) / .srt (clips), validation report
      renders/            # versioned, never overwritten
      qc-v<N>.json
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
speakers:
  - id: host1                 # referenced by transcript + clip timelines
    name: "Vaden"
    camera_file: null         # optional isolated footage (multitrack only)
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
sync: []                      # multitrack only: [{file, offset_s, confidence, method, gaps, verified}]
transcript:
  json: transcript/transcript.json
  md: transcript/transcript.md
  engine: assemblyai          # or mlx-whisper
  language: en
  word_count: 48210
review:                       # written by build_pick_doc.py / doc_ops.py
  account: incrementspodcast@gmail.com
  folder_id: "1AbC…"          # this episode's Drive folder
  pick_doc: {id: "1XyZ…", url: "https://docs.google.com/document/d/1XyZ…/edit"}
  log_comment_id: "AAAA…"     # the revision-log thread
  round: 2
  picks:                      # pick id → colour + status; colours never reused in one doc
    S1: {format: short, color: "#FFE08A", status: approved, title: "…"}
    C1: {format: clip,  color: "#B6E3F4", status: proposed, title: "…"}
status:
  stage: ingested             # ingested → picking → frozen → storyboarding → rendering → delivered
```

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
truth (the pick doc's paragraphs). Speaker IDs must match `episode.yaml speakers[].id`; the
transcription step maps diarization labels (e.g. `SPEAKER_00`) to speaker IDs and records the mapping.

## clip.yaml — the canonical per-clip manifest

Written by `freeze_picks.py`; refined by `plan_framing.py` and stage-2 comment edits.

```yaml
clip:
  id: why-incentives-fail     # slug, from the pick title
  pick: S1                    # pick id in the pick doc
  format: short               # short (9:16, < 180 s) | clip (16:9, any length)
  title: "Why incentives backfire"
  status: frozen              # frozen → storyboarded → approved_render → rendered → qc_passed → delivered
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
    audio: as-recorded        # as-recorded | duck | mute
    visual:
      kind: aroll             # aroll = the episode; insert = a credited non-episode source (clips only, § Inserts).
                              #  B-roll is never a timeline segment — it lives in `overlays:` (§ Overlays)
      treatment: closeup-host1   # short: closeup-<speaker> | splitscreen ; clip: source-frame
      speakers: null          # splitscreen only: exactly two speaker ids [top, bottom]
      locked: false           # true = user override by comment; plan_framing.py never changes it
      reason: null            # why: the framing rule, or the user's comment text
      crop: null              # optional hand override "x=..:y=..:w=..:h=.." for a closeup; normally absent —
                              # crops are computed per segment from face detection (extract_segments.py)
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
  storyboard_docs: []         # [{rev, id, url}] — append-only
  cover: null                 # chosen cover still index (from a stage-2 comment)
  final_url: null             # Drive link of the delivered render
output:                       # short: 9:16 1080x1920 ; clip: 16:9 1920x1080
  aspect: "9:16"
  resolution: "1080x1920"
  fps: 30
  duration_s: 41.70           # must equal last timeline output_out
render:
  versions: []                # append-only: {version, preview, finals: {profile: path},
                              #  rendered_at, qc: qc-v1.json}
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
13. **Overlays** (§ Overlays): `format: clip` only; a `broll:` block exists; ids unique; window inside `[0, duration_s]`; fades fit the window; picture modes have `shots` and no `lines`, text modes the reverse; `pip` needs a `box` (inside the frame, even width and height), `fullscreen` has none; `from_box` ⇔ `move_frames`; shots start at 0 and ascend inside the window, each names exactly one of `asset`/`grid`; dissolves fit both shots; zoom within 1–2; crops parse and lie inside the asset; grid tiles are stills and fit `cols×rows`; a video range lies inside the asset's duration and plays at least its slot (or says `hold_last`); every asset exists and has a provenance entry; no picture overlay over an insert; no fullscreen overlay past the start of the protected tail; text-run times lie inside the window; overlays in the same layer (picture: fullscreen+pip; text: lowerthird+card) never overlap.

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
  "pick_doc": "https://docs.google.com/document/d/…",
  "storyboard_doc": "https://docs.google.com/document/d/…",
  "generated_media": "none"
}
```

`generated_media` must always be `"none"` — AI-generated video/imagery is prohibited in this pipeline.

### broll/provenance.json (horizontal clips with overlays or inserts)

A top-level JSON list, one entry per file in `broll/` that the clip composites. Required keys:
`file`, `source_url`, `licence`, `permission`; also recorded: `source_in`, `source_out`, `author`,
`attribution`, `downloaded`, `notes`. `broll/ATTRIBUTION.txt` carries the human-readable credits for
the video description. Real, credited media only — an AI-generated file never gets an entry.
