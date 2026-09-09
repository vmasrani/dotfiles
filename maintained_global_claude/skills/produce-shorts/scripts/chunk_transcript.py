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
"""Deterministically split an episode transcript into overlapping mining chunks.

Chunk boundaries always fall on segment boundaries — a chunk is extended to finish
its last segment rather than splitting mid-segment. Emits chunk-NN.md plus a
coverage.yaml block proving the chunks cover [0, duration] with the requested overlap.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

from pslib import (
    EPSILON,
    Coverage,
    CoverageChunk,
    Episode,
    TranscriptSegment,
    fmt_mmss,
    fmt_range,
    load_episode,
    load_transcript,
    save_coverage,
)

console = Console()
app = typer.Typer(add_completion=False)


def episode_duration(episode: Episode) -> float:
    probe = episode.media.probes.get(episode.media.episode_video)
    if probe is None:
        raise typer.BadParameter(
            f"episode.yaml has no probe for media.episode_video ({episode.media.episode_video}) — "
            "run the ingest probe step so media.probes carries its duration_s"
        )
    return probe.duration_s


def build_windows(
    segments: list[TranscriptSegment], chunk_s: float, overlap_s: float
) -> list[list[TranscriptSegment]]:
    """Segment-aligned windows: each starts on a segment, ends on a segment.

    A window is extended to finish its last segment, and the next window starts early
    enough that the realised overlap is >= `overlap_s` whenever segment boundaries allow
    it — over-covering is safe, under-covering can hide a boundary-straddling moment.
    """
    windows: list[list[TranscriptSegment]] = []
    i = 0
    n = len(segments)
    while i < n:
        nominal_end = segments[i].start + chunk_s
        j = i + 1
        while j < n and segments[j].start < nominal_end:
            j += 1
        windows.append(segments[i:j])
        if j >= n:
            break
        target = segments[j - 1].end - overlap_s
        candidates = [idx for idx in range(i + 1, j) if segments[idx].start <= target]
        i = max(candidates) if candidates else i + 1
    return windows


def to_coverage(
    windows: list[list[TranscriptSegment]], duration_s: float
) -> list[CoverageChunk]:
    starts = [w[0].start for w in windows]
    ends = [w[-1].end for w in windows]
    if starts[0] > EPSILON:
        logger.warning(f"transcript starts at {starts[0]:.3f}s; chunk 1 is extended back to 0.0")
    starts[0] = 0.0
    if duration_s - ends[-1] > 1.0:
        logger.warning(
            f"transcript ends {duration_s - ends[-1]:.3f}s before the media duration "
            f"({duration_s:.3f}s); the final chunk is extended to cover that silent tail"
        )
    ends[-1] = max(ends[-1], duration_s)
    chunks = [
        CoverageChunk(
            start_s=round(start, 3),
            end_s=round(end, 3),
            overlap_next_s=round(max(0.0, end - starts[idx + 1]), 3) if idx + 1 < len(starts) else 0.0,
        )
        for idx, (start, end) in enumerate(zip(starts, ends))
    ]
    assert_covers(chunks, duration_s)
    return chunks


def assert_covers(chunks: list[CoverageChunk], duration_s: float) -> None:
    if chunks[0].start_s > EPSILON:
        raise RuntimeError(f"coverage starts at {chunks[0].start_s} — must start at 0.0")
    if chunks[-1].end_s < duration_s - EPSILON:
        raise RuntimeError(
            f"coverage ends at {chunks[-1].end_s} but the episode is {duration_s}s — transcript "
            "segments do not reach the end of the media; re-run transcription"
        )
    holes = [
        f"{prev.end_s} -> {nxt.start_s}"
        for prev, nxt in zip(chunks, chunks[1:])
        if nxt.start_s > prev.end_s + EPSILON
    ]
    if holes:
        raise RuntimeError(f"coverage has gaps between chunks: {holes}")


def render_chunk(index: int, total: int, segs: list[TranscriptSegment], chunk: CoverageChunk) -> str:
    words = sum(len(s.text.split()) for s in segs)
    header = [
        f"# Chunk {index:02d} of {total:02d}",
        "",
        f"- source range: `{fmt_range(chunk.start_s, chunk.end_s)}` "
        f"({chunk.start_s:.3f}s – {chunk.end_s:.3f}s)",
        f"- segments: {len(segs)}",
        f"- words: {words}",
        f"- overlap with next chunk: {chunk.overlap_next_s:.3f}s",
        "",
        "---",
        "",
    ]
    body = [f"[{fmt_mmss(s.start)}] {s.speaker}: {s.text.strip()}" for s in segs]
    return "\n".join(header + body) + "\n"


def render_summary(chunks: list[CoverageChunk], windows: list[list[TranscriptSegment]]) -> None:
    table = RichTable(title="Chunk coverage", header_style="bold cyan")
    for col in ("Chunk", "Range", "start_s", "end_s", "overlap_next_s", "Segments", "Words"):
        table.add_column(col)
    for idx, (chunk, segs) in enumerate(zip(chunks, windows), start=1):
        table.add_row(
            f"chunk-{idx:02d}.md",
            fmt_range(chunk.start_s, chunk.end_s),
            f"{chunk.start_s:.3f}",
            f"{chunk.end_s:.3f}",
            f"{chunk.overlap_next_s:.3f}",
            str(len(segs)),
            str(sum(len(s.text.split()) for s in segs)),
        )
    console.print(table)


@app.command()
def main(
    episode_root: Path = typer.Argument(..., help="Episode root containing episode.yaml"),
    chunk_minutes: float = typer.Option(16.0, "--chunk-minutes", help="Nominal chunk length in minutes"),
    overlap_minutes: float = typer.Option(2.0, "--overlap-minutes", help="Overlap between chunks in minutes"),
    out_dir: Path = typer.Option(..., "--out-dir", help="Directory to write chunk-NN.md and coverage.yaml"),
) -> None:
    """Split EPISODE_ROOT's transcript into overlapping, segment-aligned chunks."""
    root = episode_root.resolve()
    if not root.is_dir():
        raise typer.BadParameter(f"episode root does not exist: {root}")
    if chunk_minutes <= 0 or overlap_minutes < 0:
        raise typer.BadParameter("--chunk-minutes must be > 0 and --overlap-minutes must be >= 0")
    if overlap_minutes >= chunk_minutes:
        raise typer.BadParameter(
            f"--overlap-minutes ({overlap_minutes}) must be smaller than --chunk-minutes "
            f"({chunk_minutes}); otherwise chunks cannot advance"
        )

    episode = load_episode(root / "episode.yaml")
    transcript = load_transcript(root / episode.transcript.json_file)
    if not transcript.segments:
        raise RuntimeError(f"{episode.transcript.json_file} has no segments — nothing to chunk")

    duration = episode_duration(episode)
    segments = sorted(transcript.segments, key=lambda s: (s.start, s.end))
    windows = build_windows(segments, chunk_minutes * 60.0, overlap_minutes * 60.0)
    chunks = to_coverage(windows, duration)

    requested = overlap_minutes * 60.0
    short = [
        f"chunk-{idx:02d} -> {c.overlap_next_s:.3f}s"
        for idx, c in enumerate(chunks[:-1], start=1)
        if c.overlap_next_s < requested - EPSILON
    ]
    if short:
        logger.warning(
            f"segment boundaries prevented the requested {requested:.1f}s overlap on: {short}"
        )

    out = out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for idx, (segs, chunk) in enumerate(zip(windows, chunks), start=1):
        (out / f"chunk-{idx:02d}.md").write_text(render_chunk(idx, len(chunks), segs, chunk))
    save_coverage(out / "coverage.yaml", Coverage(chunks=chunks))

    render_summary(chunks, windows)
    logger.info(f"wrote {len(chunks)} chunk files + coverage.yaml to {out}")
    console.print(
        f"[bold green]OK[/] {len(chunks)} chunks covering "
        f"{fmt_range(chunks[0].start_s, chunks[-1].end_s)} of a {fmt_mmss(duration)} episode"
    )


if __name__ == "__main__":
    app()
