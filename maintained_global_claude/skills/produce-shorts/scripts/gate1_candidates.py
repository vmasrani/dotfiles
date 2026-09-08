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
"""Write the gate-1 reading artifact from MINED CANDIDATES, before any clip.yaml exists.

`gate1_transcripts.py` renders clips that were already selected. This renders the candidates
the miners proposed, which is where gate 1 actually belongs: the run that produced this script
approved twelve clips from a selection memo, carried all twelve through storyboarding, B-roll
research, alignment and ~2 hours of rendering, and the user then rejected most of them on
sight. Reading the words is the cheapest possible moment to say no.

Every candidate's complete verbatim text is emitted. A candidate whose text is missing is a
hard error, not an omitted section — an empty entry reads like a short candidate rather than a
broken manifest.
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml
from loguru import logger
from rich.console import Console

app = typer.Typer(add_completion=False)
console = Console()

#: Shorts are vertical and under this; anything longer is a horizontal long-form clip.
SHORT_MAX_S = 180.0


def load(paths: list[Path]) -> list[dict]:
    out: list[dict] = []
    for path in paths:
        data = yaml.safe_load(path.read_text()) or {}
        for candidate in data.get("candidates", []):
            if not (candidate.get("verbatim") or "").strip():
                raise SystemExit(
                    f"{path}: candidate {candidate.get('id')} has no verbatim text — "
                    f"nothing to review. The miner must emit the words, not a description."
                )
            out.append(candidate)
    return out


def section(candidate: dict) -> str:
    """One candidate: what it is, why it might work, then every word of it."""
    duration = candidate.get("duration_s") or 0.0
    declared = candidate.get("format", "?")
    # The format field is the miner's claim; the duration is the fact. Disagreement is worth
    # seeing at review time rather than discovering at render time.
    implied = "short" if duration < SHORT_MAX_S else "clip"
    flag = "" if declared == implied else f"  **[format says {declared}, duration implies {implied}]**"

    lines = [
        f"## {candidate.get('id')} — {candidate.get('slug')}",
        "",
        f"`{declared}` · {duration:.0f}s · {candidate.get('structure', '?')} · "
        f"{', '.join(candidate.get('speakers') or [])}{flag}",
        "",
        f"**{candidate.get('title', '')}**",
        "",
        f"*Why it might hold a stranger:* {candidate.get('why_watchable', '—')}",
        "",
        f"*Quotable:* \"{candidate.get('quotable_line', '—')}\"",
        "",
        "```",
        (candidate.get("verbatim") or "").strip(),
        "```",
        "",
    ]
    return "\n".join(lines)


@app.command()
def main(
    episode_dir: Path = typer.Argument(..., help="Episode directory containing chunks/"),
    pattern: str = typer.Option("candidates2-*.yaml", help="Glob under chunks/"),
    out: Path = typer.Option(None, "--out", help="Defaults to <episode_dir>/gate1-candidates.md"),
) -> None:
    paths = sorted((episode_dir / "chunks").glob(pattern))
    if not paths:
        raise SystemExit(f"no {pattern} under {episode_dir}/chunks — run the miners first")

    candidates = load(paths)
    shorts = [c for c in candidates if (c.get("duration_s") or 0) < SHORT_MAX_S]
    clips = [c for c in candidates if (c.get("duration_s") or 0) >= SHORT_MAX_S]

    body = [
        "# Gate 1 — candidates",
        "",
        "Every candidate's complete verbatim text. Read the words, then decide what gets made.",
        "Mark each one GOOD or BAD with a reason; the reasons are what retrain the rubric.",
        "",
        f"**{len(shorts)} shorts** (vertical, under 3 min) · **{len(clips)} clips** "
        f"(horizontal, over 3 min)",
        "",
        "---",
        "",
        "# SHORTS — vertical, under 3 minutes",
        "",
    ]
    body += [section(c) for c in sorted(shorts, key=lambda c: c.get("id", ""))]
    body += ["---", "", "# CLIPS — horizontal, over 3 minutes", ""]
    body += [section(c) for c in sorted(clips, key=lambda c: c.get("id", ""))]

    destination = out or episode_dir / "gate1-candidates.md"
    destination.write_text("\n".join(body))

    logger.info(f"{len(candidates)} candidate(s) from {len(paths)} file(s) -> {destination}")
    console.print(f"[bold]{len(shorts)}[/bold] shorts, [bold]{len(clips)}[/bold] clips")


if __name__ == "__main__":
    app()
