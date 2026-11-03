#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
# ]
# ///
"""Stage 2 for horizontal clips (`clip.format: clip`) — no Remotion, just ffmpeg.

For CLIP_DIR (any frozen-or-later status):

1. `assemble_audio.py` builds `renders/v<N>-audio.wav` (sample-accurate cuts, micro-crossfade
   at internal cuts).
2. Two-pass `loudnorm` brings that audio to the `youtube` profile's LUFS / true-peak.
3. B-roll layers (only when clip.yaml has `overlays:`; schemas.md § Overlays): every fullscreen /
   pip overlay is built as a transparent full-frame layer (overlay_picture.py, ffmpeg) and every
   lower-third / card / picture label as a transparent ProRes 4444 layer from the Remotion `Card`
   composition (overlay_text.py) — the default ffmpeg has no drawtext. Layers live in
   `renders/.v<N>-layers/` (scratch, deleted after a green render).
4. One ffmpeg run cuts every timeline segment from its 16:9 source (an insert segment from its own
   broll/ file, letterboxed; `dip-<N>f` transitions fade through black), joins them with the
   concat FILTER (never the demuxer with `-c copy`, which silently drops frames), overlays every
   layer at its window, and muxes the normalised audio -> `renders/v<N>-youtube.mp4`.
5. `align_subtitles.py --srt` force-aligns the dialogue to the final audio ->
   `subtitles/v<N>.srt` (an uploaded YouTube caption sidecar, never burned in). Word timings
   come from the episode transcript remapped onto the output timeline (`--words-json` mode; an
   insert contributes its own `insert.words`), or from re-transcribing the final audio with `--engine`.
6. `render.versions` in clip.yaml gets the new version appended and status becomes `rendered`.

Versioned, never overwritten: an existing v<N> output is a hard refusal. Next step:
`qc_render.py CLIP_DIR --version N --profile youtube`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console

from broll import load_insert_words, remapped_words
from overlay_picture import build_picture_layer, composite_filters
from overlay_text import plan_text_layers, render_text_layers
from pslib import (
    Clip,
    RenderVersion,
    ffprobe_media,
    load_clip,
    load_episode,
    load_transcript,
    save_clip,
)
from psmedia import (
    SCRIPTS_DIR,
    episode_root_for,
    ff_time,
    TRUE_PEAK_MARGIN_DB,
    frame_exact,
    load_config,
    loudnorm_filter,
    media_path,
    parse_crop,
    profile_dims,
    resolve_profile,
    run_checked,
    run_ffmpeg,
)

console = Console()
app = typer.Typer(add_completion=False)

FROZEN = "frozen"  # a frozen clip renders directly; the first render moves it to "rendered"
PROFILE = "youtube"
_DIP_RE = re.compile(r"^dip-(\d+)f$")


def dip_frames(transition: str, where: str) -> int:
    """`cut` -> 0, `dip-<N>f` -> N (fade N frames to black and N back up). Anything else is refused."""
    value = transition.strip().lower()
    if value == "cut":
        return 0
    m = _DIP_RE.match(value)
    if m is None:
        raise ValueError(
            f"{where}: transition {transition!r} is not supported on horizontal clips — use `cut` or "
            f"`dip-<N>f` (a dip through black, e.g. into and out of an insert)"
        )
    return int(m.group(1))


def video_filtergraph(clip: Clip, w: int, h: int, fps: float) -> str:
    """Per-segment trim -> (insert: crop) -> scale/pad to the profile frame -> dips -> concat filter.

    Audio comes from the wav. A `dip-<N>f` transition fades the outgoing segment's last N frames to
    black and the incoming segment's first N frames up from black; the cut point never moves.
    """
    parts = []
    dips = [dip_frames(seg.transition, seg.id) for seg in clip.timeline]
    for i, seg in enumerate(clip.timeline):
        n = round(seg.output_out * fps) - round(seg.output_in * fps)
        fades = []
        if i > 0 and dips[i - 1]:
            fades.append(f"fade=t=in:st=0:d={dips[i - 1] / fps:.6f}")
        if dips[i] and i + 1 < len(clip.timeline):
            fades.append(f"fade=t=out:st={(n - dips[i]) / fps:.6f}:d={dips[i] / fps:.6f}")
        crop = ""
        if seg.visual.crop is not None:
            cw, ch, cx, cy = parse_crop(seg.visual.crop)
            crop = f"crop={cw}:{ch}:{cx}:{cy},"
        parts.append(
            f"[{i}:v]{crop}scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,{frame_exact(seg.output_in, seg.output_out, fps)}"
            + ("," + ",".join(fades) if fades else "")
            + f",format=yuv420p[v{i}]"
        )
    labels = "".join(f"[v{i}]" for i in range(len(clip.timeline)))
    parts.append(f"{labels}concat=n={len(clip.timeline)}:v=1:a=0[cut]")
    return ";".join(parts)


def build_layers(clip: Clip, clip_dir: Path, layer_dir: Path, w: int, h: int, fps: float, config) -> list[tuple[Path, object]]:
    """Every overlay layer for this render, in compositing order: pictures, then their labels and text."""
    if not clip.overlays:
        return []
    if config.broll is None:
        raise ValueError("clip.yaml has overlays but config/defaults.yaml has no `broll:` block (card/pip style)")
    layer_dir.mkdir(parents=True, exist_ok=True)
    pictures = sorted((ov for ov in clip.overlays if ov.layer == "picture"), key=lambda o: o.start)
    out: list[tuple[Path, object]] = []
    for ov in pictures:
        path = layer_dir / f"{ov.id}.mkv"
        logger.info(f"picture layer {ov.id} ({ov.mode}) {ov.start:.2f}-{ov.end:.2f}s")
        build_picture_layer(ov, clip_dir, w, h, fps, config.broll, path)
        out.append((path, ov))
    text = plan_text_layers(clip.overlays, config.broll, config.subtitles, w, h, fps)
    logger.info(f"rendering {len(text)} text layer(s) with Remotion (Card)")
    paths = render_text_layers(text, clip_dir, layer_dir / "cards", config.broll.render.card_concurrency)
    out += sorted(((paths[t.name], t.overlay) for t in text), key=lambda pair: pair[1].start)
    return out


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml"),
    engine: str = typer.Option(
        None, "--engine",
        help="Re-transcribe the FINAL audio for subtitle timing (assemblyai | mlx-whisper). "
        "Default: remap the episode transcript's word timings onto the output timeline.",
    ),
    episode_root: Path = typer.Option(None, "--episode-root", help="Episode root holding episode.yaml (default: CLIP_DIR/../..)"),
    config_path: Path = typer.Option(None, "--config", help="Pipeline config (default: config/defaults.yaml)"),
    crf: int = typer.Option(18, "--crf", help="x264 quality of the deliverable (lower is better)"),
) -> None:
    """Render CLIP_DIR (format: clip) to renders/v<N>-youtube.mp4 + subtitles/v<N>.srt."""
    clip_dir = clip_dir.resolve()
    if not clip_dir.is_dir():
        raise typer.BadParameter(f"clip directory does not exist: {clip_dir}")
    root = episode_root_for(clip_dir, episode_root)
    config = load_config(config_path, root)  # fails loudly if the pipeline config is missing/malformed
    run_checked(["uv", "run", str(SCRIPTS_DIR / "validate_clip.py"), str(clip_dir), "--episode-root", str(root)],
                "validate_clip.py (a red manifest is never rendered)")
    clip = load_clip(clip_dir / "clip.yaml")
    episode = load_episode(root / "episode.yaml")

    if clip.clip.format != "clip":
        raise typer.BadParameter(
            f"{clip.clip.id} is format {clip.clip.format!r}; render_horizontal.py renders format: clip only "
            f"(shorts go through assemble_audio.py + Remotion)"
        )
    profile = resolve_profile(episode, PROFILE)
    if profile.format != "clip":
        raise typer.BadParameter(f"profile {PROFILE!r} in episode.yaml has format {profile.format!r}, expected 'clip'")
    w, h = profile_dims(profile)

    n = len(clip.render.versions) + 1
    renders = clip_dir / "renders"
    audio_wav = renders / f"v{n}-audio.wav"
    out_mp4 = renders / f"v{n}-{PROFILE}.mp4"
    srt = clip_dir / "subtitles" / f"v{n}.srt"
    existing = [p for p in (audio_wav, out_mp4, srt) if p.exists()]
    if existing:
        raise typer.BadParameter(
            f"v{n} outputs already exist: {[str(p) for p in existing]} — renders are versioned and never "
            f"overwritten; delete the unpublished attempt by hand or record it in render.versions"
        )
    renders.mkdir(parents=True, exist_ok=True)
    bad = [s.id for s in clip.timeline if s.audio != "as-recorded"]
    if bad:
        raise typer.BadParameter(f"segments {bad} use duck/mute audio; horizontal clips are as-recorded only")

    logger.info(f"clip={clip.clip.id} v{n} segments={len(clip.timeline)} inserts={len(clip.inserts)} "
                f"overlays={len(clip.overlays)} {w}x{h}@{profile.fps:g}")

    # 1. audio
    run_checked(
        ["uv", "run", str(SCRIPTS_DIR / "assemble_audio.py"), str(clip_dir), "--version", str(n),
         "--episode-root", str(root)],
        "assemble_audio.py",
    )
    if not audio_wav.is_file():
        raise RuntimeError(f"assemble_audio.py did not write {audio_wav}")

    # 3. B-roll layers
    layer_dir = renders / f".v{n}-layers"
    if layer_dir.exists():
        raise typer.BadParameter(f"{layer_dir} exists from an earlier attempt — delete it by hand (scratch, never reused)")
    layers = build_layers(clip, clip_dir, layer_dir, w, h, profile.fps, config)

    # 2+4. loudness + video + overlays + mux
    tp = profile.true_peak_dbtp - TRUE_PEAK_MARGIN_DB
    af = loudnorm_filter(audio_wav, profile.loudness_lufs, tp)
    n_seg = len(clip.timeline)
    inputs: list[str] = []
    for seg in clip.timeline:
        inputs += ["-ss", ff_time(seg.source_in), "-t", ff_time(seg.source_out - seg.source_in),
                   "-i", str(media_path(root, seg.source_file))]
    for path, _ov in layers:
        inputs += ["-i", str(path)]
    comp, top = composite_filters("cut", [(n_seg + k, ov) for k, (_p, ov) in enumerate(layers)], profile.fps)
    audio_idx = n_seg + len(layers)
    graph = ";".join([video_filtergraph(clip, w, h, profile.fps), *comp, f"[{top}]format=yuv420p[outv]",
                      f"[{audio_idx}:a]{af},aresample=48000[outa]"])
    run_ffmpeg(
        [
            *inputs, "-i", str(audio_wav),
            "-filter_complex", graph,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-pix_fmt", "yuv420p",
            "-r", f"{profile.fps:g}",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-t", ff_time(clip.output.duration_s),
            "-movflags", "+faststart",
            str(out_mp4),
        ],
        what=f"rendering {out_mp4.name}",
    )
    probe = ffprobe_media(out_mp4)
    if abs(probe.duration_s - clip.output.duration_s) > 0.1:
        raise RuntimeError(
            f"{out_mp4.name} is {probe.duration_s:.3f}s but clip.output.duration_s is {clip.output.duration_s:.3f}s"
        )

    # 5. subtitles
    align_cmd = ["uv", "run", str(SCRIPTS_DIR / "align_subtitles.py"), str(clip_dir), "--srt",
                 "--audio", str(audio_wav), "--version", str(n), "--profile", PROFILE,
                 "--episode-root", str(root)]
    with TemporaryDirectory(prefix="ps-hsrt-") as tmp:
        if engine:
            align_cmd += ["--engine", engine]
        else:
            transcript = load_transcript(root / episode.transcript.json_file)
            words_path = Path(tmp) / "words.json"
            words = remapped_words(clip, transcript.words, load_insert_words(clip, clip_dir))
            words_path.write_text(json.dumps({"words": words}))
            align_cmd += ["--words-json", str(words_path)]
        if config_path:
            align_cmd += ["--config", str(config_path)]
        run_checked(align_cmd, "align_subtitles.py --srt")
    if not srt.is_file():
        raise RuntimeError(f"align_subtitles.py --srt did not write {srt}")

    if layer_dir.exists():
        shutil.rmtree(layer_dir)  # scratch: the render is the artifact; layers are rebuilt per version

    # 6. manifest
    clip.render.versions.append(
        RenderVersion(
            version=n, preview=None, finals={PROFILE: str(out_mp4.relative_to(clip_dir))},
            rendered_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), qc=None,
        )
    )
    if clip.clip.status == FROZEN:
        clip.clip.status = "rendered"
    save_clip(clip_dir / "clip.yaml", clip)
    console.print(
        f"[bold green]OK[/] {clip.clip.id} v{n}: {out_mp4} ({probe.duration_s:.2f}s, {probe.width}x{probe.height}), "
        f"{srt}. Next: qc_render.py {clip_dir} --version {n} --profile {PROFILE}"
    )


if __name__ == "__main__":
    app()
