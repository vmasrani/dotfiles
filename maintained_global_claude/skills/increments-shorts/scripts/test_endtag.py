#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8", "static-ffmpeg>=2.7", "typer>=0.12", "loguru>=0.7", "httpx>=0.27", "platformdirs>=4", "pillow>=10"]
# ///
"""End-tag timing math — run: `uv run --script scripts/test_endtag.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest

import subprocess

from endtag import add_end_tag, build_filter, duration, ffmpeg_tool


def test_vertical_filter_is_separate_black_segment_with_concat():
    f = build_filter(2.333, 1080, 1920, "30")
    assert "tpad" not in f and "scale" not in f
    assert "[2:v][tagv]overlay=format=auto:eof_action=pass" in f
    assert "apad=whole_dur=2.333" in f and "concat=n=2:v=1:a=1[v][a]" in f
    assert "fps=30,setsar=1,format=yuv420p[main]" in f


def test_horizontal_filter_scales_tag_to_height_and_centres():
    f = build_filter(2.333, 1920, 1080, "30")
    assert "scale=-2:1080" in f and "x=(W-w)/2" in f


def _run(*args):
    subprocess.run([ffmpeg_tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *args], check=True)


def test_end_to_end_black_outside_tag_and_duration(tmp_path):
    src, tag, out = tmp_path / "s.mp4", tmp_path / "tag.mov", tmp_path / "o.mp4"
    _run("-f", "lavfi", "-i", "color=c=white:s=1080x1920:r=30:d=2", "-f", "lavfi", "-i", "sine=d=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src))
    # tag: 1.0 s, red 200x200 square on a transparent 1080x1920 canvas, with audio
    _run("-f", "lavfi", "-i", "color=c=red@1:s=200x200:r=30:d=1,format=yuva444p,pad=1080:1920:440:860:color=black@0",
         "-f", "lavfi", "-i", "sine=d=1", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
         "-c:a", "pcm_s16le", str(tag))
    new = add_end_tag(src, out, tag)
    assert abs(new - (duration(src) + duration(tag))) < 0.15
    png = tmp_path / "last.png"
    _run("-sseof", "-0.2", "-i", str(out), "-frames:v", "1", "-vf", "scale=1080:1920", str(png))
    from PIL import Image
    im = Image.open(png).convert("RGB")
    assert sum(im.getpixel((50, 50))) < 40            # black outside the tag
    r, g, b = im.getpixel((540, 960))
    assert r > 150 and g < 80 and b < 80              # tag's opaque pixels on top


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
