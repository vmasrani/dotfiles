#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["static-ffmpeg>=2.7", "typer>=0.12", "loguru>=0.7", "httpx>=0.27", "platformdirs>=4"]
# ///
"""Append the Increments end tag to a finished video.

Holds the last frame for the tag's length, composites the tag (ProRes 4444 with alpha, 1080x1920)
over the hold, and mixes the tag's sound in after the speech. Vertical input: the tag fills the frame.
Horizontal input: the tag is scaled to the frame height and centred over the held last frame.
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


def audio_delay_ms(video_s: float) -> int:
    """The tag's sound starts exactly when the speech video ends."""
    return int(video_s * 1000)


def build_filter(video_s: float, tag_s: float, out_w: int, out_h: int) -> str:
    """filter_complex string. Vertical (out_h > out_w): tag fills the frame; else scaled to out_h and centred."""
    tag_scale = "" if out_h > out_w else f"scale=-2:{out_h},"
    pos = "" if out_h > out_w else ":x=(W-w)/2:y=0"
    ms = audio_delay_ms(video_s)
    return (
        f"[0:v]tpad=stop_mode=clone:stop_duration={tag_s:.3f}[base];"
        f"[1:v]{tag_scale}setpts=PTS-STARTPTS+{video_s:.3f}/TB[tag];"
        f"[base][tag]overlay=eof_action=pass:format=auto{pos},format=yuv420p[v];"
        f"[0:a]apad=pad_dur={tag_s:.3f}[a0];"
        f"[1:a]aresample=48000,adelay={ms}|{ms}[ta];"
        "[a0][ta]amix=inputs=2:normalize=0:duration=first[a]"
    )


def add_end_tag(src: Path, dst: Path, tag: Path | None = None) -> float:
    """Write dst = src + end tag. Returns the new duration."""
    if not src.is_file():
        raise FileNotFoundError(f"input video not found: {src}")
    tag = tag or end_tag()
    w, h = (int(x) for x in probe(src, "stream=width,height")[:2])
    d, t = duration(src), duration(tag)
    cmd = [ffmpeg_tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", str(src), "-i", str(tag),
           "-filter_complex", build_filter(d, t, w, h), "-map", "[v]", "-map", "[a]",
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
