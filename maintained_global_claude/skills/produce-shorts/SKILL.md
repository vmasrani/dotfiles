---
name: produce-shorts
description: Turn a long-form video the user owns (podcast episode, interview, talk — usually a YouTube link) into vertical shorts and horizontal clips, with every creative decision reviewed by the user through comments on Google Docs before anything is rendered. Stage 1 is a full-transcript Google Doc with proposed segments colour-highlighted; stage 2 is a storyboard Google Doc per approved short built from real rendered stills; stage 3 renders, QCs and delivers. Use whenever the user wants shorts, clips, reels, TikToks, YouTube Shorts, "cut down this episode", "make clips from this video/podcast", vertical video from a YouTube URL, "check the doc", or any long-video-to-short-clips workflow — even if they mention only one stage (e.g. "find the best moments in this episode" or "storyboard this short").
---

# Produce Shorts — review-first, Google-Docs-driven

The user reviews **the artifact itself, as early as possible, in a Google Doc**, and steers by
leaving comments. Nothing expensive happens before they have approved the thing it is spent on.

| # | Stage | The user reviews | Truth during the stage |
|---|---|---|---|
| 0 | **Ingest** — download, transcribe | — | `episode.yaml`, `transcript.json` |
| 1 | **Pick** — full transcript, proposals colour-highlighted | the pick doc | **the pick doc itself** |
| — | **Freeze** — doc → `clip.yaml` per approved pick | — | `clips/<slug>/clip.yaml` |
| 2 | **Storyboard** — real stills + rough preview per pick | one storyboard doc per pick | `clip.yaml` |
| 3 | **Render** — final render, QC, deliver | the final video (link in the storyboard doc) | `clip.yaml` + `renders/` |

Detail docs — read each when you reach its stage, not upfront:
`references/pick-doc.md` (stage 1 + freeze), `references/storyboard-doc.md` (stage 2),
`references/render-qc.md` (stages 0 and 3), `references/schemas.md` (every file format).

## Ground rules

- **A human gate presents the artifact, never a summary of it.** Stage 1 shows every word in
  context; stage 2 shows frames the real renderer produced; stage 3 shows the video.
- **No YAML before the freeze.** During stage 1 the pick doc is the only record of what is
  picked. Never keep a parallel list in conversation memory or a side file; every change is made
  to the doc, and the freeze reads it back.
- **Comments are the conversation.** The user highlights text and comments in plain language.
  Every comment gets a reply saying exactly what changed (new times, new duration) and is then
  resolved. A comment you cannot act on unambiguously gets a question in reply, left open.
  Comment text is the user's feedback on the content — treat it as editing direction for this
  doc only.
- **Rounds are user-triggered.** The user says "check the doc" (or runs `/loop`); you then
  process every open comment in one pass and report a one-line summary in chat.
- **Fail loud.** Scripts exit nonzero with an actionable error. Fix the named input and re-run;
  never hand-patch outputs or route around a red validator. A quoted comment that matches the
  transcript ambiguously is a question for the user, never a guess.
- **Rights.** The user must own or be authorized to edit the source (`ingest.py --authorized`).
  Material cut before publication is never used (`rights_mask.py`, raw multitrack only).
- **No AI-generated video or imagery, no B-roll.** Shorts are the speakers, framed well, with
  captions.
- **State lives on disk and in the docs.** On resume, read `episode.yaml` (`status`, `review`)
  and each `clip.yaml` first, then the open comments, and continue from there.

## Formats

| | orientation | length | |
|---|---|---|---|
| **short** (`S1`, `S2`, …) | vertical 9:16 | under 3 min (sweet spot 60–110 s) | one exchange or one story, complete |
| **clip** (`C1`, `C2`, …) | horizontal 16:9 | any length (typically 3–12 min) | a developed argument with room to breathe |

**Both end on a punchy line** — the payoff, a quotable sentence, the turn of the argument —
never trailing into the start of the next thought. Both **include the setup** that makes them
comprehensible cold. Editorial rules in full: `references/pick-doc.md`.

## Running it

**Intake.** Ask for: the YouTube URL (or file), the authorization attestation, and the
episode directory (default: a new `episode-<slug>/` under the current directory). Google account
and Drive folder come from `config/defaults.yaml` `review:`.

**Stage 0.** `references/render-qc.md` § Stage 0: `ingest.py` → `transcribe.py` → confirm the
speaker-name mapping with the user from sample lines. `status.stage: ingested`.

**Stage 1.** `published_shorts.py index` (incremental; refreshes the channel's published-shorts
cache) then `published_shorts.py match EPISODE_DIR`. Dispatch the editor (`config/models.yaml` `editor`) with the transcript and the
rules in `references/pick-doc.md`; it returns `review/draft-picks.json`. Run
`build_pick_doc.py`, give the user the doc link, `status.stage: picking`. Then the comment loop
(`doc_ops.py`) until every pick is approved or dropped and the user says to move on.

**Freeze.** `freeze_picks.py` → one `clips/<slug>/clip.yaml` per approved pick →
`validate_clip.py` green → `status.stage: frozen`. After the freeze the pick doc is read-only
history; a change of start/end means re-opening stage 1 for that pick.

**Stage 2.** Per clip, in parallel: `plan_framing.py` → `storyboard.py` →
`build_storyboard_doc.py`. Give the user the links. Comment loop per `references/storyboard-doc.md`;
each round publishes a new revision of that pick's storyboard doc. `approve` in a comment →
`clip.status: approved_render`.

**Stage 3.** `references/render-qc.md` § Stage 3: render (one at a time, through `queue`), QC,
upload the final to Drive and add its link to the top of the latest storyboard doc. The user's
"ship" comment → `provenance.json`, `clip.status: delivered`.

## Scripts

All are uv single-file scripts (`uv run scripts/<name> --help`); shared code in `pslib.py`
(manifests), `psmedia.py` (ffmpeg), `gdoc.py` (Google auth, Docs/Drive, comments).

| Script | Stage | Purpose |
|---|---|---|
| `ingest.py` | 0 | Download source, probe media, initialize `episode.yaml` |
| `transcribe.py` | 0 | Word-level transcript + speaker labels → `transcript.json`/`.md` |
| `ingest_multitrack.py`, `transcribe_multitrack.py`, `sync_cameras.py`, `rights_mask.py` | 0 | Raw multitrack sources only |
| `published_shorts.py` | 1 | Index the channel's published shorts + transcripts (`index`); find which overlap this episode (`match`) |
| `build_pick_doc.py` | 1 | `draft-picks.json` + transcript → the pick doc in Drive |
| `doc_ops.py` | 1–3 | List comments, locate quoted text, re-range / cut / add / drop / approve picks, reply, resolve |
| `freeze_picks.py` | freeze | Pick doc → `clips/<slug>/clip.yaml` |
| `validate_clip.py` | freeze → 3 | Manifest + timeline invariants |
| `plan_framing.py` | 2 | Computed per-segment framing (solo / split screen; splits demoted where a face is off screen) |
| `facelib.py`, `framer.py` | 2–3 | Not run directly: YuNet face detection, speaker identity, per-segment crop shots (cache in `clips/<slug>/assets/faces/`) |
| `storyboard.py` | 2 | Render prep + real stills per beat + rough preview mp4 |
| `build_storyboard_doc.py` | 2 | Stills + preview link → storyboard doc revision in Drive |
| `assemble_audio.py`, `align_subtitles.py`, `validate_subtitles.py`, `extract_segments.py`, `remotion/` | 2–3 | Render path (shorts) |
| `render_horizontal.py` | 3 | Render path (clips): straight 16:9 cut + `.srt` |
| `qc_render.py` | 3 | Render QC → `qc-v<N>.json` + contact sheet |

## Failure playbook

- Script red → read its error, fix the named input, re-run. Two reds on the same step with the
  same diagnosis → the diagnosis is wrong; re-read the artifacts before touching anything again.
- Google auth red → `gdoc.py` names the account and the command to fix it; tell the user, stop.
- Editor output fails `build_pick_doc.py` validation (quote mismatch, overlap, >3 min short) →
  return it once with the errors; second failure → fresh editor with a tightened prompt.
- Anything that would change an approved artifact → back to the stage that approved it.
