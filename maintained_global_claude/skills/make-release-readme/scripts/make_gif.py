#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "typer", "loguru"]
# ///
"""Combine a sequence of screenshot PNGs into an animated GIF."""

from pathlib import Path

import typer
from loguru import logger
from PIL import Image


def main(
    images: list[Path] = typer.Argument(..., help="PNG files to combine, in order"),
    output: Path = typer.Option("output.gif", "--output", "-o", help="Output GIF path"),
    duration: int = typer.Option(1500, "--duration", "-d", help="Milliseconds per frame"),
):
    """Combine screenshot PNGs into an animated GIF."""
    existing = [p for p in images if p.exists()]
    if not existing:
        logger.error("No valid image files provided")
        raise typer.Exit(1)

    logger.info(f"Combining {len(existing)} images into {output}")

    target_size = Image.open(existing[0]).size
    frames = [Image.open(p).convert("RGB").resize(target_size, Image.LANCZOS) for p in existing]

    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        optimize=True,
    )
    logger.info(f"Saved {output} ({output.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    typer.run(main)
