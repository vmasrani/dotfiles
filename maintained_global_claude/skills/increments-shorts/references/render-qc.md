# Mechanics: ingest, transcription, render, QC, deliver

All commands: `uv run scripts/<name>.py ...` from the skill folder (identical on macOS / Windows / Linux).

## Stage 0 — ingest and transcribe

1. `ingest.py init EPISODE --url URL --title "Episode title" --authorized` -> `source/episode.mp4` + `source/episode.m4a`
   (yt-dlp Python API), probes, `episode.yaml`. Without `--authorized` it refuses.
2. **Engine = the user's choice.**
   - `transcribe.py EPISODE --engine assemblyai` — needs env `ASSEMBLYAI_API_KEY`
     (macOS/Linux `export ASSEMBLYAI_API_KEY=...`; Windows PowerShell `setx ASSEMBLYAI_API_KEY "..."` then a new terminal).
     First run prints sample lines per diarization label and exits 2; show them to the user, then re-run with
     `--map A=host1 --map B=guest1` (ids must exist in `episode.yaml speakers[]`; edit that file first: `id`, `name`, optional `full_name`, `role`).
   - `transcribe.py EPISODE --engine faster-whisper [--model small.en]` — local, CPU or CUDA; first run downloads the model.
     Words get speaker `unassigned`. Read the transcript, show the user sample lines per speaker, agree who talks when, write
     `turns.json` (`{"turns":[{"start":0,"end":41.2,"speaker":"host1"}, ...]}`, spans must cover every word), then
     `assign_speakers.py EPISODE turns.json`. Face/tile evidence (`sample_frame.py`) can settle who is on screen when the turns are ambiguous.
3. Fix mis-transcribed proper nouns in `transcript/transcript.json` and `.md` (keep a `*.pre-fix` copy).
4. If the source is a Zoom-style gallery whose tiles can reorder, fill `layout_timeline:` in `episode.yaml` (see schemas.md § episode.yaml)
   and `show:` (show name, hosts, guest) for name tags / intro card.

## Freeze, refine

`picks.json` -> `freeze_picks.py EPISODE` -> `clips/<slug>/clip.yaml` (validated). Refinement edits go into `clip.yaml`
(`refinement.md`); `validate_clip.py CLIP_DIR` after every edit.

## Shorts (vertical)

```
plan_framing.py CLIP_DIR     # per-segment framing (who is on screen)
prep_short.py CLIP_DIR       # audio, captions, Remotion workspace + props.json
render_short.py CLIP_DIR     # Remotion render -> loudnorm encode -> record version -> QC
```
- Needs Node >= 18. The first `prep_short.py` runs `npm ci` once in the skill's `remotion/` folder (shared by all clips; a
  clip workspace links to it — a junction on Windows, a symlink elsewhere). Remotion downloads its own Chrome on the first render.
- Outputs: `renders/v<N>-master.mp4` (visual master), `renders/v<N>-youtube-shorts.mp4` (the loudness-normalised final),
  `renders/v<N>-contact-sheet.png`, `qc-v<N>.json`. Versions are append-only; a QC failure leaves v<N> recorded — fix upstream
  and re-run `prep_short.py` (targets v<N+1>). Never edit `qc-v*.json`.
- Render ONE clip at a time; it is memory-hungry. An out-of-memory kill shows up as a Chrome/`delayRender` error: close other apps and re-run.
- If prep exits 2 the subtitle validator failed: read the printed log, fix the clip, do not render those captions.

## Clips (horizontal)

B-roll per `broll-horizontal.md`, then `render_horizontal.py CLIP_DIR` and `qc_render.py CLIP_DIR`.

## Look at the frames (always)

`sample_frame.py` extracts frames (see `--help`); view the contact sheet and a few frames at overlay entries: right person per speaker,
name tags on the right faces, captions legible at phone size, quote screenshot readable, nothing covering a speaking face.

## Deliver

`deliver.py CLIP_DIR --title ... --thumbnail ... --hashtag A --hashtag B --hashtag C` -> `deliverables/`. It refuses unless the clip is `qc_passed`.
The end tag (`endtag.py`) is applied to every vertical short (its own segment after the untouched short: full black screen with the tag over it, the tag's sound) and,
for horizontal clips, scaled to the frame height and centred on the black screen.
Upload (optional): `youtube-setup.md`.

## Failure playbook

- Script red -> read the error, fix the named input, re-run. Two reds on one step = wrong diagnosis.
- `static-ffmpeg is not installed` -> you ran bare `python`; use `uv run scripts/<name>.py`.
- `node` missing/too old -> the error prints the install command for your OS.
- End tag / font download fails -> check the network; the end tag is also in the shared folder
  https://drive.google.com/drive/folders/1Ik7EnTVXMMVH06qzJDWCDPvecm7FkNsI (drop it into the cache dir `doctor.py --fetch` prints).

## Gotcha: source must be a real file

Remotion serves `source/episode.mp4` through a linked public dir; if `source/episode.mp4` is itself a symlink to a file elsewhere,
the render fails with `missing media at render time ... HTTP 404`. `ingest.py` downloads real files, so this only bites hand-placed
sources: copy (or hard-link) the file into `EPISODE/source/`.
