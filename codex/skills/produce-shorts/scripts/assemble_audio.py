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
"""Stage 8 step 1 — assemble the clip's edited audio from the timeline mapping.

Extracts each timeline segment's source audio range sample-accurately, applies the
segment's `audio` action (as-recorded | duck | mute), and concatenates in output
order into `renders/v<N>-audio.wav` (48 kHz stereo pcm_s16le).

Internal cuts — adjacent segments whose source audio is NOT continuous (different
source file, non-contiguous source times, or a change of audio action) — get a
micro-crossfade of `render.internal_cut_crossfade_ms` across the splice: an equal
fade-out on the outgoing side and fade-in on the incoming side. That is a
constant-length splice, so the assembled duration stays sample-exact against
`clip.output.duration_s`; a true overlapping `acrossfade` would shorten the
timeline by the crossfade length at every internal cut and desync the video, which
is cut to exact per-segment lengths by extract_segments.py.

Truly contiguous source audio is concatenated with no processing at all.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

from pslib import (
    CLIP_STATUS_ORDER,
    EPSILON,
    Clip,
    Episode,
    TimelineSegment,
    ffprobe_media,
    fmt_range,
    load_clip,
    load_episode,
)
from psmedia import (
    episode_root_for,
    ff_time,
    load_config,
    media_path,
    probed_duration,
    run_ffmpeg,
)

console = Console()
app = typer.Typer(add_completion=False)

RENDER_GATE = "approved_render"
DUCK_DB = -12.0


@dataclass
class Piece:
    """One extracted segment of the assembled audio."""

    segment: TimelineSegment
    fade_in: bool
    fade_out: bool
    cut_before: str | None  # why this segment starts an internal cut, None if continuous

    @property
    def action_filter(self) -> str | None:
        if self.segment.audio == "as-recorded":
            return None
        if self.segment.audio == "duck":
            return f"volume={DUCK_DB}dB"
        return "volume=0"


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def cut_reason(prev: TimelineSegment, seg: TimelineSegment) -> str | None:
    """Why the splice from `prev` to `seg` is an internal cut, or None if continuous."""
    if prev.source_file != seg.source_file:
        return f"source file {prev.source_file} → {seg.source_file}"
    gap = seg.source_in - prev.source_out
    if abs(gap) > EPSILON:
        return f"source jump {prev.source_out:.3f} → {seg.source_in:.3f} ({gap:+.3f}s)"
    if prev.audio != seg.audio:
        return f"audio action {prev.audio} → {seg.audio}"
    return None


def plan_pieces(clip: Clip) -> list[Piece]:
    if not clip.timeline:
        raise ValueError("clip.yaml has an empty timeline — nothing to assemble")
    reasons = [None, *(cut_reason(prev, seg) for prev, seg in zip(clip.timeline, clip.timeline[1:]))]
    return [
        Piece(
            segment=seg,
            fade_in=reasons[i] is not None,
            fade_out=i + 1 < len(reasons) and reasons[i + 1] is not None,
            cut_before=reasons[i],
        )
        for i, seg in enumerate(clip.timeline)
    ]


def check_gate(clip: Clip) -> None:
    status = clip.clip.status
    if CLIP_STATUS_ORDER.index(status) < CLIP_STATUS_ORDER.index(RENDER_GATE):
        raise typer.BadParameter(
            f"clip {clip.clip.id} has status {status!r}; audio assembly requires the render gate "
            f"({RENDER_GATE}) to have been passed. Run the critique/approval steps and set "
            f"clip.status: {RENDER_GATE} before rendering."
        )


def check_sources(clip: Clip, episode: Episode, episode_root: Path) -> None:
    """Every source range must exist on disk and lie inside the probed duration."""
    problems: list[str] = []
    for seg in clip.timeline:
        duration = probed_duration(episode, seg.source_file)
        if seg.source_in < -EPSILON or seg.source_out > duration + EPSILON:
            problems.append(
                f"{seg.id}: source range {fmt_range(seg.source_in, seg.source_out)} is outside "
                f"{seg.source_file} (probed duration {duration:.3f}s)"
            )
        media_path(episode_root, seg.source_file)
    if problems:
        raise ValueError("timeline source ranges are unusable:\n  " + "\n  ".join(problems))


# ---------------------------------------------------------------------------
# Extraction and concatenation
# ---------------------------------------------------------------------------


def extract_piece(piece: Piece, episode_root: Path, out_path: Path, crossfade_s: float, work: Path) -> float:
    """Cut the segment (pass 1) and, at internal cuts, de-click it (pass 2). Returns its duration.

    The two passes are not an accident. Output-side `-ss/-to` is the sample-accurate
    cut, but it leaves the SOURCE timestamps on the frames entering the filter graph —
    a segment cut from 16s reaches `afade` at t=16s, so a fade-out at t=5.992s has
    "already finished" and the filter emits six seconds of silence (measured; the same
    happens with afade's sample-count mode, which counts from the PTS too). Fades
    therefore run in a second pass over the extracted PCM, whose timeline starts at 0.
    """
    seg = piece.segment
    faded = piece.fade_in or piece.fade_out
    if faded and crossfade_s * 2 > seg.source_duration:
        raise ValueError(
            f"{seg.id}: segment is {seg.source_duration:.3f}s but the internal-cut crossfade is "
            f"{crossfade_s * 1000:.1f}ms on each side — lower render.internal_cut_crossfade_ms "
            f"or lengthen the segment"
        )

    cut_filters = ["aresample=async=0"]
    action = piece.action_filter
    if action:
        cut_filters.append(action)
    cut_filters.append("aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo")

    cut_path = work / f"{seg.id}-cut.wav" if faded else out_path
    run_ffmpeg(
        [
            "-i", str(media_path(episode_root, seg.source_file)),
            "-ss", ff_time(seg.source_in),
            "-to", ff_time(seg.source_out),
            "-vn", "-sn", "-dn",
            "-af", ",".join(cut_filters),
            "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le",
            str(cut_path),
        ],
        what=f"extracting {seg.id} audio from {seg.source_file}",
    )
    cut_duration = ffprobe_media(cut_path).duration_s
    if not faded:
        return cut_duration

    fades = []
    if piece.fade_in:
        fades.append(f"afade=t=in:st=0:d={crossfade_s:.6f}")
    if piece.fade_out:
        fades.append(f"afade=t=out:st={cut_duration - crossfade_s:.6f}:d={crossfade_s:.6f}")
    run_ffmpeg(
        ["-i", str(cut_path), "-af", ",".join(fades), "-c:a", "pcm_s16le", str(out_path)],
        what=f"de-clicking {seg.id} across its internal cut",
    )
    faded_duration = ffprobe_media(out_path).duration_s
    if abs(faded_duration - cut_duration) > EPSILON:
        raise RuntimeError(
            f"{seg.id}: the de-click pass changed the piece from {cut_duration:.3f}s to "
            f"{faded_duration:.3f}s — a splice fade must never change length"
        )
    return faded_duration


def concat_pieces(paths: list[Path], out_path: Path, work: Path) -> None:
    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in paths))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        ["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out_path)],
        what=f"concatenating {len(paths)} audio pieces into {out_path.name}",
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def render_plan(pieces: list[Piece], measured: dict[str, float]) -> None:
    table = RichTable(title="Assembled audio", header_style="bold cyan")
    table.add_column("Seg", no_wrap=True)
    table.add_column("Source", no_wrap=True)
    table.add_column("Output", no_wrap=True)
    table.add_column("Audio")
    table.add_column("Splice")
    table.add_column("Measured", justify="right")
    for piece in pieces:
        seg = piece.segment
        table.add_row(
            seg.id,
            f"{Path(seg.source_file).name} {fmt_range(seg.source_in, seg.source_out)}",
            fmt_range(seg.output_in, seg.output_out),
            seg.audio,
            f"[yellow]cut[/] ({piece.cut_before})" if piece.cut_before else "[green]continuous[/]",
            f"{measured[seg.id]:.3f}s",
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml"),
    version: int = typer.Option(None, "--version", "-v", help="Render version (default: len(render.versions)+1)"),
    episode_root: Path = typer.Option(None, "--episode-root", help="Episode root holding episode.yaml (default: CLIP_DIR/../..)"),
    config_path: Path = typer.Option(None, "--config", help="Pipeline config (default: config/defaults.yaml)"),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing v<N> audio file (renders are versioned; only for redoing an unpublished attempt)"),
) -> None:
    """Assemble CLIP_DIR's edited audio into renders/v<N>-audio.wav."""
    clip_dir = clip_dir.resolve()
    if not clip_dir.is_dir():
        raise typer.BadParameter(f"clip directory does not exist: {clip_dir}")
    root = episode_root_for(clip_dir, episode_root)
    config = load_config(config_path)

    clip = load_clip(clip_dir / "clip.yaml")
    episode = load_episode(root / "episode.yaml")
    check_gate(clip)
    check_sources(clip, episode, root)

    n = version if version is not None else len(clip.render.versions) + 1
    out_path = clip_dir / "renders" / f"v{n}-audio.wav"
    if out_path.exists() and not force:
        raise typer.BadParameter(
            f"{out_path} already exists — renders are versioned and never overwritten. "
            f"Use --version {len(clip.render.versions) + 1} for a new version, or --force to redo this one."
        )

    crossfade_s = config.render.internal_cut_crossfade_ms / 1000.0
    pieces = plan_pieces(clip)
    cuts = [p for p in pieces if p.cut_before]
    logger.info(
        f"clip={clip.clip.id} version={n} segments={len(pieces)} internal_cuts={len(cuts)} "
        f"crossfade={config.render.internal_cut_crossfade_ms:.1f}ms"
    )

    with TemporaryDirectory(prefix="ps-audio-") as tmp:
        work = Path(tmp)
        paths = []
        measured: dict[str, float] = {}
        for piece in pieces:
            piece_path = work / f"{piece.segment.id}.wav"
            duration = extract_piece(piece, root, piece_path, crossfade_s, work)
            measured[piece.segment.id] = duration
            if abs(duration - piece.segment.source_duration) > EPSILON:
                raise RuntimeError(
                    f"{piece.segment.id}: extracted {duration:.3f}s but the timeline says "
                    f"{piece.segment.source_duration:.3f}s — the source range is not decodable as written"
                )
            paths.append(piece_path)
        concat_pieces(paths, out_path, work)

    result = ffprobe_media(out_path)
    expected = clip.output.duration_s
    allowance = EPSILON + crossfade_s
    delta = result.duration_s - expected
    render_plan(pieces, measured)
    console.print(
        f"[bold]{out_path.relative_to(clip_dir)}[/]: {result.duration_s:.3f}s vs manifest "
        f"{expected:.3f}s (delta {delta:+.4f}s, tolerance ±{allowance:.4f}s = ε {EPSILON} + one "
        f"{config.render.internal_cut_crossfade_ms:.0f}ms crossfade), "
        f"{result.sample_rate} Hz / {result.audio_channels} ch / {result.audio_codec}"
    )
    if abs(delta) > allowance:
        console.print(
            f"[bold red]FAIL[/] assembled audio duration disagrees with clip.output.duration_s by "
            f"{delta:+.4f}s — the timeline and the source media do not agree; fix the manifest, do not re-time the audio"
        )
        raise typer.Exit(1)
    console.print(
        f"[bold green]OK[/] {clip.clip.id} v{n}: {len(pieces)} segments, {len(cuts)} internal cut(s) "
        f"crossfaded at {config.render.internal_cut_crossfade_ms:.0f}ms → {out_path}"
    )


if __name__ == "__main__":
    app()
