#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer", "loguru", "rich"]
# ///
"""Extract still frames from a media file so a human (or a vision-capable agent) can
SEE the shot before choosing a crop.

Why this exists: `episode.yaml speakers[].preferred_crop` is documented as "set after
probe", but probing returns only width/height — it cannot tell you where the speaker
actually sits in frame. A camera that is zoomed out, off-centre, or framed for landscape
needs a crop chosen by looking. This script is the looking.

Two modes:

  sample   pull one or more frames at given timestamps
  grid     pull N frames spread evenly across the file, tiled into one contact sheet

Both write PNGs and print their paths. Nothing is guessed: a timestamp past the end of
the file, an unreadable input, or a missing ffmpeg stops with an actionable error.

`crop-preview` renders a candidate crop so you can check the framing BEFORE committing it
to episode.yaml — it takes the same `x=..:y=..:w=..:h=..` string the manifest stores.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

app = typer.Typer(add_completion=False, help=__doc__)
console = Console()


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise typer.BadParameter(
                f"{tool} not found on PATH — install it (brew install ffmpeg) and re-run"
            )


def probe_duration(media: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(media)],
        capture_output=True, text=True,
    )
    if out.returncode != 0 or not out.stdout.strip():
        raise typer.BadParameter(f"ffprobe could not read {media}: {out.stderr.strip()}")
    return float(out.stdout.strip())


def probe_size(media: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(media)],
        capture_output=True, text=True,
    )
    if out.returncode != 0 or not out.stdout.strip():
        raise typer.BadParameter(f"{media} has no readable video stream")
    w, h = out.stdout.strip().split(",")[:2]
    return int(w), int(h)


def extract(media: Path, at_s: float, dest: Path, scale: int | None) -> None:
    vf = f"scale={scale}:-1" if scale else "null"
    cmd = ["ffmpeg", "-nostdin", "-y", "-ss", f"{at_s:.3f}", "-i", str(media),
           "-frames:v", "1", "-vf", vf, "-q:v", "2", str(dest)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not dest.exists():
        raise RuntimeError(f"ffmpeg failed extracting {at_s:.3f}s from {media}:\n{r.stderr[-800:]}")


def validate_times(times: list[float], duration: float, media: Path) -> None:
    bad = [t for t in times if t < 0 or t >= duration]
    if bad:
        raise typer.BadParameter(
            f"timestamp(s) {bad} lie outside {media.name} (0–{duration:.2f}s)"
        )


@app.command()
def sample(
    media: Path = typer.Argument(..., help="Media file to sample"),
    at: list[float] = typer.Option(..., "--at", help="Timestamp in seconds; repeatable"),
    out_dir: Path = typer.Option(..., "--out-dir", help="Directory for the PNGs"),
    scale: int = typer.Option(None, "--scale", help="Scale output to this width, keeping aspect"),
) -> None:
    """Extract a frame at each --at timestamp."""
    require_ffmpeg()
    if not media.exists():
        raise typer.BadParameter(f"{media} does not exist")
    duration = probe_duration(media)
    validate_times(list(at), duration, media)
    w, h = probe_size(media)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"{media.name}: {w}x{h}, {duration:.1f}s")
    for t in at:
        dest = out_dir / f"{media.stem}-t{int(round(t))}.png"
        extract(media, t, dest, scale)
        console.print(f"[green]wrote[/] {dest}  (t={t:.2f}s)")


@app.command()
def grid(
    media: Path = typer.Argument(..., help="Media file to sample"),
    count: int = typer.Option(9, "--count", help="How many frames to spread across the file"),
    out: Path = typer.Option(..., "--out", help="Output contact-sheet PNG"),
    columns: int = typer.Option(3, "--columns", help="Tiles per row"),
    width: int = typer.Option(480, "--width", help="Width of each tile"),
) -> None:
    """Tile COUNT frames spread evenly across the file into one contact sheet."""
    require_ffmpeg()
    if not media.exists():
        raise typer.BadParameter(f"{media} does not exist")
    if count < 1:
        raise typer.BadParameter("--count must be >= 1")
    duration = probe_duration(media)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Sample strictly inside the file: avoid 0.0 and the final frame, both of which are
    # often black or malformed in recorder output.
    step = duration / (count + 1)
    times = [step * (i + 1) for i in range(count)]

    tmp = out.parent / f".{out.stem}-tiles"
    tmp.mkdir(parents=True, exist_ok=True)
    tiles = []
    for i, t in enumerate(times):
        dest = tmp / f"tile-{i:02d}.png"
        extract(media, t, dest, width)
        tiles.append(dest)

    # xstack's layout takes PIXEL OFFSETS, not grid indices. Every tile is scaled to
    # `width`, so tile height follows from the source aspect and is uniform.
    src_w, src_h = probe_size(media)
    tile_h = int(round(width * src_h / src_w))
    rows = (len(tiles) + columns - 1) // columns
    cmd = ["ffmpeg", "-nostdin", "-y"]
    for tile in tiles:
        cmd += ["-i", str(tile)]
    layout = "|".join(
        f"{(i % columns) * width}_{(i // columns) * tile_h}" for i in range(len(tiles))
    )
    cmd += ["-filter_complex", f"xstack=inputs={len(tiles)}:layout={layout}:fill=black", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"contact sheet failed:\n{r.stderr[-800:]}")

    for tile in tiles:
        tile.unlink()
    tmp.rmdir()
    console.print(f"[green]wrote[/] {out}  ({len(tiles)} frames, {rows}x{columns}, "
                  f"t={times[0]:.0f}s–{times[-1]:.0f}s)")


@app.command("crop-preview")
def crop_preview(
    media: Path = typer.Argument(..., help="Media file to sample"),
    crop: str = typer.Option(..., "--crop", help="ffmpeg crop, e.g. 'x=120:y=0:w=405:h=720'"),
    at: list[float] = typer.Option(..., "--at", help="Timestamp in seconds; repeatable"),
    out_dir: Path = typer.Option(..., "--out-dir", help="Directory for the PNGs"),
) -> None:
    """Render a candidate crop so you can check framing before writing it to episode.yaml."""
    require_ffmpeg()
    if not media.exists():
        raise typer.BadParameter(f"{media} does not exist")
    parts = dict(p.split("=", 1) for p in crop.split(":"))
    missing = {"x", "y", "w", "h"} - set(parts)
    if missing:
        raise typer.BadParameter(f"--crop is missing {sorted(missing)}; expected x=..:y=..:w=..:h=..")
    x, y, w, h = (int(parts[k]) for k in ("x", "y", "w", "h"))

    src_w, src_h = probe_size(media)
    if x < 0 or y < 0 or x + w > src_w or y + h > src_h:
        raise typer.BadParameter(
            f"crop {crop} falls outside the {src_w}x{src_h} frame "
            f"(needs x+w<={src_w}, y+h<={src_h})"
        )
    duration = probe_duration(media)
    validate_times(list(at), duration, media)
    out_dir.mkdir(parents=True, exist_ok=True)

    ratio = w / h
    console.print(f"crop {w}x{h} (aspect {ratio:.4f}; 9:16 = {9/16:.4f}) from {src_w}x{src_h}")
    if abs(ratio - 9 / 16) > 0.005:
        logger.warning(f"crop aspect {ratio:.4f} is not 9:16 — the renderer will letterbox or stretch")

    for t in at:
        dest = out_dir / f"{media.stem}-crop-t{int(round(t))}.png"
        cmd = ["ffmpeg", "-nostdin", "-y", "-ss", f"{t:.3f}", "-i", str(media),
               "-frames:v", "1", "-vf", f"crop={w}:{h}:{x}:{y}", "-q:v", "2", str(dest)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not dest.exists():
            raise RuntimeError(f"crop preview failed at {t}s:\n{r.stderr[-800:]}")
        console.print(f"[green]wrote[/] {dest}")


if __name__ == "__main__":
    app()
