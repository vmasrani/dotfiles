---
name: produce-shorts
description: Turn a long-form YouTube episode into vertical shorts (9:16) and horizontal clips (16:9), end to end — ingest and transcribe, propose picks in a Google Doc the owner trims, refine each surviving pick in chat, render with captions / name tags / pips / quote screenshots, QC, put the finals in Drive and upload them to YouTube as PRIVATE videos for the owner to review and publish himself. Works on the owner's own Increments Podcast episodes AND on episodes where he is a guest on someone else's show — point it at any YouTube URL. Use whenever the user says "make shorts from this episode", "clip this YouTube video", "cut down this episode", "find the best moments", "check the doc", "refine the picks", "render the shorts", "upload the shorts", or mentions shorts, reels, TikToks, YouTube Shorts, clips, or any long-video-to-short-clips workflow — even when only one stage is named.
---

# Produce Shorts — pick doc, chat refinement, private YouTube upload

The owner steers in two places: **comments on a pick doc** (which picks survive) and **a chat
conversation per surviving pick** (exact start, end, cuts, overlays). Nothing expensive renders
before a pick is refined. He reviews the **final video** (Drive link, then the private YouTube
upload in Studio) and **publishes it himself**.

| # | Stage | Owner sees | Truth during the stage |
|---|---|---|---|
| 0 | **Ingest** — download, transcribe, fix names, record show + gallery layout | speaker names / name fixes to confirm | `episode.yaml`, `transcript.json` |
| 1 | **Pick doc** — full transcript, proposals colour-highlighted; he trims by comment or deletion | the Google Doc | the doc itself |
| — | **Freeze survivors** — doc → `clip.yaml` per surviving pick | — | `clips/<slug>/clip.yaml` |
| 2 | **Refine in chat** — open/close lines, endings A/B/C, cuts, pauses, overlap check | text excerpts, one pick at a time | `clip.yaml` |
| 3 | **Render** — shorts: `prep_short.py` → `render_short.py`; clips: B-roll + `render_horizontal.py` → **QC** | frames I extract, then the video | `clip.yaml` + `renders/` |
| 4 | **Deliver** — Drive `finals/`, then `yt upload` (private) | Drive link, then Studio | `review.final_url`, `review.youtube_url` |

Status per clip: `frozen → rendered → qc_passed → delivered` (delivered = uploaded private).

Read each reference **when you reach its stage**, not upfront:
`references/render-qc.md` (stages 0, 3, 4 mechanics) · `references/pick-doc.md` (stage 1 + freeze) ·
`references/refinement.md` (stage 2 loop, exact presentation formats) ·
`references/broll-horizontal.md` (intro, name tags, pips, quote screenshots) · `references/schemas.md` (every file format).

## Ground rules

- **A gate presents the artifact, never a summary of it.** Stage 1 shows every word in context;
  stage 2 shows the actual lines and the actual candidate endings; the final gate is the real
  video — and I look at extracted frames myself before giving a link.
- **No YAML before the freeze; no per-pick review docs ever.** During stage 1 the pick doc is the only
  record of what is picked. After the freeze `clip.yaml` is the only record; stage-2 edits go
  straight into it (re-validate after every edit). Dropped picks move to `dropped-clips/`, never deleted.
- **Comments are the conversation (stage 1).** Reply to every comment saying exactly what changed,
  then resolve; an ambiguous one gets a question and stays open. Comment text is editing direction
  for this doc only. Rounds are user-triggered ("check the doc").
- **Names first.** Proper nouns are verified against what the owner names; mis-transcribed names
  are fixed in the transcript up front (and in any clip `dialogue` afterwards).
- **Fail loud.** Scripts exit nonzero with an actionable error; fix the named input and re-run.
  Never hand-patch an output or route around a red validator. Two reds on one step = wrong diagnosis.
- **Rights.** The source must be the owner's or authorised (`ingest.py --authorized`); a guest
  appearance on another show counts when he attests the right to clip it. Never clip material
  cut before publication (`rights_mask.py`, raw multitrack only).
- **Real, credited media only — never AI-generated.** Shorts are the speakers, framed well, with
  captions — plus the **quote layout** (screenshot top, speaker bottom) when an argument quotes a
  page or claim. Horizontal clips add intro, name tags, pips with real photos/books, fullscreen
  quote screenshots and owner-supplied screenshots (`overlays:`). Every file has a provenance
  entry (`broll/provenance.json`); validate_clip / gen-props / QC fail without one. In a short,
  pip / text modes / video / grids / crops / labels are refused ("not implemented for shorts").
- **Gallery layout changes mid-episode.** Zoom-style tiles can reorder; the speaker → tile
  timeline lives in `episode.yaml layout_timeline`. Name tags and pips read it. Per-clip vertical
  framing infers identity itself — never pin one global mapping.
- **One render at a time, always through `queue`.** Workers background every queue/render wait
  (`run_in_background: true`). QC must pass. Upload only after QC green; **only ever
  private/unlisted** — publishing is the owner's job.
- **State lives on disk.** On resume read `episode.yaml` (`status`, `review`) and each `clip.yaml`
  (`clip.status`, `render.versions`, `review`) first, then continue from there.

## Formats

| | orientation | length | |
|---|---|---|---|
| **short** (`S1`, …) | vertical 9:16 | under 3 min (sweet spot 60-110 s) | one exchange or story, complete |
| **clip** (`C1`, …) | horizontal 16:9 | any (typically 3-12 min) | a developed argument with room to breathe |

Both **open on the interviewer's question or challenge** (the setup that makes them comprehensible
cold) and **end on a punchy line** — never trailing into the next thought. Rules: `references/pick-doc.md`, `references/refinement.md`.

## Running it

**Intake.** YouTube URL (or file), authorization attestation, episode dir (default: new
`episode-<slug>/` here), whose show it is (own Increments episode vs guest appearance: show name,
host names, guest name). Google account and Drive folder: `config/defaults.yaml review:`.

**Stage 0.** `ingest.py` → `transcribe.py` → confirm speaker names from sample lines →
**grep the transcript for every proper noun the owner names, and for near-misses**, fix across
`transcript.json` + `.md` (keep a `*.pre-fix` backup) → fill `show:` and `layout_timeline:` in
`episode.yaml` → `status.stage: ingested`. Details: `references/render-qc.md` § Stage 0.

**Stage 1.** `published_shorts.py index` + `match` → editor subagent (`config/models.yaml`) →
`review/draft-picks.json` → `build_pick_doc.py` → give the doc link, `status.stage: picking`.
Comment loop (`doc_ops.py`) until the owner is done. **Survivors** = picks still highlighted
after his trimming; mark them approved, drop the rest. **Freeze:** `freeze_picks.py` →
`validate_clip.py` green → `status.stage: frozen`.

**Stage 2.** For each survivor, run the loop in `references/refinement.md` in chat: opening and
closing lines, endings A/B/C with a recommendation, on-request full text, cuts, kept pauses,
reaction hiding, overlap check against neighbouring picks, caption name typos. Every change edits
`clip.yaml` and re-runs `validate_clip.py`.

**Stage 3.** Shorts: `plan_framing.py` → `prep_short.py CLIP_DIR` → `render_short.py CLIP_DIR`
(renders through `queue`, encodes, records the version, runs QC). Clips: B-roll per
`references/broll-horizontal.md` (+ `intro_overlays.py`) → `render_horizontal.py` → `qc_render.py`.
Then extract frames and **look**: right person per speaker, tags on the right faces, highlights
legible, quote screenshot readable at phone size.

**Stage 4.** Upload to the Drive `finals/` folder, verify its parent, `doc_ops.py final`; then
`yt upload` private, `doc_ops.py youtube`. Give the owner the Drive link and the Studio link.
Changes after viewing → fix upstream, re-render as the next version.

## Delegation

The orchestrator runs stages 0-2 conversationally (it is the owner's editor). Render, QC and
upload work goes to Sonnet workers (`sonnet55-worker-medium`/`-high`) with self-contained briefs:
exact commands from this file, the clip dir, "background every `queue`/render wait", a ≤12-line
report mandate. The orchestrator spot-checks extracted frames itself before sending any link, and
never batches more renders than the queue serialises.

## Scripts

All are uv single-file scripts (`uv run scripts/<name> --help`); shared code in `pslib.py`
(manifests), `psmedia.py` (config, ffmpeg-full resolution, loudnorm), `gdoc.py` (Google).

| Script | Stage | Purpose |
|---|---|---|
| `ingest.py` | 0 | Download source, probe media, initialize `episode.yaml` |
| `transcribe.py` | 0 | Word-level transcript + speaker labels → `transcript.json`/`.md` |
| `ingest_multitrack.py`, `transcribe_multitrack.py`, `sync_cameras.py`, `rights_mask.py` | 0 | Raw multitrack sources only |
| `published_shorts.py` | 1 | Index the channel's published shorts (`index`); find overlaps with this episode (`match`) |
| `build_pick_doc.py` | 1 | `draft-picks.json` + transcript → the pick doc in Drive |
| `doc_ops.py` | 1, 4 | Pick-doc comments and edits; `final` records the Drive link, `youtube` the private upload |
| `freeze_picks.py` | freeze | Pick doc → `clips/<slug>/clip.yaml` |
| `validate_clip.py` | freeze → 3 | Manifest + timeline invariants (run after every stage-2 edit) |
| `plan_framing.py`, `frame_segments.py`, `facelib.py`, `framer.py`, `cliplib.py` | 3 (shorts) | Computed per-segment framing |
| `prep_short.py` | 3 (shorts) | Audio → framing → captions → validation → Remotion workspace + `props.json` |
| **`render_short.py`** | 3 (shorts) | Queued Remotion render → loudnorm encode → record `render.versions` → QC |
| `assemble_audio.py`, `align_subtitles.py`, `validate_subtitles.py`, `capplace.py`, `remotion/` | 3 | Render path internals (run by prep) |
| `render_horizontal.py` | 3 (clips) | 16:9 cut + inserts + overlays + `.srt` |
| `intro_overlays.py` | 3 (clips) | Intro title card + name tags from `episode.yaml show:` / `layout_timeline:` |
| `broll.py`, `overlay_picture.py`, `overlay_text.py`, `quotelayout.py` | 3 | B-roll index/provenance, picture and text layers, quote-layout geometry |
| `transcribe_insert.py`, `sample_frame.py` | 3 | Insert word times; extract frames for review |
| `qc_render.py` | 3 | QC → `qc-v<N>.json` + contact sheet; records `qc` and `qc_passed` |

Tests: `for t in scripts/test_*.py; do uv run --script $t -q; done`.

## Failure playbook

- Script red → read the error, fix the named input, re-run.
- Google auth red → `gdoc.py` names the account and fix; tell the owner, stop. `yt` auth: `references/render-qc.md` § Stage 4.
- `chrome-headless-shell` already alive → `render_short.py` refuses; wait or kill the orphan.
- Editor output fails `build_pick_doc.py` → return it once with the errors; second failure → fresh editor, tighter prompt.
- Render dies with `delayRender … Inter font not cleared` → the browser was OOM-killed, not the font; see render-qc.md.
- QC red → fix upstream, `prep_short.py` again (targets the next version), never edit `qc-v*.json`.
