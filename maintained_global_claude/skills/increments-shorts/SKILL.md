---
name: increments-shorts
description: Turn an Increments Podcast YouTube episode into vertical shorts (9:16) and/or horizontal clips (16:9) through an interview — download, transcribe (AssemblyAI or local faster-whisper), propose picks, approve the exact words in chat, add real credited B-roll, design thumbnails + titles + descriptions, render with captions and the Increments end tag, QC, and optionally upload PRIVATE to your own YouTube channel. Works on macOS, Windows and Linux. Use when the user says "make shorts from this episode", "clip this podcast", "cut the Increments episode", "find the best moments", "make thumbnails for the shorts", or mentions shorts, reels, clips or a long-video-to-short-clips workflow.
---

# Increments Shorts — interview-driven shorts and clips

Everything is decided **in the chat**; nothing expensive renders before you approve it. Copy this
folder anywhere (e.g. `~/.claude/skills/increments-shorts/`) and it runs on macOS, Windows and Linux.

## Before anything: `uv run scripts/doctor.py --fetch --npm`

Needs only **[uv](https://docs.astral.sh/uv/)** and **Node >= 18** (for the Remotion caption renderer).
`doctor.py` checks ffmpeg (bundled via the `static-ffmpeg` package — libx264 + libass included),
Node, installs Remotion deps once, and downloads the Anton font and the Increments end tag into the
per-user cache. Fix whatever it prints FAIL for (it names the per-OS install command). Run every
script as `uv run scripts/<name>.py ...` — works the same on every OS. Paths below are relative to this folder.

## The interview (use AskUserQuestion at each gate; never skip one)

1. **Intake.** Ask: the Increments YouTube URL; confirm they own or are authorised to cut it
   (record as `--authorized`); episode folder (default `./episode-<slug>/`).
   `uv run scripts/ingest.py init EPISODE --url URL --title "..." --authorized` (downloads video + audio via the yt-dlp Python API).
   Ask **which transcription engine**: *AssemblyAI* (needs env `ASSEMBLYAI_API_KEY`; labels speakers
   automatically) or *local faster-whisper* (no key, CPU/GPU, no speaker labels). Run
   `uv run scripts/transcribe.py EPISODE --engine assemblyai --map A=host1 ...` (first run without `--map` prints sample
   lines per label — confirm names with the user, then re-run) or `--engine faster-whisper`, then write a `turns.json` from
   sample lines the user confirms and `uv run scripts/assign_speakers.py EPISODE turns.json` (see `references/render-qc.md` § Stage 0).
   Missing key → the script fails with how to set it on macOS/Linux/Windows; relay that, don't work around it.
   Fix mis-transcribed proper nouns in `transcript.json`/`.md` before picking.
2. **Format + count.** Vertical shorts, horizontal clips, or both? Roughly how many?
3. **Propose picks.** Read the **whole** transcript yourself (or hand it to one editor subagent, then
   re-check its picks). Each pick = one exchange or argument, **includes the setup that makes it
   comprehensible cold**, **ends on a punchy line** (payoff, quotable sentence, turn). Shorts <= 2:57 of speech (the 2.3 s end tag brings the file to YouTube's 3:00 cap); clips any length.
   List them as a table: id, working title, time range, length, one-line why, ending line.
   **Before listing, check what is already published:** `uv run scripts/published_shorts.py index` (no login; incremental cache),
   then `uv run scripts/published_shorts.py match EPISODE [--picks EPISODE/picks.json]`. Drop picks it marks `duplicate`, flag `partial`
   ones in the table, and relay any short it reports as ERROR/unchecked (never assume "no overlap" for those).
4. **Approve the words.** For EACH pick print the FULL transcript text with speaker names and
   `[mm:ss]` in/out stamps (`references/refinement.md` has the exact format). The user approves,
   re-ranges, cuts a span inside, or drops. Iterate until every kept pick is approved. Then write
   `EPISODE/picks.json` (shape in `scripts/picklib.py`) and run `uv run scripts/freeze_picks.py EPISODE` — it writes
   `clips/<slug>/clip.yaml` and validates each. Remaining refinement edits go straight into `clip.yaml`; re-run
   `uv run scripts/validate_clip.py CLIP_DIR` after every edit.
5. **B-roll interview** (per pick; ask with AskUserQuestion): none · name tags / lower thirds · picture-in-picture
   of people/books mentioned · highlighted quote screenshots (prefer the guest's own blog over papers, to drive
   traffic; browser-bar strip shows the URL) · intro title card (horizontal only). **Real, credited material only —
   never AI-generated imagery.** Every file gets a provenance entry (source URL, licence). Shorts support the
   quote layout and name tags; pips/cards/grids are horizontal-only. See `references/broll-horizontal.md`.
6. **Thumbnail + title + description interview** — read `references/thumbnails-titles.md` first. Propose 2-3
   thumbnail options per short (varying who is on each thumbnail across the batch), a title in the channel's voice,
   and the description (links + 3 hashtags only). Write `thumbnails.yaml`, run `uv run scripts/thumbnails.py EPISODE`.
7. **FINAL APPROVAL GATE.** Show, for **every short**, a markdown table: `| short | title | thumbnail text | chosen option |`
   side by side, plus the contact sheet image (`EPISODE/thumbnails/contact-sheet.jpg` — open it with the Read tool).
   The user picks or edits per short. **Only then render finals.**
8. **Render, one at a time:** shorts `plan_framing.py CLIP_DIR` -> `prep_short.py CLIP_DIR` -> `render_short.py CLIP_DIR`
   (renders, loudness-encodes, runs QC). Clips: B-roll per the reference -> `render_horizontal.py` -> `qc_render.py`.
   QC must pass. Then **extract frames and look** (`sample_frame.py`): right person per speaker, tags on the right
   faces, captions legible, quote screenshot readable at phone size.
9. **Deliver:** `uv run scripts/deliver.py CLIP_DIR --title "..." --thumbnail EPISODE/thumbnails/<slug>/<id>.jpg --hashtag A --hashtag B --hashtag C [--blog URL]`
   writes `deliverables/<slug>.mp4` (end tag added), `<slug>-thumbnail.jpg`, `<slug>.txt` (title, description, tags).
10. **Optional YouTube upload** (always PRIVATE): one-time setup in `references/youtube-setup.md`, then
    `uv run scripts/upload_youtube.py upload deliverables/<slug>.mp4 --meta deliverables/<slug>.txt --thumbnail deliverables/<slug>-thumbnail.jpg`.
    `--publish-at 2026-11-04T19:00:00-08:00` (or `upload_youtube.py schedule ID --at ...` later) sets a scheduled release while
    the video stays private; always write the viewer's UTC offset explicitly (ask which timezone; evenings suit Shorts).
    **Thumbnails set during processing get replaced by YouTube:** once Studio shows processing done, re-set with
    `upload_youtube.py thumbnail ID FILE` and confirm by fetching the live thumbnail.
    Remind the user: in Studio set **"Related video"** to the full episode (the only tappable link from a Short; no API for it),
    and that the Shorts feed may ignore custom thumbnails. YouTube cannot replace a file: a fix = upload new, then
    `upload_youtube.py delete OLD_ID` (asks them to type the id back — only with explicit user confirmation).

## Ground rules

- **A gate presents the artifact, not a summary.** Full words in context; the real thumbnails; real frames from the render.
- **Fail loud.** Scripts exit nonzero with an actionable message. Fix the named input and re-run; never hand-patch an
  output or route around a red validator. Two reds on one step = wrong diagnosis; re-read the code.
- **State lives on disk:** `episode.yaml`, `picks.json`, each `clip.yaml` (`clip.status`: frozen -> rendered -> qc_passed). On resume read these first.
- **Rights:** the source must be the user's or authorised (`ingest.py --authorized`).
- **Real, credited media only**; provenance for every B-roll file (validate_clip fails without it).
- **Names first:** verify proper nouns against what the user names; fix in the transcript (and in any clip `dialogue`).
- **Lessons baked into the code** are in `references/lessons.md` — read when framing, captions or quotes misbehave.
- Heavy steps (render, transcription, `npm ci`) are slow: run them in the background and keep talking to the user.
  Render one clip at a time.

## Formats

| | orientation | length |
|---|---|---|
| **short** (`S1`..) | 9:16, 1080x1920 | up to 2:57 of speech (sweet spot 60-110 s) + 2.3 s end tag |
| **clip** (`C1`..) | 16:9, 1920x1080 | any (typically 3-12 min) |

## Scripts (all `uv run scripts/<name>.py --help`)

| Script | Purpose |
|---|---|
| `doctor.py` | environment check + one-time setup |
| `ingest.py`, `transcribe.py`, `assign_speakers.py`, `transcribe_insert.py` | download, transcribe, label speakers |
| `published_shorts.py` | `index` the channel's published shorts + transcripts; `match` them against an episode / picks -> `published-overlap.json` |
| `freeze_picks.py`, `picklib.py`, `validate_clip.py` | picks.json -> clip.yaml + invariants |
| `plan_framing.py`, `frame_segments.py`, `facelib.py`, `framer.py`, `cliplib.py` | per-segment vertical framing |
| `prep_short.py`, `render_short.py` | shorts: audio, captions, Remotion workspace, render, encode, QC |
| `render_horizontal.py`, `intro_overlays.py`, `broll.py`, `overlay_picture.py`, `overlay_text.py`, `quotelayout.py` | horizontal clips + B-roll |
| `qc_render.py`, `sample_frame.py` | QC report + contact sheet; frame extraction |
| `thumbnails.py` | declarative thumbnail options + contact sheet |
| `endtag.py`, `deliver.py` | end tag, deliverables |
| `upload_youtube.py` | optional private upload, `schedule`, `thumbnail` (after processing), guarded `delete` |
| `mediatools.py`, `remotion_env.py`, `assets.py`, `pslib.py`, `psmedia.py` | shared libraries |

Tests: `uv run --script scripts/test_<name>.py -q` for each `scripts/test_*.py`.
Credit: built from the Increments Podcast production pipeline by Vaden Masrani.
