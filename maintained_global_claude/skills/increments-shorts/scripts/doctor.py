#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["static-ffmpeg>=2.7", "httpx>=0.27", "platformdirs>=4", "rich>=13.7", "typer>=0.12"]
# ///
"""Environment check + one-time setup. Run first: `uv run scripts/doctor.py` (add --fetch to download assets, --npm to install Remotion deps).

Checks: ffmpeg/ffprobe (bundled via static-ffmpeg, needs libx264 + libass), Node >= 18, Remotion deps,
Anton font + end tag downloads, transcription options. Exits nonzero if a REQUIRED item fails.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(add_completion=False)
console = Console()


def check(name: str, fn) -> tuple[str, str, str]:
    try:
        return name, "ok", str(fn())
    except Exception as e:  # noqa: BLE001 — doctor reports every failure, then exits nonzero once
        return name, "FAIL", str(e).splitlines()[0][:200]


@app.command()
def main(fetch: bool = typer.Option(False, "--fetch", help="Download Anton font + end tag now"),
         npm: bool = typer.Option(False, "--npm", help="Run npm ci for Remotion now")) -> None:
    from assets import anton_font, end_tag  # noqa: PLC0415
    from mediatools import ffmpeg_tool  # noqa: PLC0415
    from remotion_env import check_node, ensure_node_modules  # noqa: PLC0415

    rows = [check("ffmpeg (libx264, libass)", lambda: ffmpeg_tool("ffmpeg")), check("ffprobe", lambda: ffmpeg_tool("ffprobe")),
            check("node >= 18", check_node)]
    if npm:
        rows.append(check("remotion deps (npm ci)", ensure_node_modules))
    if fetch:
        rows += [check("Anton font", anton_font), check("end tag (13.7 MB)", end_tag)]
    optional = [("ASSEMBLYAI_API_KEY", "set" if os.environ.get("ASSEMBLYAI_API_KEY") else "not set — fine if you use faster-whisper")]
    t = Table(title="increments-shorts doctor")
    for c in ("check", "status", "detail"):
        t.add_column(c)
    for r in rows:
        t.add_row(*r)
    for n, d in optional:
        t.add_row(n, "info", d)
    console.print(t)
    if any(r[1] == "FAIL" for r in rows):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
