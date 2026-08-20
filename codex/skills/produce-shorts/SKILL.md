---
name: produce-shorts
description: Full production pipeline turning a long-form video (podcast episode, interview, talk) the user owns into polished vertical short-form clips — ingest & transcription, candidate mining, story editing, human clip selection, visual storyboards, real licensed B-roll, styled subtitles, independent critique, Remotion/FFmpeg rendering, and automated QC. Use whenever the user wants shorts, clips, reels, TikToks, YouTube Shorts, "cut down this episode", "make clips from this video/podcast", vertical video from a YouTube URL, or any long-video-to-short-clips workflow — even if they only mention one stage (e.g. "find the best moments in this episode" or "storyboard a clip").
---

# Produce Shorts — orchestrated long-form → shorts pipeline

You are the **orchestrator**. You own sequencing, state, approval gates, retries, and final outputs. You never do creative work or media processing yourself: subagents perform bounded creative roles; the deterministic scripts in `scripts/` handle all media mechanics. Design and approve every short **before** spending on asset acquisition or rendering.

## Ground rules

- **State lives in the episode directory**, never in conversation memory. `episode.yaml` and each `clips/<slug>/clip.yaml` carry a `status` field — on any resume, read them first and continue from the recorded stage. Layout and every schema: `references/schemas.md` (read it before touching any manifest).
- **Markdown is the human surface; YAML is the machine truth.** They must agree — `scripts/validate_clip.py` enforces it. Run it after every step that touches a manifest or storyboard, and always before rendering.
- **Model routing comes from `config/models.yaml`**, thresholds and profiles from `config/defaults.yaml`. Never hard-code a model in a prompt or pick one ad hoc. Every subagent gets an explicit `model` from the roles table and a self-contained prompt (paste in the schema blocks and artifacts it needs).
- **Two human gates are hard stops.** Gate 1: clip selection before any B-roll research/licensing. Gate 2: storyboard/subtitle/asset/critique sign-off before any render. Never proceed past a gate on your own judgment, and never treat silence as approval.
- **Fail loud.** Scripts exit nonzero with actionable errors; when one does, fix the input and re-run — never hand-patch outputs, eyeball-adjust media, or route around a red validator.
- **Never AI-generated video or imagery.** B-roll is real, licensed, and manifest-tracked. `provenance.json.generated_media` is always `"none"`.
- **Rights first:** the user must attest they own or are authorized to edit the source. `ingest.py` requires `--authorized`; without the attestation the pipeline does not start.

## Stage sequence

| # | Stage | Actor | Model role | Detail doc |
|---|---|---|---|---|
| 1 | Ingest, transcribe, sync | `ingest.py`, `transcribe.py`, `sync_cameras.py` | — | `references/render-qc.md` |
| 2 | Mine candidates | miner subagents, one per chunk, parallel | `strong_reasoning` | `references/editorial.md` |
| 3 | Select & edit stories | senior-editor subagent | `strong_reasoning` | `references/editorial.md` |
| — | **GATE 1: human clip selection** | user | — | `references/editorial.md` |
| 4 | Storyboard | visual-director subagent per clip, parallel | `strong_reasoning` | `references/storyboard.md` |
| 5 | B-roll research (∥ with 4) + synthesis | researcher per clip; synthesis pass | `research`, `strong_reasoning` | `references/assets.md` |
| 6 | Subtitle design (inside storyboard) | visual director | `strong_reasoning` | `references/storyboard.md` |
| 7 | Independent critique, ≤2 rounds | critic subagent per clip | `critic` | `references/editorial.md` |
| — | **GATE 2: human storyboard sign-off** | user | — | below |
| 8 | Render | `assemble_audio.py`, `align_subtitles.py`, `extract_segments.py`, `remotion/` | — | `references/render-qc.md` |
| 9 | QC + visual review | `qc_render.py`, contact sheet to user | `mechanical` for triage only | `references/render-qc.md` |

Read the detail doc when you reach the stage — not all upfront. Stages 4+5 run concurrently per clip and clips run in parallel with each other; everything else per clip is sequential.

## Running the pipeline

### Intake

Collect from the user before stage 1: source URL + authorization attestation; optional raw camera files with speaker-name → file mapping; any known sync signal/offset; target platforms (default: `youtube-shorts` profile). Create `episode-<slug>/` in the directory the user chooses.

### Stage 1 — ingest

Follow `references/render-qc.md` § Stage 1. Hard stop if camera files cannot be reliably synchronized (`sync_cameras.py` red, or verification fails): report it and ask whether to proceed source-only. Set `status.stage: ingested`.

### Stages 2–3 — editorial

Follow `references/editorial.md`: chunk → parallel miners → merge into `candidates.yaml`/`candidates.md` → senior editor produces per-clip `clip.yaml` drafts + selection memo. Quality over quota in both directions. Set stages `mined`, then `selected`.

### GATE 1

Present the selection memo, durations, and rejected list. AskUserQuestion (multiSelect) for the clips to produce. Mark approvals `approved_edit`. **No B-roll searching, licensing, or downloading before this gate passes.**

### Stages 4–7 — design loop (per approved clip, clips in parallel)

1. Dispatch visual director (storyboard + subtitle design) and asset researcher concurrently.
2. Synthesis pass reconciles intents ↔ available assets; download only synthesis-selected assets via `stock_download.py`.
3. `validate_clip.py` green.
4. Critique loop per `references/editorial.md` (max 2 rounds; unresolved disagreements go to gate 2 as open questions).
5. Statuses: `storyboarded` → `assets_ready` → `critiqued`.

### GATE 2

Present per clip: storyboard, subtitle plan, thumbnail spec, asset list with licenses, critic findings (resolved + unresolved). On approval set `approved_render`. Rejected clips loop back to stage 4 with the user's notes.

### Stages 8–9 — render & QC

Follow `references/render-qc.md`: assemble audio → lock timeline → align+validate subtitles → extract segments → Remotion compose → per-profile encode → `qc_render.py`. Renders are versioned, never overwritten. On QC red: diagnose from `qc-v<N>.json`, fix upstream input, re-render as v<N+1>. On QC green: show the user the contact sheet + render path for final approval, write `provenance.json`, set `delivered`.

### Done means

Every approved clip: green `qc-v<N>.json`, human approval on the final render, and complete deliverables — `clip.yaml`, `storyboard.md`, `assets/`, `subtitles/`, `renders/`, `qc.json`, `provenance.json`.

## Scripts index

All scripts are uv single-file scripts (`uv run scripts/<name> --help` for usage); they share `scripts/pslib.py`.

| Script | Purpose |
|---|---|
| `ingest.py` | Download source, probe media, initialize `episode.yaml` |
| `transcribe.py` | Word-level transcript + speaker labels → `transcript.json`/`.md` |
| `sync_cameras.py` | Cross-correlate camera audio → sync offsets; `verify` subcommand |
| `chunk_transcript.py` | Overlapping mining chunks + coverage proof |
| `validate_clip.py` | Manifest ↔ storyboard agreement + all timeline invariants |
| `stock_search.py` | Real provider search (configured providers only) |
| `stock_download.py` | Download + checksum + full manifest entry for a selected asset |
| `assemble_audio.py` | Build edited clip audio from the timeline mapping |
| `extract_segments.py` | Cut/crop A-roll segments (sync-offset aware) |
| `align_subtitles.py` | Force-align verbatim text to final audio → styled `.ass` |
| `validate_subtitles.py` | Readability, safe zones, overflow, timing |
| `qc_render.py` | Full render QC → `qc-v<N>.json` + contact sheet |
| `remotion/` | Deterministic composition template (`props.json` from `clip.yaml`) |

## Failure playbook

- Script red → read its error, fix the named input, re-run. Two consecutive reds on the same step with the same diagnosis → the diagnosis is wrong; re-read the artifacts before touching anything again.
- Subagent output violates schema → return it once with the validator findings; second violation → respawn fresh with a tightened prompt.
- Provider API down / key missing → that provider is out for the session; report which intents are affected, never substitute silently.
- Anything that would change an approved artifact (post-gate) → back to the gate that approved it.
