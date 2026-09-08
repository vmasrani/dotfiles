# Canonical schemas — the machine-readable source of truth

Markdown (`storyboard.md`, `candidates.md`) is the human review surface. YAML (`episode.yaml`, `clip.yaml`, `candidates.yaml`) is the machine truth. The two must agree; `scripts/validate_clip.py` enforces agreement before any render. When they disagree, the pipeline stops — nobody "picks one".

## Units and time systems

- All times in YAML are **seconds as floats** (e.g. `734.20`). Markdown surfaces render `MM:SS.mmm` or `MM:SS.mmm-MM:SS.mmm` ranges.
- Two distinct time systems exist and must never be conflated:
  - **Source time** — position in the original media file.
  - **Output time** — position in the finished short.
- Comparison epsilon everywhere: `0.01s`.
- All IDs are stable once assigned: segment IDs `S01, S02, …` per clip; asset IDs `A01, A02, …` per clip. Never renumber on revision — retire IDs and append new ones.

## Project layout

```text
episode-<slug>/
  episode.yaml
  source/                 # downloaded episode + raw camera files
  transcript/
    transcript.json
    transcript.md
  candidates.yaml         # machine truth for stage 2/3
  candidates.md           # human review surface
  clips/
    <clip-slug>/
      clip.yaml           # canonical manifest (schema below)
      storyboard.md       # human creative plan
      assets/             # licensed B-roll + extracted source shots
      subtitles/          # design plan, aligned .ass, validation report
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
  authorized: true            # user attested ownership/authorization; ingest refuses to run when false/absent
  created: "2026-08-05"
platform_profiles:
  - name: youtube-shorts
    aspect: "9:16"
    resolution: "1080x1920"
    fps: 30
    max_duration_s: 180
    container: mp4
    video_codec: h264
    audio_codec: aac
    loudness_lufs: -14.0
    true_peak_dbtp: -1.0
speakers:
  - id: host1                 # referenced by transcript + clip timelines
    name: "Vaden"
    camera_file: source/cam_vaden.mp4    # optional isolated footage
    preferred_crop: null      # e.g. "x=120:y=0:w=960:h=1080", set after probe
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
sync:                         # one entry per camera file; empty list if none
  - file: source/cam_vaden.mp4
    offset_s: 12.432          # camera t0 occurs 12.432s after episode t0
    confidence: 0.97          # correlation confidence, 0..1
    method: audio-cross-correlation
    gaps: []                  # [{camera_s: 840.0, duration_s: 3.2}] discontinuities
    verified: true            # set true only after spot-check passes
transcript:
  json: transcript/transcript.json
  md: transcript/transcript.md
  engine: assemblyai          # or mlx-whisper
  language: en
  word_count: 48210
status:
  stage: ingested             # ingested → mined → selected → storyboarded → assets_acquired
                              # → critiqued → approved_for_render → rendered → qc_passed
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

`words` is the alignment truth (subtitles, cut points). `segments` is the readable/mining truth. Speaker IDs must match `episode.yaml speakers[].id`; the transcription step maps diarization labels (e.g. `SPEAKER_00`) to speaker IDs and records the mapping.

## candidates.yaml

```yaml
coverage:                     # proves no transcript range was skipped during mining
  chunks:
    - {start_s: 0.0, end_s: 960.0, overlap_next_s: 120.0}
candidates:
  - id: C01
    slug: why-incentives-fail
    source_in: 734.2
    source_out: 851.0
    context_before: "…text of the ~30s before…"
    context_after: "…text of the ~30s after…"
    summary: "One-sentence central idea."
    hook_text: "verbatim first line"
    scores:                   # each 1-10
      hook: 8
      standalone: 9
      central_idea: 8
      payoff: 7
      edit_boundaries: 9
      visual_potential: 6
      missing_context: 8      # 10 = none missing
      redundancy: 9           # 10 = fully distinct
      risk: 10                # 10 = no factual/legal/reputational risk
    notes: "why this works / concerns"
    verdict: null             # senior editor fills: selected | rejected:<reason>
```

## clip.yaml — the canonical per-clip manifest

```yaml
clip:
  id: why-incentives-fail
  title: "Why incentives backfire"
  status: proposed            # proposed → approved_edit → storyboarded → assets_ready
                              # → critiqued → approved_render → rendered → qc_passed → delivered
  logline: "One-sentence central idea."
  audience_response: "What the viewer should feel/think."
  hook: "Why the first 3 seconds hold."
  payoff: "How the ending lands."
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
      kind: aroll             # aroll | broll
      treatment: closeup-host1   # aroll: closeup-<speaker>|splitscreen|source-frame|reaction-<speaker>
                              # broll: cover | contain | letterbox (closed set — the renderer
                              # refuses free-form B-roll treatments rather than guessing)
      asset_id: null          # broll only: must exist in assets[]
      motion: null            # e.g. "slow zoom-in 100->108% over segment"
    transition: cut           # transition INTO next segment: cut | crossfade-<N>f
subtitles:
  font: "Inter Semibold"
  base_color: "#FFFFFF"
  emphasis_palette: ["#FFD34D"]   # episode-level, restrained
  position_default: bottom-center
  lines:
    - output_range: [0.0, 3.0]    # design-time; final timing comes from forced alignment
      text: "Today we're breaking down..."
      emphasis:
        - {word: "breaking", style: bold-gold}
      position: bottom-center     # bottom-center | middle-lower
      note: "why moved, if moved"
assets:
  - id: A03
    provider: pexels
    provider_asset_id: "857195"
    source_url: "https://www.pexels.com/video/857195/"
    license: "Pexels License"
    entitlement: free            # free | subscription | purchased
    download_date: "2026-08-05"
    creator: "Jane Doe"
    credit_required: false
    width: 3840
    height: 2160
    fps: 25.0
    duration_s: 14.2
    file: assets/A03-cityscape.mp4
    sha256: "…"
    used_in_segments: [S03]
output:
  aspect: "9:16"
  resolution: "1080x1920"
  fps: 30
  duration_s: 41.70             # must equal last timeline output_out
thumbnail:
  first_frame_text: "INCENTIVES BACKFIRE"
  hierarchy: "hook word largest; subtitle line secondary"
  placement: "upper third, inside safe zone"
render:
  versions: []                  # append-only: {version, preview, finals: {profile: path},
                                #  rendered_at, qc: qc-v1.json}
```

## Timeline invariants (enforced by validate_clip.py)

1. Output timeline is contiguous from zero: `timeline[0].output_in == 0.0`; each `output_in == previous output_out` (±ε). No gaps, no overlaps.
2. Segment durations match across time systems: `output_out - output_in == source_out - source_in` (±ε). No speed changes exist in this pipeline; a mismatch is an error, not a feature.
3. Every `source_in/source_out` lies within the probed duration of `source_file` (from `episode.yaml media.probes`).
4. `clip.output.duration_s == timeline[-1].output_out` (±ε) and ≤ every target profile's `max_duration_s`.
5. Every `broll` segment names an `asset_id` present in `assets[]`, and that asset's `duration_s` ≥ segment duration.
6. Every asset's `used_in_segments` matches the timeline exactly (both directions — no unused assets, no untracked usage).
7. Every asset file exists on disk and its `sha256` matches.
8. Subtitle `output_range`s lie within `[0, duration_s]`, do not overlap, and each range's text words appear (in order) in the union of `dialogue` of the segments it spans.
9. `storyboard.md` agrees with `clip.yaml` (see parse rules below).
10. Speaker IDs and `treatment` speaker references exist in `episode.yaml speakers[]`.

## storyboard.md — parse contract

The storyboard must contain exactly one **Timeline** table and one **Subtitle plan** table with these headers (columns in this order):

```markdown
| Segment | Output | Source | Visual | Audio/Dialogue | Speaker | Shot/Transition |
|---|---|---|---|---|---|---|
| S01 | 00:00.000-00:07.350 | 12:14.200-12:21.550 | Close-up host1 | "exact dialogue" | host1 | cut |
```

```markdown
| Output | Verbatim text | Emphasis | Position | Notes |
|---|---|---|---|---|
| 00:00.000-00:03.000 | Today we're breaking down... | **breaking** gold | bottom-center | opening |
```

Validator checks per row: segment ID exists in `clip.yaml`, output/source ranges match (±ε after `MM:SS.mmm` → seconds conversion), speaker matches, B-roll rows mention the correct asset ID in the Visual cell. Prose sections around the tables are free-form and unvalidated.

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
    {"name": "black_frames", "passed": true, "detail": "none outside storyboard"},
    {"name": "frozen_frames", "passed": true, "detail": ""},
    {"name": "loudness", "passed": false, "detail": "-11.2 LUFS, target -14.0 ±1.0"},
    {"name": "clipping", "passed": true, "detail": ""},
    {"name": "silence", "passed": true, "detail": ""},
    {"name": "cut_points", "passed": true, "detail": "2 hard cut(s) matched; 1 crossfade exempt"},
    {"name": "subtitles_present", "passed": true, "detail": "subtitle rules re-validated against final timing"},
    {"name": "assets_tracked", "passed": true, "detail": ""},
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
  "assets": [
    {"id": "A03", "provider": "pexels", "provider_asset_id": "857195",
     "license": "Pexels License", "source_url": "…", "credit_required": false,
     "credit_text": null}
  ],
  "generated_media": "none"
}
```

`generated_media` must always be `"none"` — AI-generated video/imagery is prohibited in this pipeline.
