#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
# ]
# ///
"""Write the gate-1 reading artifact: every candidate clip's WHOLE verbatim transcript.

Gate 1 asks a human to approve clips for production. The run that produced this script
approved twelve clips on a title, a duration and a one-line memo, and two of the weakest
were rendered before anyone read their words. The gate was real; the artifact behind it
was too thin to decide on. This writes the thing that is actually decidable.

The transcript is joined from each timeline segment's `dialogue`, which IS the verbatim
text the clip will speak — the same field `validate_clip.py` holds the subtitles to. It is
not a summary and must never become one.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import fill

import typer
import yaml
from loguru import logger
from rich.console import Console

WRAP_COLUMNS = 100
app = typer.Typer(add_completion=False)
console = Console()


def clip_transcript(clip_yaml: Path) -> tuple[str, float | None, str]:
    """(slug, duration_s, whole verbatim text) for one clip manifest."""
    data = yaml.safe_load(clip_yaml.read_text())
    spoken = [
        (segment.get("dialogue") or "").strip()
        for segment in data.get("timeline", [])
    ]
    text = " ".join(part for part in spoken if part)
    if not text:
        # A candidate with no dialogue cannot be judged, and silently emitting an empty
        # section would look like a short clip rather than a broken manifest.
        raise SystemExit(
            f"{clip_yaml} has no dialogue in any timeline segment — nothing to review. "
            f"Fix the manifest before running gate 1."
        )
    return clip_yaml.parent.name, data.get("output", {}).get("duration_s"), text


def render_markdown(entries: list[tuple[str, float | None, str]]) -> str:
    """One section per clip: slug, duration, word count, then the whole text."""
    out = [
        "# Gate 1 — candidate transcripts",
        "",
        "Every candidate's complete verbatim text. Read the words, then decide what gets made.",
        "A clip that does not read well here will not read better with captions on it.",
        "",
    ]
    for slug, duration, text in entries:
        length = f"{duration}s, " if duration is not None else ""
        out += [f"## {slug}  ({length}{len(text.split())} words)", "", fill(text, WRAP_COLUMNS), ""]
    return "\n".join(out)


@app.command()
def main(
    episode_dir: Path = typer.Argument(..., help="Episode directory containing clips/"),
    out: Path = typer.Option(None, "--out", help="Defaults to <episode_dir>/gate1-transcripts.md"),
) -> None:
    clips = sorted((episode_dir / "clips").glob("*/clip.yaml"))
    if not clips:
        raise SystemExit(f"no clips/*/clip.yaml under {episode_dir} — run stage 3 first")

    entries = [clip_transcript(path) for path in clips]
    destination = out or episode_dir / "gate1-transcripts.md"
    destination.write_text(render_markdown(entries))

    logger.info(f"{len(entries)} candidate(s) -> {destination}")
    console.print(f"[bold]{len(entries)}[/bold] transcripts, "
                  f"{sum(len(text.split()) for _, _, text in entries)} words total")


if __name__ == "__main__":
    app()
