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
      kind: aroll             # always aroll — no B-roll in this pipeline
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
  base_color: "#FFFFFF"
  emphasis_palette: ["#FFD34D"]
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
5. Every `broll` segment names an `asset_id` present in `assets[]` (vacuous: no B-roll).
6. Every asset's `used_in_segments` matches the timeline exactly (vacuous: `assets: []`).
7. Every asset file exists on disk and its `sha256` matches (vacuous).
8. Subtitle `output_range`s lie within `[0, duration_s]`, do not overlap, and each range's text words appear (in order) in the union of `dialogue` of the segments it spans.
9. `format: short` uses only `closeup-*` / `splitscreen`; a `splitscreen` names exactly two distinct speakers; `format: clip` uses only `source-frame`. `output.aspect` matches the format.
10. Speaker IDs and `treatment` speaker references exist in `episode.yaml speakers[]`.

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
