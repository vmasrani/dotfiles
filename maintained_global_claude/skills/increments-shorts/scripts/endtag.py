#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["static-ffmpeg>=2.7", "typer>=0.12", "loguru>=0.7", "httpx>=0.27", "platformdirs>=4"]
# ///
"""Append the Increments end tag to a finished video.

The tag is its own segment after the untouched video: a full black screen (input size and fps) with the tag
(ProRes 4444 with alpha, 1080x1920) composited on top, plus the tag's sound, concatenated after the video.
Vertical input: the tag fills the frame. Horizontal input: the tag is scaled to the frame height and centred.
The tag is downloaded once into the user cache (assets.end_tag) and size-verified.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger

from assets import end_tag
from mediatools import ffmpeg_tool

app = typer.Typer(add_completion=False)


def probe(path: Path, entries: str) -> list[str]:
    proc = subprocess.run([ffmpeg_tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", entries,
                           "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"ffprobe failed on {path}: {proc.stderr.strip()}")
    return proc.stdout.strip().split(",")


def duration(path: Path) -> float:
    proc = subprocess.run([ffmpeg_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {proc.stderr.strip()}")
    return float(proc.stdout.strip())


def probe_fps(path: Path) -> str:
    num, den = probe(path, "stream=r_frame_rate")[0].split("/")
    return f"{int(num)}/{int(den)}"


def build_filter(tag_s: float, out_w: int, out_h: int, fps: str = "30") -> str:
    """filter_complex string; inputs 0=short, 1=tag, 2=black lavfi. The tag is its own segment after the untouched short.
    Vertical (out_h > out_w): tag fills the frame; else scaled to out_h and centred on the black screen."""
    tag_scale = "" if out_h > out_w else f"scale=-2:{out_h},"
    return (
        f"[0:v]fps={fps},setsar=1,format=yuv420p[main];"
        f"[1:v]{tag_scale}format=yuva444p[tagv];"
        f"[2:v][tagv]overlay=format=auto:eof_action=pass:x=(W-w)/2:y=(H-h)/2,setsar=1,format=yuv420p[end];"
        "[0:a]aresample=48000,aformat=channel_layouts=stereo[ma];"
        f"[1:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={tag_s:.3f}[ea];"
        "[main][ma][end][ea]concat=n=2:v=1:a=1[v][a]"
    )


def add_end_tag(src: Path, dst: Path, tag: Path | None = None) -> float:
    """Write dst = src + end tag. Returns the new duration."""
    if not src.is_file():
        raise FileNotFoundError(f"input video not found: {src}")
    tag = tag or end_tag()
    w, h = (int(x) for x in probe(src, "stream=width,height")[:2])
    d, t = duration(src), duration(tag)
    fps = probe_fps(src)
    cmd = [ffmpeg_tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", str(src), "-i", str(tag),
           "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}:d={t:.3f}",
           "-filter_complex", build_filter(t, w, h, fps), "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-profile:v", "high", "-r", "30",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(dst)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg end-tag mux failed (exit {proc.returncode}): {proc.stderr.strip()[-800:]}")
    new = duration(dst)
    logger.info(f"{dst.name}: {new:.2f}s (was {d:.2f}s + tag {t:.2f}s)")
    return new


@app.command()
def main(src: Path = typer.Argument(...), dst: Path = typer.Argument(...)) -> None:
    """Add the end tag to SRC, write DST."""
    add_end_tag(src.expanduser(), dst.expanduser())
    print(dst)


if __name__ == "__main__":
    app()
